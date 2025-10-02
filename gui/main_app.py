"""
Main application class for the ontahood-downloader GUI.
"""

import json
import os
import signal
import sys
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
from typing import Optional

import drive_fetch_resilient as dfr

from .config import DEFAULT_URLS
from .i18n import T
from .log_handler import TkLogHandler
from .preferences import PreferencesManager
from .utils import locate_credentials, validate_image_size
from .workers import run_worker, run_converter, start_worker_thread


class App(tk.Tk):
    """Main application window."""
    
    SIZE_OPTIONS = [
        "400 (thumbnail)",
        "700 (thumbnail)", 
        "1024 (thumbnail)",
        "1600 (thumbnail)",
        "2400 (thumbnail)",
        "3200 (thumbnail)",
        "4800 (thumbnail)",
        "6000 (thumbnail)",
        "ORIGINAL (full size)",
    ]
    
    def __init__(self):
        super().__init__()
        
        # Initialize state
        self._loading_prefs = True
        self._geom_save_job = None
        self.lang = "en"
        self.expected_bytes_total = 0
        self.bytes_written = 0
        
        # Initialize preferences manager
        self.prefs_manager = PreferencesManager()
        
        # Set up window
        self.title(T(self.lang, "app_title"))
        self.geometry("980x950")
        self.minsize(820, 760)
        
        # Create UI components
        self._create_ui()
        
        # Load preferences and apply language
        self._load_preferences()
        self.apply_i18n()
        
        # Set up event handlers
        self._setup_event_handlers()
        
        # Check account status in background
        threading.Thread(target=self._check_account_async, daemon=True).start()
        
        # Done loading
        self._loading_prefs = False
    
    def _create_ui(self):
        """Create the main UI components."""
        # Top bar with language and account
        self._create_top_bar()
        
        # Main intro text
        self.intro_label = ttk.Label(self, wraplength=940, justify="left")
        self.intro_label.pack(anchor="w", padx=12, pady=(12, 6))
        
        # Downloader section
        self._create_downloader_section()
        
        # Separator
        sep = ttk.Separator(self, orient="horizontal")
        sep.pack(fill="x", padx=12, pady=(6, 8))
        
        # Converter section
        self._create_converter_section()
        
        # Logs and progress section
        self._create_logs_section()
        self._create_progress_section()
    
    def _create_top_bar(self):
        """Create the top bar with language selector and account info."""
        topbar = ttk.Frame(self)
        topbar.pack(fill="x", padx=12, pady=(10, 0))
        
        # Language selector
        ttk.Label(topbar, text=T(self.lang, "language")).pack(side="left")
        self.lang_var = tk.StringVar(value=T(self.lang, "lang_en"))
        self.lang_box = ttk.Combobox(
            topbar, textvariable=self.lang_var,
            values=[T("en", "lang_en"), T("id", "lang_id")], 
            width=22, state="readonly"
        )
        self.lang_box.pack(side="left", padx=(8, 0))
        self.lang_box.bind("<<ComboboxSelected>>", self._on_lang_change)
        
        # Account info
        self.acct_var = tk.StringVar(value="Account: (not signed in)")
        self.acct_label = ttk.Label(topbar, textvariable=self.acct_var)
        self.acct_label.pack(side="right")
        
        self.auth_btn = ttk.Button(topbar, text="Sign in", command=self.sign_in)
        self.auth_btn.pack(side="right", padx=(0, 8))
    
    def _create_downloader_section(self):
        """Create the main downloader section."""
        # URLs input
        self.urls_label = ttk.Label(self)
        self.urls_label.pack(anchor="w", padx=12)
        
        self.urlbox = scrolledtext.ScrolledText(self, height=6)
        self.urlbox.insert("1.0", "\n".join(DEFAULT_URLS) + "\n")
        self.urlbox.pack(fill="x", padx=12)
        
        # Output directory selection
        out_row = ttk.Frame(self)
        out_row.pack(fill="x", padx=12)
        
        self.out_label = ttk.Label(out_row)
        self.out_label.pack(side="left")
        
        self.outvar = tk.StringVar()
        self.out_entry = ttk.Entry(out_row, textvariable=self.outvar)
        self.out_entry.pack(side="left", fill="x", expand=True, padx=8)
        
        self.choose_btn = ttk.Button(out_row, command=self.pick_out)
        self.choose_btn.pack(side="left")
        
        # Image mode selection
        mode_row = ttk.Frame(self)
        mode_row.pack(fill="x", padx=12)
        
        self.mode_label = ttk.Label(mode_row)
        self.mode_label.pack(side="left")
        
        self.sizevar = tk.StringVar(value=self.SIZE_OPTIONS[1])
        ttk.Combobox(
            mode_row, textvariable=self.sizevar, 
            values=self.SIZE_OPTIONS, width=28, state="readonly"
        ).pack(side="left", padx=8)
        
        self.mode_hint = ttk.Label(mode_row)
        self.mode_hint.pack(side="left", padx=12)
        
        # Video download option
        video_row = ttk.Frame(self)
        video_row.pack(fill="x", padx=12, pady=(0, 10))
        
        self.videos_var = tk.BooleanVar(value=True)
        self.videos_check = ttk.Checkbutton(video_row, variable=self.videos_var)
        self.videos_check.pack(side="left")
        
        # Control buttons
        btn_row = ttk.Frame(self)
        btn_row.pack(fill="x", padx=12, pady=(2, 10))
        
        self.start_btn = ttk.Button(btn_row, command=self.start)
        self.start_btn.pack(side="right")
        
        self.cancel_btn = ttk.Button(
            btn_row, text="Cancel", command=self.cancel, state="disabled"
        )
        self.cancel_btn.pack(side="left")
    
    def _create_converter_section(self):
        """Create the thumbnail converter section."""
        # Section title and subtitle
        conv_box = ttk.Frame(self)
        conv_box.pack(fill="x", padx=12, pady=(4, 6))
        
        self.conv_title = ttk.Label(conv_box, font=("TkDefaultFont", 11, "bold"))
        self.conv_title.pack(anchor="w")
        
        self.conv_subtitle = ttk.Label(conv_box, wraplength=940, justify="left")
        self.conv_subtitle.pack(anchor="w", pady=(4, 8))
        
        # Directory selection
        conv_row = ttk.Frame(self)
        conv_row.pack(fill="x", padx=12, pady=(0, 4))
        
        self.conv_pick_label = ttk.Label(conv_row)
        self.conv_pick_label.pack(side="left")
        
        self.conv_dir_var = tk.StringVar()
        self.conv_dir_entry = ttk.Entry(conv_row, textvariable=self.conv_dir_var)
        self.conv_dir_entry.pack(side="left", fill="x", expand=True, padx=8)
        
        self.conv_choose_btn = ttk.Button(conv_row, command=self.pick_conv_dir)
        self.conv_choose_btn.pack(side="left")
        
        # Convert button
        conv_btn_row = ttk.Frame(self)
        conv_btn_row.pack(fill="x", padx=12, pady=(4, 8))
        
        self.conv_start_btn = ttk.Button(conv_btn_row, command=self.start_converter)
        self.conv_start_btn.pack(side="right")
    
    def _create_logs_section(self):
        """Create the logs section."""
        self.log_title = ttk.Label(self)
        self.log_title.pack(anchor="w", padx=12)
        
        self.logs = scrolledtext.ScrolledText(self, height=16, state="disabled")
        self.logs.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        
        self.log_handler = TkLogHandler(self.logs)
        self.log_handler.put("2025-10-02 00:00:00 | INFO    | [GUI] Application started - logging system active")
    
    def _create_progress_section(self):
        """Create the progress bars section."""
        prow = ttk.Frame(self)
        prow.pack(fill="x", padx=12, pady=(0, 12))
        
        # Images progress
        img_frame = ttk.Frame(prow)
        img_frame.pack(fill="x", pady=(0, 6))
        
        self.images_label = ttk.Label(img_frame)
        self.images_label.pack(side="left")
        
        self.progress_images = ttk.Progressbar(img_frame, length=520, mode="determinate")
        self.progress_images.pack(side="left", padx=(8, 8))
        
        self.progress_images_value = ttk.Label(img_frame, text="0/0")
        self.progress_images_value.pack(side="left")
        
        # Videos progress
        vid_frame = ttk.Frame(prow)
        vid_frame.pack(fill="x", pady=(0, 6))
        
        self.videos_label = ttk.Label(vid_frame)
        self.videos_label.pack(side="left")
        
        self.progress_videos = ttk.Progressbar(vid_frame, length=520, mode="determinate")
        self.progress_videos.pack(side="left", padx=(8, 8))
        
        self.progress_videos_value = ttk.Label(vid_frame, text="0/0")
        self.progress_videos_value.pack(side="left")
    
    def _setup_event_handlers(self):
        """Set up event handlers and bindings."""
        # Variable change tracking for auto-save
        try:
            self.outvar.trace_add('write', self._on_var_changed)
            self.sizevar.trace_add('write', self._on_var_changed) 
            self.videos_var.trace_add('write', self._on_var_changed)
            self.conv_dir_var.trace_add('write', self._on_var_changed)
        except Exception:
            pass
        
        # URL box modification tracking
        try:
            self.urlbox.bind('<<Modified>>', self._on_urlbox_modified)
            self.urlbox.edit_modified(False)
        except Exception:
            pass
        
        # Window geometry changes
        self.bind('<Configure>', self._on_configure)
        
        # Window close handler
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Signal handlers for graceful shutdown
        self._install_signal_handlers()
    
    def _load_preferences(self):
        """Load user preferences."""
        try:
            prefs = self.prefs_manager.load_preferences()
            prefs = self.prefs_manager.validate_preferences(prefs)
            
            # Apply preferences
            self.lang = prefs.get("language", "en")
            
            if prefs.get("geometry"):
                self.geometry(prefs["geometry"])
            
            if prefs.get("output_dir"):
                self.outvar.set(prefs["output_dir"])
            
            if prefs.get("image_mode"):
                self.sizevar.set(prefs["image_mode"])
            
            self.videos_var.set(prefs.get("download_videos", True))
            
            if prefs.get("urls"):
                self.urlbox.delete("1.0", tk.END)
                self.urlbox.insert("1.0", prefs["urls"])
            
            if prefs.get("converter_dir"):
                self.conv_dir_var.set(prefs["converter_dir"])
        
        except Exception:
            pass  # Use defaults if loading fails
    
    def _save_preferences(self):
        """Save current preferences."""
        if self._loading_prefs:
            return
        
        try:
            prefs = {
                "geometry": self.geometry(),
                "language": self.lang,
                "output_dir": self.outvar.get(),
                "image_mode": self.sizevar.get(),
                "download_videos": self.videos_var.get(),
                "urls": self.urlbox.get("1.0", tk.END),
                "converter_dir": self.conv_dir_var.get(),
            }
            self.prefs_manager.save_preferences(prefs)
        except Exception:
            pass  # Silent fail
    
    # Event handlers
    def _on_var_changed(self, *args):
        """Handle variable changes for auto-save."""
        self._save_preferences()
    
    def _on_urlbox_modified(self, event=None):
        """Handle URL box modifications."""
        try:
            self.urlbox.edit_modified(False)
        except Exception:
            pass
        self._save_preferences()
    
    def _on_configure(self, event=None):
        """Handle window configure events."""
        if self._loading_prefs:
            return
        
        # Debounce geometry saving
        if self._geom_save_job:
            try:
                self.after_cancel(self._geom_save_job)
            except Exception:
                pass
        
        self._geom_save_job = self.after(500, self._save_preferences)
    
    def _on_lang_change(self, event=None):
        """Handle language change."""
        selected = self.lang_var.get()
        if T("id", "lang_id") in selected:
            self.lang = "id"
        else:
            self.lang = "en"
        
        self.apply_i18n()
        self._save_preferences()
    
    def _on_close(self):
        """Handle window close."""
        self._save_preferences()
        self.destroy()
    
    def _install_signal_handlers(self):
        """Install signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            try:
                self._save_preferences()
            except Exception:
                pass
            self.quit()
        
        try:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        except Exception:
            pass  # May not work on all platforms
    
    # UI Actions
    def apply_i18n(self):
        """Apply current language to all UI elements."""
        self.title(T(self.lang, "app_title"))
        
        # Update intro text
        self.intro_label.configure(text=T(self.lang, "intro"))
        
        # Update labels
        self.urls_label.configure(text=T(self.lang, "urls_label"))
        self.out_label.configure(text=T(self.lang, "output_label"))
        self.choose_btn.configure(text=T(self.lang, "choose"))
        self.mode_label.configure(text=T(self.lang, "mode_label"))
        self.mode_hint.configure(text=T(self.lang, "mode_hint"))
        self.videos_check.configure(text=T(self.lang, "videos_check"))
        self.start_btn.configure(text=T(self.lang, "btn_start"))
        
        # Update converter section
        self.conv_title.configure(text=T(self.lang, "conv_title"))
        self.conv_subtitle.configure(text=T(self.lang, "conv_subtitle"))
        self.conv_pick_label.configure(text=T(self.lang, "conv_pick_label"))
        self.conv_choose_btn.configure(text=T(self.lang, "conv_btn_choose"))
        self.conv_start_btn.configure(text=T(self.lang, "conv_btn_start"))
        
        # Update progress section
        self.log_title.configure(text=T(self.lang, "log"))
        self.images_label.configure(text=T(self.lang, "images"))
        self.videos_label.configure(text=T(self.lang, "videos"))
        
        # Update language selector
        self.lang_var.set(T(self.lang, "lang_id" if self.lang == "id" else "lang_en"))
    
    def pick_out(self):
        """Handle output directory selection."""
        folder = filedialog.askdirectory(title=T(self.lang, "choose"))
        if folder:
            self.outvar.set(folder)
    
    def pick_conv_dir(self):
        """Handle converter directory selection.""" 
        folder = filedialog.askdirectory(title=T(self.lang, "conv_btn_choose"))
        if folder:
            self.conv_dir_var.set(folder)
    
    def start(self):
        """Start the main download process."""
        # Get and validate URLs
        urls_text = self.urlbox.get("1.0", tk.END).strip()
        if not urls_text:
            messagebox.showerror(T(self.lang, "missing_urls_msg"), T(self.lang, "missing_urls_msg"))
            return
        
        urls = [url.strip() for url in urls_text.split('\n') if url.strip()]
        if not urls:
            messagebox.showerror(T(self.lang, "missing_urls_msg"), T(self.lang, "missing_urls_msg"))
            return
        
        # Validate output directory
        outdir = self.outvar.get().strip()
        if not outdir:
            messagebox.showerror(T(self.lang, "missing_out_title"), T(self.lang, "missing_out_msg"))
            return
        
        # Validate image size
        size_text = self.sizevar.get()
        is_valid, width = validate_image_size(size_text)
        if not is_valid:
            messagebox.showerror(T(self.lang, "invalid_size_title"), T(self.lang, "invalid_size_msg"))
            return
        
        # Determine if original images requested
        img_original = (width == -1)  # -1 indicates ORIGINAL mode
        if not img_original:
            width = int(width)
        
        # Reset progress
        self.update_progress_images(0, 0)
        self.update_progress_videos(0, 0)
        
        # Save preferences before starting
        self._save_preferences()
        
        # Start worker thread
        start_worker_thread(
            run_worker,
            urls, outdir, self.log_handler, self.start_btn,
            width, self.videos_var.get(), img_original,
            self, self.lang
        )
    
    def start_converter(self):
        """Start the thumbnail converter process."""
        local_dir = self.conv_dir_var.get().strip()
        if not local_dir:
            messagebox.showerror(
                T(self.lang, "missing_conv_dir_title"), 
                T(self.lang, "missing_conv_dir_msg")
            )
            return
        
        # Reset progress
        self.update_progress_images(0, 0)
        self.update_progress_videos(0, 0)
        
        # Start converter worker
        start_worker_thread(
            run_converter,
            local_dir, self.log_handler, self.conv_start_btn, self, self.lang
        )
    
    def cancel(self):
        """Cancel current operation."""
        try:
            setattr(dfr, "INTERRUPTED", True)
        except Exception:
            pass
    
    def sign_in(self):
        """Handle sign in/out."""
        # This will trigger OAuth flow
        try:
            service, creds = dfr.get_service_and_creds(dfr.TOKEN_FILE, dfr.CREDENTIALS_FILE)
            account = dfr.get_account_info(service)
            if account.get("email"):
                self.set_account(account.get("name", ""), account["email"])
        except Exception as e:
            messagebox.showerror("Sign In Error", f"Failed to sign in: {e}")
    
    def sign_out(self):
        """Sign out and clear token."""
        try:
            import os
            from pathlib import Path
            token_path = Path(dfr.TOKEN_FILE)
            if token_path.exists():
                backup_path = token_path.with_suffix(token_path.suffix + ".bak")
                try:
                    if backup_path.exists():
                        backup_path.unlink()
                except Exception:
                    pass
                token_path.rename(backup_path)
            self.set_account("", "")
        except Exception as e:
            messagebox.showerror("Sign Out Error", f"Failed to sign out: {e}")
    
    def _check_account_async(self):
        """Check account status in background thread."""
        try:
            account = dfr.try_get_account_info(dfr.TOKEN_FILE, dfr.CREDENTIALS_FILE)
            if account.get("email"):
                self.after(0, lambda: self.set_account(account.get("name", ""), account["email"]))
        except Exception:
            pass  # Silent fail for background check
    
    # Progress updates
    def set_account(self, name: str, email: str):
        """Update account display."""
        if email:
            if name:
                self.acct_var.set(f"Account: {name} <{email}>")
            else:
                self.acct_var.set(f"Account: {email}")
            self.auth_btn.configure(text="Sign out", command=self.sign_out)
        else:
            self.acct_var.set("Account: (not signed in)")
            self.auth_btn.configure(text="Sign in", command=self.sign_in)
    
    def update_progress_images(self, done: int, total: int):
        """Update image progress bar."""
        total = max(total, 0)
        done = min(max(done, 0), total) if total else 0
        
        self.progress_images["maximum"] = total if total else 1
        self.progress_images["value"] = done
        
        progress_text = f"{done}/{total} ({T(self.lang, 'progress_left')} {max(total-done, 0)})"
        self.progress_images_value.configure(text=progress_text)
        self.update_idletasks()
    
    def update_progress_videos(self, done: int, total: int):
        """Update video progress bar."""
        total = max(total, 0)
        done = min(max(done, 0), total) if total else 0
        
        self.progress_videos["maximum"] = total if total else 1
        self.progress_videos["value"] = done
        
        progress_text = f"{done}/{total} ({T(self.lang, 'progress_left')} {max(total-done, 0)})"
        self.progress_videos_value.configure(text=progress_text)
        self.update_idletasks()
    
    def update_progress_bytes(self, bytes_written: int):
        """Update bytes progress (if implemented in UI)."""
        self.bytes_written = max(0, bytes_written)
        # Could add a bytes progress bar here if needed