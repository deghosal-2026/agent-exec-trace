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

    db_dsn: str = "postgresql://analytics:analytics@localhost:5432/analytics"
    db_pool_min_size: int = 2
    db_pool_max_size: int = 10

    host: str = "0.0.0.0"
    port: int = 8000

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    otel_service_name: str = "api-service"

    log_level: str = "INFO"

    model_config = {"env_prefix": "API_", "env_file": ".env", "extra": "ignore"}


# Module-level singleton: imported throughout the API service.
settings = Settings()