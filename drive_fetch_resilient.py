#!/usr/bin/env python3
# drive_fetch_resilient.py v1.7 — 2025-09-29

import os, re, io, sys, time, signal, random, requests
from urllib.parse import urlparse, parse_qs
from typing import Iterator, Dict, Optional, List
from dataclasses import dataclass, field
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.auth.transport.requests import AuthorizedSession
from googleapiclient.errors import HttpError
import logging
from logging.handlers import RotatingFileHandler

import platform
from pathlib import Path

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

# Allow env overrides
CREDENTIALS_FILE = os.environ.get("CREDENTIALS_FILE", "credentials.json")
TOKEN_FILE       = os.environ.get("TOKEN_FILE", str(SUPPORT_DIR / "token.json"))
OUTPUT_DIR       = os.environ.get("OUTPUT_DIR", "./output")

# Resolve credentials.json robustly:
def _resolve_credentials_path(p: str) -> str:
    pth = Path(p)
    if pth.is_file():
        return str(pth)
    # Try support dir
    pth2 = SUPPORT_DIR / Path(p).name
    if pth2.is_file():
        return str(pth2)
    # Try alongside script (handles pyinstaller & normal)
    try:
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    except Exception:
        base = Path(__file__).resolve().parent
    pth3 = base / Path(p).name
    if pth3.is_file():
        return str(pth3)
    raise FileNotFoundError(f"Could not find {p!r}. Looked in: "
                            f"{Path(p).resolve()}, {pth2}, {pth3}")

# -------------------- Runtime options --------------------
IMAGE_WIDTH              = 400
OVERWRITE                = False
ROBUST_RESUME            = True
DOWNLOAD_VIDEOS          = True
DOWNLOAD_IMAGES_ORIGINAL = False   # <— NEW: full-res image download toggle

LOG_LEVEL        = "INFO"
LOG_FILENAME     = "drive_fetch.log"
LOG_MAX_BYTES    = 10 * 1024 * 1024
LOG_BACKUPS      = 3
FOLDER_URLS: List[str] = []

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

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
ALREADY_HAVE_IMAGES = 0
ALREADY_HAVE_VIDEOS = 0

# -------------------- Logging --------------------

class ColorFormatter(logging.Formatter):
    COLORS = {logging.DEBUG: "\033[36m", logging.INFO: "\033[32m", logging.WARNING: "\033[33m", logging.ERROR: "\033[31m", logging.CRITICAL: "\033[41m"}
    RESET = "\033[0m"
    def format(self, record):
        try:
            color = self.COLORS.get(record.levelno, self.RESET)
            msg = super().format(record)
            return f"{color}{msg}{self.RESET}"
        except Exception:
            return super().format(record)

def setup_logging():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    log_path = os.path.join(OUTPUT_DIR, LOG_FILENAME)
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    fmt = "%(asctime)s | %(levelname)-7s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    root = logging.getLogger(); root.setLevel(level)
    ch = logging.StreamHandler(sys.stdout); ch.setLevel(level); ch.setFormatter(ColorFormatter(fmt, datefmt)); root.addHandler(ch)
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

def on_sigint(sig, frame):
    global INTERRUPTED; INTERRUPTED = True
    logging.warning("Menerima sinyal interupsi — menyelesaikan langkah saat ini lalu meringkas... (Received interrupt signal — finishing current step and summarizing...)")
signal.signal(signal.SIGINT, on_sigint)

# -------------------- Auth / Service --------------------

