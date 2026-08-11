import os
import sys
import logging
from logging.handlers import RotatingFileHandler

LOG_FILE = os.getenv("SMARTRECO_LOG_FILE", "smartreco.log")

def setup_logger(name: str = "smartreco") -> logging.Logger:
    """
    Sets up a comprehensive logging service that outputs structured logs to stdout
    and writes persistent logs to smartreco.log.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers if already initialized
    if logger.hasHandlers():
        return logger

    # Log Formatter: Timestamp [Level] File:Line - Message
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s:%(filename)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console Handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler (rotating log file, max 5MB per file, 3 backups)
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

# Global default logger
logger = setup_logger()
