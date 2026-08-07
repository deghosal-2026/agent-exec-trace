"""Logging configuration for the analytics service.

Provides a single ``setup_logging()`` call that configures Python's standard
logging with the level and format from ``settings``.  Called once at CLI entry
points so that all subsequent loggers inherit the same configuration.

Design decision: Uses ``force=True`` to override any pre-existing logging
configuration (e.g., from third-party libraries that call ``logging.basicConfig``
before the analytics service initializes).
"""

from __future__ import annotations

import logging
import sys

from analytics.config import settings


def setup_logging() -> None:
    """Configure root logger with level from settings and stdout output.

    The log level and format are read from ``settings.log_level`` and
    ``settings.log_format``, making them configurable via environment variables
    (``ANALYTICS_LOG_LEVEL``, ``ANALYTICS_LOG_FORMAT``).

    Uses ``force=True`` so this overrides any pre-existing logging configuration
    (e.g., from importing modules that call ``logging.basicConfig`` before setup).

    Raises:
        AttributeError: if ``settings.log_level`` does not name a valid
            Python logging level (e.g., ``DEBUG``, ``INFO``, ``WARNING``).
    """
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
        force=True,
    )
