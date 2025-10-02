#!/usr/bin/env python3
# drive_fetch_resilient.py v1.10 — 2025-10-01
# Minimal wrapper for the modular dfr backend package

import os, time, signal, logging, platform
from typing import List, Dict, Optional
from pathlib import Path
from dataclasses import dataclass, field

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

# -------------------- Runtime options (shared with dfr modules) --------------------
CREDENTIALS_FILE = os.environ.get("CREDENTIALS_FILE", "credentials.json")
TOKEN_FILE       = os.environ.get("TOKEN_FILE", str(SUPPORT_DIR / "token.json"))
OUTPUT_DIR       = os.environ.get("OUTPUT_DIR", "./output")

IMAGE_WIDTH              = 400
OVERWRITE                = False
ROBUST_RESUME            = True
DOWNLOAD_VIDEOS          = True
DOWNLOAD_IMAGES_ORIGINAL = False
CONVERT_THUMBS_DIR       = ""   # if set to a local folder path, convert matching thumbnails to originals
PAUSE                    = False  # Flow control for GUI

LOG_LEVEL        = "INFO"
LOG_FILENAME     = "drive_fetch.log"
LOG_MAX_BYTES    = 10 * 1024 * 1024
LOG_BACKUPS      = 3
FOLDER_URLS: List[str] = []

# Link summaries and retry support
LINK_SUMMARIES: List[Dict] = []
FAILED_ITEMS: List[Dict] = []
DIRECT_TASKS: Optional[List[Dict]] = None

CONCURRENCY = int(os.environ.get("CONCURRENCY", "3"))
LANG = "en"  # Language for logs ("en" or "id")

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# -------------------- Shared counters/state --------------------

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
INCOMPLETE_TARGETS = set()

# -------------------- i18n helper --------------------

def L(en: str, id_: str) -> str:
    """Return English or Indonesian string based on LANG."""
    return en if (LANG or "en").lower().startswith("en") else id_

# -------------------- Signal handling --------------------

def on_sigint(_sig, _frame):
    global INTERRUPTED
    INTERRUPTED = True
    logging.warning(L(
        "Received interrupt signal — finishing current step and summarizing...",
        "Menerima sinyal interupsi — menyelesaikan langkah saat ini lalu meringkas..."
    ))

signal.signal(signal.SIGINT, on_sigint)

def reset_counters():
    """Reset all global counters and state."""
    global TOTALS, EXPECTED_IMAGES, EXPECTED_VIDEOS, EXPECTED_DATA
    global ALREADY_HAVE_IMAGES, ALREADY_HAVE_VIDEOS, ALREADY_HAVE_DATA  
    global START_TS, INTERRUPTED, LINK_SUMMARIES, FAILED_ITEMS, EXPECTED_TOTAL_BYTES
    TOTALS = Totals()
    EXPECTED_IMAGES = 0
    EXPECTED_VIDEOS = 0
    EXPECTED_DATA = 0
    ALREADY_HAVE_IMAGES = 0
    ALREADY_HAVE_VIDEOS = 0
    ALREADY_HAVE_DATA = 0
    EXPECTED_TOTAL_BYTES = 0
    START_TS = time.time()
    INTERRUPTED = False
    LINK_SUMMARIES = []
    FAILED_ITEMS = []

# -------------------- Main entry points --------------------

def main():
    """Main entry point - delegate to modular dfr.main."""
    from dfr.main import main as dfr_main
    return dfr_main()

def get_totals_snapshot() -> Dict:
    """Get totals snapshot - delegate to modular dfr.utils."""
    from dfr.utils import get_totals_snapshot as dfr_get_totals
    return dfr_get_totals()

def get_failed_items() -> List[Dict]:
    """Get list of failed download items."""
    return list(FAILED_ITEMS)

def set_direct_tasks(tasks: List[Dict]):
    """Set direct tasks list for retry functionality."""
    global DIRECT_TASKS
    DIRECT_TASKS = list(tasks)

# -------------------- Re-export key functions from dfr modules --------------------

# Auth functions
from dfr.auth import get_service_and_creds, get_service_if_token_valid, get_account_info, try_get_account_info

# Utility functions  
from dfr.utils import human_bytes, elapsed, extract_folder_id, safe_filename, ensure_dir, backoff_sleep, classify_media

# Processing functions
from dfr.process import process_file, print_folder_summary, print_grand_summary, print_progress

# Listing functions
from dfr.listing import resolve_folder, wait_if_paused, list_folder_recursive, get_item, gapi_execute_with_retry

# Download functions
from dfr.downloads import cleanup_incomplete_targets, download_thumbnail, download_file_resumable, download_video_resumable

# Pre-scan functions
from dfr.prescan import prescan_tasks

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.exception(L(f"Fatal error: {e}", f"Kesalahan fatal: {e}"))
        print_grand_summary()
        exit(1)