def get_service_and_creds(token_path: str, credentials_path: str):
    from google.auth.transport.requests import Request
    token_path = str(Path(token_path))  # ensure string path
    creds = None

    # Read token if present
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    # Refresh or start fresh
    if not creds or not creds.valid:
        try:
            if creds and creds.expired and creds.refresh_token:
                logging.info("Menyegarkan kredensial tersimpan... (Refreshing stored credentials...)")
                creds.refresh(Request())
            else:
                raise Exception("Need fresh auth")
        except Exception:
            logging.info("Membuka browser untuk OAuth Google... (Launching browser for Google OAuth...)")
            cred_path_resolved = _resolve_credentials_path(credentials_path)
            flow = InstalledAppFlow.from_client_secrets_file(cred_path_resolved, SCOPES)
            creds = flow.run_local_server(port=0)

        # Ensure support dir and write token there even if user pointed elsewhere
        Path(token_path).parent.mkdir(parents=True, exist_ok=True)
        with open(token_path, "w") as f:
            f.write(creds.to_json())
            logging.info(f"Menulis token file: {token_path} (Wrote token file)")

    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    return service, creds

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
    logging.debug(f"Jeda {jitter:.1f} dtk (percobaan {attempt}) (Backing off {jitter:.1f}s, attempt {attempt})")
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
        logging.error("URL folder tidak memiliki ID. (Folder URL had no ID.)"); return None, False
    try:
        req = service.files().get(fileId=folder_id, fields="id,name,mimeType", supportsAllDrives=True)
        meta = gapi_execute_with_retry(req)
        if meta.get("mimeType") != "application/vnd.google-apps.folder":
            logging.error(f"Bukan folder: {meta.get('name')} ({meta.get('mimeType')}) (Not a folder)"); return None, False
        return safe_filename(meta.get("name", folder_id)), True
    except HttpError as e:
        content = (getattr(e, "content", b"") or b"").decode("utf-8", "ignore")
        if e.resp.status == 404:
            logging.error(f"Folder tidak ditemukan/akses ditolak: {folder_id} (Not found/no access)")
        elif e.resp.status == 403:
            logging.error(f"Akses ditolak untuk folder: {folder_id} (Access denied)")
        else:
            logging.error(f"Gagal resolve folder {folder_id}: {e} {content} (Failed to resolve)")
        return None, False

def list_folder_recursive(service, folder_id: str, rel_path: str = "") -> Iterator[Dict]:
    fields = "nextPageToken, files(id, name, mimeType, fileExtension, shortcutDetails(targetId, targetMimeType))"
    query = f"'{folder_id}' in parents and trashed = false"
    page_token = None
    while True:
        if INTERRUPTED: return
        req = service.files().list(q=query, fields=fields, pageToken=page_token, supportsAllDrives=True, includeItemsFromAllDrives=True, corpora="allDrives")
        resp = gapi_execute_with_retry(req)
        for item in resp.get("files", []):
            mime = item.get("mimeType")
            if mime == "application/vnd.google-apps.folder":
                sub_name = safe_filename(item.get("name", "")); sub_rel = os.path.join(rel_path, sub_name) if rel_path else sub_name
                logging.debug(f"Masuk subfolder: {sub_name} -> {sub_rel} (Descending into subfolder)")
                yield from list_folder_recursive(service, item.get("id"), sub_rel)
            elif mime == "application/vnd.google-apps.shortcut":
                sd = (item.get("shortcutDetails") or {}); target_id = sd.get("targetId"); target_mime = sd.get("targetMimeType")
                sub_name = safe_filename(item.get("name", "shortcut"))
                if target_mime == "application/vnd.google-apps.folder":
                    sub_rel = os.path.join(rel_path, sub_name) if rel_path else sub_name
                    logging.debug(f"Mengikuti shortcut folder: {sub_name} -> {target_id} (Following folder shortcut)")
                    yield from list_folder_recursive(service, target_id, sub_rel)
                else:
                    item["__rel_path"] = rel_path; item["__shortcut_file_target_id"] = target_id; item["__shortcut_file_target_mime"] = target_mime
                    yield item
            else:
                item["__rel_path"] = rel_path; yield item
        page_token = resp.get("nextPageToken")
        if not page_token: break

# -------------------- Downloads --------------------

def download_thumbnail(url: str, out_path: str, retries=10) -> bool:
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
            logging.info(f"Gambar tersimpan: {out_path} (Image saved) ({human_bytes(bytes_written)})")
            TOTALS.grand.bytes_written += bytes_written; return True
        except Exception as e:
            if attempt == 10:
                logging.error(f"[!] Thumbnail gagal permanen: {url} -> {e} (failed permanently)"); return False
            logging.warning(f"Percobaan thumbnail {attempt}/10 gagal: {e} (Thumbnail attempt failed)"); backoff_sleep(attempt)

