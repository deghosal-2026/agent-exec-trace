"""Pydantic-based settings for the analytics service.

All configuration is driven by environment variables with the ``ANALYTICS_``
prefix, enabling twelve-factor-app-style deployment.  A local ``.env`` file is
also loaded when present for development convenience.

**Threshold rationale summary:**

Most detector thresholds have been chosen through empirical observation of
agent trace data.  They are intentionally conservative (high thresholds) to
minimize false positives.  Each threshold can be tuned independently via
its own environment variable.

For production, operators should:
1. Start with the defaults.
2. Observe the anomaly fire rate per detector via the validation reports.
3. Adjust thresholds where the fire rate exceeds 5-10% (indicating too
   many false positives) or where critical anomalies are missed.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Runtime configuration for the analytics ingestion service.

    Every setting is overridable via an ``ANALYTICS_<UPPERCASE_NAME>``
    environment variable.  See ``model_config`` at the bottom for the
    prefix and env-file configuration.

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

    # --- Database ---
    db_dsn: str = "postgresql://analytics:analytics@localhost:5432/analytics"
    db_pool_min_size: int = 2
    db_pool_max_size: int = 10

    # --- Trace sources ---
    jaeger_endpoint: str = "http://localhost:16686"
    collector_endpoint: str = "http://localhost:4318"
    trace_query_services: tuple[str, ...] = ("demo-agent",)

    # --- Worker ---
    polling_interval_seconds: int = 30

    # --- Legacy detector thresholds (kept for backward compat) ---
    # These are referenced by the original LoopDetector, RetryStormDetector,
    # and CostSpikeDetector which pre-date the settings expansion.
    loop_threshold: int = 5
    retry_threshold: int = 5
    cost_threshold_usd: float = 5.0

    # --- Observability ---
    otel_metric_export_interval: int = 60
    otel_service_name: str = "analytics-service"

    # --- Logging ---
    log_level: str = "INFO"
    log_format: str = "json"

    # --- Alerting ---
    webhook_url: str = ""

    # --- LLM client settings (MLX / OpenAI-compatible endpoint) ---
    llm_base_url: str = "http://127.0.0.1:8000/v1"
    llm_api_key: str = "omlx-test"
    llm_chat_model: str = "Qwen3.5-9B-MLX-4bit"
    llm_embed_model: str = "all-MiniLM-L6-v2"
    llm_timeout_seconds: float = 30.0

    # --- Tool execution detector thresholds ---
    # Why these values?  A 4-tool pattern repeating twice is a strong signal
    # of a loop (e.g., read→search→read→search).  Argument loops are stronger
    # (same tool + same args), so the threshold is lower (3).
    detector_pattern_loop_window: int = 4
    detector_argument_loop_threshold: int = 3
    # 30% error rate across all tool calls is well above normal (<5%).
    detector_tool_error_rate_pct: float = 30.0
    detector_specific_tool_error_pct: float = 30.0
    # A tool call taking 3x the average of its peers is suspicious.
    detector_tool_latency_multiplier: float = 3.0
    # 60 seconds is a generous tool timeout; real tools should finish faster.
    detector_tool_timeout_seconds: float = 60.0
    # 3 identical calls (same tool + same args + same result) are redundant.
    detector_redundant_tool_threshold: int = 3

    # --- Cost & resource detector thresholds ---
    # 2x baseline: a run costing twice the version average is worth a look.
    detector_cost_baseline_multiplier: float = 2.0
    # Need at least 5 runs to compute a meaningful baseline average.
    detector_cost_min_baseline_runs: int = 5
    detector_cost_vs_baseline_multiplier: float = 2.0
    # $0.50 per tool call is considered expensive for a single tool invocation.
    detector_cost_per_tool_high: float = 0.50
    # 20 tool calls for a successful run suggests inefficiency.
    detector_cost_efficiency_max_calls: int = 20
    # 3x token growth from early to late half of the run is an explosion.
    detector_token_explosion_multiplier: float = 3.0
    detector_per_tool_cost_multiplier: float = 2.0
    detector_wasted_tool_threshold: int = 3

    # --- Runtime & completion detector thresholds ---
    # 5x the average duration is definitely anomalous.
    detector_run_duration_multiplier: float = 5.0
    detector_step_efficiency_max_calls: int = 20
    # 30 seconds of idle time between consecutive spans is a long gap.
    detector_inactivity_gap_seconds: float = 30.0

    # --- Retry & recovery detector thresholds ---
    # 3 transient retries is common; beyond that it's worth flagging.
    detector_transient_retry_threshold: int = 3
    # 5 extra tool calls after the first error is a complex recovery.
    detector_recovery_path_threshold: int = 5

    # --- Interaction & control detector thresholds ---
    # 3+ human interventions per run suggests the agent is struggling.
    detector_intervention_frequency_threshold: int = 3
    # 2x the baseline escalation rate is anomalous.
    detector_escalation_rate_multiplier: float = 2.0
    # 60 seconds to approve is a long human-in-the-loop delay.
    detector_approval_latency_seconds: float = 60.0
    # 2+ repeated human overrides suggests agent/human misalignment.
    detector_intervention_rejection_threshold: int = 2

    # --- Output quality detector thresholds ---
    # 50 chars is about one sentence — anything less is suspiciously short.
    detector_low_output_min_chars: int = 50
    # 3x deviation from baseline output length is significant drift.
    detector_output_drift_multiplier: float = 3.0

    # --- Cross-run pattern detector thresholds ---
    # 3+ distinct anomaly types firing on the same run is a cluster.
    detector_anomaly_cluster_min_types: int = 3
    # Need at least 5 runs to assess frequency normality.
    detector_run_frequency_min_runs: int = 5
    detector_run_frequency_max_multiplier: float = 3.0

    # --- Per-detector on/off toggle ---
    # Set via ANALYTICS_DETECTOR_DISABLED='["loop","retry_storm"]' to disable
    # specific detectors.  Detectors not in this set are enabled by default.
    detector_disabled: set[str] = set()

    # Pydantic model config: reads ANALYTICS_* env vars, supports .env file,
    # ignores extra env vars to avoid crashes from unrelated variables.
    model_config = {"env_prefix": "ANALYTICS_", "env_file": ".env", "extra": "ignore"}


# Module-level singleton: imported throughout the service.
# All modules import this single instance, ensuring consistent config.
settings = Settings()