"""
dfr package - modular backend for ontahood-downloader
"""

# Make key functions available at package level for backward compatibility
from . import main
from . import auth
from . import utils
from . import prescan
from . import process
from . import downloads
from . import listing
from . import logfmt

# Re-export commonly used functions
__all__ = ['main', 'auth', 'utils', 'prescan', 'process', 'downloads', 'listing', 'logfmt']
