"""Pydantic-based settings for the analytics service.

All configuration is driven by environment variables with the ``ANALYTICS_``
prefix, enabling twelve-factor-app-style deployment.  A local ``.env`` file is
also loaded when present for development convenience.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Runtime configuration for the analytics ingestion service.

    Attributes:
        db_dsn: PostgreSQL connection string for the analytics database.
        db_pool_min_size: minimum connection pool size.
        db_pool_max_size: maximum connection pool size.
        jaeger_endpoint: base URL for the Jaeger API (trace fetching).
        collector_endpoint: OTLP HTTP endpoint for the OpenTelemetry Collector.
        trace_query_service: the Jaeger service name to query for traces.
        polling_interval_seconds: how often the worker fetches new traces.
        loop_threshold: consecutive identical tool calls that trigger a loop anomaly.
        retry_threshold: total retries in a run that trigger a retry storm anomaly.
        cost_threshold_usd: absolute cost threshold for cost spike detection.
        otel_metric_export_interval: OTel metric export interval in seconds.
        otel_service_name: OTel service name for the analytics service itself.
        log_level: logging level (INFO, DEBUG, etc.).
        log_format: structured log format (json, text).
        webhook_url: optional webhook URL for anomaly alerts.
    """

    db_dsn: str = "postgresql://analytics:analytics@localhost:5432/analytics"
    db_pool_min_size: int = 2
    db_pool_max_size: int = 10

    jaeger_endpoint: str = "http://localhost:16686"
    collector_endpoint: str = "http://localhost:4318"
    trace_query_service: str = "demo-agent"

    polling_interval_seconds: int = 30
    loop_threshold: int = 5
    retry_threshold: int = 5
    cost_threshold_usd: float = 5.0

    otel_metric_export_interval: int = 60
    otel_service_name: str = "analytics-service"

    log_level: str = "INFO"
    log_format: str = "json"

    webhook_url: str = ""

    model_config = {"env_prefix": "ANALYTICS_", "env_file": ".env", "extra": "ignore"}


# Module-level singleton: imported throughout the service.
settings = Settings()