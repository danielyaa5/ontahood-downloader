"""
Configuration constants and settings for the GUI application.
"""

from pathlib import Path
import sys

# Import the backend module for support directory
try:
    import drive_fetch_resilient as dfr
except Exception as e:
    raise SystemExit("Could not import drive_fetch_resilient.py. Put this GUI file next to it. " + str(e))

# Default Google Drive folder URLs for testing/examples
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

# Path to thumbnails directory for conversion mode
CONVERT_THUMBS_DIR = None

# Preferences file path (persist GUI state between runs)
try:
    GUI_PREFS_FILE = Path(dfr.SUPPORT_DIR) / "gui_prefs.json"
except Exception:
    GUI_PREFS_FILE = Path.home() / ".ontahood_gui_prefs.json"

# Window configuration
WINDOW_TITLE = "ontahood-downloader"
WINDOW_MIN_WIDTH = 800
WINDOW_MIN_HEIGHT = 600

# UI Configuration
PADDING = 5
BUTTON_WIDTH = 20
TEXT_AREA_HEIGHT = 15