#!/usr/bin/env python3
# drive_fetch_resilient.py v1.10 — 2025-10-01
# - Fix: accurate per-link file counts (handles Drive shortcuts without extra API calls)
# - Adds per-link file count logs during pre-scan
# - Log language switches via global LANG ("en" or "id")
# - Keeps "thumbnail-folder → originals" mode via CONVERT_THUMBS_DIR
# - Works with GUI by toggling globals before calling main()

import os, re, io, sys, time, signal, requests, logging, platform
from urllib.parse import urlparse, parse_qs
from typing import Iterator, Dict, Optional, List
from dataclasses import dataclass, field
from pathlib import Path
from logging.handlers import RotatingFileHandler
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.auth.transport.requests import AuthorizedSession
from googleapiclient.errors import HttpError

APP_NAME = "OntahoodDownloader"

def _default_support_dir() -> Path:
    if platform.system() == "Darwin":  # macOS
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if platform.system() == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / APP_NAME
    # Linux and others
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP_NAME

SUPPORT_DIR = _default_support_dir()
SUPPORT_DIR.mkdir(parents=True, exist_ok=True)

# -------------------- Runtime options --------------------
CREDENTIALS_FILE = os.environ.get("CREDENTIALS_FILE", "credentials.json")
TOKEN_FILE       = os.environ.get("TOKEN_FILE", str(SUPPORT_DIR / "token.json"))
OUTPUT_DIR       = os.environ.get("OUTPUT_DIR", "./output")

IMAGE_WIDTH              = 400
OVERWRITE                = False
ROBUST_RESUME            = True
DOWNLOAD_VIDEOS          = True
DOWNLOAD_IMAGES_ORIGINAL = False
CONVERT_THUMBS_DIR       = ""   # if set to a local folder path, convert matching thumbnails to originals
# Flow control (GUI can toggle these)
PAUSE = False  # when True, long-running loops will pause safely until resumed

LOG_LEVEL        = "INFO"
LOG_FILENAME     = "drive_fetch.log"
LOG_MAX_BYTES    = 10 * 1024 * 1024
LOG_BACKUPS      = 3
FOLDER_URLS: List[str] = []

# Link summaries and retry support
LINK_SUMMARIES: List[Dict] = []
FAILED_ITEMS: List[Dict] = []
DIRECT_TASKS: Optional[List[Dict]] = None

# Concurrency
CONCURRENCY = int(os.environ.get("CONCURRENCY", "3"))

# Thread-safety for shared counters/collections
_LOCK = threading.Lock()

# Language for logs ("en" or "id"); the GUI should set this before calling main()
LANG = "en"

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# -------------------- i18n helpers --------------------

def L(en: str, id_: str) -> str:
    """Return English or Indonesian string based on LANG."""
    return en if (LANG or "en").lower().startswith("en") else id_

# -------------------- Accounting --------------------

@dataclass
class Counters:
    scanned: int = 0
    images_done: int = 0
    images_skipped: int = 0
    images_failed: int = 0
    videos_done: int = 0
    videos_skipped: int = 0
    videos_failed: int = 0
    data_done: int = 0
    data_skipped: int = 0
    data_failed: int = 0
    bytes_written: int = 0

@dataclass
class Totals:
    grand: Counters = field(default_factory=Counters)
    per_folder: Dict[str, Counters] = field(default_factory=dict)
    def folder(self, key: str) -> Counters:
        if key not in self.per_folder:
            self.per_folder[key] = Counters()
        return self.per_folder[key]

TOTALS = Totals()
START_TS = time.time()
INTERRUPTED = False
EXPECTED_IMAGES = 0
EXPECTED_VIDEOS = 0
EXPECTED_DATA = 0
ALREADY_HAVE_IMAGES = 0
ALREADY_HAVE_VIDEOS = 0
ALREADY_HAVE_DATA = 0
EXPECTED_TOTAL_BYTES = 0

# -------------------- Logging --------------------

def reset_counters():
    global TOTALS, EXPECTED_IMAGES, EXPECTED_VIDEOS, EXPECTED_DATA, ALREADY_HAVE_IMAGES, ALREADY_HAVE_VIDEOS, ALREADY_HAVE_DATA, START_TS, INTERRUPTED, LINK_SUMMARIES, FAILED_ITEMS
    TOTALS = Totals()
    EXPECTED_IMAGES = 0
    EXPECTED_VIDEOS = 0
    EXPECTED_DATA = 0
    ALREADY_HAVE_IMAGES = 0
    ALREADY_HAVE_VIDEOS = 0
    ALREADY_HAVE_DATA = 0
    global EXPECTED_TOTAL_BYTES
    EXPECTED_TOTAL_BYTES = 0
    START_TS = time.time()
    INTERRUPTED = False
    LINK_SUMMARIES = []
    FAILED_ITEMS = []

