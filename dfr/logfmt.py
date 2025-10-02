# dfr/logfmt.py
# Logging formatter and setup

import os, sys, logging
from logging.handlers import RotatingFileHandler

import drive_fetch_resilient as dfr

class ColorFormatter(logging.Formatter):
    RESET = "\033[0m"
    GREY = "\033[90m"
    LEVEL_COLORS = {
        logging.DEBUG: "\033[96m",
        logging.INFO: "\033[92m",
        logging.WARNING: "\033[93m",
        logging.ERROR: "\033[91m",
        logging.CRITICAL: "\033[97m\033[101m",
    }
    BOLD_ON = "\033[1m"; BOLD_OFF = "\033[22m"

    def format(self, record):
        base = super().format(record)
        try:
            import re
            m = re.match(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| ([A-Z]+)\s+\| (.*)$", base, re.DOTALL)
            def emph(body: str) -> str:
                pattern = r"(\[[^\]]+\])|(\b(?:images|videos|gambar|video)\s\d+/\d+\b)|(\b(?:left|sisa)\s\d+\b)|(\b[A-Za-z_]+=\d+\b)"
                return re.sub(pattern, lambda mt: f"{self.BOLD_ON}{mt.group(0)}{self.BOLD_OFF}", body)
            if not m:
                return emph(base) + self.RESET
            ts, level, msg = m.groups()
            lvl_color = self.LEVEL_COLORS.get(record.levelno, "")
            msg2 = emph(msg)
            return f"{self.GREY}{ts}{self.RESET} | {lvl_color}{level}{self.RESET} | {msg2}{self.RESET}"
        except Exception:
            return base


def setup_logging():
    os.makedirs(dfr.OUTPUT_DIR, exist_ok=True)
    log_path = os.path.join(dfr.OUTPUT_DIR, dfr.LOG_FILENAME)
    level = getattr(logging, dfr.LOG_LEVEL.upper(), logging.INFO)
    fmt = "%(asctime)s | %(levelname)-7s | %(message)s"; datefmt = "%Y-%m-%d %H:%M:%S"
    root = logging.getLogger(); root.setLevel(level)
    if root.handlers:
        root.setLevel(level)
        return
    ch = logging.StreamHandler(sys.stdout); ch.setLevel(level); ch.setFormatter(ColorFormatter(fmt, datefmt)); root.addHandler(ch)
    fh = RotatingFileHandler(log_path, maxBytes=dfr.LOG_MAX_BYTES, backupCount=dfr.LOG_BACKUPS, encoding="utf-8")
    fh.setLevel(level); fh.setFormatter(logging.Formatter(fmt, datefmt)); root.addHandler(fh)
