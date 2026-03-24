"""
utils/logger.py — Loguru logging setup for the LinkedIn Profile Extractor.
"""

import sys
from loguru import logger


def setup_logger(log_file: str = "extractor.log") -> None:
    """
    Configure loguru with console + file sinks.

    Call once at startup from main.py.
    """
    # Remove default handler
    logger.remove()

    # Console sink — colored, INFO level
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> — <level>{message}</level>",
        level="INFO",
        colorize=True,
    )

    # File sink — DEBUG level, rotation at 5 MB
    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{function}:{line} — {message}",
        level="DEBUG",
        rotation="5 MB",
        retention="7 days",
        encoding="utf-8",
    )

    logger.info("Logger initialised")
