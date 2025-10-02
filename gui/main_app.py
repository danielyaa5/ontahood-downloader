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
from .workers import run_worker, run_converter, start_worker_thread, run_prescan


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
        """Start the main download process (with pre-scan preview)."""
        try:
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
            
            # Add initial log message
            self.log_handler.put("[GUI] Starting pre-scan...")

            # Store context for after preview confirm
            self._pending_start_ctx = {
                "urls": urls,
                "outdir": outdir,
                "width": width,
                "img_original": img_original,
                "download_videos": self.videos_var.get(),
            }

            # Disable Start and enable Cancel while prescan runs
            try:
                self.start_btn.configure(state="disabled")
                self.cancel_btn.configure(state="normal")
            except Exception:
                pass
            
            # Create prescan window immediately with loading state
            # Pass the number of URLs so we can display the counter
            self.create_prescan_window()
            
            # Start prescan worker thread
            start_worker_thread(
                run_prescan,
                urls, outdir, self.log_handler,
                width, self.videos_var.get(), img_original,
                self, self.lang
            )
        except Exception as e:
            import traceback
            error_msg = f"Error starting download: {e}\n{traceback.format_exc()}"
            self.log_handler.put(error_msg)
            messagebox.showerror("Start Error", str(e))
    
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

    # Pre-scan preview dialog
    def create_prescan_window(self):
        """Create and show prescan window immediately with loading state."""
        try:
            # Close any existing preview window
            if hasattr(self, "_prescan_win") and self._prescan_win and tk.Toplevel.winfo_exists(self._prescan_win):
                try:
                    self._prescan_win.destroy()
                except Exception:
                    pass
        except Exception:
            pass

        self._prescan_tasks = []
        self._prescan_totals = {"images": 0, "videos": 0, "data": 0, "have_images": 0, "have_videos": 0, "have_data": 0}
        self._prescan_total_bytes = 0
        self._prescan_loading_dots = 0
        self._prescan_folders_scanned = 0
        # Get total folder count from pending context
        try:
            self._prescan_folders_total = len(self._pending_start_ctx.get("urls", []))
        except Exception:
            self._prescan_folders_total = 0

        win = tk.Toplevel(self)
        self._prescan_win = win
        try:
            win.title(T(self.lang, "prescan_title"))
        except Exception:
            win.title("Pre-Scan Preview")
        win.geometry("820x520")
        win.minsize(680, 420)
        win.transient(self)
        win.grab_set()
        
        # Handle window close (X button) same as Cancel
        def on_window_close():
            self._prescan_loading = False
            try:
                # Signal the backend to stop
                import drive_fetch_resilient as dfr
                dfr.INTERRUPTED = True
            except Exception:
                pass
            try:
                win.destroy()
            except Exception:
                pass
            # Re-enable Start, disable Cancel
            try:
                self.start_btn.configure(state="normal")
                self.cancel_btn.configure(state="disabled")
            except Exception:
                pass
        
        win.protocol("WM_DELETE_WINDOW", on_window_close)

        # Description
        desc = ttk.Label(win, text=T(self.lang, "prescan_desc"), wraplength=780, justify="left")
        desc.pack(anchor="w", padx=12, pady=(12, 6))

        # Treeview for per-link counts
        cols = ("root", "images", "videos", "size")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=12)
        tree.heading("root", text=T(self.lang, "prescan_col_root"))
        tree.heading("images", text=T(self.lang, "prescan_col_images"))
        tree.heading("videos", text=T(self.lang, "prescan_col_videos"))
        tree.heading("size", text="Size")
        tree.column("root", width=320, anchor="w")
        tree.column("images", width=140, anchor="center")
        tree.column("videos", width=140, anchor="center")
        tree.column("size", width=140, anchor="center")
        tree.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        
        self._prescan_tree = tree

        # Totals line (initially empty)
        totals_label = ttk.Label(win, text="", justify="left")
        totals_label.pack(anchor="w", padx=12, pady=(4, 4))
        self._prescan_totals_label = totals_label
        
        # Loading animation footer
        loading_label = ttk.Label(win, text=T(self.lang, "prescan_scanning"), justify="center")
        loading_label.pack(anchor="center", padx=12, pady=(0, 10))
        self._prescan_loading_label = loading_label
        self._animate_prescan_loading()

        # Buttons
        btn_row = ttk.Frame(win)
        btn_row.pack(fill="x", padx=12, pady=(0, 12))

        def on_cancel():
            self._prescan_loading = False  # Stop animation
            try:
                # Signal the backend to stop
                import drive_fetch_resilient as dfr
                dfr.INTERRUPTED = True
            except Exception:
                pass
            try:
                win.destroy()
            except Exception:
                pass
            # Re-enable Start, disable Cancel
            try:
                self.start_btn.configure(state="normal")
                self.cancel_btn.configure(state="disabled")
            except Exception:
                pass

        def on_start():
            # If there are no tasks, inform and do nothing
            if not self._prescan_tasks:
                try:
                    messagebox.showinfo(T(self.lang, "prescan_title"), T(self.lang, "prescan_none"))
                except Exception:
                    pass
                on_cancel()
                return
            # Set direct tasks and start the main worker
            try:
                import drive_fetch_resilient as dfr
                dfr.set_direct_tasks(self._prescan_tasks)
            except Exception:
                pass
            try:
                self._prescan_loading = False  # Stop animation
                win.destroy()
            except Exception:
                pass
            # Start worker thread (Start is already disabled)
            ctx = getattr(self, "_pending_start_ctx", {})
            start_worker_thread(
                run_worker,
                ctx.get("urls"), ctx.get("outdir"), self.log_handler, self.start_btn,
                ctx.get("width"), self._pending_start_ctx.get("download_videos", True), ctx.get("img_original"),
                self, self.lang
            )

        cancel_button = ttk.Button(btn_row, text=T(self.lang, "prescan_btn_cancel"), command=on_cancel)
        cancel_button.pack(side="left")
        start_button = ttk.Button(btn_row, text=T(self.lang, "prescan_btn_start"), command=on_start)
        start_button.pack(side="right")
        start_button.configure(state="disabled")  # Disabled until prescan completes
        self._prescan_start_button = start_button
        
        self._prescan_loading = True
    
    def _animate_prescan_loading(self):
        """Animate loading dots in prescan window."""
        if not hasattr(self, "_prescan_loading") or not self._prescan_loading:
            return
        
        if not hasattr(self, "_prescan_win") or not self._prescan_win or not tk.Toplevel.winfo_exists(self._prescan_win):
            self._prescan_loading = False
            return
        
        try:
            dots = "." * (self._prescan_loading_dots % 4)
            # Show progress: "Scanning in progress... (3/8)"
            scanned = getattr(self, "_prescan_folders_scanned", 0)
            total = getattr(self, "_prescan_folders_total", 0)
            if total > 0:
                progress_text = f"{T(self.lang, 'prescan_scanning')}{dots} ({scanned}/{total})"
            else:
                progress_text = f"{T(self.lang, 'prescan_scanning')}{dots}"
            self._prescan_loading_label.configure(text=progress_text)
            self._prescan_loading_dots += 1
            self.after(500, self._animate_prescan_loading)
        except Exception:
            self._prescan_loading = False
    
    def add_prescan_folder(self, summary):
        """Add a folder to the prescan tree as it completes."""
        if not hasattr(self, "_prescan_tree") or not self._prescan_tree:
            return
        
        try:
            root_name = summary.get("root_name") or summary.get("url") or "(link)"
            imgs = f"{summary.get('images',0)} (" + T(self.lang, "prescan_have_fmt", n=summary.get('images_existing',0)) + ")"
            vids = f"{summary.get('videos',0)} (" + T(self.lang, "prescan_have_fmt", n=summary.get('videos_existing',0)) + ")"
            
            # Calculate total size for this folder
            folder_bytes = summary.get('images_bytes', 0) + summary.get('videos_bytes', 0) + summary.get('data_bytes', 0)
            try:
                import drive_fetch_resilient as dfr
                size_text = dfr.human_bytes(int(folder_bytes))
            except Exception:
                # Fallback formatting
                if folder_bytes >= 1024**3:
                    size_text = f"{folder_bytes / (1024**3):.2f} GB"
                elif folder_bytes >= 1024**2:
                    size_text = f"{folder_bytes / (1024**2):.2f} MB"
                elif folder_bytes >= 1024:
                    size_text = f"{folder_bytes / 1024:.2f} KB"
                else:
                    size_text = f"{folder_bytes} B"
            
            self._prescan_tree.insert("", "end", values=(root_name, imgs, vids, size_text))
            
            # Update running totals
            self._prescan_totals["images"] += summary.get('images', 0)
            self._prescan_totals["videos"] += summary.get('videos', 0)
            self._prescan_totals["data"] += summary.get('data', 0)
            self._prescan_totals["have_images"] += summary.get('images_existing', 0)
            self._prescan_totals["have_videos"] += summary.get('videos_existing', 0)
            self._prescan_totals["have_data"] += summary.get('data_existing', 0)
            
            # Accumulate bytes from this folder
            self._prescan_total_bytes += summary.get('images_bytes', 0)
            self._prescan_total_bytes += summary.get('videos_bytes', 0)
            self._prescan_total_bytes += summary.get('data_bytes', 0)
            
            # Increment scanned folder count
            self._prescan_folders_scanned += 1
            
            self._update_prescan_totals()
        except Exception:
            pass
    
    def _update_prescan_totals(self):
        """Update the totals label in prescan window."""
        if not hasattr(self, "_prescan_totals_label") or not self._prescan_totals_label:
            return
        
        try:
            import drive_fetch_resilient as dfr
            bytes_text = dfr.human_bytes(int(self._prescan_total_bytes or 0))
        except Exception:
            bytes_text = f"{int(self._prescan_total_bytes or 0)} B"
        
        totals = self._prescan_totals
        totals_text = (
            f"{T(self.lang, 'prescan_totals')}: "
            f"{T(self.lang,'images')}={totals.get('images',0)} (" + T(self.lang,'prescan_have_fmt', n=totals.get('have_images',0)) + ") | "
            f"{T(self.lang,'videos')}={totals.get('videos',0)} (" + T(self.lang,'prescan_have_fmt', n=totals.get('have_videos',0)) + ") | "
            f"{T(self.lang,'data')}={totals.get('data',0)} (" + T(self.lang,'prescan_have_fmt', n=totals.get('have_data',0)) + ")\n"
            f"{T(self.lang, 'prescan_bytes_total')}: {bytes_text}"
        )
        self._prescan_totals_label.configure(text=totals_text)
    
    def finish_prescan(self, tasks, total_bytes):
        """Called when prescan completes. Enable the start button and hide loading."""
        self._prescan_loading = False
        self._prescan_tasks = list(tasks or [])
        self._prescan_total_bytes = total_bytes
        
        # Check if window was closed early
        if not hasattr(self, "_prescan_win") or not self._prescan_win:
            # Window was closed, just re-enable the main Start button
            try:
                self.start_btn.configure(state="normal")
                self.cancel_btn.configure(state="disabled")
            except Exception:
                pass
            return
        
        try:
            # Check if window still exists
            if not tk.Toplevel.winfo_exists(self._prescan_win):
                # Window was closed, just re-enable the main Start button
                try:
                    self.start_btn.configure(state="normal")
                    self.cancel_btn.configure(state="disabled")
                except Exception:
                    pass
                return
        except Exception:
            # Window was closed, just re-enable the main Start button
            try:
                self.start_btn.configure(state="normal")
                self.cancel_btn.configure(state="disabled")
            except Exception:
                pass
            return
        
        try:
            # Hide loading label
            if hasattr(self, "_prescan_loading_label") and self._prescan_loading_label:
                self._prescan_loading_label.configure(text="")
            
            # Update totals one final time
            self._update_prescan_totals()
            
            # Enable start button
            if hasattr(self, "_prescan_start_button") and self._prescan_start_button:
                self._prescan_start_button.configure(state="normal")
        except Exception:
            # If any error, still re-enable the main Start button
            try:
                self.start_btn.configure(state="normal")
                self.cancel_btn.configure(state="disabled")
            except Exception:
                pass
