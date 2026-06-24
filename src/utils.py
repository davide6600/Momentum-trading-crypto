"""
utils.py — Shared utilities: logging, retries, date helpers.
"""

import logging
import time
import functools
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


# ── Project root ──
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "daily"
OUTPUT_DIR = PROJECT_ROOT / "output"


def setup_logging(name: str = "momentum", level: int = logging.INFO,
                  log_file: Optional[str] = None) -> logging.Logger:
    """
    Configure and return a logger with console + optional file output.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured

    logger.setLevel(level)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # File handler (optional)
    if log_file:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(OUTPUT_DIR / log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0,
                       max_delay: float = 30.0):
    """
    Decorator: retry a function on exception with exponential backoff.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = base_delay
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries:
                        raise
                    logger = logging.getLogger("momentum")
                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): "
                        f"{type(e).__name__}: {e}. Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    delay = min(delay * 2, max_delay)
        return wrapper
    return decorator


def get_weekly_rebalance_dates(start_date: datetime, end_date: datetime,
                               day_name: str = "sunday") -> list:
    """
    Generate all weekly rebalance dates between start and end.

    Args:
        start_date: First possible date.
        end_date: Last possible date (inclusive).
        day_name: Day of week for rebalance (e.g., 'sunday').

    Returns:
        List of datetime objects, one per rebalance date.
    """
    day_map = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6
    }
    target_weekday = day_map[day_name.lower()]

    # Find first target weekday on or after start_date
    current = start_date
    days_ahead = (target_weekday - current.weekday()) % 7
    if days_ahead == 0 and current > start_date:
        pass  # already on the right day
    current = current + timedelta(days=days_ahead)

    dates = []
    while current <= end_date:
        dates.append(current)
        current += timedelta(weeks=1)

    return dates


def ensure_dirs():
    """Create data and output directories if they don't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
