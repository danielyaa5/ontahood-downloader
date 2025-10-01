#!/usr/bin/env python3
# drive_fetch_gui.py — Simple Tkinter GUI (bilingual EN/ID)
# v0.15 — 2025-10-01
# - Keeps original thumbnail/video downloader at top
# - Adds separate section to convert local thumbnail folders to ORIGINAL images
#   (select a folder of your chosen thumbnails and it will add full-size images into the same folder)
# - Log view now only auto-scrolls if the user is at the bottom

import os
import threading, queue, traceback, sys, re, json, signal
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from tkinter import font as tkfont

# Optional imports (help the freezer detect deps if you bundle them)
try:
    import requests  # noqa: F401
    import googleapiclient.discovery  # noqa: F401
except Exception:
    pass

try:
    import drive_fetch_resilient as dfr
except Exception as e:
    raise SystemExit("Could not import drive_fetch_resilient.py. Put this GUI file next to it. " + str(e))

DEFAULT_URLS = [
    "https://drive.google.com/drive/folders/1w3ZDXNc84uicLw4C2wmYydq_hlg2MLcS?usp=sharing",
    "https://drive.google.com/drive/folders/1vD1WYNk9dVCYq253HPidldm0ZrNM6jnN?usp=sharing",
    "https://drive.google.com/drive/folders/1nklHSD6T3MjOnvBcCJk3vyIwSvWWWU1p?usp=sharing",
    "https://drive.google.com/drive/folders/1UXQWP96aBOsMMNZMj2Bjc9DRz3-uYdiK?usp=sharing",
    "https://drive.google.com/drive/folders/1tw2_FqrKOTg4M3S7TjA8uFo7O0uo5fUl?usp=sharing",
    "https://drive.google.com/drive/folders/1m_ilkLvARbsOINanTsb7PdTPTuhrP4lZ?usp=sharing",
    "https://drive.google.com/drive/folders/1hCPcSOfmmv125hNi4cL3xs6grXSQVnxN",
    "https://drive.google.com/drive/folders/1aOgrp6huu_5b-egMRgTtefpiCXYGhDxS",
    "https://drive.google.com/drive/folders/1nozDgru1P9-NQRxTBOVp0m-_ujZHtt6H",
]
CONVERT_THUMBS_DIR = None  # path to a local folder of thumbnails for conversion

# Preferences file (persist GUI state between runs)
try:
    GUI_PREFS_FILE = (Path(dfr.SUPPORT_DIR) / "gui_prefs.json")
except Exception:
    GUI_PREFS_FILE = Path.home() / ".ontahood_gui_prefs.json"

# ----------------- i18n -----------------

I18N = {
    "en": {
        "app_title": "ontahood-downloader",
        "intro": (
            "Paste Google Drive folder URLs below. Choose ORIGINAL to fetch full-size images, "
            "or a thumbnail width (up to 6000 px) for previews. Each URL is saved under its own parent folder."
        ),
        "urls_label": "Google Drive folder URLs (one per line):",
        "output_label": "Output folder:",
        "choose": "Choose…",
        "mode_label": "Image mode (thumbnail width / ORIGINAL):",
        "mode_hint": "ORIGINAL = full-size download; XXXpx = reduced image size (MUCH smaller file size).",
        "videos_check": "Download videos (full size)",
        "btn_start": "Start",
        "log": "Log:",
        "images": "Images:",
        "videos": "Videos:",
        "missing_urls_title": "Missing URLs",
        "missing_urls_msg": "Paste at least one folder URL.",
        "missing_out_title": "Missing output folder",
        "missing_out_msg": "Choose an output folder.",
        "invalid_size_title": "Invalid size",
        "invalid_size_msg": "Pick 100–6000 or ORIGINAL.",
        "progress_left": "left",
        "log_img_mode_original": "[GUI] Image mode: ORIGINAL (full size)",
        "log_img_mode_thumb": "[GUI] Image mode: THUMBNAIL {w}px",
        "log_vids": "[GUI] Download videos: {state}",
        "log_vids_on": "ENABLED",
        "log_vids_off": "DISABLED",
        "log_processing": "[GUI] Processing {n} URL(s)",
        "log_creds_found": "[GUI] credentials.json found: {path}",
        "log_creds_missing": "[GUI] credentials.json not found — sign-in will fail until included.",
        "done": "[GUI] Done.",
        "fatal": "[GUI] Fatal error:",
        "language": "Language / Bahasa",
        "lang_en": "English",
        "lang_id": "Bahasa Indonesia",

        # Converter section
        "conv_title": "🔁 Convert Thumbnails to Original Images",
        "conv_subtitle": (
            "Once you finish your downloads, pick the images you want in full size and put them into a folder on your computer. "
            "Then run this. It will add the full-size images to that same folder."
        ),
        "conv_pick_label": "Folder containing chosen thumbnails:",
        "conv_btn_choose": "Choose Folder…",
        "conv_btn_start": "Start",
        "missing_conv_dir_title": "Missing folder",
        "missing_conv_dir_msg": "Please choose the folder that contains your selected thumbnails.",
        "log_conv_using": "[GUI] Converting thumbnails in: {path}",
        "log_conv_start": "[GUI] Starting original-size fetch for files in this folder…",
    },
    "id": {
        "app_title": "Drive Fetch",
        "intro": (
            "Tempel tautan folder Google Drive di bawah. Pilih ORIGINAL untuk mengunduh gambar ukuran penuh, "
            "atau lebar thumbnail (hingga 6000 px) untuk pratinjau. Setiap URL disimpan pada folder induknya sendiri."
        ),
        "urls_label": "Tautan folder Google Drive (satu per baris):",
        "output_label": "Folder keluaran:",
        "choose": "Pilih…",
        "mode_label": "Mode gambar (lebar thumbnail / ORIGINAL):",
        "mode_hint": "ORIGINAL = unduhan ukuran penuh; angka = thumbnail lokal.",
        "videos_check": "Unduh video (ukuran penuh)",
        "btn_start": "Mulai",
        "log": "Log:",
        "images": "Gambar:",
        "videos": "Video:",
        "missing_urls_title": "URL kosong",
        "missing_urls_msg": "Tempel minimal satu tautan folder.",
        "missing_out_title": "Folder keluaran kosong",
        "missing_out_msg": "Pilih folder keluaran.",
        "invalid_size_title": "Ukuran tidak valid",
        "invalid_size_msg": "Pilih 100–6000 atau ORIGINAL.",
        "progress_left": "sisa",
        "log_img_mode_original": "[GUI] Mode gambar: ORIGINAL (ukuran penuh)",
        "log_img_mode_thumb": "[GUI] Mode gambar: THUMBNAIL {w}px",
        "log_vids": "[GUI] Unduh video: {state}",
        "log_vids_on": "DIAKTIFKAN",
        "log_vids_off": "DINONAKTIFKAN",
        "log_processing": "[GUI] Memproses {n} URL",
        "log_creds_found": "[GUI] credentials.json ditemukan: {path}",
        "log_creds_missing": "[GUI] credentials.json tidak ditemukan — login akan gagal sampai disertakan.",
        "done": "[GUI] Selesai.",
        "fatal": "[GUI] Kesalahan fatal:",
        "language": "Bahasa / Language",
        "lang_en": "English",
        "lang_id": "Bahasa Indonesia",

        # Converter section
        "conv_title": "🔁 Ubah Thumbnail ke Gambar Asli",
        "conv_subtitle": (
            "Setelah selesai mengunduh, pilih gambar yang Anda inginkan ukuran aslinya dan masukkan ke sebuah folder di komputer. "
            "Lalu jalankan bagian ini. Aplikasi akan menambahkan gambar ukuran penuh ke folder yang sama."
        ),
        "conv_pick_label": "Folder berisi thumbnail pilihan:",
        "conv_btn_choose": "Pilih Folder…",
        "conv_btn_start": "Mulai Ambil Ukuran Asli",
        "missing_conv_dir_title": "Folder belum dipilih",
        "missing_conv_dir_msg": "Silakan pilih folder yang berisi thumbnail pilihan Anda.",
        "log_conv_using": "[GUI] Mengonversi thumbnail di: {path}",
        "log_conv_start": "[GUI] Memulai unduhan gambar ukuran asli untuk file di folder ini…",
    },
}

