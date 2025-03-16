"""
Logging utility for MediBrief.
"""

import logging
import os
from typing import Optional


def setup_logger(
    level: int = logging.INFO,
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    Set up the logger for the application.

    Args:
        level: Logging level.
        log_format: Format string for log messages.
        log_file: Path to log file. If None, logs will only be sent to stdout.

    Returns:
        Configured logger instance.
    """
    # Create logger
    logger = logging.getLogger("medbrief")
    logger.setLevel(level)

    # Create formatter
    formatter = logging.Formatter(log_format)

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Create file handler if log_file is specified
    if log_file:
        # Ensure the directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Prevent propagation to the root logger
    logger.propagate = False

    return logger


def get_logger() -> logging.Logger:
    """
    Get the application logger.

    Returns:
        Logger instance.
    """
    return logging.getLogger("medbrief")