class ColorFormatter(logging.Formatter):
    """ANSI color formatter that matches the GUI style:
    - Color only timestamp and level.
    - Emphasize bracket tags and counters in the message body.
    """
    RESET = "\033[0m"
    GREY = "\033[90m"  # timestamp
    LEVEL_COLORS = {
        logging.DEBUG: "\033[96m",   # bright cyan
        logging.INFO: "\033[92m",    # bright green
        logging.WARNING: "\033[93m", # bright yellow
        logging.ERROR: "\033[91m",   # bright red
        logging.CRITICAL: "\033[97m\033[101m",  # white on bright red background
    }
    BOLD_ON = "\033[1m"
    BOLD_OFF = "\033[22m"

    def format(self, record):
        base = super().format(record)
        try:
            import re
            # Expect format: "YYYY-MM-DD HH:MM:SS | LEVEL   | message"
            m = re.match(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| ([A-Z]+)\s+\| (.*)$", base, re.DOTALL)
            def emph(body: str) -> str:
                # Emphasize [Tags], selective counters, key=123 pairs
                # Avoid variable-width lookbehinds for compatibility; match full context instead.
                pattern = r"(\[[^\]]+\])|(\b(?:images|videos|gambar|video)\s\d+/\d+\b)|(\b(?:left|sisa)\s\d+\b)|(\b[A-Za-z_]+=\d+\b)"
                return re.sub(pattern, lambda mt: f"{self.BOLD_ON}{mt.group(0)}{self.BOLD_OFF}", body)
            if not m:
                # No parsed ts/level; still emphasize
                return emph(base) + self.RESET
            ts, level, msg = m.groups()
            lvl_color = self.LEVEL_COLORS.get(record.levelno, "")
            msg2 = emph(msg)
            return f"{self.GREY}{ts}{self.RESET} | {lvl_color}{level}{self.RESET} | {msg2}{self.RESET}"
        except Exception:
            return base

def setup_logging():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    log_path = os.path.join(OUTPUT_DIR, LOG_FILENAME)
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    fmt = "%(asctime)s | %(levelname)-7s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    root = logging.getLogger(); root.setLevel(level)
    # Idempotent: if handlers already exist, keep level consistent and do not add duplicates
    if root.handlers:
        root.setLevel(level)
        return
    # console
    ch = logging.StreamHandler(sys.stdout); ch.setLevel(level); ch.setFormatter(ColorFormatter(fmt, datefmt)); root.addHandler(ch)
    # file
    fh = RotatingFileHandler(log_path, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUPS, encoding="utf-8")
    fh.setLevel(level); fh.setFormatter(logging.Formatter(fmt, datefmt)); root.addHandler(fh)

def human_bytes(n: int) -> str:
    units = ["B","KB","MB","GB","TB","PB"]; f = float(n); i = 0
    while f >= 1024 and i < len(units)-1:
        f /= 1024.0; i += 1
    return f"{f:.2f} {units[i]}"

def elapsed() -> str:
    d = time.time() - START_TS; h = int(d//3600); m = int((d%3600)//60); s = int(d%60)
    return f"{h}h {m}m {s}s" if h else (f"{m}m {s}s" if m else f"{s}s")

def on_sigint(_sig, _frame):
    global INTERRUPTED; INTERRUPTED = True
    logging.warning(L(
        "Received interrupt signal — finishing current step and summarizing...",
        "Menerima sinyal interupsi — menyelesaikan langkah saat ini lalu meringkas..."
    ))

signal.signal(signal.SIGINT, on_sigint)

# -------------------- Auth / Service --------------------

def _resolve_credentials_path(p: str) -> str:
    pth = Path(p)
    if pth.is_file():
        return str(pth)
    # Try support dir
    pth2 = SUPPORT_DIR / Path(p).name
    if pth2.is_file():
        return str(pth2)
    # Try alongside executable / script
    try:
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    except Exception:
        base = Path(__file__).resolve().parent
    pth3 = base / Path(p).name
    if pth3.is_file():
        return str(pth3)
    raise FileNotFoundError(
        f"Could not find {p!r}. Looked in: {Path(p).resolve()}, {pth2}, {pth3}"
    )

def get_service_and_creds(token_path: str, credentials_path: str):
    from google.auth.transport.requests import Request
    token_path = str(Path(token_path))  # ensure string path
    creds = None

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        try:
            if creds and creds.expired and creds.refresh_token:
                logging.info(L("Refreshing stored credentials...", "Menyegarkan kredensial tersimpan..."))
                creds.refresh(Request())
            else:
                raise Exception("Need fresh auth")
        except Exception:
            logging.info(L("Launching browser for Google OAuth...", "Membuka browser untuk OAuth Google..."))
            cred_path_resolved = _resolve_credentials_path(credentials_path)
            flow = InstalledAppFlow.from_client_secrets_file(cred_path_resolved, SCOPES)
            creds = flow.run_local_server(port=0)

        Path(token_path).parent.mkdir(parents=True, exist_ok=True)
        with open(token_path, "w") as f:
            f.write(creds.to_json())
            logging.info(L(f"Wrote token file: {token_path}", f"Menulis token file: {token_path}"))

    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    return service, creds

def get_service_if_token_valid(token_path: str, credentials_path: str):
    """Return (service, creds) if token exists and can be used/refreshed WITHOUT launching OAuth.
    Otherwise return (None, None).
    """
    try:
        from google.auth.transport.requests import Request
        token_path = str(Path(token_path))
        creds = None
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        if not creds:
            return None, None
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    return None, None
            else:
                return None, None
        service = build("drive", "v3", credentials=creds, cache_discovery=False)
        return service, creds
    except Exception:
        return None, None

def try_get_account_info(token_path: str, credentials_path: str) -> Dict:
    svc, _ = get_service_if_token_valid(token_path, credentials_path)
    if svc is None:
        return {}
    return get_account_info(svc)

def get_account_info(service) -> Dict:
    try:
        about = service.about().get(fields="user(emailAddress,displayName)").execute()
        u = about.get("user") or {}
        return {"email": u.get("emailAddress"), "name": u.get("displayName")}
    except Exception:
        return {}

# -------------------- Helpers --------------------

def extract_folder_id(url: str) -> str:
    m = re.search(r"/folders/([a-zA-Z0-9_-]+)", url)
    if m: return m.group(1)
    qs = parse_qs(urlparse(url).query)
    return (qs.get("id", [""])[0]).strip()

def safe_filename(name: str) -> str:
    src = "" if name is None else str(name)
    for ch in '/\\:*?"<>|': src = src.replace(ch, "_")
    return src.strip().rstrip(".") or "untitled"

def ensure_dir(path: str): os.makedirs(path, exist_ok=True)

def backoff_sleep(attempt: int):
    base = min(30, (2 ** (attempt - 1)) + 0.1 * attempt)
    import random as _r, time as _t
    jitter = base * (0.75 + 0.5 * _r.random())
    logging.debug(L(
        f"Backing off {jitter:.1f}s, attempt {attempt}",
        f"Jeda {jitter:.1f} dtk (percobaan {attempt})"
    ))
    _t.sleep(jitter)

_IMAGE_EXTS = {"jpg","jpeg","png","gif","webp","tif","tiff","bmp","heic","heif","cr2","cr3","arw","nef","dng","raf","rw2"}
_VIDEO_EXTS = {"mp4","mov","m4v","mkv","avi","webm","mts","m2ts","3gp","mod","tod"}

def _ext_from(name: str, file_ext: Optional[str]) -> str:
    if file_ext: return file_ext.lower()
    _, ext = os.path.splitext(name or ""); return ext.lstrip(".").lower()

def classify_media(mime: str, name: str, file_ext: Optional[str]) -> Optional[str]:
    ext = _ext_from(name, file_ext)
    if (mime or "").startswith("image/") or ext in _IMAGE_EXTS: return "image"
    if (mime or "").startswith("video/") or ext in _VIDEO_EXTS: return "video"
    # Classify as "data" for documents and other files (PDFs, docs, spreadsheets, etc.)
    # This gives users visibility into non-media file downloads
    mime_lower = (mime or "").lower()
    if (mime_lower.startswith("application/") or 
        mime_lower.startswith("text/") or 
        ext in {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "csv", "zip", "rar", "7z"}):
        return "data"
    return None

def gapi_execute_with_retry(req, retries: int = 8):
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            return req.execute()
        except HttpError as e:
            code = getattr(getattr(e, "resp", None), "status", None)
            if code in (429, 500, 502, 503, 504):
                last_exc = e; backoff_sleep(attempt); continue
            raise
        except Exception as e:
            last_exc = e; backoff_sleep(attempt)
    raise RuntimeError(f"Google API request failed after retries: {last_exc}")

def get_item(service, file_id: str, fields: str) -> Dict:
    req = service.files().get(fileId=file_id, fields=fields, supportsAllDrives=True)
    return gapi_execute_with_retry(req)

# -------------------- Listing --------------------

def resolve_folder(service, folder_id: str):
    if not folder_id:
        logging.error(L("Folder URL had no ID.", "URL folder tidak memiliki ID.")); return None, False
    try:
        req = service.files().get(fileId=folder_id, fields="id,name,mimeType", supportsAllDrives=True)
        meta = gapi_execute_with_retry(req)
        if meta.get("mimeType") != "application/vnd.google-apps.folder":
            logging.error(L(f"Not a folder: {meta.get('name')} ({meta.get('mimeType')})",
                            f"Bukan folder: {meta.get('name')} ({meta.get('mimeType')})")); return None, False
        return safe_filename(meta.get("name", folder_id)), True
    except HttpError as e:
        content = (getattr(e, "content", b"") or b"").decode("utf-8", "ignore")
        if e.resp.status == 404:
            logging.error(L(f"Not found/no access: {folder_id}",
                            f"Folder tidak ditemukan/akses ditolak: {folder_id}"))
        elif e.resp.status == 403:
            logging.error(L(f"Access denied for folder: {folder_id}",
                            f"Akses ditolak untuk folder: {folder_id}"))
        else:
            logging.error(L(f"Failed to resolve folder {folder_id}: {e} {content}",
                            f"Gagal resolve folder {folder_id}: {e} {content}"))
        return None, False

def wait_if_paused():
    """Block while PAUSE is True, unless interrupted."""
    import time as _t
    while PAUSE and not INTERRUPTED:
        _t.sleep(0.2)


def list_folder_recursive(service, folder_id: str, rel_path: str = "", external_cancel_check=None) -> Iterator[Dict]:
    """
    Yield file dicts for all media items under folder_id, descending into subfolders.
    Shortcut files are normalized to look like real files using shortcutDetails so that
    counting and downloading work without extra API calls.
    
    external_cancel_check: Optional callable that returns True if operation should be cancelled
    """
    fields = (
            "nextPageToken, "
            "files(id, name, mimeType, fileExtension, size, "
            "      shortcutDetails(targetId, targetMimeType))"
        )
    query = f"'{folder_id}' in parents and trashed = false"
    page_token = None

    while True:
        if INTERRUPTED or (external_cancel_check and external_cancel_check()):
            return
        wait_if_paused()
        req = service.files().list(
            q=query,
            fields=fields,
            pageToken=page_token,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            corpora="allDrives",
            pageSize=1000,
            orderBy="name_natural"
        )
        resp = gapi_execute_with_retry(req)

        wait_if_paused()
        for item in resp.get("files", []):
            if INTERRUPTED or (external_cancel_check and external_cancel_check()):
                return
            wait_if_paused()
            mime = item.get("mimeType", "")
            if mime == "application/vnd.google-apps.folder":
                sub_name = safe_filename(item.get("name", ""))
                sub_rel  = os.path.join(rel_path, sub_name) if rel_path else sub_name
                logging.debug(L(f"Descending into subfolder: {sub_name} -> {sub_rel}",
                                f"Masuk subfolder: {sub_name} -> {sub_rel}"))
                yield from list_folder_recursive(service, item.get("id"), sub_rel, external_cancel_check)

            elif mime == "application/vnd.google-apps.shortcut":
                sd = item.get("shortcutDetails") or {}
                target_id   = sd.get("targetId")
                target_mime = sd.get("targetMimeType")

                # If the shortcut points at a folder, recurse into that folder.
                if target_mime == "application/vnd.google-apps.folder" and target_id:
                    sub_name = safe_filename(item.get("name", "shortcut"))
                    sub_rel  = os.path.join(rel_path, sub_name) if rel_path else sub_name
                    logging.debug(L(f"Following folder shortcut: {sub_name} -> {target_id}",
                                    f"Mengikuti shortcut folder: {sub_name} -> {target_id}"))
                    yield from list_folder_recursive(service, target_id, sub_rel, external_cancel_check)
                else:
                    # Normalize file-shortcuts into "real file" dicts so counting/downloading just works.
                    norm = {
                        "id":            target_id or item.get("id"),
                        "name":          item.get("name", "shortcut"),
                        "mimeType":      target_mime or mime,
                        "fileExtension": item.get("fileExtension"),
                        "size":          item.get("size"),  # Copy size from original item
                        "__rel_path":    rel_path,
                        "__from_shortcut": True,
                    }
                    yield norm

            else:
                item["__rel_path"] = rel_path
                yield item

        page_token = resp.get("nextPageToken")
        if not page_token:
            break

# -------------------- Downloads --------------------

# Track targets that are currently being written so we can clean up on cancel/exit
INCOMPLETE_TARGETS = set()

def _mark_incomplete(target: str):
    with _LOCK:
        INCOMPLETE_TARGETS.add(target)

def _mark_complete(target: str):
    with _LOCK:
        INCOMPLETE_TARGETS.discard(target)

def cleanup_incomplete_targets():
    removed = 0
    with _LOCK:
        targets = list(INCOMPLETE_TARGETS)
        INCOMPLETE_TARGETS.clear()
    for t in targets:
        try:
            if os.path.exists(t):
                os.remove(t)
                removed += 1
        except Exception:
            pass
    if removed:
        logging.warning(L(f"Removed {removed} incomplete file(s) on exit/cancel.",
                          f"Menghapus {removed} berkas yang belum selesai saat keluar/batal."))

def download_thumbnail(url: str, out_path: str, retries=10) -> bool:
    _mark_incomplete(out_path)
    for attempt in range(1, retries + 1):
        try:
            with requests.get(url, stream=True, timeout=60) as r:
                if r.status_code == 404: raise requests.HTTPError("thumbnail not ready (404)")
                r.raise_for_status()
                bytes_written = 0
                ensure_dir(os.path.dirname(out_path))
                with open(out_path, "wb") as f:
                    for chunk in r.iter_content(8192):
                        if chunk: f.write(chunk); bytes_written += len(chunk)
            _mark_complete(out_path)
            logging.info(L(f"Image saved: {out_path} ({human_bytes(bytes_written)})",
                           f"Gambar tersimpan: {out_path} ({human_bytes(bytes_written)})"))
            logging.info(f"[Bytes] {TOTALS.grand.bytes_written}")
            TOTALS.grand.bytes_written += bytes_written; return True
        except Exception as e:
            if attempt == 10:
                _mark_incomplete(out_path)  # remains for cleanup
                logging.error(L(f"[!] Thumbnail failed permanently: {url} -> {e}",
                                f"[!] Thumbnail gagal permanen: {url} -> {e}")); return False
            logging.warning(L(f"Thumbnail attempt {attempt}/10 failed: {e}",
                              f"Percobaan thumbnail {attempt}/10 gagal: {e}")); backoff_sleep(attempt)

def download_file_resumable(service, creds, file_id: str, target: str, label: str = "File") -> bool:
    _mark_incomplete(target)
    """Generic resumable GET ?alt=media using AuthorizedSession with Range, for images or any file."""
    ensure_dir(os.path.dirname(target)); session = AuthorizedSession(creds)
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
    total_size = None
    try:
        meta = get_item(service, file_id, "size, name")
        if "size" in meta: total_size = int(meta["size"])
    except Exception as e:
        logging.debug(L(f"Could not get size for {file_id}: {e}",
                        f"Tidak bisa mendapatkan ukuran untuk {file_id}: {e}"))
    downloaded = os.path.getsize(target) if os.path.exists(target) else 0
    mode = "ab" if downloaded > 0 else "wb"
    if downloaded > 0:
        logging.info(L(f"Resuming {label.lower()} at {human_bytes(downloaded)} -> {os.path.basename(target)}",
                       f"Melanjutkan {label.lower()} di {human_bytes(downloaded)} -> {os.path.basename(target)}"))
    if total_size is not None and downloaded >= total_size:
            _mark_complete(target)
            logging.info(L(f"Already complete: {os.path.basename(target)}",
                       f"Sudah lengkap: {os.path.basename(target)}")); return True
    last_report = time.time()
    while True:
        if INTERRUPTED: return False
        wait_if_paused()
        headers = {"Range": f"bytes={downloaded}-"} if downloaded else {}
        for attempt in range(1, 9):
            try:
                with session.get(url, headers=headers, stream=True, timeout=60) as r:
                    if r.status_code not in (200, 206):
                        if r.status_code == 416 and total_size and os.path.getsize(target) >= total_size:
                            logging.info(L("Server reports complete (416).", "Server melapor selesai (416).")); return True
                        r.raise_for_status()
                    with open(target, mode) as f:
                        for chunk in r.iter_content(chunk_size=8*1024*1024):
                            if INTERRUPTED: return False
                            wait_if_paused()
                            if chunk:
                                f.write(chunk); downloaded += len(chunk); TOTALS.grand.bytes_written += len(chunk)
                                now = time.time()
                                if now - last_report >= 1.5:
                                    if total_size:
                                        pct = 100.0 * downloaded / total_size
                                        logging.info(L(
                                            f"{label} {os.path.basename(target)}: {pct:.1f}% ({human_bytes(downloaded)}/{human_bytes(total_size)})",
                                            f"{label} {os.path.basename(target)}: {pct:.1f}% ({human_bytes(downloaded)}/{human_bytes(total_size)})"
                                        ))
                                        logging.info(f"[Bytes] {TOTALS.grand.bytes_written}")
                                        last_report = now
                                    else:
                                        logging.info(L(
                                            f"{label} {os.path.basename(target)}: {human_bytes(downloaded)} downloaded",
                                            f"{label} {os.path.basename(target)}: {human_bytes(downloaded)} diunduh"
                                        ))
                break
            except Exception as e:
                if attempt == 8:
                    logging.error(L(f"[!] Chunk failed permanently (id={file_id}): {e}",
                                    f"[!] Potongan gagal permanen (id={file_id}): {e}")); return False
                logging.warning(L(f"Chunk attempt {attempt}/8 failed: {e}",
                                  f"Percobaan potongan {attempt}/8 gagal: {e}")); backoff_sleep(attempt); mode = "ab"
        if total_size is None:
            headers_probe = {"Range": f"bytes={downloaded}-"}
            try:
                wait_if_paused()
                with session.get(url, headers=headers_probe, stream=True, timeout=30) as r2:
                    if r2.status_code == 416:
                        _mark_complete(target)
                        logging.info(L("Server indicated EOF (416); treating as complete.",
                                       "Server menunjukkan EOF (416); dianggap selesai.")); return True
            except Exception:
                return True
        if total_size is not None and downloaded >= total_size:
            _mark_complete(target)
            logging.info(L(f"{label} done: {os.path.basename(target)} ({human_bytes(downloaded)})",
                           f"{label} selesai: {os.path.basename(target)} ({human_bytes(downloaded)})"))
            logging.info(f"[Bytes] {TOTALS.grand.bytes_written}")
            return True

def download_video_resumable(service, creds, file_id: str, target: str) -> bool:
    return download_file_resumable(service, creds, file_id, target, label=L("Video", "Video"))

# -------------------- Target paths --------------------

def _image_target_path(out_subdir: str, name: str, file_id: str, original: bool, file_ext: Optional[str]) -> str:
    base, ext_from_name = os.path.splitext(name)
    if original:
        ext = ext_from_name or (("." + file_ext) if file_ext else ".jpg")
        return os.path.join(out_subdir, f"{base}__{file_id}{ext}")
    # thumbnail
    return os.path.join(out_subdir, f"{base}__{file_id}_w{IMAGE_WIDTH}.jpg")

def _video_target_path(out_subdir: str, name: str, file_id: str) -> str:
    base, ext = os.path.splitext(name)
    if not ext:
        ext = ".mp4"
    return os.path.join(out_subdir, f"{base}__{file_id}{ext}")

# -------------------- Processing --------------------

def process_file(service, creds, file_obj: Dict, out_dir: str, counters_key: str) -> bool:
    with _LOCK:
        TOTALS.grand.scanned += 1
        folder_ctrs = TOTALS.folder(counters_key)
        folder_ctrs.scanned += 1
    name = safe_filename(file_obj.get("name", file_obj.get("id","file"))); mime = file_obj.get("mimeType",""); fid = file_obj.get("id"); file_ext = file_obj.get("fileExtension")
    media_kind = classify_media(mime, name, file_ext)
    rel_path = file_obj.get("__rel_path",""); out_subdir = os.path.join(out_dir, rel_path) if rel_path else out_dir; ensure_dir(out_subdir)

    if media_kind == "image":
        target = _image_target_path(out_subdir, name, fid, DOWNLOAD_IMAGES_ORIGINAL, file_ext)
        if not OVERWRITE and os.path.exists(target):
            logging.info(L(f"= exists (image): {target}", f"= sudah ada (gambar): {target}"))
            with _LOCK:
                TOTALS.grand.images_skipped += 1; folder_ctrs.images_skipped += 1
            # Return True for existing files so they count as "completed" for progress purposes
            return True
        if DOWNLOAD_IMAGES_ORIGINAL:
            logging.info(L(f"Downloading image original -> {target}",
                           f"Mengunduh gambar ukuran asli -> {target}"))
            ok = download_file_resumable(service, creds, fid, target, label=L("Image", "Gambar"))
        else:
            url = f"https://drive.google.com/thumbnail?sz=w{IMAGE_WIDTH}&id={fid}"
            logging.info(L(f"Downloading image thumbnail -> {target}",
                           f"Mengunduh thumbnail -> {target}"))
            ok = download_thumbnail(url, target)
        if ok:
            with _LOCK:
                TOTALS.grand.images_done += 1; folder_ctrs.images_done += 1
            return True
        # failed
        with _LOCK:
            TOTALS.grand.images_failed += 1; folder_ctrs.images_failed += 1
        try:
            with _LOCK:
                FAILED_ITEMS.append({
                "id": fid, "name": name, "kind": "image", "__root_name": counters_key,
                "__folder_out": out_subdir, "target": target
            })
        except Exception:
            pass
        return False

    elif media_kind == "video":
        target = _video_target_path(out_subdir, name, fid)
        if not OVERWRITE and os.path.exists(target):
            logging.info(L(f"= exists (video): {target}", f"= sudah ada (video): {target}"))
            with _LOCK:
                TOTALS.grand.videos_skipped += 1; folder_ctrs.videos_skipped += 1
            # Return True for existing files so they count as "completed" for progress purposes
            return True
        if not DOWNLOAD_VIDEOS:
            logging.info(L("Skipping video; option disabled.", "Lewati video (opsi nonaktif)."))
            with _LOCK:
                TOTALS.grand.videos_skipped += 1; folder_ctrs.videos_skipped += 1
            # Return False for videos that are intentionally skipped (don't count as completed)
            return False
        logging.info(L(f"Downloading video -> {target}", f"Mengunduh video -> {target}"))
        ok = download_video_resumable(service, creds, fid, target) if ROBUST_RESUME else _download_video_simple(service, fid, target)
        if ok:
            with _LOCK:
                TOTALS.grand.videos_done += 1; folder_ctrs.videos_done += 1
            return True
        # failed
        with _LOCK:
            TOTALS.grand.videos_failed += 1; folder_ctrs.videos_failed += 1
        try:
            with _LOCK:
                FAILED_ITEMS.append({
                "id": fid, "name": name, "kind": "video", "__root_name": counters_key,
                "__folder_out": out_subdir, "target": target
            })
        except Exception:
            pass
        return False

    elif media_kind == "data":
        # Handle data files (PDFs, documents, etc.)
        base, ext = os.path.splitext(name)
        if not ext:
            # Try to determine extension from mime type or file extension metadata
            if "pdf" in mime.lower():
                ext = ".pdf"
            elif "text" in mime.lower():
                ext = ".txt"
            elif file_ext:
                ext = f".{file_ext}"
            else:
                ext = ".dat"  # generic data extension
        target = os.path.join(out_subdir, f"{base}__{fid}{ext}")
        
        if not OVERWRITE and os.path.exists(target):
            logging.info(L(f"= exists (data): {target}", f"= sudah ada (data): {target}"))
            with _LOCK:
                TOTALS.grand.data_skipped += 1; folder_ctrs.data_skipped += 1
            # Return True for existing files so they count as "completed" for progress purposes
            return True
            
        logging.info(L(f"Downloading data file -> {target}", f"Mengunduh file data -> {target}"))
        ok = download_file_resumable(service, creds, fid, target, label=L("Data", "Data"))
        if ok:
            with _LOCK:
                TOTALS.grand.data_done += 1; folder_ctrs.data_done += 1
            return True
        # failed
        with _LOCK:
            TOTALS.grand.data_failed += 1; folder_ctrs.data_failed += 1
        try:
            with _LOCK:
                FAILED_ITEMS.append({
                "id": fid, "name": name, "kind": "data", "__root_name": counters_key,
                "__folder_out": out_subdir, "target": target
            })
        except Exception:
            pass
        return False

    else:
        logging.debug(L(f"- skip unclassified: {name} [{mime}]", f"- lewati (tidak terklasifikasi): {name} [{mime}]")); return False

# -------------------- Summaries --------------------

def print_folder_summary(root_name: str, link_images: int, link_images_existing: int, link_videos: int, link_videos_existing: int):
    logging.info(L(
        f"[Pre-Scan Folder] {root_name} | images total={link_images} (have {link_images_existing}) | "
        f"videos total={link_videos} (have {link_videos_existing})",
        f"[Pra-Pindai Folder] {root_name} | total gambar={link_images} (sudah {link_images_existing}) | "
        f"total video={link_videos} (sudah {link_videos_existing})"
    ))

def print_grand_summary():
    g = TOTALS.grand
    logging.info(L(
        f"[Grand Summary] elapsed={elapsed()} | total scanned={g.scanned} | "
        f"images: done={g.images_done} skip={g.images_skipped} fail={g.images_failed} | "
        f"videos: done={g.videos_done} skip={g.videos_skipped} fail={g.videos_failed} | "
        f"bytes written={human_bytes(g.bytes_written)}",
        f"[Ringkasan Total] durasi={elapsed()} | total dipindai={g.scanned} | "
        f"gambar: selesai={g.images_done} lewati={g.images_skipped} gagal={g.images_failed} | "
        f"video: selesai={g.videos_done} lewati={g.videos_skipped} gagal={g.videos_failed} | "
        f"bytes ditulis={human_bytes(g.bytes_written)}"
    ))

def print_progress():
    total_images = EXPECTED_IMAGES; total_videos = EXPECTED_VIDEOS; total_data = EXPECTED_DATA
    # Include both newly downloaded AND already existing files in the "done" count
    # This gives users accurate progress including files they already had
    done_images = ALREADY_HAVE_IMAGES + TOTALS.grand.images_done
    done_videos = ALREADY_HAVE_VIDEOS + TOTALS.grand.videos_done
    done_data = ALREADY_HAVE_DATA + TOTALS.grand.data_done
    remaining_images = max(0, total_images - done_images)
    remaining_videos = max(0, total_videos - done_videos)
    remaining_data = max(0, total_data - done_data)
    
    # Include data in progress report if any data files are expected
    if total_data > 0:
        logging.info(L(
            f"[Progress] images {done_images}/{total_images} (left {remaining_images}) | "
            f"videos {done_videos}/{total_videos} (left {remaining_videos}) | "
            f"data {done_data}/{total_data} (left {remaining_data})",
            f"[Progress] gambar {done_images}/{total_images} (sisa {remaining_images}) | "
            f"video {done_videos}/{total_videos} (sisa {remaining_videos}) | "
            f"data {done_data}/{total_data} (sisa {remaining_data})"
        ))
    else:
        logging.info(L(
            f"[Progress] images {done_images}/{total_images} (left {remaining_images}) | "
            f"videos {done_videos}/{total_videos} (left {remaining_videos})",
            f"[Progress] gambar {done_images}/{total_images} (sisa {remaining_images}) | "
            f"video {done_videos}/{total_videos} (sisa {remaining_videos})"
        ))

# -------------------- Pre-scan --------------------
def prescan_tasks(service) -> List[Dict]:
    global EXPECTED_IMAGES, EXPECTED_VIDEOS, EXPECTED_DATA, ALREADY_HAVE_IMAGES, ALREADY_HAVE_VIDEOS, ALREADY_HAVE_DATA, LINK_SUMMARIES
    LINK_SUMMARIES = []

    urls = list(FOLDER_URLS)
    tasks_all: List[Dict] = []

    def _scan_one(url: str):
        # Modify shared counters from within this worker
        global EXPECTED_IMAGES, EXPECTED_VIDEOS, EXPECTED_DATA, ALREADY_HAVE_IMAGES, ALREADY_HAVE_VIDEOS, ALREADY_HAVE_DATA, EXPECTED_TOTAL_BYTES
        local_tasks: List[Dict] = []
        if INTERRUPTED:
            return local_tasks
        try:
            # Build a thread-local service to avoid cross-thread issues
            svc, _ = get_service_and_creds(TOKEN_FILE, CREDENTIALS_FILE)
            folder_id = extract_folder_id(url)
            name, ok = resolve_folder(svc, folder_id)
            if not ok:
                return local_tasks
            url_label = safe_filename(url)[:160]
            base_out = os.path.join(OUTPUT_DIR, url_label); ensure_dir(base_out)
            root_name = name
            folder_out = os.path.join(base_out, root_name); ensure_dir(folder_out)

            logging.info(L(
                f"# Pre-scan: {root_name} ({url}) -> parent {url_label}",
                f"# Pra-pindai: {root_name} ({url}) -> induk {url_label}"
            ))

            link_images = 0; link_videos = 0; link_data = 0
            link_images_existing = 0; link_videos_existing = 0; link_data_existing = 0
            link_images_bytes = 0; link_videos_bytes = 0; link_data_bytes = 0

            for f in list_folder_recursive(svc, folder_id, rel_path=""):
                if INTERRUPTED: break
                fid  = f.get("id"); mime = f.get("mimeType",""); fext = f.get("fileExtension")
                kind = classify_media(mime, f.get("name",""), fext)
                if kind in ("image", "video", "data"):
                    f["__root_name"] = root_name
                    f["__folder_out"] = folder_out
                    rel = f.get("__rel_path","")
                    target_dir = os.path.join(folder_out, rel); ensure_dir(target_dir)
                    base, ext = os.path.splitext(f.get("name","file"))
                    
                    # Debug: log file size info
                    file_size = f.get("size")
                    logging.debug(L(
                        f"File {f.get('name', 'unknown')}: kind={kind}, size={file_size}, from_shortcut={f.get('__from_shortcut', False)}",
                        f"File {f.get('name', 'unknown')}: jenis={kind}, ukuran={file_size}, dari_shortcut={f.get('__from_shortcut', False)}"
                    ))
                    if kind == "image":
                        link_images += 1
                        with _LOCK:
                            EXPECTED_IMAGES += 1
                        if DOWNLOAD_IMAGES_ORIGINAL:
                            ext_out = ext or (("." + fext) if fext else ".jpg")
                            img_target = os.path.join(target_dir, f"{base}__{fid}{ext_out}")
                        else:
                            img_target = os.path.join(target_dir, f"{base}__{fid}_w{IMAGE_WIDTH}.jpg")
                        if os.path.exists(img_target):
                            with _LOCK:
                                ALREADY_HAVE_IMAGES += 1
                            link_images_existing += 1
                        else:
                            local_tasks.append(f)
                            if DOWNLOAD_IMAGES_ORIGINAL:
                                try:
                                    sz = int(f.get("size") or 0)
                                    # If missing, try to fetch size
                                    if not sz:
                                        meta = get_item(svc, fid, "size")
                                        sz = int(meta.get("size") or 0)
                                    link_images_bytes += sz
                                except Exception:
                                    pass
                            else:
                                # For thumbnail downloads, estimate size based on typical thumbnail sizes
                                # Most thumbnails are 50-200KB depending on complexity and compression
                                try:
                                    # Use a conservative estimate: 100KB per thumbnail
                                    # This gives users a rough idea of data usage
                                    estimated_thumb_size = 100 * 1024  # 100KB
                                    link_images_bytes += estimated_thumb_size
                                except Exception:
                                    pass
                    elif kind == "data":
                        link_data += 1
                        with _LOCK:
                            EXPECTED_DATA += 1
                        base, ext = os.path.splitext(f.get("name", "file"))
                        if not ext:
                            if "pdf" in mime.lower():
                                ext = ".pdf"
                            elif "text" in mime.lower():
                                ext = ".txt"
                            elif fext:
                                ext = f".{fext}"
                            else:
                                ext = ".dat"
                        data_target = os.path.join(target_dir, f"{base}__{fid}{ext}")
                        if os.path.exists(data_target):
                            with _LOCK:
                                ALREADY_HAVE_DATA += 1
                            link_data_existing += 1
                        else:
                            local_tasks.append(f)
                            try:
                                sz = int(f.get("size") or 0)
                                if not sz:
                                    meta = get_item(svc, fid, "size")
                                    sz = int(meta.get("size") or 0)
                                link_data_bytes += sz
                            except Exception as e:
                                logging.debug(L(
                                    f"Could not get size for data file {fid}: {e}",
                                    f"Tidak bisa mendapatkan ukuran untuk file data {fid}: {e}"
                                ))
                    else:  # video
                        link_videos += 1
                        with _LOCK:
                            EXPECTED_VIDEOS += 1
                        ext_out = ext or ".mp4"
                        vid_target = os.path.join(target_dir, f"{base}__{fid}{ext_out}")
                        if os.path.exists(vid_target):
                            with _LOCK:
                                ALREADY_HAVE_VIDEOS += 1
                            link_videos_existing += 1
                        else:
                            if DOWNLOAD_VIDEOS:
                                local_tasks.append(f)
                                try:
                                    sz = int(f.get("size") or 0)
                                    if not sz:
                                        meta = get_item(svc, fid, "size")
                                        sz = int(meta.get("size") or 0)
                                    link_videos_bytes += sz
                                except Exception as e:
                                    # Log when we can't get video size for debugging
                                    logging.debug(L(
                                        f"Could not get size for video {fid}: {e}",
                                        f"Tidak bisa mendapatkan ukuran untuk video {fid}: {e}"
                                    ))
        except Exception as e:
            logging.error(L(f"Listing failed for URL {url}: {e}", f"Listing gagal untuk URL {url}: {e}"))
            return local_tasks

        # Log summary with data files if any are found
        if link_data > 0:
            logging.info(L(
                f"[Count] {root_name}: images={link_images} (have {link_images_existing}) | "
                f"videos={link_videos} (have {link_videos_existing}) | data={link_data} (have {link_data_existing})",
                f"[Jumlah] {root_name}: gambar={link_images} (sudah {link_images_existing}) | "
                f"video={link_videos} (sudah {link_videos_existing}) | data={link_data} (sudah {link_data_existing})"
            ))
        else:
            logging.info(L(
                f"[Count] {root_name}: images={link_images} (have {link_images_existing}) | videos={link_videos} (have {link_videos_existing})",
                f"[Jumlah] {root_name}: gambar={link_images} (sudah {link_images_existing}) | video={link_videos} (sudah {link_videos_existing})"
            ))
        with _LOCK:
            LINK_SUMMARIES.append({
                "root_name": root_name,
                "images": link_images,
                "images_existing": link_images_existing,
                "images_bytes": link_images_bytes,
                "videos": link_videos,
                "videos_existing": link_videos_existing,
                "videos_bytes": link_videos_bytes,
                "data": link_data,
                "data_existing": link_data_existing,
                "data_bytes": link_data_bytes,
                "url": url,
            })
            EXPECTED_TOTAL_BYTES += (link_images_bytes + link_videos_bytes + link_data_bytes)
        print_folder_summary(root_name, link_images, link_images_existing, link_videos, link_videos_existing)
        return local_tasks

    # Run scans in parallel per-URL
    futures = []
    with ThreadPoolExecutor(max_workers=max(1, int(CONCURRENCY) if str(CONCURRENCY).isdigit() else 1)) as ex:
        for url in urls:
            if INTERRUPTED: break
            futures.append(ex.submit(_scan_one, url))
        for fut in as_completed(futures):
            try:
                ts = fut.result()
                if ts:
                    tasks_all.extend(ts)
            except Exception as e:
                logging.error(L(f"Prescan worker error: {e}", f"Kesalahan prescan: {e}"))

    # Log final pre-scan summary with data files if any found
    if EXPECTED_DATA > 0:
        logging.info(L(
            f"[Pre-Scan Summary] images={EXPECTED_IMAGES} (have {ALREADY_HAVE_IMAGES}) | "
            f"videos={EXPECTED_VIDEOS} (have {ALREADY_HAVE_VIDEOS}) | data={EXPECTED_DATA} (have {ALREADY_HAVE_DATA})",
            f"[Ringkasan Pra-Pindai] gambar={EXPECTED_IMAGES} (sudah {ALREADY_HAVE_IMAGES}) | "
            f"video={EXPECTED_VIDEOS} (sudah {ALREADY_HAVE_VIDEOS}) | data={EXPECTED_DATA} (sudah {ALREADY_HAVE_DATA})"
        ))
    else:
        logging.info(L(
            f"[Pre-Scan Summary] images={EXPECTED_IMAGES} (have {ALREADY_HAVE_IMAGES}) | videos={EXPECTED_VIDEOS} (have {ALREADY_HAVE_VIDEOS})",
            f"[Ringkasan Pra-Pindai] gambar={EXPECTED_IMAGES} (sudah {ALREADY_HAVE_IMAGES}) | video={EXPECTED_VIDEOS} (sudah {ALREADY_HAVE_VIDEOS})"
        ))
    return tasks_all

# -------------------- Simple (non-resumable) video --------------------

def _download_video_simple(service, file_id: str, target: str) -> bool:
    req = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    with io.FileIO(target, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, req, chunksize=10 * 1024 * 1024)
        done = False; last_pct = -1
        while not done:
            status, done = downloader.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                if pct != last_pct:
                    logging.info(L(f"Video {os.path.basename(target)}: {pct}%",
                                   f"Video {os.path.basename(target)}: {pct}%"))
                    last_pct = pct
    try:
        TOTALS.grand.bytes_written += os.path.getsize(target)
        logging.info(f"[Bytes] {TOTALS.grand.bytes_written}")
    except Exception:
        pass
    return True

# -------------------- Main --------------------

def main():
    global TOTALS, EXPECTED_IMAGES, EXPECTED_VIDEOS, ALREADY_HAVE_IMAGES, ALREADY_HAVE_VIDEOS, START_TS, INTERRUPTED, DIRECT_TASKS
    TOTALS = Totals()
    EXPECTED_IMAGES = 0
    EXPECTED_VIDEOS = 0
    ALREADY_HAVE_IMAGES = 0
    ALREADY_HAVE_VIDEOS = 0
    START_TS = time.time()
    INTERRUPTED = False
    setup_logging()

    # --- Mode A: Convert thumbnails folder → originals in-place ---
    if CONVERT_THUMBS_DIR:
        logging.info(L(
            f"=== Convert thumbnails in {CONVERT_THUMBS_DIR} to originals ===",
            f"=== Konversi thumbnail di {CONVERT_THUMBS_DIR} ke ukuran asli ==="
        ))
        service, creds = get_service_and_creds(TOKEN_FILE, CREDENTIALS_FILE)
        acct = get_account_info(service)
        if acct.get("email") or acct.get("name"):
            logging.info(L(
                f"Using account: {acct.get('name') or ''} <{acct.get('email') or ''}>",
                f"Menggunakan akun: {acct.get('name') or ''} <{acct.get('email') or ''}>"
            ))

        thumb_dir = Path(CONVERT_THUMBS_DIR)
        if not thumb_dir.exists():
            logging.error(L(f"Folder not found: {thumb_dir}", f"Folder tidak ditemukan: {thumb_dir}"))
            print_grand_summary()
            return

        # Files like: name__<fileid>_w700.jpg (id chars [A-Za-z0-9_-])
        pat = re.compile(r"__(?P<fid>[A-Za-z0-9_-]+)_w\d+\.jpg$", re.IGNORECASE)

        for path in thumb_dir.rglob("*_w*.jpg"):
            if INTERRUPTED: break
            m = pat.search(path.name)
            if not m:
                continue
            fid = m.group("fid")

            # Figure out correct extension from Drive metadata (fallback .jpg)
            ext_out = ".jpg"
            try:
                meta = get_item(service, fid, "id,name,fileExtension")
                name_on_drive = meta.get("name") or fid
                _, name_ext = os.path.splitext(name_on_drive)
                if name_ext:
                    ext_out = name_ext
                elif meta.get("fileExtension"):
                    ext_out = f".{meta['fileExtension']}"
            except Exception as e:
                logging.debug(L(f"Could not query ext for {fid}: {e}",
                                f"Tidak bisa mengambil ekstensi untuk {fid}: {e}"))

            # Remove trailing _w###.jpg to form base
            base_no_thumb = re.sub(r"_w\d+\.jpg$", "", path.name, flags=re.IGNORECASE)
            target = path.with_name(f"{base_no_thumb}{ext_out}")

            if target.exists() and not OVERWRITE:
                logging.info(L(f"Already have original: {target.name}",
                               f"Sudah ada ukuran asli: {target.name}"))
                TOTALS.grand.images_skipped += 1
                continue

            logging.info(L(f"Fetching original for {path.name} (id={fid}) -> {target.name}",
                           f"Mengambil ukuran asli untuk {path.name} (id={fid}) -> {target.name}"))
            ok = download_file_resumable(service, creds, fid, str(target), label=L("Image", "Gambar"))
            if ok:
                TOTALS.grand.images_done += 1
            else:
                TOTALS.grand.images_failed += 1

        print_grand_summary()
        return  # inside main()

    # --- Mode B: Normal Drive crawl (previews + videos and/or original images) ---
    logging.info(L(
        "=== Drive Previews (images) + Full Videos ===",
        "=== Ambil Pratinjau Drive (gambar) + Video Penuh ==="
    ))
    logging.info(
        L(
            f"Output dir: {OUTPUT_DIR}\nImage width: {IMAGE_WIDTH}px | Overwrite: {OVERWRITE} | Resume: {ROBUST_RESUME} | "
            f"Download videos: {DOWNLOAD_VIDEOS} | Image originals: {DOWNLOAD_IMAGES_ORIGINAL}",
            f"Folder keluaran: {OUTPUT_DIR}\nLebar gambar: {IMAGE_WIDTH}px | Overwrite: {OVERWRITE} | Resume: {ROBUST_RESUME} | "
            f"Unduh video: {DOWNLOAD_VIDEOS} | Gambar asli: {DOWNLOAD_IMAGES_ORIGINAL}"
        )
    )
    ensure_dir(OUTPUT_DIR)

    service, creds = get_service_and_creds(TOKEN_FILE, CREDENTIALS_FILE)
    acct = get_account_info(service)
    if acct.get("email") or acct.get("name"):
        logging.info(L(
            f"Using account: {acct.get('name') or ''} <{acct.get('email') or ''}>",
            f"Menggunakan akun: {acct.get('name') or ''} <{acct.get('email') or ''}>"
        ))
    # If DIRECT_TASKS provided (e.g., retry failed), use them and set expected counts accordingly
    if DIRECT_TASKS:
        tasks = DIRECT_TASKS
        EXPECTED_IMAGES = sum(1 for t in tasks if classify_media(t.get("mimeType",""), t.get("name",""), t.get("fileExtension")) == "image")
        EXPECTED_VIDEOS = sum(1 for t in tasks if classify_media(t.get("mimeType",""), t.get("name",""), t.get("fileExtension")) == "video")
        EXPECTED_DATA = sum(1 for t in tasks if classify_media(t.get("mimeType",""), t.get("name",""), t.get("fileExtension")) == "data")
        logging.info(L(f"Using direct task list: {len(tasks)} items", f"Memakai daftar tugas langsung: {len(tasks)} item"))
    else:
        tasks = prescan_tasks(service)

    # Split tasks into images, videos, and data files for organized processing
    image_tasks: List[Dict] = []
    video_tasks: List[Dict] = []
    data_tasks: List[Dict] = []
    for f in tasks:
        kind = classify_media(f.get("mimeType",""), f.get("name",""), f.get("fileExtension"))
        if kind == "video":
            video_tasks.append(f)
        elif kind == "data":
            data_tasks.append(f)
        else:  # images and unknown types default to image processing
            image_tasks.append(f)

    # Images: execute with concurrency
    futures = []
    with ThreadPoolExecutor(max_workers=max(1, int(CONCURRENCY) if str(CONCURRENCY).isdigit() else 1)) as ex:
        for f in image_tasks:
            if INTERRUPTED:
                break
            wait_if_paused()
            futures.append(ex.submit(process_file, service, creds, f, f['__folder_out'], f['__root_name']))
        for fut in as_completed(futures):
            if INTERRUPTED:
                break
            wait_if_paused()
            try:
                ok = fut.result()
                if ok:
                    print_progress()
            except Exception as e:
                logging.error(L(f"Worker error: {e}", f"Kesalahan pekerja: {e}"))

    # Videos: execute sequentially (no concurrency)
    for f in video_tasks:
        if INTERRUPTED:
            break
        wait_if_paused()
        try:
            ok = process_file(service, creds, f, f['__folder_out'], f['__root_name'])
            if ok:
                print_progress()
        except Exception as e:
            logging.error(L(f"Worker error: {e}", f"Kesalahan pekerja: {e}"))

    # Data files: execute with moderate concurrency (between images and videos)
    if data_tasks:
        data_futures = []
        with ThreadPoolExecutor(max_workers=max(1, min(2, int(CONCURRENCY) // 2) if str(CONCURRENCY).isdigit() else 1)) as ex:
            for f in data_tasks:
                if INTERRUPTED:
                    break
                wait_if_paused()
                data_futures.append(ex.submit(process_file, service, creds, f, f['__folder_out'], f['__root_name']))
            for fut in as_completed(data_futures):
                if INTERRUPTED:
                    break
                wait_if_paused()
                try:
                    ok = fut.result()
                    if ok:
                        print_progress()
                except Exception as e:
                    logging.error(L(f"Data worker error: {e}", f"Kesalahan pekerja data: {e}"))

    # If interrupted or finished, ensure any incomplete targets are removed
    cleanup_incomplete_targets()
    print_progress()
    print_grand_summary()
    logging.info(L("Done.", "Selesai."))
    # Clear DIRECT_TASKS after run
    DIRECT_TASKS = None

def get_failed_items() -> List[Dict]:
    return list(FAILED_ITEMS)

def get_totals_snapshot() -> Dict:
    return {
        "elapsed": elapsed(),
        "scanned": TOTALS.grand.scanned,
        "images": {
            "done": TOTALS.grand.images_done,
            "skipped": TOTALS.grand.images_skipped,
            "failed": TOTALS.grand.images_failed,
            "expected": EXPECTED_IMAGES,
            "already": ALREADY_HAVE_IMAGES,
        },
        "videos": {
            "done": TOTALS.grand.videos_done,
            "skipped": TOTALS.grand.videos_skipped,
            "failed": TOTALS.grand.videos_failed,
            "expected": EXPECTED_VIDEOS,
            "already": ALREADY_HAVE_VIDEOS,
        },
        "bytes_written": TOTALS.grand.bytes_written,
        "expected_total_bytes": EXPECTED_TOTAL_BYTES,
        "link_summaries": list(LINK_SUMMARIES),
    }

def set_direct_tasks(tasks: List[Dict]):
    global DIRECT_TASKS
    DIRECT_TASKS = list(tasks)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.exception(L(f"Fatal error: {e}", f"Kesalahan fatal: {e}"))
        print_grand_summary()
        sys.exit(1)