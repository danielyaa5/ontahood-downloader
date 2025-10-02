"""
UI components and widgets for the GUI application.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
from typing import Callable, Optional

from .i18n import T
from .utils import format_bytes


class ProgressFrame(ttk.Frame):
    """A frame containing a progress bar with label and value display."""
    
    def __init__(self, parent, label_text: str, width: int = 520):
        super().__init__(parent)
        
        # Create label
        self.label = ttk.Label(self, text=label_text)
        self.label.pack(side="left")
        
        # Create progress bar
        self.progressbar = ttk.Progressbar(self, length=width, mode="determinate")
        self.progressbar.pack(side="left", padx=(8, 8))
        
        # Create value label
        self.value_label = ttk.Label(self, text="0/0")
        self.value_label.pack(side="left")
    
    def update_progress(self, done: int, total: int, lang: str = "en"):
        """Update the progress bar and labels."""
        total = max(total, 0)
        done = min(max(done, 0), total) if total else 0
        
        self.progressbar["maximum"] = total if total else 1
        self.progressbar["value"] = done
        
        remaining = max(total - done, 0)
        progress_text = f"{done}/{total} ({T(lang, 'progress_left')} {remaining})"
        self.value_label.configure(text=progress_text)


class FileSelectionFrame(ttk.Frame):
    """A frame for file/folder selection with entry and browse button."""
    
    def __init__(self, parent, label_text: str, button_text: str, 
                 select_callback: Callable, is_folder: bool = False):
        super().__init__(parent)
        
        self.is_folder = is_folder
        self.select_callback = select_callback
        
        # Create label
        self.label = ttk.Label(self, text=label_text)
        self.label.pack(side="left")
        
        # Create variable and entry
        self.var = tk.StringVar()
        self.entry = ttk.Entry(self, textvariable=self.var)
        self.entry.pack(side="left", fill="x", expand=True, padx=8)
        
        # Create browse button
        self.button = ttk.Button(self, text=button_text, command=self._browse)
        self.button.pack(side="left")
    
    def _browse(self):
        """Handle browse button click."""
        if self.is_folder:
            path = filedialog.askdirectory(title="Select Folder")
        else:
            path = filedialog.askopenfilename(title="Select File")
        
        if path:
            self.var.set(path)
            if self.select_callback:
                self.select_callback(path)
    
    def get_value(self) -> str:
        """Get the current path value."""
        return self.var.get().strip()
    
    def set_value(self, value: str):
        """Set the path value."""
        self.var.set(value)


class AccountFrame(ttk.Frame):
    """Frame showing account information and sign in/out button."""
    
    def __init__(self, parent, sign_in_callback: Callable, sign_out_callback: Callable):
        super().__init__(parent)
        
        self.sign_in_callback = sign_in_callback
        self.sign_out_callback = sign_out_callback
        self.is_signed_in = False
        
        # Account label
        self.account_var = tk.StringVar(value="Account: (not signed in)")
        self.account_label = ttk.Label(self, textvariable=self.account_var)
        self.account_label.pack(side="right")
        
        # Auth button
        self.auth_button = ttk.Button(self, text="Sign in", command=self._toggle_auth)
        self.auth_button.pack(side="right", padx=(0, 8))
    
    def _toggle_auth(self):
        """Handle sign in/out button click."""
        if self.is_signed_in:
            self.sign_out_callback()
        else:
            self.sign_in_callback()
    
    def set_account(self, name: str, email: str):
        """Update account information."""
        if email:
            if name:
                self.account_var.set(f"Account: {name} <{email}>")
            else:
                self.account_var.set(f"Account: {email}")
            self.auth_button.configure(text="Sign out")
            self.is_signed_in = True
        else:
            self.account_var.set("Account: (not signed in)")
            self.auth_button.configure(text="Sign in")
            self.is_signed_in = False
    
    def clear_account(self):
        """Clear account information."""
        self.set_account("", "")


class LanguageFrame(ttk.Frame):
    """Frame for language selection."""
    
    def __init__(self, parent, language_change_callback: Callable):
        super().__init__(parent)
        
        self.language_change_callback = language_change_callback
        
        # Language label
        self.label = ttk.Label(self, text="Language / Bahasa")
        self.label.pack(side="left")
        
        # Language combobox
        self.lang_var = tk.StringVar(value="English")
        self.lang_combobox = ttk.Combobox(
            self, textvariable=self.lang_var,
            values=["English", "Bahasa Indonesia"], 
            width=22, state="readonly"
        )
        self.lang_combobox.pack(side="left", padx=(8, 0))
        self.lang_combobox.bind("<<ComboboxSelected>>", self._on_language_change)
    
    def _on_language_change(self, event=None):
        """Handle language change."""
        selected = self.lang_var.get()
        lang_code = "id" if "Indonesia" in selected else "en"
        if self.language_change_callback:
            self.language_change_callback(lang_code)
    
    def set_language(self, lang_code: str):
        """Set the current language."""
        if lang_code == "id":
            self.lang_var.set("Bahasa Indonesia")
        else:
            self.lang_var.set("English")


class SectionFrame(ttk.Frame):
    """A frame representing a major application section with title and content."""
    
    def __init__(self, parent, title: str, subtitle: str = ""):
        super().__init__(parent)
        
        # Title label
        self.title_label = ttk.Label(self, text=title, font=("TkDefaultFont", 11, "bold"))
        self.title_label.pack(anchor="w")
        
        # Subtitle label (if provided)
        if subtitle:
            self.subtitle_label = ttk.Label(self, text=subtitle, wraplength=940, justify="left")
            self.subtitle_label.pack(anchor="w", pady=(4, 8))
        
        # Content frame for child widgets
        self.content_frame = ttk.Frame(self)
        self.content_frame.pack(fill="both", expand=True)
    
    def update_title(self, title: str):
        """Update the section title."""
        self.title_label.configure(text=title)
    
    def update_subtitle(self, subtitle: str):
        """Update the section subtitle."""
        if hasattr(self, 'subtitle_label'):
            self.subtitle_label.configure(text=subtitle)


class ControlButtonFrame(ttk.Frame):
    """Frame containing control buttons (Start, Cancel, etc.)."""
    
    def __init__(self, parent):
        super().__init__(parent)
        
        self.buttons = {}
    
    def add_button(self, name: str, text: str, command: Callable, 
                   side: str = "right", **kwargs) -> ttk.Button:
        """Add a button to the frame."""
        button = ttk.Button(self, text=text, command=command, **kwargs)
        button.pack(side=side, padx=(6, 0) if side == "right" else (0, 6))
        self.buttons[name] = button
        return button
    
    def get_button(self, name: str) -> Optional[ttk.Button]:
        """Get a button by name."""
        return self.buttons.get(name)
    
    def enable_button(self, name: str, enabled: bool = True):
        """Enable or disable a button."""
        button = self.get_button(name)
        if button:
            button.configure(state="normal" if enabled else "disabled")


def create_scrolled_text(parent, height: int = 15, width: int = None, **kwargs) -> scrolledtext.ScrolledText:
    """Create a scrolled text widget with consistent styling."""
    text_widget = scrolledtext.ScrolledText(
        parent, 
        height=height,
        width=width,
        state="disabled",  # Make read-only by default
        **kwargs
    )
    return text_widget


def show_error(title: str, message: str):
    """Show an error message dialog."""
    messagebox.showerror(title, message)


def show_warning(title: str, message: str):
    """Show a warning message dialog."""
    messagebox.showwarning(title, message)


def show_info(title: str, message: str):
    """Show an info message dialog."""
    messagebox.showinfo(title, message)


def ask_yes_no(title: str, message: str) -> bool:
    """Ask a yes/no question."""
    return messagebox.askyesno(title, message)