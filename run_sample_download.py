#!/usr/bin/env python3
"""
Run a small sample download to sanity-check concurrency performance.
Downloads first N missing images from the JAGOAN folder.
"""
import os
import drive_fetch_resilient as dfr
from dfr.auth import get_service_and_creds
from dfr.prescan import prescan_tasks
from dfr.utils import classify_media
from dfr.main import main as run_main

# User-adjustable parameters
URL = "https://drive.google.com/drive/folders/1jUjWloriy-cRugvQFCU93Q7RSESo3HxR"
SAMPLE_N = int(os.environ.get("SAMPLE_N", "10"))
CONCURRENCY = int(os.environ.get("CONCURRENCY", "3"))

# Configure globals
outdir = os.environ.get("OUTPUT_DIR", "./output")
dfr.FOLDER_URLS = [URL]
dfr.OUTPUT_DIR = outdir

# Use thumbnails (faster) for the sample; set ORIGINAL with env if desired
if os.environ.get("ORIGINAL", "0") in ("1", "true", "True"):
    dfr.DOWNLOAD_IMAGES_ORIGINAL = True
else:
    dfr.DOWNLOAD_IMAGES_ORIGINAL = False
    dfr.IMAGE_WIDTH = int(os.environ.get("IMAGE_WIDTH", "1600"))

# Limit concurrency for the sample
dfr.CONCURRENCY = max(1, min(CONCURRENCY, 12))

# Build task list
svc, _ = get_service_and_creds(dfr.TOKEN_FILE, dfr.CREDENTIALS_FILE)
all_tasks = prescan_tasks(svc)
image_tasks = [t for t in all_tasks if classify_media(t.get("mimeType",""), t.get("name",""), t.get("fileExtension")) == "image"]

sample = image_tasks[:SAMPLE_N]
dfr.set_direct_tasks(sample)

print(f"[Sample] Downloading {len(sample)} images with concurrency={dfr.CONCURRENCY} (original={dfr.DOWNLOAD_IMAGES_ORIGINAL})")
run_main()
