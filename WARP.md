# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

Project summary
- Purpose: Download fast, low-res image previews and optional full-size videos from shared Google Drive folders; optionally convert selected local thumbnails into full-size originals.
- Primary language: Python
- Entry points: gui_main.py (modular Tkinter GUI), drive_fetch_resilient.py (headless/core logic)
- Packaging target: macOS universal2 app via PyInstaller (built by pre-commit.sh)

Common commands
- Install dependencies
```bash path=null start=null
python3 -m pip install -r requirements.txt
```

- Run the GUI (recommended for normal use)
```bash path=null start=null
python3 gui_main.py
```

- Headless run (download previews and optional videos)
  Notes:
  - The core script reads Google OAuth client secrets from CREDENTIALS_FILE (defaults to credentials.json if present in script dir or Application Support/OntahoodDownloader).
  - Results and logs are written under OUTPUT_DIR (default ./output). Log file: drive_fetch.log.
  - Choose logs language with LANG=en or LANG=id.
```bash path=null start=null
# Example: two Drive folder URLs, 700px thumbnails, videos enabled
python3 - <<'PY'
import drive_fetch_resilient as d

d.FOLDER_URLS = [
  "https://drive.google.com/drive/folders/<FOLDER_ID_1>",
  "https://drive.google.com/drive/folders/<FOLDER_ID_2>",
]
# Optional: override credential/token/output
# d.CREDENTIALS_FILE = "./credentials.json"
# d.TOKEN_FILE = "~/.config/OntahoodDownloader/token.json"
# d.OUTPUT_DIR = "./output"

# Options
d.IMAGE_WIDTH = 700           # thumbnail width (px)
d.DOWNLOAD_VIDEOS = True      # also download full-size videos
d.DOWNLOAD_IMAGES_ORIGINAL = False  # keep as thumbnails

# Logs language: "en" or "id"
d.LANG = "en"

d.main()
PY
```

- Conversion mode (convert local thumbnails to full-size originals in-place)
  Notes:
  - Point CONVERT_THUMBS_DIR to a folder containing files named like name__<fileid>_w700.jpg; originals will be saved alongside.
```bash path=null start=null
python3 - <<'PY'
import drive_fetch_resilient as d

d.CONVERT_THUMBS_DIR = "/path/to/folder/of/thumbnails"  # required
d.DOWNLOAD_IMAGES_ORIGINAL = True
# Optional: d.CREDENTIALS_FILE = "./credentials.json"
# Logging language
d.LANG = "en"

d.main()
PY
```

- Build macOS app (universal2) and zip
  Notes:
  - Script expects Python 3.13 at /Library/Frameworks/Python.framework/Versions/3.13/bin/python3. Update PYTHON_UNI inside pre-commit.sh if different on your machine.
  - Produces dist/Ontahood Downloader.app and Ontahood Downloader.app.zip at repo root.
```bash path=null start=null
chmod +x pre-commit.sh
./pre-commit.sh
```

Repository-specific safeguards (from pre-commit.sh)
- Blocks committing Google OAuth secrets: credentials.json, token.json.
- Blocks committing macOS bundles/images (*.app, *.dmg) except under dmg-staging/.
- Large file guard: rejects staged files >95MB unless GIT_ALLOW_BIG=1.
- Warns if README.md is missing the expected download link.
- On build: installs missing Python deps, includes hidden-import/collect-all for requirements, verifies universal2 slices via lipo, zips and stages the .app.

High-level architecture
- Core downloader (drive_fetch_resilient.py)
  - Support dir: platform-aware Application Support path under OntahoodDownloader; default TOKEN_FILE lives here.
  - Auth: Resolves credentials.json from multiple locations; OAuth flow persists token.json to TOKEN_FILE.
  - Modes
    - Normal: Pre-scans folder URLs to compute expected counts and skip already-downloaded outputs, then processes tasks.
    - Conversion: Scans a local folder for *_w###.jpg thumbnails and fetches originals (by Drive file ID) to the same folder.
  - Listing: Recursively walks Drive folders (supports Shared Drives), follows folder and file shortcuts, and carries a relative path for output structure.
  - Media classification: Uses MIME type and extensions to treat images vs videos.
  - Downloads
    - Images (thumbnails): Uses Drive thumbnail endpoint ?sz=w{IMAGE_WIDTH}.
    - Images (originals) and videos: Robust resumable downloads via AuthorizedSession with Range support; retries with exponential backoff.
  - File naming
    - Thumbnails: <name>__<fileid>_w<width>.jpg
    - Originals: <name>__<fileid><ext>
  - Accounting and logs: Per-folder and global counters; human-readable byte totals and elapsed; i18n via LANG ("en"/"id"). Logs to stdout and rotating file drive_fetch.log under OUTPUT_DIR.

- GUI (gui_main.py and gui/ package)
  - Tkinter-based bilingual interface (English/Bahasa Indonesia) wrapping the core module.
  - Two sections:
    - Downloader: paste Drive folder URLs; choose output, image mode (thumbnail width or ORIGINAL), toggle videos; streams backend logs into a non-intrusive log view that only auto-scrolls when at bottom.
    - Converter: select a local folder of chosen thumbnails to fetch originals in-place.
  - Progress: Parses backend "[Progress]" log lines to update image/video progress bars and counts.
  - Credential discovery: Attempts to locate credentials.json next to the executable, next to the script, or in Application Support.

- Packaging/build (pre-commit.sh)
  - Builds a macOS universal2 app via PyInstaller, collecting all packages from requirements.txt with --hidden-import/--collect-all to avoid missing modules at runtime.
  - Verifies x86_64 and arm64 slices for both the app binary and embedded Python; bundles drive_fetch_resilient.py and optionally credentials.json as data.
  - Zips the .app with ditto and stages the archive for commit (subject to size guard).

Notes
- Tests and lint: No test suite or linter configuration is present in the repo.
- Credentials: For development, place credentials.json alongside the scripts or in Application Support/OntahoodDownloader; override via CREDENTIALS_FILE if needed.
