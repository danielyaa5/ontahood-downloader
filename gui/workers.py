"""
Background worker functions for the GUI application.
"""

import os
import re
import sys
import threading
import traceback
from pathlib import Path
from tkinter import ttk, messagebox

# Import dfr modules and main backend
import dfr.main as dfr_main
import dfr.auth as dfr_auth
import dfr.utils as dfr_utils
import dfr.prescan as dfr_prescan
import drive_fetch_resilient as dfr
from .i18n import T
from .utils import locate_credentials, notify
from .log_handler import TkLogHandler


def run_worker(urls, outdir, log: TkLogHandler, btn: ttk.Button,
               preview_width: int, download_videos: bool, img_original: bool, 
               app_ref, lang: str):
    """
    Main worker function for downloading from Google Drive URLs.
    
    Args:
        urls: List of Google Drive folder URLs
        outdir: Output directory path
        log: Log handler for GUI output
        btn: Button to re-enable when finished
        preview_width: Image preview width in pixels
        download_videos: Whether to download videos
        img_original: Whether to download original images
        app_ref: Reference to main app for progress updates
        lang: Language code ('en' or 'id')
    """
    btn.configure(state="disabled")
    
    try:
        # Enable cancel button
        try:
            app_ref.cancel_btn.configure(state="normal")
        except Exception:
            pass
        
        # Create output directory
        out_root = Path(outdir)
        out_root.mkdir(parents=True, exist_ok=True)
        
        # Log configuration
        if img_original:
            msg = T(lang, "log_img_mode_original")
            log.put(msg)
            print(msg)
        else:
            msg = T(lang, "log_img_mode_thumb", w=preview_width)
            log.put(msg)
            print(msg)
        
        msg = T(lang, "log_vids", state=T(lang, "log_vids_on" if download_videos else "log_vids_off"))
        log.put(msg)
        print(msg)
        
        msg = T(lang, "log_processing", n=len(urls))
        log.put(msg)
        print(msg)
        
        # Locate credentials
        cred_path = locate_credentials()
        if cred_path:
            dfr.CREDENTIALS_FILE = str(cred_path)
            msg = T(lang, "log_creds_found", path=cred_path)
            log.put(msg)
            print(msg)
        else:
            msg = T(lang, "log_creds_missing")
            log.put(msg)
            print(msg)
        
        # Configure backend variables
        dfr.FOLDER_URLS = urls
        dfr.OUTPUT_DIR = str(out_root)
        dfr.IMAGE_WIDTH = int(preview_width)
        dfr.DOWNLOAD_VIDEOS = bool(download_videos)
        dfr.DOWNLOAD_IMAGES_ORIGINAL = bool(img_original)
        dfr.CONVERT_THUMBS_DIR = ""  # make sure converter mode is off
        
        # Set up GUI logging handler
        class _GuiHandler(dfr.logging.Handler):
            def emit(self, record):
                try:
                    msg = self.format(record)
                    log.put(msg)
                    
                    # Parse progress information
                    if "[Progress]" in msg:
                        # Parse progress from backend logging
                        progress_matches = re.findall(r"(\d+)/(\d+)", msg)
                        if progress_matches:
                            # First pair for images, second for videos if present
                            app_ref.update_progress_images(int(progress_matches[0][0]), int(progress_matches[0][1]))
                            if len(progress_matches) > 1:
                                app_ref.update_progress_videos(int(progress_matches[1][0]), int(progress_matches[1][1]))
                    
                    # Parse bytes information
                    if msg.startswith("[Bytes] "):
                        try:
                            bytes_written = int(msg.split()[1])
                            app_ref.update_progress_bytes(bytes_written)
                        except Exception:
                            pass
                    
                    # Parse account information
                    account_match = re.search(r"(Using account:|Menggunakan akun:)\s*(.*?)\s*<([^>]+)>", msg)
                    if account_match:
                        app_ref.set_account(account_match.group(2).strip(), account_match.group(3).strip())
                    else:
                        email_match = re.search(r"<([^>]+)>", msg)
                        if email_match:
                            app_ref.set_account("", email_match.group(1).strip())
                except Exception:
                    pass
        
        # Set up logging
        dfr.LANG = lang
        fmt = dfr.logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%Y-%m-%d %H:%M:%S")
        gui_handler = _GuiHandler()
        gui_handler.setLevel(getattr(dfr.logging, dfr.LOG_LEVEL.upper(), dfr.logging.INFO))
        gui_handler.setFormatter(fmt)
        dfr.logging.getLogger().addHandler(gui_handler)
        
        # Run the main process
        dfr_main.main()
        
        # Show summary
        try:
            snap = dfr_utils.get_totals_snapshot()
            summary = (
                f"Elapsed: {snap.get('elapsed')}\n"
                f"Scanned: {snap.get('scanned')}\n"
                f"Images: done={snap['images']['done']} skip={snap['images']['skipped']} fail={snap['images']['failed']} "
                f"(expected {snap['images']['expected']}, already {snap['images']['already']})\n"
                f"Videos: done={snap['videos']['done']} skip={snap['videos']['skipped']} fail={snap['videos']['failed']} "
                f"(expected {snap['videos']['expected']}, already {snap['videos']['already']})\n"
                f"Bytes written: {dfr_utils.human_bytes(snap.get('bytes_written', 0))}"
            )
            messagebox.showinfo("Summary", summary)
        except Exception:
            pass
        
        log.put("\n" + T(lang, "done"))
        
        try:
            notify("Ontahood Downloader", "Completed successfully")
        except Exception:
            pass
    
    except Exception:
        # Log error with traceback
        try:
            dfr.logging.getLogger().error(T(lang, "fatal"), exc_info=True)
        except Exception:
            pass
        
        try:
            log.put("\n" + T(lang, "fatal") + "\n" + traceback.format_exc())
        except Exception:
            pass
        
        try:
            notify("Ontahood Downloader", "Error: see log")
        except Exception:
            pass
    
    finally:
        # Re-enable UI elements
        try:
            app_ref.cancel_btn.configure(state="disabled")
        except Exception:
            pass
        btn.configure(state="normal")


