from __future__ import annotations
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

def configure_logging(log_file: Path, level: str = 'INFO') -> None:
    """Configure structured-ish rotating logging inside D:/Jarvis/Logs."""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')
    handler = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=5, encoding='utf-8')
    handler.setFormatter(formatter)
    root.addHandler(handler)
