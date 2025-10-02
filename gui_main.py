#!/usr/bin/env python3
"""
Entry point for the modular ontahood-downloader GUI application.

This script launches the GUI using the new modular structure.
"""

import sys
from pathlib import Path

# Add the current directory to Python path to ensure gui module can be imported
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

try:
    from gui import App
except ImportError as e:
    print(f"Failed to import GUI modules: {e}")
    print("Make sure you're running this from the ontahood-downloader directory")
    sys.exit(1)


def main():
    """Main entry point for the GUI application."""
    try:
        # Create and run the application
        app = App()
        app.mainloop()
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()