def run_converter(local_folder: str, log: TkLogHandler, btn: ttk.Button, app_ref, lang: str):
    """
    Conversion mode: scan a local folder for *_w###.jpg thumbnails and fetch originals.
    
    Args:
        local_folder: Path to folder containing thumbnails
        log: Log handler for GUI output  
        btn: Button to re-enable when finished
        app_ref: Reference to main app for progress updates
        lang: Language code ('en' or 'id')
    """
    btn.configure(state="disabled")
    
    try:
        # Enable cancel button
        try:
            app_ref.cancel_btn.configure(state="normal")
        except Exception:
            pass
        
        # Validate folder
        if not local_folder or not os.path.isdir(local_folder):
            messagebox.showerror(T(lang, "missing_conv_dir_title"), T(lang, "missing_conv_dir_msg"))
            return
        
        # Log configuration
        msg = T(lang, "log_conv_using", path=local_folder)
        log.put(msg)
        print(msg)
        
        msg = T(lang, "log_conv_start")
        log.put(msg)
        print(msg)
        
        # Locate credentials
        cred_path = locate_credentials()
        if cred_path:
            dfr.CREDENTIALS_FILE = str(cred_path)
            log.put(T(lang, "log_creds_found", path=cred_path))
        else:
            log.put(T(lang, "log_creds_missing"))
        
        # Configure backend for conversion mode
        dfr.CONVERT_THUMBS_DIR = str(local_folder)
        dfr.DOWNLOAD_IMAGES_ORIGINAL = True
        dfr.DOWNLOAD_VIDEOS = False  # not needed for conversion
        
        # Set up GUI logging handler
        class _GuiHandler(dfr.logging.Handler):
            def emit(self, record):
                try:
                    msg = self.format(record)
                    log.put(msg)
                    
                    # Parse progress information
                    if "[Progress]" in msg:
                        progress_matches = re.findall(r"(\d+)/(\d+)", msg)
                        if progress_matches:
                            app_ref.update_progress_images(int(progress_matches[0][0]), int(progress_matches[0][1]))
                except Exception:
                    pass
        
        # Set up logging
        dfr.LANG = lang
        fmt = dfr.logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%Y-%m-%d %H:%M:%S")
        gui_handler = _GuiHandler()
        gui_handler.setLevel(getattr(dfr.logging, dfr.LOG_LEVEL.upper(), dfr.logging.INFO))
        gui_handler.setFormatter(fmt)
        dfr.logging.getLogger().addHandler(gui_handler)
        
        # Run the conversion
        dfr_main.main()
        
        log.put("\n" + T(lang, "done"))
        
        try:
            notify("Ontahood Downloader", "Converter completed")
        except Exception:
            pass
    
    except Exception:
        # Log error with traceback
        error_text = "\n" + T(lang, "fatal") + "\n" + traceback.format_exc()
        log.put(error_text)
        
        try:
            sys.stderr.write(error_text)
            sys.stderr.flush()
        except Exception:
            pass
        
        try:
            notify("Ontahood Downloader", "Converter error: see log")
        except Exception:
            pass
    
    finally:
        # Re-enable UI elements
        try:
            app_ref.cancel_btn.configure(state="disabled")
        except Exception:
            pass
        btn.configure(state="normal")


def start_worker_thread(target_func, *args, **kwargs):
    """
    Start a worker function in a background thread.
    
    Args:
        target_func: Function to run in background
        *args: Arguments to pass to target function
        **kwargs: Keyword arguments to pass to target function
    
    Returns:
        Thread object
    """
    thread = threading.Thread(target=target_func, args=args, kwargs=kwargs, daemon=True)
    thread.start()
    return thread