def download_file_resumable(service, creds, file_id: str, target: str, label: str = "File") -> bool:
    """Generic resumable GET ?alt=media using AuthorizedSession with Range, for images or any file."""
    ensure_dir(os.path.dirname(target)); session = AuthorizedSession(creds)
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
    total_size = None
    try:
        meta = get_item(service, file_id, "size, name")
        if "size" in meta: total_size = int(meta["size"])
    except Exception as e:
        logging.debug(f"Tidak bisa mendapatkan ukuran untuk {file_id}: {e}")
    downloaded = os.path.getsize(target) if os.path.exists(target) else 0
    mode = "ab" if downloaded > 0 else "wb"
    if downloaded > 0:
        logging.info(f"Melanjutkan {label.lower()} di {human_bytes(downloaded)} -> {os.path.basename(target)}")
    if total_size is not None and downloaded >= total_size:
        logging.info(f"Sudah lengkap: {os.path.basename(target)}"); return True
    last_report = time.time()
    while True:
        if INTERRUPTED: return False
        headers = {"Range": f"bytes={downloaded}-"} if downloaded else {}
        for attempt in range(1, 9):
            try:
                with session.get(url, headers=headers, stream=True, timeout=60) as r:
                    if r.status_code not in (200, 206):
                        if r.status_code == 416 and total_size and os.path.getsize(target) >= total_size:
                            logging.info("Server melapor selesai (416)."); return True
                        r.raise_for_status()
                    with open(target, mode) as f:
                        for chunk in r.iter_content(chunk_size=8*1024*1024):
                            if INTERRUPTED: return False
                            if chunk:
                                f.write(chunk); downloaded += len(chunk); TOTALS.grand.bytes_written += len(chunk)
                                now = time.time()
                                if now - last_report >= 1.5:
                                    if total_size:
                                        pct = 100.0 * downloaded / total_size
                                        logging.info(f"{label} {os.path.basename(target)}: {pct:.1f}% ({human_bytes(downloaded)}/{human_bytes(total_size)})")
                                        last_report = now
                                    else:
                                        logging.info(f"{label} {os.path.basename(target)}: {human_bytes(downloaded)} diunduh")
                break
            except Exception as e:
                if attempt == 8:
                    logging.error(f"[!] Potongan {label.lower()} gagal permanen (id={file_id}): {e}"); return False
                logging.warning(f"Percobaan potongan {label.lower()} {attempt}/8 gagal: {e}"); backoff_sleep(attempt); mode = "ab"
        if total_size is None:
            headers_probe = {"Range": f"bytes={downloaded}-"}
            try:
                with session.get(url, headers=headers_probe, stream=True, timeout=30) as r2:
                    if r2.status_code == 416:
                        logging.info("Server menunjukkan EOF (416); dianggap selesai."); return True
            except Exception:
                return True
        if total_size is not None and downloaded >= total_size:
            logging.info(f"{label} selesai: {os.path.basename(target)} ({human_bytes(downloaded)})"); return True

