"""
Utility functions for the GUI application.
"""

import os
import sys
import platform
from pathlib import Path


def locate_credentials():
    """
    Locate the credentials.json file in various possible locations.
    
    Returns:
        Path to credentials.json if found, None otherwise
    """
    candidates = []
    
    # Try next to the current script
    try:
        candidates.append(Path(__file__).resolve().parent.parent / "credentials.json")
    except Exception:
        pass
    
    # Try in PyInstaller bundle
    if hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / "credentials.json")
    
    # Try in Application Support directory (macOS)
    candidates.append(
        Path.home() / "Library" / "Application Support" / "OntahoodDownloader" / "credentials.json"
    )
    
    # Try in current working directory
    candidates.append(Path.cwd() / "credentials.json")
    
    for path in candidates:
        try:
            if path.exists():
                return path
        except Exception:
            continue
    
    return None


def notify(title: str, message: str):
    """
    Show a system notification (macOS specific for now).
    
    Args:
        title: Notification title
        message: Notification message
    """
    if platform.system() == "Darwin":  # macOS
        try:
            import subprocess
            script = f'display notification "{message}" with title "{title}"'
            subprocess.run(['osascript', '-e', script], check=False)
        except Exception:
            pass  # Silently fail if notification doesn't work


def format_bytes(size: int) -> str:
    """
    Format byte size to human readable format.
    
    Args:
        size: Size in bytes
        
    Returns:
        Human readable size string (e.g., "1.5 MB")
    """
    if size == 0:
        return "0 B"
    
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    size_float = float(size)
    
    while size_float >= 1024 and unit_index < len(units) - 1:
        size_float /= 1024.0
        unit_index += 1
    
    return f"{size_float:.2f} {units[unit_index]}"


def validate_image_size(size_str: str) -> tuple[bool, int]:
    """
    Validate and parse image size input.
    
    Args:
        size_str: Size string (e.g., "400", "ORIGINAL")
        
    Returns:
        Tuple of (is_valid, parsed_size)
        For ORIGINAL mode, parsed_size will be -1
    """
    size_str = size_str.strip().upper()
    
    if size_str == "ORIGINAL":
        return True, -1
    
    try:
        size = int(size_str.replace("PX", "").strip())
        if 100 <= size <= 6000:
            return True, size
        else:
            return False, 0
    except (ValueError, AttributeError):
        return False, 0


def get_app_version() -> str:
    """
    Get the application version.
    
    Returns:
        Version string
    """
    return "v0.15"