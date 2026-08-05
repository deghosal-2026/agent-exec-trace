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

    # --- LLM client settings (MLX / OpenAI-compatible endpoint) ---
    llm_base_url: str = "http://127.0.0.1:8000/v1"
    llm_api_key: str = "omlx-test"
    llm_chat_model: str = "Qwen3.5-4B-4bit"
    llm_embed_model: str = "all-MiniLM-L6-v2"
    llm_timeout_seconds: float = 30.0

    # --- Tool execution detector thresholds ---
    detector_pattern_loop_window: int = 4
    detector_argument_loop_threshold: int = 3
    detector_tool_error_rate_pct: float = 30.0
    detector_specific_tool_error_pct: float = 30.0
    detector_tool_latency_multiplier: float = 3.0
    detector_tool_timeout_seconds: float = 60.0
    detector_redundant_tool_threshold: int = 3

    # --- Cost & resource detector thresholds ---
    detector_cost_baseline_multiplier: float = 2.0
    detector_cost_min_baseline_runs: int = 5
    detector_cost_vs_baseline_multiplier: float = 2.0
    detector_cost_per_tool_high: float = 0.50
    detector_cost_efficiency_max_calls: int = 20
    detector_token_explosion_multiplier: float = 3.0
    detector_per_tool_cost_multiplier: float = 2.0
    detector_wasted_tool_threshold: int = 3

    # --- Runtime & completion detector thresholds ---
    detector_run_duration_multiplier: float = 5.0
    detector_step_efficiency_max_calls: int = 20
    detector_inactivity_gap_seconds: float = 30.0

    # --- Retry & recovery detector thresholds ---
    detector_transient_retry_threshold: int = 3
    detector_recovery_path_threshold: int = 5

    # --- Interaction & control detector thresholds ---
    detector_intervention_frequency_threshold: int = 3
    detector_escalation_rate_multiplier: float = 2.0
    detector_approval_latency_seconds: float = 60.0
    detector_intervention_rejection_threshold: int = 2

    # --- Output quality detector thresholds ---
    detector_low_output_min_chars: int = 50
    detector_output_drift_multiplier: float = 3.0

    # --- Cross-run pattern detector thresholds ---
    detector_anomaly_cluster_min_types: int = 3
    detector_run_frequency_min_runs: int = 5
    detector_run_frequency_max_multiplier: float = 3.0

    # --- Per-detector on/off toggle ---
    detector_disabled: set[str] = set()

    model_config = {"env_prefix": "ANALYTICS_", "env_file": ".env", "extra": "ignore"}


# Module-level singleton: imported throughout the service.
settings = Settings()