def download_video_resumable(service, creds, file_id: str, target: str) -> bool:
    # Keep for backward-compat; call generic with proper label
    return download_file_resumable(service, creds, file_id, target, label="Video")

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
    TOTALS.grand.scanned += 1; folder_ctrs = TOTALS.folder(counters_key); folder_ctrs.scanned += 1
    name = safe_filename(file_obj.get("name", file_obj.get("id","file"))); mime = file_obj.get("mimeType",""); fid = file_obj.get("id"); file_ext = file_obj.get("fileExtension")
    media_kind = classify_media(mime, name, file_ext)
    rel_path = file_obj.get("__rel_path",""); out_subdir = os.path.join(out_dir, rel_path) if rel_path else out_dir; ensure_dir(out_subdir)

    if media_kind == "image":
        target = _image_target_path(out_subdir, name, fid, DOWNLOAD_IMAGES_ORIGINAL, file_ext)
        if not OVERWRITE and os.path.exists(target):
            logging.info(f"= sudah ada (gambar): {target} (= exists, image)"); TOTALS.grand.images_skipped += 1; folder_ctrs.images_skipped += 1; return False
        if DOWNLOAD_IMAGES_ORIGINAL:
            logging.info(f"Mengunduh gambar ukuran asli -> {target} (Downloading image original)")
            ok = download_file_resumable(service, creds, fid, target, label="Gambar")
        else:
            url = f"https://drive.google.com/thumbnail?sz=w{IMAGE_WIDTH}&id={fid}"
            logging.info(f"Mengunduh thumbnail -> {target} (Downloading image thumbnail)")
            ok = download_thumbnail(url, target)
        if ok:
            TOTALS.grand.images_done += 1; folder_ctrs.images_done += 1; return True
        TOTALS.grand.images_failed += 1; folder_ctrs.images_failed += 1; return False

    elif media_kind == "video":
        target = _video_target_path(out_subdir, name, fid)
        if not OVERWRITE and os.path.exists(target):
            logging.info(f"= sudah ada (video): {target} (= exists, video)"); TOTALS.grand.videos_skipped += 1; folder_ctrs.videos_skipped += 1; return False
        if not DOWNLOAD_VIDEOS:
            logging.info("Lewati video (opsi nonaktif). (Skipping video; option disabled.)"); TOTALS.grand.videos_skipped += 1; folder_ctrs.videos_skipped += 1; return False
        logging.info(f"Mengunduh video -> {target} (Downloading video)")
        ok = download_video_resumable(service, creds, fid, target) if ROBUST_RESUME else _download_video_simple(service, fid, target)
        if ok:
            TOTALS.grand.videos_done += 1; folder_ctrs.videos_done += 1; return True
        TOTALS.grand.videos_failed += 1; folder_ctrs.videos_failed += 1; return False

    else:
        logging.debug(f"- lewati (bukan media): {name} [{mime}] (- skip non-media)"); return False

# -------------------- Summaries --------------------

def print_folder_summary(folder_name: str):
    c = TOTALS.folder(folder_name)
    logging.info(f"[Ringkasan Folder] {folder_name} | dipindai={c.scanned}, gambar: selesai={c.images_done} lewati={c.images_skipped} gagal={c.images_failed}; video: selesai={c.videos_done} lewati={c.videos_skipped} gagal={c.videos_failed} (Folder Summary)")

def print_grand_summary():
    g = TOTALS.grand
    logging.info(f"[Ringkasan Total] elapsed={elapsed()} | total dipindai={g.scanned} | gambar: selesai={g.images_done} lewati={g.images_skipped} gagal={g.images_failed} | video: selesai={g.videos_done} lewati={g.videos_skipped} gagal={g.videos_failed} | bytes ditulis={human_bytes(g.bytes_written)} (Grand Summary)")

def print_progress():
    total_images = EXPECTED_IMAGES; total_videos = EXPECTED_VIDEOS
    done_images = ALREADY_HAVE_IMAGES + TOTALS.grand.images_done
    done_videos = ALREADY_HAVE_VIDEOS + TOTALS.grand.videos_done
    remaining_images = max(0, total_images - done_images)
    remaining_videos = max(0, total_videos - done_videos)
    logging.info(f"[Progress] gambar {done_images}/{total_images} (sisa {remaining_images}) | video {done_videos}/{total_videos} (sisa {remaining_videos}) ([Progress] images {done_images}/{total_images} (left {remaining_images}) | videos {done_videos}/{total_videos} (left {remaining_videos}))")

# -------------------- Prescan / Task build --------------------

