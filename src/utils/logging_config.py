"""
Centralized logging configuration for crypto-analytics project.

This module provides a standardized logging setup that can be used
across all modules instead of scattered loguru imports.
"""

import sys
from pathlib import Path
from loguru import logger
from typing import Optional


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    project_name: str = "crypto-analytics",
) -> None:
    """
    Set up centralized logging for the project.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path. If None, uses project logs directory
        project_name: Project name for log formatting
    """
    # Remove default handler
    logger.remove()

    # Console handler with colored output
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>",
        colorize=True,
    )

    # File handler
    if log_file is None:
        # Default to project logs directory
        project_root = Path(__file__).parent.parent.parent
        logs_dir = project_root / "logs"
        logs_dir.mkdir(exist_ok=True)
        log_file = logs_dir / f"{project_name}.log"

    logger.add(
        str(log_file),
        level=log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="100 MB",  # Rotate when file reaches 100MB
        retention="30 days",  # Keep logs for 30 days
        compression="zip",  # Compress old logs
        catch=True,
    )

    logger.info(f"Logging configured - Level: {log_level}, File: {log_file}")


def get_logger(name: str):
    """
    Get a logger instance for a specific module.

    Args:
        name: Usually __name__ from the calling module

    Returns:
        Configured logger instance
    """
    return logger.bind(name=name)


# Default setup - can be imported and used directly
setup_logging()
