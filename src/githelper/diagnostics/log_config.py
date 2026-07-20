"""Logging configuration.

Defines log format, rotation, levels, and contextual tagging.
No sensitive content (file contents, diffs, commit messages) in logs.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from githelper.common.constants import APP_AUTHOR, APP_NAME

# The default log format includes timestamp, level, thread name, module, and message.
_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | [%(threadName)s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 5 MB max per file, keep 3 backups.
_MAX_BYTES = 5 * 1024 * 1024
_BACKUP_COUNT = 3


def _get_default_log_dir() -> Path:
    """Get the cross-platform default log directory.
    
    Using standard appdata locations.
    """
    import os
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.path.expanduser("~")
        return Path(base) / APP_AUTHOR / APP_NAME / "logs"
    elif os.name == "posix":
        import sys
        if sys.platform == "darwin":
            return Path(os.path.expanduser("~/Library/Logs")) / APP_NAME
        else:
            return Path(os.path.expanduser("~/.local/state")) / APP_NAME / "logs"
    
    return Path.cwd() / "logs"


def configure_logging(log_dir: Path | None = None, level: int = logging.INFO) -> None:
    """Configure the root logger with rotation and formatting.
    
    Args:
        log_dir: Optional override for log directory. Defaults to standard OS paths.
        level: Root logging level.
    """
    if log_dir is None:
        log_dir = _get_default_log_dir()
        
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "githelper.log"
    
    # Configure the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers if re-configuring
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    # File handler with rotation
    file_handler = RotatingFileHandler(
        filename=str(log_file),
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8"
    )
    formatter = logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)
    file_handler.setFormatter(formatter)
    
    root_logger.addHandler(file_handler)
    
    # Also log to console if running interactively/for tests
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    # console_handler is usually WARNING for stdout, but we match the file level for dev
    console_handler.setLevel(level)
    root_logger.addHandler(console_handler)
    
    # Quiet down some chatty third-party libs if we ever use them
    logging.getLogger("watchdog").setLevel(logging.WARNING)
