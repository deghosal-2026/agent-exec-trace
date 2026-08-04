"""Logging configuration for the analytics service.

Provides a single ``setup_logging()`` call that configures Python's standard
logging with the level and format from ``settings``.  Called once at CLI entry
points.
"""

from __future__ import annotations

import logging
import sys

from analytics.config import settings


def setup_logging() -> None:
    """Configure root logger with level from settings and stdout output.

    Uses ``force=True`` so this overrides any pre-existing logging configuration
    (e.g. from importing modules that call ``logging.basicConfig`` before setup).
    """
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
        force=True,
    )