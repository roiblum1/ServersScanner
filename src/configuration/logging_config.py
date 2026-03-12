"""
Logging configuration and setup.
"""

import logging
import os
from typing import Optional


class LogConfig:
    """Logging settings."""

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
    DETAILED_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"

    LOG_FILE = os.getenv("LOG_FILE")
    LOG_FILE_MAX_BYTES = int(os.getenv("LOG_FILE_MAX_BYTES", "10485760"))  # 10 MB
    LOG_FILE_BACKUP_COUNT = int(os.getenv("LOG_FILE_BACKUP_COUNT", "5"))


def setup_logging(verbose: bool = False, log_file: Optional[str] = None) -> None:
    """Configure application logging."""
    log_level = logging.DEBUG if verbose else getattr(logging, LogConfig.LOG_LEVEL, logging.INFO)
    log_format = LogConfig.DETAILED_FORMAT if verbose else LogConfig.LOG_FORMAT

    logging.basicConfig(level=log_level, format=log_format, datefmt=LogConfig.LOG_DATE_FORMAT)

    if log_file or LogConfig.LOG_FILE:
        from logging.handlers import RotatingFileHandler
        file_path = log_file or LogConfig.LOG_FILE
        handler = RotatingFileHandler(
            file_path,
            maxBytes=LogConfig.LOG_FILE_MAX_BYTES,
            backupCount=LogConfig.LOG_FILE_BACKUP_COUNT,
        )
        handler.setLevel(log_level)
        handler.setFormatter(logging.Formatter(log_format, LogConfig.LOG_DATE_FORMAT))
        logging.getLogger().addHandler(handler)
        logging.getLogger(__name__).info(f"Logging to file: {file_path}")

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("kubernetes").setLevel(logging.WARNING)
    logging.getLogger(__name__).info(f"Logging configured: level={logging.getLevelName(log_level)}")