def T(lang: str, key: str, **kw) -> str:
    txt = I18N.get(lang, I18N["en"]).get(key, I18N["en"].get(key, key))
    return txt.format(**kw) if kw else txt

# ----------------- Helpers -----------------

def locate_credentials():
    cands = []
    try:
        cands.append(Path(__file__).resolve().parent / "credentials.json")
    except Exception:
        pass
    if hasattr(sys, "_MEIPASS"):
        cands.append(Path(sys._MEIPASS) / "credentials.json")  # type: ignore
    cands.append(Path.home() / "Library" / "Application Support" / "OntahoodDownloader" / "credentials.json")
    for p in cands:
        try:
            if p.exists():
                return p
        except Exception:
            continue
    return None

# ----------------- Logging bridge -----------------

class TkLogHandler:
    """
    Log → Tkinter ScrolledText bridge that only auto-scrolls when the user is at the bottom.
    If the user scrolls up, it stops following until they scroll back down.

    Enhancements:
    - Colorize only timestamp and level.
    - Emphasize bracket tags like [Progress]/[Count] and counters like 10/20 or key=123.
    """
    def __init__(self, widget: scrolledtext.ScrolledText):
        self.widget = widget
        self.queue = queue.Queue()
        self._follow_tail = True  # auto-scroll enabled iff user is at bottom

        # Fonts and tags for styling
        try:
            base_font = tkfont.nametofont(self.widget.cget("font"))
        except Exception:
            base_font = tkfont.nametofont("TkFixedFont")
        self.bold_font = base_font.copy()
        try:
            self.bold_font.configure(weight="bold")
        except Exception:
            pass

        # Colors roughly match terminal formatter
        self.widget.tag_config("ts", foreground="#7f8c8d")
        self.widget.tag_config("level-DEBUG", foreground="#00acc1")
        self.widget.tag_config("level-INFO", foreground="#2ecc71")
        self.widget.tag_config("level-WARNING", foreground="#f39c12")
        self.widget.tag_config("level-ERROR", foreground="#e74c3c")
        self.widget.tag_config("level-CRITICAL", foreground="#ffffff", background="#c0392b")
        self.widget.tag_config("bracket", font=self.bold_font)
        self.widget.tag_config("counter", font=self.bold_font)

        # Update follow state whenever the user scrolls (mouse wheel, keys, dragging)
        for ev in ("<MouseWheel>", "<Shift-MouseWheel>", "<Button-4>", "<Button-5>",  # Windows/macOS, Linux
                   "<ButtonPress-1>", "<B1-Motion>", "<ButtonRelease-1>",            # scrollbar drag
                   "<Key-Up>", "<Key-Down>", "<Prior>", "<Next>", "<Home>", "<End>"):  # PageUp/PageDown
            self.widget.bind(ev, self._on_user_scroll, add="+")

        # Limit retained lines to avoid memory growth
        self.max_lines = 10000

        # Periodically drain log queue (store id so we can cancel on exit)
        self._after_id = None
        try:
            self._after_id = self.widget.after(100, self._drain)
        except Exception:
            self._after_id = None

    def stop(self):
        # Cancel scheduled after-callback and mark stopped
        try:
            self._stopped = True
        except Exception:
            pass
        try:
            if getattr(self, "_after_id", None):
                self.widget.after_cancel(self._after_id)
                self._after_id = None
        except Exception:
            pass

    def _insert_styled(self, line: str):
        # Insert one line with styled timestamp, level, and emphasized tags/counters
        import re as _re
        s = line.rstrip("\n")
        m = _re.match(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| ([A-Z]+)\s+\| (.*)$", s)
        if not m:
            # Fallback: plain insert
            self.widget.insert("end", line)
            return
        ts, level, msg = m.groups()
        # Timestamp
        self.widget.insert("end", ts, ("ts",))
        self.widget.insert("end", " | ")
        # Level (colorized)
        level_tag = f"level-{level}"
        self.widget.insert("end", level, (level_tag,))
        self.widget.insert("end", " | ")
        # Message with emphasis on [brackets] and selective counters only
        # Avoid bolding dates like "2025/5" by only bolding N/N after 'images|videos|gambar|video',
        # and numbers after 'left|sisa', plus key=value pairs.
        pat = _re.compile(r"(\[[^\]]+\])|(\b(?:images|videos|gambar|video)\s\d+/\d+\b)|(\b(?:left|sisa)\s\d+\b)|(\b[A-Za-z_]+=\d+\b)")
        idx = 0
        for m2 in pat.finditer(msg):
            if m2.start() > idx:
                self.widget.insert("end", msg[idx:m2.start()])
            chunk = m2.group(0)
            if m2.group(1):
                self.widget.insert("end", chunk, ("bracket",))
            else:
                self.widget.insert("end", chunk, ("counter",))
            idx = m2.end()
        if idx < len(msg):
            self.widget.insert("end", msg[idx:])
        self.widget.insert("end", "\n")

    def _near_bottom(self, eps: float = 0.001) -> bool:
        """Return True if the visible bottom is at (or very near) the end."""
        try:
            first, last = self.widget.yview()
            return (1.0 - last) <= eps
        except Exception:
            return True

    def _on_user_scroll(self, _evt=None):
        # After Tk processes the scroll/drag, recompute follow state
        self.widget.after_idle(self._update_follow_state)

    def _update_follow_state(self):
        self._follow_tail = self._near_bottom()

    def put(self, line: str):
        if not line.endswith("\n"):
            line += "\n"
        self.queue.put(line)

    def _drain(self):
        # If stopped (during app exit), do not continue scheduling
        if getattr(self, "_stopped", False):
            return
        try:
            while True:
                line = self.queue.get_nowait()
                # Check if we were at the bottom *before* inserting
                was_at_bottom = self._near_bottom()

                self.widget.configure(state="normal")
                self._insert_styled(line)
                # Trim lines if over limit
                try:
                    end_idx = self.widget.index("end-1c")
                    total_lines = int(end_idx.split(".")[0])
                    if total_lines > self.max_lines:
                        cut = total_lines - self.max_lines
                        self.widget.delete("1.0", f"{cut}.0")
                except Exception:
                    pass
                self.widget.configure(state="disabled")

                # Only jump to end if the user was already at the bottom (or follow is on)
                if self._follow_tail and was_at_bottom:
                    self.widget.see("end")
        except queue.Empty:
            pass
        # Keep running
        try:
            if not getattr(self, "_stopped", False):
                self._after_id = self.widget.after(100, self._drain)
        except Exception:
            pass

# ----------------- Workers -----------------

def run_worker(urls, outdir, log: TkLogHandler, btn: ttk.Button,
               preview_width: int, download_videos: bool, img_original: bool, app_ref, lang: str):
    btn.configure(state="disabled")
    try:
        try:
            app_ref.cancel_btn.configure(state="normal")
        except Exception:
            pass
        out_root = Path(outdir); out_root.mkdir(parents=True, exist_ok=True)

        if img_original:
            msg = T(lang, "log_img_mode_original")
            log.put(msg); print(msg)
        else:
            msg = T(lang, "log_img_mode_thumb", w=preview_width)
            log.put(msg); print(msg)
        msg = T(lang, "log_vids", state=T(lang, "log_vids_on" if download_videos else "log_vids_off"))
        log.put(msg); print(msg)
        msg = T(lang, "log_processing", n=len(urls))
        log.put(msg); print(msg)

        cred_path = locate_credentials()
        if cred_path:
            dfr.CREDENTIALS_FILE = str(cred_path)
            msg = T(lang, "log_creds_found", path=cred_path)
            log.put(msg); print(msg)
        else:
            msg = T(lang, "log_creds_missing")
            log.put(msg); print(msg)

        # Pass options to backend
        dfr.FOLDER_URLS = urls
        dfr.OUTPUT_DIR = str(out_root)
        dfr.IMAGE_WIDTH = int(preview_width)
        dfr.DOWNLOAD_VIDEOS = bool(download_videos)
        setattr(dfr, "DOWNLOAD_IMAGES_ORIGINAL", bool(img_original))
        setattr(dfr, "CONVERT_THUMBS_DIR", "")  # make sure converter mode is off

        # Stream backend logs into GUI (and update progress when keywords appear)
        class _GuiHandler(dfr.logging.Handler):
            def emit(self, record):
                try:
                    msg = self.format(record)
                    log.put(msg)
                    if "[Progress]" in msg:
                        # Update images/videos progress if we can parse counts
                        mi = re.findall(r"(\d+)/(\d+)", msg)
                        if mi:
                            # Try first pair for images, second for videos if present
                            app_ref.update_progress_images(int(mi[0][0]), int(mi[0][1]))
                            if len(mi) > 1:
                                app_ref.update_progress_videos(int(mi[1][0]), int(mi[1][1]))
                    if msg.startswith("[Bytes] "):
                        try:
                            bw = int(msg.split()[1])
                            app_ref.update_progress_bytes(bw)
                        except Exception:
                            pass
                    # Update account label for both EN and ID log lines, or any line with <email>
                    m = re.search(r"(Using account:|Menggunakan akun:)\s*(.*?)\s*<([^>]+)>", msg)
                    if m:
                        app_ref.set_account(m.group(2).strip(), m.group(3).strip())
                    else:
                        m2 = re.search(r"<([^>]+)>", msg)
                        if m2:
                            app_ref.set_account("", m2.group(1).strip())
                except Exception:
                    pass

        # Set backend log language and attach GUI log handler. Let backend configure console/file handlers.
        setattr(dfr, "LANG", lang)  # "en" or "id" from the GUI
        fmt = dfr.logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%Y-%m-%d %H:%M:%S")
        gh = _GuiHandler(); gh.setLevel(getattr(dfr.logging, dfr.LOG_LEVEL.upper(), dfr.logging.INFO)); gh.setFormatter(fmt)
        dfr.logging.getLogger().addHandler(gh)

        dfr.main()
        # Post-run summary
        try:
            snap = dfr.get_totals_snapshot()
            summ = (
                f"Elapsed: {snap.get('elapsed')}\n"
                f"Scanned: {snap.get('scanned')}\n"
                f"Images: done={snap['images']['done']} skip={snap['images']['skipped']} fail={snap['images']['failed']} "
                f"(expected {snap['images']['expected']}, already {snap['images']['already']})\n"
                f"Videos: done={snap['videos']['done']} skip={snap['videos']['skipped']} fail={snap['videos']['failed']} "
                f"(expected {snap['videos']['expected']}, already {snap['videos']['already']})\n"
                f"Bytes written: {dfr.human_bytes(snap.get('bytes_written', 0))}"
            )
            messagebox.showinfo("Summary", summ)
        except Exception:
            pass
        log.put("\n" + T(lang, "done"))
        try:
            notify("Ontahood Downloader", "Completed successfully")
        except Exception:
            pass
    except Exception:
        # Emit an ERROR-level log so it renders in red, and include traceback in the GUI log
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
        try:
            app_ref.cancel_btn.configure(state="disabled")
        except Exception:
            pass
        btn.configure(state="normal")

def run_converter(local_folder: str, log: TkLogHandler, btn: ttk.Button, app_ref, lang: str):
    """
    Conversion mode: scan a local folder for *_w###.jpg thumbnails and fetch originals into the same folder.
    """
    btn.configure(state="disabled")
    try:
        try:
            app_ref.cancel_btn.configure(state="normal")
        except Exception:
            pass
        if not local_folder or not os.path.isdir(local_folder):
            messagebox.showerror(T(lang, "missing_conv_dir_title"), T(lang, "missing_conv_dir_msg"))
            return

        msg = T(lang, "log_conv_using", path=local_folder)
        log.put(msg); print(msg)
        msg = T(lang, "log_conv_start")
        log.put(msg); print(msg)

        cred_path = locate_credentials()
        if cred_path:
            dfr.CREDENTIALS_FILE = str(cred_path)
            log.put(T(lang, "log_creds_found", path=cred_path))
        else:
            log.put(T(lang, "log_creds_missing"))

        # Configure backend for conversion mode
        setattr(dfr, "CONVERT_THUMBS_DIR", str(local_folder))
        setattr(dfr, "DOWNLOAD_IMAGES_ORIGINAL", True)
        setattr(dfr, "DOWNLOAD_VIDEOS", False)  # not needed here

        # Stream logs to GUI
        class _GuiHandler(dfr.logging.Handler):
            def emit(self, record):
                try:
                    msg = self.format(record)
                    log.put(msg)
                    if "[Progress]" in msg:
                        mi = re.findall(r"(\d+)/(\d+)", msg)
                        if mi:
                            app_ref.update_progress_images(int(mi[0][0]), int(mi[0][1]))
                except Exception:
                    pass

        # Set backend log language and attach GUI log handler. Let backend configure console/file handlers.
        setattr(dfr, "LANG", lang)  # "en" or "id" from the GUI
        fmt = dfr.logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%Y-%m-%d %H:%M:%S")
        gh = _GuiHandler(); gh.setLevel(getattr(dfr.logging, dfr.LOG_LEVEL.upper(), dfr.logging.INFO)); gh.setFormatter(fmt)
        dfr.logging.getLogger().addHandler(gh)

        dfr.main()
        log.put("\n" + T(lang, "done"))
        try:
            notify("Ontahood Downloader", "Converter completed")
        except Exception:
            pass
    except Exception:
        text = "\n" + T(lang, "fatal") + "\n" + traceback.format_exc()
        log.put(text)
        try:
            sys.stderr.write(text)
            sys.stderr.flush()
        except Exception:
            pass
        try:
            notify("Ontahood Downloader", "Converter error: see log")
        except Exception:
            pass
    finally:
        # Reset converter flag so future thumbnail runs aren't intercepted
        setattr(dfr, "CONVERT_THUMBS_DIR", "")
        try:
            app_ref.cancel_btn.configure(state="disabled")
        except Exception:
            pass
        btn.configure(state="normal")

# ----------------- Notifications -----------------

def notify(title: str, message: str):
    try:
        if sys.platform == "darwin":
            # Use AppleScript notification
            esc_title = title.replace("\"", "\\\"")
            esc_msg = message.replace("\"", "\\\"")
            os.system(f"osascript -e \"display notification \"\"{esc_msg}\"\" with title \"\"{esc_title}\"\"\"")
        elif sys.platform.startswith("win"):
            # Best-effort toast via powershell
            pass
        else:
            # Linux: try notify-send if available
            os.system(f"notify-send '{title}' '{message}' 2>/dev/null || true")
    except Exception:
        pass

# ----------------- App -----------------

class App(tk.Tk):
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
        self._loading_prefs = True
        self._geom_save_job = None
        self.lang = "en"  # default language
        self.title(T(self.lang, "app_title"))
        self.geometry("980x950"); self.minsize(820, 760)

        # Language switcher & account area
        topbar = ttk.Frame(self); topbar.pack(fill="x", padx=12, pady=(10, 0))
        ttk.Label(topbar, text=T(self.lang, "language")).pack(side="left")
        self.lang_var = tk.StringVar(value=T(self.lang, "lang_en"))
        self.lang_box = ttk.Combobox(
            topbar, textvariable=self.lang_var,
            values=[T("en", "lang_en"), T("id", "lang_id")], width=22, state="readonly"
        )
        self.lang_box.pack(side="left", padx=(8, 0))
        self.lang_box.bind("<<ComboboxSelected>>", self._on_lang_change)

        # Account indicator and auth button (Sign in / Sign out)
        self.acct_var = tk.StringVar(value="Account: (not signed in)")
        self.acct_label = ttk.Label(topbar, textvariable=self.acct_var)
        self.acct_label.pack(side="right")
        self.auth_btn = ttk.Button(topbar, text="Sign in", command=self.sign_in)
        self.auth_btn.pack(side="right", padx=(0,8))

        # Intro / instructions (Downloader section)
        self.hdr = ttk.Label(self, wraplength=940, justify="left")
        self.hdr.pack(anchor="w", padx=12, pady=(12, 6))

        # --- DOWNLOADER (top) ---
        self.urls_label = ttk.Label(self)
        self.urls_label.pack(anchor="w", padx=12)
        self.urlbox = scrolledtext.ScrolledText(self, height=6)
        self.urlbox.insert("1.0", "\n".join(DEFAULT_URLS) + "\n")
        self.urlbox.pack(fill="x", padx=12)

        row = ttk.Frame(self); row.pack(fill="x", padx=12)
        self.out_label = ttk.Label(row)
        self.out_label.pack(side="left")
        self.outvar = tk.StringVar(); self.out_entry = ttk.Entry(row, textvariable=self.outvar)
        self.out_entry.pack(side="left", fill="x", expand=True, padx=8)
        self.choose_btn = ttk.Button(row, command=self.pick_out)
        self.choose_btn.pack(side="left")
        self.open_btn = ttk.Button(row, text="Open", command=self.open_outdir)
        self.open_btn.pack(side="left", padx=(6,0))

        psz = ttk.Frame(self); psz.pack(fill="x", padx=12)
        self.mode_label = ttk.Label(psz)
        self.mode_label.pack(side="left")
        self.sizevar = tk.StringVar(value=self.SIZE_OPTIONS[1])
        ttk.Combobox(psz, textvariable=self.sizevar, values=self.SIZE_OPTIONS, width=28, state="readonly").pack(side="left", padx=8)
        self.mode_hint = ttk.Label(psz)
        self.mode_hint.pack(side="left", padx=12)

        vrow = ttk.Frame(self); vrow.pack(fill="x", padx=12, pady=(0,10))
        self.videos_var = tk.BooleanVar(value=True)
        self.videos_check = ttk.Checkbutton(vrow, variable=self.videos_var)
        self.videos_check.pack(side="left")

        btnrow = ttk.Frame(self); btnrow.pack(fill="x", padx=12, pady=(2,10))
        self.start_btn = ttk.Button(btnrow, command=self.start)
        self.start_btn.pack(side="right")
        # Cancel control (enabled only while processing)
        self.cancel_btn = ttk.Button(btnrow, text="Cancel", command=self.cancel, state="disabled")
        self.cancel_btn.pack(side="left")

        # Advanced: concurrency control
        adv = ttk.Frame(self); adv.pack(fill="x", padx=12, pady=(0,6))
        ttk.Label(adv, text="Parallel downloads:").pack(side="left")
        self.concurrent_var = tk.IntVar(value=3)
        self.concurrent_spin = tk.Spinbox(adv, from_=1, to=8, textvariable=self.concurrent_var, width=4)
        self.concurrent_spin.pack(side="left", padx=(6,0))

        # --- CONVERTER (below) ---
        sep = ttk.Separator(self, orient="horizontal"); sep.pack(fill="x", padx=12, pady=(6, 8))

        conv_box = ttk.Frame(self); conv_box.pack(fill="x", padx=12, pady=(4, 6))
        self.conv_title = ttk.Label(conv_box, font=("TkDefaultFont", 11, "bold"))
        self.conv_title.pack(anchor="w")
        self.conv_subtitle = ttk.Label(conv_box, wraplength=940, justify="left")
        self.conv_subtitle.pack(anchor="w", pady=(4, 8))

        conv_row = ttk.Frame(self); conv_row.pack(fill="x", padx=12, pady=(0, 4))
        self.conv_pick_label = ttk.Label(conv_row)
        self.conv_pick_label.pack(side="left")
        self.conv_dir_var = tk.StringVar()
        self.conv_dir_entry = ttk.Entry(conv_row, textvariable=self.conv_dir_var)
        self.conv_dir_entry.pack(side="left", fill="x", expand=True, padx=8)
        self.conv_choose_btn = ttk.Button(conv_row, command=self.pick_conv_dir)
        self.conv_choose_btn.pack(side="left")

        conv_btn_row = ttk.Frame(self); conv_btn_row.pack(fill="x", padx=12, pady=(4, 8))
        self.conv_start_btn = ttk.Button(conv_btn_row, command=self.start_converter)
        self.conv_start_btn.pack(side="right")

        # --- Logs & progress (shared) ---
        self.log_title = ttk.Label(self)
        self.log_title.pack(anchor="w", padx=12)
        self.logs = scrolledtext.ScrolledText(self, height=16, state="disabled"); self.logs.pack(fill="both", expand=True, padx=12, pady=(0,10))
        self.log_handler = TkLogHandler(self.logs)
        # Test log message to verify logging works
        self.log_handler.put(f"2025-10-01 05:15:00 | INFO    | [GUI] Application started - logging system active")

        prow = ttk.Frame(self); prow.pack(fill="x", padx=12, pady=(0,12))
        img_frame = ttk.Frame(prow); img_frame.pack(fill="x", pady=(0,6))
        self.images_label = ttk.Label(img_frame)
        self.images_label.pack(side="left")
        self.progress_images = ttk.Progressbar(img_frame, length=520, mode="determinate")
        self.progress_images.pack(side="left", padx=(8,8))
        self.progress_images_value = ttk.Label(img_frame, text="0/0"); self.progress_images_value.pack(side="left")

        vid_frame = ttk.Frame(prow); vid_frame.pack(fill="x", pady=(0,6))
        self.videos_label = ttk.Label(vid_frame)
        self.videos_label.pack(side="left")
        self.progress_videos = ttk.Progressbar(vid_frame, length=520, mode="determinate")
        self.progress_videos.pack(side="left", padx=(8,8))
        self.progress_videos_value = ttk.Label(vid_frame, text="0/0"); self.progress_videos_value.pack(side="left")

        data_frame = ttk.Frame(prow); data_frame.pack(fill="x")
        ttk.Label(data_frame, text="Data:").pack(side="left")
        self.progress_bytes = ttk.Progressbar(data_frame, length=520, mode="determinate")
        self.progress_bytes.pack(side="left", padx=(8,8))
        self.progress_bytes_value = ttk.Label(data_frame, text="0 / 0"); self.progress_bytes_value.pack(side="left")
        self.expected_bytes_total = 0
        self.bytes_written = 0

        # Load saved preferences before applying language and states
        try:
            self._load_prefs()
        except Exception:
            pass

        # Apply saved auth state to button/label
        try:
            threading.Thread(target=self._check_account_async, daemon=True).start()
        except Exception:
            pass

        # Apply initial language
        self.apply_i18n()

        # Persist on close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Kick off a non-blocking account check (no OAuth popups) to update the label if token is valid
        try:
            threading.Thread(target=self._check_account_async, daemon=True).start()
        except Exception:
            pass

        # Autosave on changes
        try:
            self.outvar.trace_add('write', self._on_var_changed)
            self.sizevar.trace_add('write', self._on_var_changed)
            self.videos_var.trace_add('write', self._on_var_changed)
            self.conv_dir_var.trace_add('write', self._on_var_changed)
            # concurrency
            self.concurrent_var.trace_add('write', self._on_var_changed)
        except Exception:
            pass
        try:
            self.urlbox.bind('<<Modified>>', self._on_urlbox_modified)
            self.urlbox.edit_modified(False)
        except Exception:
            pass
        # Debounced geometry save
        self.bind('<Configure>', self._on_configure)
        # Save on Start/Converter buttons too (handled in handlers)

        # Save on SIGINT/SIGTERM (e.g., Ctrl+C)
        self._install_signal_handlers()

        # Done loading
        self._loading_prefs = False

    # ----- preferences (load/save) -----

    def _maybe_save_prefs(self):
        if not getattr(self, "_loading_prefs", False):
            try:
                self._save_prefs()
            except Exception:
                pass

    def _on_var_changed(self, *args):
        self._maybe_save_prefs()

    def _on_urlbox_modified(self, _evt=None):
        try:
            self.urlbox.edit_modified(False)
        except Exception:
            pass
        self._maybe_save_prefs()

    def _on_configure(self, _evt=None):
        if getattr(self, "_loading_prefs", False):
            return
        if self._geom_save_job:
            try:
                self.after_cancel(self._geom_save_job)
            except Exception:
                pass
        self._geom_save_job = self.after(1000, self._maybe_save_prefs)

    def _check_account_async(self):
        try:
            info = dfr.try_get_account_info(dfr.TOKEN_FILE, dfr.CREDENTIALS_FILE)
            self.after(0, lambda i=info: self.update_auth_ui(i))
        except Exception:
            pass

    def _install_signal_handlers(self):
        def _sig_terminate(_s, _f):
            try:
                # Schedule graceful cancel + save + exit on Tk loop
                def _do_exit():
                    try:
                        self.cancel()
                    except Exception:
                        pass
                    try:
                        setattr(dfr, "INTERRUPTED", True)
                    except Exception:
                        pass
                    try:
                        if hasattr(self, "log_handler") and self.log_handler:
                            self.log_handler.stop()
                    except Exception:
                        pass
                    try:
                        self._save_prefs()
                    except Exception:
                        pass
                    try:
                        dfr.logging.shutdown()
                    except Exception:
                        pass
                    try:
                        self.quit()
                    except Exception:
                        pass
                    try:
                        self.destroy()
                    except Exception:
                        pass
                    try:
                        os._exit(0)
                    except Exception:
                        pass
                self.after(0, _do_exit)
            except Exception:
                try:
                    os._exit(0)
                except Exception:
                    pass
        try:
            signal.signal(signal.SIGINT, _sig_terminate)
        except Exception:
            pass
        try:
            signal.signal(signal.SIGTERM, _sig_terminate)
        except Exception:
            pass

    def _load_prefs(self):
        try:
            if not GUI_PREFS_FILE.exists():
                return
            with open(GUI_PREFS_FILE, "r", encoding="utf-8") as f:
                pref = json.load(f)
        except Exception:
            return
        # Language first so labels use saved language
        lang = pref.get("lang")
        if lang in ("en", "id"):
            self.lang = lang
            # Set selector display (will be corrected by apply_i18n)
            self.lang_var.set(T(self.lang, "lang_en") if self.lang == "en" else T("id", "lang_id"))

        # URLs
        urls_text = pref.get("urls_text")
        if isinstance(urls_text, str) and urls_text.strip():
            self.urlbox.delete("1.0", "end")
            # Ensure trailing newline for consistency
            if not urls_text.endswith("\n"):
                urls_text = urls_text + "\n"
            self.urlbox.insert("1.0", urls_text)

        # Output directory
        outdir = pref.get("outdir")
        if isinstance(outdir, str):
            self.outvar.set(outdir)

        # Size selection
        size_sel = pref.get("size_selection")
        if isinstance(size_sel, str) and size_sel in self.SIZE_OPTIONS:
            self.sizevar.set(size_sel)

        # Videos checkbox
        vids = pref.get("download_videos")
        if isinstance(vids, bool):
            self.videos_var.set(vids)

        # Concurrency
        conc = pref.get("concurrency")
        try:
            if conc:
                self.concurrent_var.set(int(conc))
        except Exception:
            pass

        # Converter directory
        conv_dir = pref.get("converter_dir")
        if isinstance(conv_dir, str):
            self.conv_dir_var.set(conv_dir)

        # Window geometry
        geom = pref.get("geometry")
        if isinstance(geom, str) and geom:
            try:
                self.geometry(geom)
            except Exception:
                pass

    def _save_prefs(self):
        try:
            GUI_PREFS_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "lang": self.lang,
                "urls_text": self.urlbox.get("1.0", "end").strip(),
                "outdir": self.outvar.get().strip(),
                "size_selection": self.sizevar.get().strip(),
                "download_videos": bool(self.videos_var.get()),
                "converter_dir": self.conv_dir_var.get().strip(),
                "concurrency": int(self.concurrent_var.get()),
                "geometry": self.geometry(),
            }
            with open(GUI_PREFS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _on_close(self):
        # Attempt graceful shutdown: stop log drain, save prefs, destroy UI, and ensure process exit
        try:
            try:
                # Signal backend to stop
                setattr(dfr, "INTERRUPTED", True)
            except Exception:
                pass
            try:
                # Stop periodic log drain callbacks to avoid lingering after the window is gone
                if hasattr(self, "log_handler") and self.log_handler:
                    self.log_handler.stop()
            except Exception:
                pass
            try:
                self._save_prefs()
            except Exception:
                pass
            try:
                # Flush and close logging to avoid hangs on interpreter shutdown
                dfr.logging.shutdown()
            except Exception:
                pass
        finally:
            try:
                self.quit()
            except Exception:
                pass
            try:
                self.destroy()
            finally:
                # Last-resort hard exit in case Tk hangs
                try:
                    os._exit(0)
                except Exception:
                    pass

    # ----- i18n helpers -----

    def _on_lang_change(self, _evt=None):
        sel = self.lang_var.get()
        self.lang = "id" if "Indonesia" in sel else "en"
        self.apply_i18n()

    def apply_i18n(self):
        self.title(T(self.lang, "app_title"))
        self.hdr.configure(text=T(self.lang, "intro"))
        self.urls_label.configure(text=T(self.lang, "urls_label"))
        self.out_label.configure(text=T(self.lang, "output_label"))
        self.choose_btn.configure(text=T(self.lang, "choose"))
        self.mode_label.configure(text=T(self.lang, "mode_label"))
        self.mode_hint.configure(text=T(self.lang, "mode_hint"))
        self.videos_check.configure(text=T(self.lang, "videos_check"))
        self.start_btn.configure(text=T(self.lang, "btn_start"))
        self.log_title.configure(text=T(self.lang, "log"))
        self.images_label.configure(text=T(self.lang, "images"))
        self.videos_label.configure(text=T(self.lang, "videos"))
        # Converter labels
        self.conv_title.configure(text=T(self.lang, "conv_title"))
        self.conv_subtitle.configure(text=T(self.lang, "conv_subtitle"))
        self.conv_pick_label.configure(text=T(self.lang, "conv_pick_label"))
        self.conv_choose_btn.configure(text=T(self.lang, "conv_btn_choose"))
        self.conv_start_btn.configure(text=T(self.lang, "conv_btn_start"))
        # Update language selector label text
        self.lang_box.configure(values=[T("en", "lang_en"), T("id", "lang_id")])
        self.lang_var.set(T(self.lang, "lang_en") if self.lang == "en" else T(self.lang, "lang_id"))

    # ----- core -----

    def _parse_size_selection(self):
        sel = self.sizevar.get().strip().upper()
        if sel.startswith("ORIGINAL"):
            return True, 700
        try:
            num = int(sel.split()[0])
            return False, num
        except Exception:
            return False, 700

    def pick_out(self):
        d = filedialog.askdirectory()
        if d: self.outvar.set(d)

    def open_outdir(self):
        p = self.outvar.get().strip()
        if not p:
            return
        try:
            if sys.platform == "darwin":
                os.system(f"open '{p.replace("'", "'\\''")}'")
            elif sys.platform.startswith("win"):
                os.startfile(p)  # type: ignore[attr-defined]
            else:
                os.system(f"xdg-open '{p.replace("'", "'\\''")}'")
        except Exception:
            pass

    def pick_conv_dir(self):
        d = filedialog.askdirectory()
        if d: self.conv_dir_var.set(d)

    def start(self):
        urls = [u.strip() for u in self.urlbox.get("1.0","end").splitlines() if u.strip()]
        # Normalize & deduplicate by Drive folder ID to avoid duplicates with different query params
        id_to_url = {}
        bad_urls = []
        for u in urls:
            try:
                fid = dfr.extract_folder_id(u)
            except Exception:
                fid = ""
            if not fid:
                bad_urls.append(u)
                continue
            if fid not in id_to_url:
                id_to_url[fid] = u
        urls = list(id_to_url.values())
        if not urls:
            messagebox.showerror(T(self.lang, "missing_urls_title"), T(self.lang, "missing_urls_msg")); return
        outdir = self.outvar.get().strip()
        if not outdir:
            messagebox.showerror(T(self.lang, "missing_out_title"), T(self.lang, "missing_out_msg")); return

        img_original, width = self._parse_size_selection()
        if not img_original and not (100 <= width <= 6000):
            messagebox.showerror(T(self.lang, "invalid_size_title"), T(self.lang, "invalid_size_msg")); return

        # Save current prefs when starting
        try:
            self._save_prefs()
        except Exception:
            pass
        # Reset control flags
        try:
            setattr(dfr, "PAUSE", False)
            setattr(dfr, "INTERRUPTED", False)
        except Exception:
            pass

        # Set concurrency
        try:
            setattr(dfr, "CONCURRENCY", int(self.concurrent_var.get()))
        except Exception:
            pass

        # Kick off pre-scan with a preview dialog that opens immediately with a loader
        self.start_btn.configure(state="disabled")

        # Helper for human-readable bytes
        def _hb(n):
            units = ["B","KB","MB","GB","TB"]; f = float(max(0, int(n))); i = 0
            while f >= 1024 and i < len(units)-1:
                f /= 1024.0; i += 1
            return f"{f:.2f} {units[i]}"

        # Build preview window immediately
        sel_win = tk.Toplevel(self)
        sel_win.title("Pre-scan Preview")
        sel_win.grab_set()
        # Initial geometry: wide enough to fit all columns properly
        try:
            screen_w = sel_win.winfo_screenwidth()
        except Exception:
            screen_w = 1440
        # Calculate minimum width needed for all columns (8+34+16+12+16+12 = 98 chars * ~8px + padding)
        min_needed_w = 1100  # Conservative estimate for all columns
        max_w = max(800, screen_w - 100)  # Leave some screen margin
        init_w = min(min_needed_w, max_w)
        try:
            sel_win.geometry(f"{init_w}x520")
            sel_win.minsize(1000, 360)  # Ensure minimum width shows all columns
        except Exception:
            pass
        frm = ttk.Frame(sel_win); frm.pack(fill="both", expand=True, padx=12, pady=12)
        ttk.Label(frm, text="Select folders to include:").pack(anchor="w")

        # Loader area at bottom
        loader_frame = ttk.Frame(frm); loader_frame.pack(fill="x", side="bottom", pady=(8,0))
        loader_label = ttk.Label(loader_frame, text="Scanning…")
        loader_label.pack(side="left")
        loader_pb = ttk.Progressbar(loader_frame, mode="indeterminate", length=200)
        loader_pb.pack(side="left", padx=(8,0))
        try: loader_pb.start(10)
        except Exception: pass

        # Scrollable area for rows; initially empty until scan completes
        canvas = tk.Canvas(frm, height=280)
        sbar = ttk.Scrollbar(frm, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        sbar.pack(side="right", fill="y")

        # Header row (columns) - adjusted widths for better fit
        header = ttk.Frame(inner); header.pack(fill="x", pady=(0,4))
        ttk.Label(header, text="✓", width=6).grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="Folder", width=30).grid(row=0, column=1, sticky="w")
        ttk.Label(header, text="Images (have)", width=14).grid(row=0, column=2, sticky="w")
        ttk.Label(header, text="Img Size", width=10).grid(row=0, column=3, sticky="w")
        ttk.Label(header, text="Videos (have)", width=14).grid(row=0, column=4, sticky="w")
        ttk.Label(header, text="Vid Size", width=10).grid(row=0, column=5, sticky="w")

        rows_container = ttk.Frame(inner); rows_container.pack(fill="x")
        vars_by_root = {}

        # Buttons
        btns = ttk.Frame(frm); btns.pack(fill="x", pady=(8,0))
        def _cancel_sel():
            try:
                loader_pb.stop()
            except Exception:
                pass
            self.start_btn.configure(state="normal")
            sel_win.destroy()
        def _start_selected(tasks):
            selected_roots = {rn for rn, v in vars_by_root.items() if v.get()}
            if not selected_roots:
                messagebox.showwarning("Pre-scan", "No folders selected."); return
            selected_tasks = [t for t in tasks if t.get("__root_name") in selected_roots]
            dfr.set_direct_tasks(selected_tasks)
            # Expected bytes based on selection
            exp_bytes = 0
            for s in dfr.LINK_SUMMARIES:
                if s.get("root_name") in selected_roots:
                    exp_bytes += int(s.get("images_bytes") or 0) + int(s.get("videos_bytes") or 0)
            self.expected_bytes_total = exp_bytes
            # Start worker
            sel_win.destroy()
            self.update_progress_images(0,0); self.update_progress_videos(0,0)
            t = threading.Thread(
                target=run_worker,
                args=(urls, outdir, self.log_handler, self.start_btn, width, self.videos_var.get(), img_original, self, self.lang),
                daemon=True
            )
            t.start()
        start_sel_btn = ttk.Button(btns, text="Start", state="disabled")
        start_sel_btn.pack(side="right")
        ttk.Button(btns, text="Cancel", command=_cancel_sel).pack(side="right", padx=(0,6))

        # State for progressive updates
        completed_scans = 0
        total_urls = len(urls)
        all_tasks = []
        scan_lock = threading.Lock()
        scan_cancelled = threading.Event()
        
        def _update_progress_status(current, total, current_folder=None):
            """Update the progress status in the loader area"""
            if current_folder:
                status_text = f"Scanning {current}/{total}: {current_folder}..."
            else:
                status_text = f"Scanning folders... {current}/{total} complete"
            try:
                loader_label.configure(text=status_text)
                # Update progress bar to show completion percentage
                if total > 0:
                    progress_pct = (current / total) * 100
                    loader_pb.configure(mode="determinate", maximum=100, value=progress_pct)
            except Exception:
                pass
        
        def _add_folder_row(summary):
            """Add a single folder row to the preview (called from main thread)"""
            nonlocal vars_by_root
            try:
                rn = summary.get("root_name")
                var = tk.BooleanVar(value=True)
                vars_by_root[rn] = var
                
                row = ttk.Frame(rows_container)
                row.pack(fill="x", pady=1)
                
                ttk.Checkbutton(row, variable=var, width=6).grid(row=0, column=0, sticky="w")
                
                # Folder name with tooltip
                folder_name = rn[:28] + "..." if len(rn) > 31 else rn
                folder_label = ttk.Label(row, text=folder_name, width=30)
                folder_label.grid(row=0, column=1, sticky="w")
                
                if len(rn) > 31:
                    try:
                        def on_enter(event, full_name=rn):
                            folder_label.configure(text=full_name)
                        def on_leave(event, short_name=folder_name):
                            folder_label.configure(text=short_name)
                        folder_label.bind("<Enter>", on_enter)
                        folder_label.bind("<Leave>", on_leave)
                    except Exception:
                        pass
                
                # File counts and sizes
                ttk.Label(row, text=f"{summary.get('images')} (have {summary.get('images_existing')})", width=14).grid(row=0, column=2, sticky="w")
                img_bytes = _hb(summary.get('images_bytes') or 0)
                ttk.Label(row, text=img_bytes, width=10).grid(row=0, column=3, sticky="w")
                ttk.Label(row, text=f"{summary.get('videos')} (have {summary.get('videos_existing')})", width=14).grid(row=0, column=4, sticky="w")
                vid_bytes = _hb(summary.get('videos_bytes') or 0)
                ttk.Label(row, text=vid_bytes, width=10).grid(row=0, column=5, sticky="w")
                
                # Auto-resize window if needed
                sel_win.update_idletasks()
                
            except Exception as e:
                logging.debug(f"Error adding folder row: {e}")
        
        def _scan_single_url(url, url_index):
            """Scan a single URL and update UI progressively"""
            try:
                # Create thread-local service
                svc, _ = dfr.get_service_and_creds(dfr.TOKEN_FILE, dfr.CREDENTIALS_FILE)
                
                folder_id = dfr.extract_folder_id(url)
                name, ok = dfr.resolve_folder(svc, folder_id)
                if not ok:
                    return []
                    
                # Update status to show current folder being scanned
                self.after(0, lambda: _update_progress_status(url_index, total_urls, name))
                
                # Scan this folder
                url_label = dfr.safe_filename(url)[:160]
                base_out = os.path.join(outdir, url_label)
                dfr.ensure_dir(base_out)
                root_name = name
                folder_out = os.path.join(base_out, root_name)
                dfr.ensure_dir(folder_out)
                
                link_images = 0; link_videos = 0; link_images_existing = 0; link_videos_existing = 0
                link_images_bytes = 0; link_videos_bytes = 0
                local_tasks = []
                
                for f in dfr.list_folder_recursive(svc, folder_id, rel_path=""):
                    if scan_cancelled.is_set():
                        break
                        
                    fid = f.get("id")
                    mime = f.get("mimeType", "")
                    fext = f.get("fileExtension")
                    kind = dfr.classify_media(mime, f.get("name", ""), fext)
                    
                    if kind in ("image", "video"):
                        f["__root_name"] = root_name
                        f["__folder_out"] = folder_out
                        rel = f.get("__rel_path", "")
                        target_dir = os.path.join(folder_out, rel)
                        dfr.ensure_dir(target_dir)
                        base, ext = os.path.splitext(f.get("name", "file"))
                        
                        if kind == "image":
                            link_images += 1
                            if img_original:
                                ext_out = ext or (("." + fext) if fext else ".jpg")
                                img_target = os.path.join(target_dir, f"{base}__{fid}{ext_out}")
                            else:
                                img_target = os.path.join(target_dir, f"{base}__{fid}_w{width}.jpg")
                                
                            if os.path.exists(img_target):
                                link_images_existing += 1
                                # Also estimate size for existing files to show total folder size
                                if img_original:
                                    try:
                                        # Try to get actual file size from local file first
                                        local_size = os.path.getsize(img_target)
                                        link_images_bytes += local_size
                                    except Exception:
                                        # Fallback to Drive API or estimate
                                        try:
                                            sz = int(f.get("size") or 0)
                                            if not sz:
                                                meta = dfr.get_item(svc, fid, "size")
                                                sz = int(meta.get("size") or 0)
                                            link_images_bytes += sz
                                        except Exception:
                                            # Final fallback: estimate based on original image size
                                            link_images_bytes += 2 * 1024 * 1024  # 2MB estimate
                                else:
                                    # For thumbnails, check local file size or estimate
                                    try:
                                        local_size = os.path.getsize(img_target)
                                        link_images_bytes += local_size
                                    except Exception:
                                        link_images_bytes += 100 * 1024  # 100KB estimate
                            else:
                                local_tasks.append(f)
                                if img_original:
                                    try:
                                        sz = int(f.get("size") or 0)
                                        if not sz:
                                            meta = dfr.get_item(svc, fid, "size")
                                            sz = int(meta.get("size") or 0)
                                        link_images_bytes += sz
                                    except Exception:
                                        link_images_bytes += 2 * 1024 * 1024  # 2MB estimate
                                else:
                                    # Estimate thumbnail size
                                    link_images_bytes += 100 * 1024  # 100KB estimate
                        else:  # video
                            link_videos += 1
                            ext_out = ext or ".mp4"
                            vid_target = os.path.join(target_dir, f"{base}__{fid}{ext_out}")
                            
                            if os.path.exists(vid_target):
                                link_videos_existing += 1
                                # Include size for existing videos
                                try:
                                    local_size = os.path.getsize(vid_target)
                                    link_videos_bytes += local_size
                                except Exception:
                                    # Fallback to Drive API or estimate
                                    try:
                                        sz = int(f.get("size") or 0)
                                        if not sz:
                                            meta = dfr.get_item(svc, fid, "size")
                                            sz = int(meta.get("size") or 0)
                                        link_videos_bytes += sz
                                    except Exception:
                                        # Estimate video size (much larger than images)
                                        link_videos_bytes += 50 * 1024 * 1024  # 50MB estimate
                            else:
                                if self.videos_var.get():
                                    local_tasks.append(f)
                                    try:
                                        sz = int(f.get("size") or 0)
                                        if not sz:
                                            meta = dfr.get_item(svc, fid, "size")
                                            sz = int(meta.get("size") or 0)
                                        link_videos_bytes += sz
                                    except Exception:
                                        link_videos_bytes += 50 * 1024 * 1024  # 50MB estimate
                
                # Create summary for this folder
                summary = {
                    "root_name": root_name,
                    "images": link_images,
                    "images_existing": link_images_existing,
                    "images_bytes": link_images_bytes,
                    "videos": link_videos,
                    "videos_existing": link_videos_existing,
                    "videos_bytes": link_videos_bytes,
                    "url": url,
                }
                
                # Thread-safe updates
                with scan_lock:
                    dfr.LINK_SUMMARIES.append(summary)
                    all_tasks.extend(local_tasks)
                
                # Update UI on main thread
                self.after(0, lambda s=summary: _add_folder_row(s))
                
                return local_tasks
                
            except Exception as e:
                logging.error(f"Scan error for URL {url}: {e}")
                return []
        
        def _prescan_parallel():
            """Run parallel pre-scan with progressive updates"""
            nonlocal completed_scans
            gh = None
            
            try:
                # Set up logging
                setattr(dfr, "LANG", self.lang)
                try:
                    root_logger = dfr.logging.getLogger()
                    if not root_logger.handlers:
                        dfr.setup_logging()
                except Exception:
                    pass
                    
                # Bridge backend logging into Tk log view
                logh = self.log_handler
                class _GuiHandler(dfr.logging.Handler):
                    def emit(self, record):
                        try:
                            msg = self.format(record)
                            logh.put(msg)
                        except Exception:
                            pass
                            
                fmt = dfr.logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%Y-%m-%d %H:%M:%S")
                gh = _GuiHandler()
                gh.setLevel(getattr(dfr.logging, dfr.LOG_LEVEL.upper(), dfr.logging.INFO))
                gh.setFormatter(fmt)
                dfr.logging.getLogger().addHandler(gh)
                
                dfr.reset_counters()
                # Configure backend globals
                setattr(dfr, "FOLDER_URLS", urls)
                setattr(dfr, "OUTPUT_DIR", str(outdir))
                setattr(dfr, "IMAGE_WIDTH", int(width))
                setattr(dfr, "DOWNLOAD_VIDEOS", bool(self.videos_var.get()))
                setattr(dfr, "DOWNLOAD_IMAGES_ORIGINAL", bool(img_original))
                
                # Ensure credentials
                cred_path = locate_credentials()
                if cred_path is None:
                    raise RuntimeError("credentials.json not found — click Sign in or place credentials.json next to the app.")
                setattr(dfr, "CREDENTIALS_FILE", str(cred_path))
                
                # Run scans in parallel (limit to 3 concurrent to avoid rate limits)
                max_workers = min(3, len(urls))
                completed_scans = 0
                
                self.after(0, lambda: _update_progress_status(0, total_urls))
                
                with dfr.ThreadPoolExecutor(max_workers=max_workers) as executor:
                    # Submit all scan jobs
                    future_to_url = {}
                    for i, url in enumerate(urls):
                        if scan_cancelled.is_set():
                            break
                        future = executor.submit(_scan_single_url, url, i + 1)
                        future_to_url[future] = url
                    
                    # Process completed scans as they finish
                    for future in dfr.as_completed(future_to_url):
                        if scan_cancelled.is_set():
                            break
                            
                        try:
                            tasks = future.result()
                            completed_scans += 1
                            
                            # Update progress
                            self.after(0, lambda: _update_progress_status(completed_scans, total_urls))
                            
                        except Exception as e:
                            url = future_to_url[future]
                            logging.error(f"Scan failed for {url}: {e}")
                            completed_scans += 1
                            self.after(0, lambda: _update_progress_status(completed_scans, total_urls))
                
                # Finalize scan
                def _finalize():
                    try:
                        loader_pb.stop()
                        loader_pb.pack_forget()
                    except Exception:
                        pass
                    
                    if dfr.LINK_SUMMARIES:
                        loader_label.configure(text="Scan complete. Select folders and click Start.")
                        start_sel_btn.configure(state="normal", command=lambda: _start_selected(all_tasks))
                    else:
                        loader_label.configure(text="Scan complete. No selectable items found.")
                        start_sel_btn.configure(state="disabled")
                
                self.after(0, _finalize)
                
            except Exception as e:
                # Handle scan failure
                dfr.logging.getLogger().error(f"Pre-scan failed: {e}", exc_info=True)
                def _err():
                    try:
                        loader_pb.stop()
                        loader_pb.pack_forget()
                    except Exception:
                        pass
                    loader_label.configure(text=f"Pre-scan failed: {e}")
                    start_sel_btn.configure(state="disabled")
                    self.start_btn.configure(state="normal")
                self.after(0, _err)
            finally:
                # Cleanup logging
                try:
                    if gh is not None:
                        dfr.logging.getLogger().removeHandler(gh)
                except Exception:
                    pass
        
        # Update cancel function to stop parallel scans
        def _cancel_sel_new():
            scan_cancelled.set()
            try:
                loader_pb.stop()
            except Exception:
                pass
            self.start_btn.configure(state="normal")
            sel_win.destroy()
        
        # Replace the cancel command
        btns.winfo_children()[-1].configure(command=_cancel_sel_new)
        
        # Start parallel pre-scan
        threading.Thread(target=_prescan_parallel, daemon=True).start()

    def start_converter(self):
        local_dir = self.conv_dir_var.get().strip()
        if not local_dir:
            messagebox.showerror(T(self.lang, "missing_conv_dir_title"), T(self.lang, "missing_conv_dir_msg")); return
        self.update_progress_images(0,0)  # Converter mainly affects images
        t = threading.Thread(
            target=run_converter,
            args=(local_dir, self.log_handler, self.conv_start_btn, self, self.lang),
            daemon=True
        )
        t.start()

    def update_progress_images(self, done, total):
        total = max(total, 0)
        done = min(max(done,0), total) if total else 0
        self.progress_images["maximum"] = total if total else 1
        self.progress_images["value"] = done
        self.progress_images_value.configure(text=f"{done}/{total} ({T(self.lang, 'progress_left')} {max(total-done,0)})")
        self.update_idletasks()

    def update_progress_videos(self, done, total):
        total = max(total, 0)
        done = min(max(done,0), total) if total else 0
        self.progress_videos["maximum"] = total if total else 1
        self.progress_videos["value"] = done
        self.progress_videos_value.configure(text=f"{done}/{total} ({T(self.lang, 'progress_left')} {max(total-done,0)})")
        self.update_idletasks()

    def update_progress_bytes(self, bytes_written):
        self.bytes_written = max(0, int(bytes_written))
        total = max(1, int(self.expected_bytes_total) or 1)
        val = min(self.bytes_written, total)
        self.progress_bytes["maximum"] = total
        self.progress_bytes["value"] = val
        # Format human-readable
        def _hb(n):
            units = ["B","KB","MB","GB","TB"]; f = float(n); i = 0
            while f >= 1024 and i < len(units)-1:
                f /= 1024.0; i += 1
            return f"{f:.2f} {units[i]}"
        self.progress_bytes_value.configure(text=f"{_hb(val)} / {_hb(total)}")
        self.update_idletasks()

    # ----- control actions -----

    def cancel(self):
        try:
            setattr(dfr, "INTERRUPTED", True)
        except Exception:
            pass


    def sign_out(self):
        try:
            tok = Path(dfr.TOKEN_FILE)
            if tok.exists():
                bak = tok.with_suffix(tok.suffix + ".bak")
                try:
                    if bak.exists(): bak.unlink()
                except Exception:
                    pass
                tok.replace(bak)
                messagebox.showinfo("Sign out", f"Signed out. Backup token at: {bak}")
            else:
                messagebox.showinfo("Sign out", "No token found. You are not signed in.")
        except Exception as e:
            messagebox.showerror("Sign out", f"Failed to sign out: {e}")
        # Immediately reflect unsigned state in UI
        self.update_auth_ui({})

    def sign_in(self):
        def _do_sign_in():
            try:
                # Ensure credentials path is honored; this will launch OAuth if needed
                svc, _creds = dfr.get_service_and_creds(dfr.TOKEN_FILE, dfr.CREDENTIALS_FILE)
                info = dfr.get_account_info(svc)
                self.after(0, lambda i=info: self.update_auth_ui(i))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Sign in", f"Failed to sign in: {e}"))
        try:
            threading.Thread(target=_do_sign_in, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Sign in", f"Failed to start sign in: {e}")

    def set_account(self, name: str, email: str):
        disp = name or email or "(unknown)"
        self.acct_var.set(f"Account: {disp}")

    def update_auth_ui(self, info: dict | None = None):
        try:
            if info is None:
                info = dfr.try_get_account_info(dfr.TOKEN_FILE, dfr.CREDENTIALS_FILE)
        except Exception:
            info = {}
        name = (info.get("name") or "").strip() if isinstance(info, dict) else ""
        email = (info.get("email") or "").strip() if isinstance(info, dict) else ""
        if name or email:
            self.set_account(name, email)
            # Show Sign out action
            self.auth_btn.configure(text="Sign out", command=self.sign_out)
        else:
            self.acct_var.set("Account: (not signed in)")
            # Show Sign in action
            self.auth_btn.configure(text="Sign in", command=self.sign_in)


if __name__ == "__main__":
    try:
        App().mainloop()
    except KeyboardInterrupt:
        try:
            # Best-effort graceful exit
            # We don’t have direct app ref here, but ensure process exits
            os._exit(0)
        except Exception:
            pass
