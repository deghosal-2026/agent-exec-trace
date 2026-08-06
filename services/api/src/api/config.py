"""Pydantic-based settings for the API service.

All configuration is driven by environment variables with the ``API_`` prefix,
enabling twelve-factor-app-style deployment.  A local ``.env`` file is also
loaded when present for development convenience.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Runtime configuration for the REST API service.

    Attributes:
        db_dsn: PostgreSQL connection string for the analytics database.
        db_pool_min_size: minimum connection pool size.
        db_pool_max_size: maximum connection pool size.
        host: host address the HTTP server binds to.
        port: port the HTTP server listens on.
        cors_origins: allowed CORS origins (frontend dev servers).
        otel_service_name: OTel service name for the API service itself.
        log_level: logging level (INFO, DEBUG, etc.).
    """

    # Default DSN points to the local Postgres container on the standard port.
    # Override with API_DB_DSN for staging/production environments.
    db_dsn: str = "postgresql://analytics:analytics@localhost:5432/analytics"

    # Pool sizing: conservative defaults suitable for local dev and CI.
    # Scale up in production via API_DB_POOL_MIN_SIZE / API_DB_POOL_MAX_SIZE.
    db_pool_min_size: int = 2
    db_pool_max_size: int = 10

    # Bind to all interfaces so Docker port mapping works out of the box.
    host: str = "0.0.0.0"
    port: int = 8000

    # Allowed CORS origins for the Vite dev server (port 5173) and a typical
    # React dev server (port 3000).  Extend for additional frontend origins.
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # OTel service name used in trace/metric instrumentation for this process.
    otel_service_name: str = "api-service"

    # Standard Python logging level.  Override with API_LOG_LEVEL=DEBUG.
    log_level: str = "INFO"

    # Pydantic-settings v2 model_config: env prefix + .env file loading.
    # ``extra="ignore"`` means unknown env vars (e.g. unrelated system vars) are
    # silently ignored rather than raising validation errors.
    model_config = {"env_prefix": "API_", "env_file": ".env", "extra": "ignore"}


# Module-level singleton: imported throughout the API service.
# Constructed once at import time so all submodules share the same config.
# Tests can monkeypatch attributes on this instance to override settings.
settings = Settings()
