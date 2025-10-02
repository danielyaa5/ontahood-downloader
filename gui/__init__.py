"""
GUI package for ontahood-downloader

This package contains the modular Tkinter GUI components broken down for better code organization.
"""

from .main_app import App
from .config import DEFAULT_URLS, GUI_PREFS_FILE
from .i18n import T
from .utils import locate_credentials, notify, validate_image_size, format_bytes
from .log_handler import TkLogHandler
from .preferences import PreferencesManager
from .workers import run_worker, run_converter, start_worker_thread

__all__ = [
    'App', 'DEFAULT_URLS', 'GUI_PREFS_FILE', 'T', 
    'locate_credentials', 'notify', 'validate_image_size', 'format_bytes',
    'TkLogHandler', 'PreferencesManager',
    'run_worker', 'run_converter', 'start_worker_thread'
]