def prescan_tasks(service) -> List[Dict]:
    global EXPECTED_IMAGES, EXPECTED_VIDEOS, ALREADY_HAVE_IMAGES, ALREADY_HAVE_VIDEOS
    tasks: List[Dict] = []
    for url in FOLDER_URLS:
        if INTERRUPTED: break
        folder_id = extract_folder_id(url)
        name, ok = resolve_folder(service, folder_id)
        if not ok: continue
        url_label = safe_filename(url)[:160]
        base_out = os.path.join(OUTPUT_DIR, url_label); ensure_dir(base_out)
        root_name = name; folder_out = os.path.join(base_out, root_name); ensure_dir(folder_out)
        logging.info(f"# Memindai (pra-pindai): {root_name} ({url}) -> induk {url_label} (# Scanning pre-scan)")
        try:
            for f in list_folder_recursive(service, folder_id, rel_path=""):
                if INTERRUPTED: break
                if f.get("mimeType") == "application/vnd.google-apps.shortcut" and f.get("__shortcut_file_target_id"):
                    tid = f.get("__shortcut_file_target_id")
                    try:
                        meta = get_item(service, tid, "id,name,mimeType,fileExtension")
                        f = {**meta, "__rel_path": f.get("__rel_path","")}
                    except Exception:
                        continue
                fid = f.get("id")
                mime = f.get("mimeType",""); fext = f.get("fileExtension")
                kind = classify_media(mime, f.get("name",""), fext)
                if kind in ("image","video"):
                    f["__root_name"] = root_name; f["__folder_out"] = folder_out
                    rel = f.get("__rel_path","")
                    target_dir = os.path.join(folder_out, rel); ensure_dir(target_dir)
                    base, ext = os.path.splitext(f.get("name","file"))
                    if kind == "image":
                        EXPECTED_IMAGES += 1
                        if DOWNLOAD_IMAGES_ORIGINAL:
                            ext_out = ext or (("." + fext) if fext else ".jpg")
                            img_target = os.path.join(target_dir, f"{base}__{fid}{ext_out}")
                        else:
                            img_target = os.path.join(target_dir, f"{base}__{fid}_w{IMAGE_WIDTH}.jpg")
                        if os.path.exists(img_target): ALREADY_HAVE_IMAGES += 1
                        else: tasks.append(f)
                    else:
                        EXPECTED_VIDEOS += 1
                        ext_out = ext or ".mp4"
                        vid_target = os.path.join(target_dir, f"{base}__{fid}{ext_out}")
                        if os.path.exists(vid_target): ALREADY_HAVE_VIDEOS += 1
                        else:
                            if DOWNLOAD_VIDEOS: tasks.append(f)
                else:
                    pass
        except Exception as e:
            logging.error(f"Listing gagal untuk {root_name}: {e} (Listing failed)")
        print_folder_summary(root_name)
    logging.info(f"[Ringkasan Pra-Pindai] gambar={EXPECTED_IMAGES} (sudah {ALREADY_HAVE_IMAGES}) | video={EXPECTED_VIDEOS} (sudah {ALREADY_HAVE_VIDEOS}) (Pre-Scan Summary)")
    return tasks

# -------------------- Simple (non-resumable) video (kept) --------------------

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
                    logging.info(f"Video {os.path.basename(target)}: {pct}%"); last_pct = pct
    try: TOTALS.grand.bytes_written += os.path.getsize(target)
    except Exception: pass
    return True

# -------------------- Main --------------------

def main():
    global TOTALS, EXPECTED_IMAGES, EXPECTED_VIDEOS, ALREADY_HAVE_IMAGES, ALREADY_HAVE_VIDEOS, START_TS, INTERRUPTED
    TOTALS = Totals(); EXPECTED_IMAGES = 0; EXPECTED_VIDEOS = 0; ALREADY_HAVE_IMAGES = 0; ALREADY_HAVE_VIDEOS = 0
    START_TS = time.time(); INTERRUPTED = False
    setup_logging()
    logging.info("=== Ambil Pratinjau Drive (gambar) + Video Penuh (Drive Low-Res + Full Videos) ===")
    logging.info(f"Folder keluaran: {OUTPUT_DIR} (Output dir)")
    logging.info(f"Lebar gambar: {IMAGE_WIDTH}px | Overwrite: {OVERWRITE} | Resume: {ROBUST_RESUME} | Unduh video: {DOWNLOAD_VIDEOS} | Gambar asli: {DOWNLOAD_IMAGES_ORIGINAL}")
    ensure_dir(OUTPUT_DIR)
    service, creds = get_service_and_creds(TOKEN_FILE, CREDENTIALS_FILE)
    tasks = prescan_tasks(service)
    for f in tasks:
        if INTERRUPTED: break
        ok = process_file(service, creds, f, f['__folder_out'], counters_key=f['__root_name'])
        if ok: print_progress()
    print_progress(); print_grand_summary()
    logging.info("Selesai. (Done.)")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.exception(f"Kesalahan fatal: {e} (Fatal error)")
        print_grand_summary()
        sys.exit(1)