#!/usr/bin/env python3
# drive_fetch_gui.py — Simple Tkinter GUI (bilingual EN/ID)
# v0.13 — 2025-09-29 (language switcher + i18n, sizes up to 6000)

import os
import threading, queue, traceback, sys, re
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

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
        "mode_hint": "ORIGINAL = full-size download; numbers = local thumbnails.",
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
    def __init__(self, widget: scrolledtext.ScrolledText):
        self.widget = widget
        self.queue = queue.Queue()
        self.widget.after(100, self._drain)
    def put(self, line: str):
        if not line.endswith("\n"):
            line += "\n"
        self.queue.put(line)
    def _drain(self):
        try:
            while True:
                line = self.queue.get_nowait()
                self.widget.configure(state="normal")
                self.widget.insert("end", line)
                self.widget.configure(state="disabled")
                self.widget.see("end")
        except queue.Empty:
            pass
        self.widget.after(100, self._drain)


# ----------------- Worker -----------------

def run_worker(urls, outdir, log: TkLogHandler, btn: ttk.Button,
               preview_width: int, download_videos: bool, img_original: bool, app_ref, lang: str):
    btn.configure(state="disabled")
    try:
        out_root = Path(outdir); out_root.mkdir(parents=True, exist_ok=True)

        if img_original:
            log.put(T(lang, "log_img_mode_original"))
        else:
            log.put(T(lang, "log_img_mode_thumb", w=preview_width))
        log.put(T(lang, "log_vids", state=T(lang, "log_vids_on" if download_videos else "log_vids_off")))
        log.put(T(lang, "log_processing", n=len(urls)))

        cred_path = locate_credentials()
        if cred_path:
            dfr.CREDENTIALS_FILE = str(cred_path)
            log.put(T(lang, "log_creds_found", path=cred_path))
        else:
            log.put(T(lang, "log_creds_missing"))

        # Pass options to backend
        dfr.FOLDER_URLS = urls
        dfr.OUTPUT_DIR = str(out_root)
        dfr.IMAGE_WIDTH = int(preview_width)
        dfr.DOWNLOAD_VIDEOS = bool(download_videos)
        setattr(dfr, "DOWNLOAD_IMAGES_ORIGINAL", bool(img_original))

        # Stream backend logs into GUI
        class _GuiHandler(dfr.logging.Handler):
            def emit(self, record):
                try:
                    msg = self.format(record)
                    log.put(msg)
                    if "[Progress]" in msg:
                        mi = re.search(r"(\d+)/(\d+)", msg)
                        if mi:
                            # We don't know which it is; update both if present
                            app_ref.update_progress_images(int(mi.group(1)), int(mi.group(2)))
                            app_ref.update_progress_videos(int(mi.group(1)), int(mi.group(2)))
                except Exception:
                    pass

        root_logger = dfr.logging.getLogger()
        for h in list(root_logger.handlers):
            root_logger.removeHandler(h)
        dfr.setup_logging()
        fmt = dfr.logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%Y-%m-%d %H:%M:%S")
        gh = _GuiHandler(); gh.setLevel(getattr(dfr.logging, dfr.LOG_LEVEL.upper(), dfr.logging.INFO)); gh.setFormatter(fmt)
        dfr.logging.getLogger().addHandler(gh)

        dfr.main()
        log.put("\n" + T(lang, "done"))
    except Exception:
        log.put("\n" + T(lang, "fatal") + "\n" + traceback.format_exc())
    finally:
        btn.configure(state="normal")


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
        self.lang = "en"  # default language
        self.title(T(self.lang, "app_title"))
        self.geometry("980x860"); self.minsize(820, 660)

        # Language switcher
        topbar = ttk.Frame(self); topbar.pack(fill="x", padx=12, pady=(10, 0))
        ttk.Label(topbar, text=T(self.lang, "language")).pack(side="left")
        self.lang_var = tk.StringVar(value=T(self.lang, "lang_en"))
        self.lang_box = ttk.Combobox(
            topbar, textvariable=self.lang_var,
            values=[T("en", "lang_en"), T("id", "lang_id")], width=22, state="readonly"
        )
        self.lang_box.pack(side="left", padx=(8, 0))
        self.lang_box.bind("<<ComboboxSelected>>", self._on_lang_change)

        # Intro / instructions
        self.hdr = ttk.Label(self, wraplength=940, justify="left")
        self.hdr.pack(anchor="w", padx=12, pady=(12, 6))

        self.urls_label = ttk.Label(self)
        self.urls_label.pack(anchor="w", padx=12)
        self.urlbox = scrolledtext.ScrolledText(self, height=7)
        self.urlbox.insert("1.0", "\n".join(DEFAULT_URLS) + "\n")
        self.urlbox.pack(fill="x", padx=12)

        row = ttk.Frame(self); row.pack(fill="x", padx=12)
        self.out_label = ttk.Label(row)
        self.out_label.pack(side="left")
        self.outvar = tk.StringVar(); self.out_entry = ttk.Entry(row, textvariable=self.outvar)
        self.out_entry.pack(side="left", fill="x", expand=True, padx=8)
        self.choose_btn = ttk.Button(row, command=self.pick_out)
        self.choose_btn.pack(side="left")

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

        btnrow = ttk.Frame(self); btnrow.pack(fill="x", padx=12, pady=(0,8))
        self.start_btn = ttk.Button(btnrow, command=self.start); self.start_btn.pack(side="right")

        self.log_title = ttk.Label(self)
        self.log_title.pack(anchor="w", padx=12)
        self.logs = scrolledtext.ScrolledText(self, height=18, state="disabled"); self.logs.pack(fill="both", expand=True, padx=12, pady=(0,10))
        self.log_handler = TkLogHandler(self.logs)

        prow = ttk.Frame(self); prow.pack(fill="x", padx=12, pady=(0,12))
        img_frame = ttk.Frame(prow); img_frame.pack(fill="x", pady=(0,6))
        self.images_label = ttk.Label(img_frame)
        self.images_label.pack(side="left")
        self.progress_images = ttk.Progressbar(img_frame, length=520, mode="determinate")
        self.progress_images.pack(side="left", padx=(8,8))
        self.progress_images_value = ttk.Label(img_frame, text="0/0"); self.progress_images_value.pack(side="left")

        vid_frame = ttk.Frame(prow); vid_frame.pack(fill="x")
        self.videos_label = ttk.Label(vid_frame)
        self.videos_label.pack(side="left")
        self.progress_videos = ttk.Progressbar(vid_frame, length=520, mode="determinate")
        self.progress_videos.pack(side="left", padx=(8,8))
        self.progress_videos_value = ttk.Label(vid_frame, text="0/0"); self.progress_videos_value.pack(side="left")

        # Apply initial language
        self.apply_i18n()

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

    def start(self):
        urls = [u.strip() for u in self.urlbox.get("1.0","end").splitlines() if u.strip()]
        if not urls:
            messagebox.showerror(T(self.lang, "missing_urls_title"), T(self.lang, "missing_urls_msg")); return
        outdir = self.outvar.get().strip()
        if not outdir:
            messagebox.showerror(T(self.lang, "missing_out_title"), T(self.lang, "missing_out_msg")); return

        img_original, width = self._parse_size_selection()
        if not img_original and not (100 <= width <= 6000):
            messagebox.showerror(T(self.lang, "invalid_size_title"), T(self.lang, "invalid_size_msg")); return

        self.update_progress_images(0,0); self.update_progress_videos(0,0)
        t = threading.Thread(
            target=run_worker,
            args=(urls, outdir, self.log_handler, self.start_btn, width, self.videos_var.get(), img_original, self, self.lang),
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


if __name__ == "__main__":
    App().mainloop()