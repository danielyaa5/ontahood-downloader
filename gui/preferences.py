"""
Preferences management for the GUI application.
Handles loading and saving user preferences like window geometry, settings, etc.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

from .config import GUI_PREFS_FILE, DEFAULT_URLS


class PreferencesManager:
    """Manages application preferences and settings."""
    
    def __init__(self):
        self.prefs_file = GUI_PREFS_FILE
        self._default_prefs = {
            "geometry": "980x950",
            "language": "en", 
            "output_dir": "",
            "image_mode": "700 (thumbnail)",
            "download_videos": True,
            "urls": "\n".join(DEFAULT_URLS) + "\n",
            "converter_dir": "",
        }
    
    def load_preferences(self) -> Dict[str, Any]:
        """
        Load preferences from file.
        
        Returns:
            Dictionary of preferences, with defaults for missing keys
        """
        prefs = self._default_prefs.copy()
        
        try:
            if self.prefs_file.exists():
                with open(self.prefs_file, 'r', encoding='utf-8') as f:
                    saved_prefs = json.load(f)
                    prefs.update(saved_prefs)
        except Exception:
            pass  # Use defaults if loading fails
        
        return prefs
    
    def save_preferences(self, prefs: Dict[str, Any]) -> None:
        """
        Save preferences to file.
        
        Args:
            prefs: Dictionary of preferences to save
        """
        try:
            # Ensure directory exists
            self.prefs_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.prefs_file, 'w', encoding='utf-8') as f:
                json.dump(prefs, f, indent=2, ensure_ascii=False)
        except Exception:
            pass  # Silently fail if saving fails
    
    def get_default_output_dir(self) -> str:
        """
        Get a reasonable default output directory.
        
        Returns:
            Path to default output directory
        """
        default_paths = [
            Path.home() / "Downloads" / "ontahood-downloads",
            Path.home() / "Desktop" / "ontahood-downloads", 
            Path.cwd() / "output"
        ]
        
        for path in default_paths:
            try:
                # Try to create the directory to test if it's writable
                path.mkdir(parents=True, exist_ok=True)
                return str(path)
            except (OSError, PermissionError):
                continue
        
        # Fallback to current directory
        return str(Path.cwd() / "output")
    
    def validate_preferences(self, prefs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and clean up preferences.
        
        Args:
            prefs: Raw preferences dictionary
            
        Returns:
            Validated preferences dictionary
        """
        validated = prefs.copy()
        
        # Validate geometry
        if not self._is_valid_geometry(validated.get("geometry", "")):
            validated["geometry"] = self._default_prefs["geometry"]
        
        # Validate language
        if validated.get("language") not in ["en", "id"]:
            validated["language"] = "en"
        
        # Validate boolean values
        if not isinstance(validated.get("download_videos"), bool):
            validated["download_videos"] = True
        
        # Ensure output directory exists or use default
        output_dir = validated.get("output_dir", "")
        if not output_dir or not self._is_valid_directory(output_dir):
            validated["output_dir"] = self.get_default_output_dir()
        
        return validated
    
    def _is_valid_geometry(self, geometry: str) -> bool:
        """Check if geometry string is valid."""
        try:
            if not geometry or 'x' not in geometry:
                return False
            
            # Parse geometry string like "980x950" or "980x950+100+50"  
            size_part = geometry.split('+')[0]  # Remove position if present
            width, height = size_part.split('x')
            width, height = int(width), int(height)
            
            # Check reasonable bounds
            return 400 <= width <= 3000 and 300 <= height <= 2000
        except (ValueError, AttributeError):
            return False
    
    def _is_valid_directory(self, path: str) -> bool:
        """Check if directory path is valid and accessible."""
        try:
            path_obj = Path(path)
            return path_obj.exists() and path_obj.is_dir() and os.access(path, os.W_OK)
        except (OSError, TypeError):
            return False