# dfr/utils.py
# Helper utilities and classifications

import os, re, time
from urllib.parse import urlparse, parse_qs
from typing import Optional

# We intentionally import the main module to read runtime globals
import drive_fetch_resilient as dfr

_IMAGE_EXTS = {"jpg","jpeg","png","gif","webp","tif","tiff","bmp","heic","heif","cr2","cr3","arw","nef","dng","raf","rw2"}
_VIDEO_EXTS = {"mp4","mov","m4v","mkv","avi","webm","mts","m2ts","3gp","mod","tod"}


def human_bytes(n: int) -> str:
    units = ["B","KB","MB","GB","TB","PB"]; f = float(max(0, int(n))); i = 0
    while f >= 1024 and i < len(units)-1:
        f /= 1024.0; i += 1
    return f"{f:.2f} {units[i]}"


def estimate_thumbnail_size_bytes(target_width: int) -> int:
    """
    Roughly estimate a JPEG thumbnail size (bytes) for a given width.

    Assumptions:
    - Typical aspect ratio ~ 4:3 (height = 0.75 * width)
    - Typical JPEG quality ~1.5 bits per pixel (~0.1875 bytes/px)
    Result: bytes ≈ 0.1875 * (width * height) = 0.1875 * 0.75 * width^2
    Clamp to a sane range to avoid extremes.
    """
    try:
        w = max(1, int(target_width))
    except Exception:
        w = 800
    # bytes per square pixel constant derived from the assumptions above
    bytes_per_pixel = 0.1875
    height = int(0.75 * w)
    est = int(bytes_per_pixel * w * height)
    # Clamp between 40 KB and 3 MB to keep estimates reasonable
    return int(min(max(est, 40 * 1024), 3 * 1024 * 1024))


def elapsed() -> str:
    d = time.time() - dfr.START_TS
    h = int(d//3600); m = int((d%3600)//60); s = int(d%60)
    return f"{h}h {m}m {s}s" if h else (f"{m}m {s}s" if m else f"{s}s")


def extract_folder_id(url: str) -> str:
    m = re.search(r"/folders/([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1)
    qs = parse_qs(urlparse(url).query)
    return (qs.get("id", [""])[0]).strip()


def safe_filename(name: str) -> str:
    src = "" if name is None else str(name)
    for ch in '/\\:*?"<>|':
        src = src.replace(ch, "_")
    return src.strip().rstrip(".") or "untitled"


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def backoff_sleep(attempt: int):
    base = min(30, (2 ** (attempt - 1)) + 0.1 * attempt)
    import random as _r, time as _t
    jitter = base * (0.75 + 0.5 * _r.random())
    dfr.logging.debug(dfr.L(
        f"Backing off {jitter:.1f}s, attempt {attempt}",
        f"Jeda {jitter:.1f} dtk (percobaan {attempt})"
    ))
    _t.sleep(jitter)


def _ext_from(name: str, file_ext: Optional[str]) -> str:
    if file_ext:
        return file_ext.lower()
    _, ext = os.path.splitext(name or "")
    return ext.lstrip(".").lower()


def classify_media(mime: str, name: str, file_ext: Optional[str]) -> Optional[str]:
    ext = _ext_from(name, file_ext)
    if (mime or "").startswith("image/") or ext in _IMAGE_EXTS:
        return "image"
    if (mime or "").startswith("video/") or ext in _VIDEO_EXTS:
        return "video"
    return None


def get_totals_snapshot() -> dict:
    """Return a snapshot of current totals and counters."""
    return {
        "elapsed": elapsed(),
        "scanned": dfr.TOTALS.grand.scanned,
        "images": {
            "done": dfr.TOTALS.grand.images_done,
            "skipped": dfr.TOTALS.grand.images_skipped,
            "failed": dfr.TOTALS.grand.images_failed,
            "expected": dfr.EXPECTED_IMAGES,
            "already": dfr.ALREADY_HAVE_IMAGES,
        },
        "videos": {
            "done": dfr.TOTALS.grand.videos_done,
            "skipped": dfr.TOTALS.grand.videos_skipped,
            "failed": dfr.TOTALS.grand.videos_failed,
            "expected": dfr.EXPECTED_VIDEOS,
            "already": dfr.ALREADY_HAVE_VIDEOS,
        },
        "bytes_written": dfr.TOTALS.grand.bytes_written,
        "expected_total_bytes": dfr.EXPECTED_TOTAL_BYTES,
        "link_summaries": list(dfr.LINK_SUMMARIES),
    }
