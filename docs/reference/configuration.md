# Configuration Reference

This document covers the full configuration surface for all four services in the
agent-exec-trace monorepo: the Python SDK, Analytics service, API service, and
Web application.

---

## Quick-Reference: All Environment Variables

| Service | Env Var | Default | Description |
|---|---|---|---|
| SDK | `AET_SERVICE_NAME` | `agent-exec-trace` | OTel service name |
| SDK | `AET_OTLP_ENDPOINT` | `http://localhost:4317` | OTLP gRPC endpoint |
| SDK | `AET_DEFAULT_AGENT_NAME` | `unnamed_agent` | Fallback agent name |
| SDK | `AET_DEFAULT_AGENT_VERSION` | *(none)* | Fallback agent version |
| SDK | `AET_DEFAULT_WORKLOAD_TYPE` | *(none)* | Fallback workload classification |
| SDK | `AET_REDACTION_MODE` | `metadata_only` | Privacy mode (`metadata_only`, `truncated`, `hashed`) |
| SDK | `AET_CAPTURE_PROMPTS` | `false` | Capture model prompts |
| SDK | `AET_CAPTURE_TOOL_ARGS` | `false` | Capture tool arguments |
| SDK | `AET_CAPTURE_MEMORY` | `false` | Capture memory content |
| SDK | `AET_HASH_SALT` | `""` | Salt for hashed content |
| SDK | `AET_TRUNCATE_AT` | `512` | Max chars in truncated mode |
| Analytics | `ANALYTICS_DB_DSN` | `postgresql://analytics:analytics@localhost:5432/analytics` | PostgreSQL connection string |
| Analytics | `ANALYTICS_DB_POOL_MIN_SIZE` | `2` | Min DB connection pool size |
| Analytics | `ANALYTICS_DB_POOL_MAX_SIZE` | `10` | Max DB connection pool size |
| Analytics | `ANALYTICS_JAEGER_ENDPOINT` | `http://localhost:16686` | Jaeger API base URL |
| Analytics | `ANALYTICS_COLLECTOR_ENDPOINT` | `http://localhost:4318` | OTLP HTTP collector endpoint |
| Analytics | `ANALYTICS_TRACE_QUERY_SERVICE` | `demo-agent` | Jaeger service name to query for traces |
| Analytics | `ANALYTICS_POLLING_INTERVAL_SECONDS` | `30` | Worker trace fetch interval (s) |
| Analytics | `ANALYTICS_LOOP_THRESHOLD` | `5` | Consecutive identical tool calls → loop anomaly |
| Analytics | `ANALYTICS_RETRY_THRESHOLD` | `5` | Total retries → retry storm anomaly |
| Analytics | `ANALYTICS_COST_THRESHOLD_USD` | `5.0` | Absolute cost threshold for spike detection |
| Analytics | `ANALYTICS_OTEL_METRIC_EXPORT_INTERVAL` | `60` | OTel metric export interval (s) |
| Analytics | `ANALYTICS_OTEL_SERVICE_NAME` | `analytics-service` | OTel service name for analytics itself |
| Analytics | `ANALYTICS_LOG_LEVEL` | `INFO` | Logging level |
| Analytics | `ANALYTICS_LOG_FORMAT` | `json` | Log format (`json` or `text`) |
| Analytics | `ANALYTICS_WEBHOOK_URL` | `""` | Webhook URL for anomaly alerts |
| Analytics | `ANALYTICS_LLM_BASE_URL` | `http://127.0.0.1:8000/v1` | LLM API base URL (OpenAI-compatible) |
| Analytics | `ANALYTICS_LLM_API_KEY` | `omlx-test` | LLM API key |
| Analytics | `ANALYTICS_LLM_CHAT_MODEL` | `Qwen3.5-4B-4bit` | LLM chat model name |
| Analytics | `ANALYTICS_LLM_EMBED_MODEL` | `all-MiniLM-L6-v2` | LLM embedding model name |
| Analytics | `ANALYTICS_LLM_TIMEOUT_SECONDS` | `30.0` | LLM request timeout (s) |
| Analytics | `ANALYTICS_DETECTOR_PATTERN_LOOP_WINDOW` | `4` | Tool pattern window for loop detection |
| Analytics | `ANALYTICS_DETECTOR_ARGUMENT_LOOP_THRESHOLD` | `3` | Same tool+args repetition → argument loop |
| Analytics | `ANALYTICS_DETECTOR_TOOL_ERROR_RATE_PCT` | `30.0` | Error rate % across all tool calls |
| Analytics | `ANALYTICS_DETECTOR_SPECIFIC_TOOL_ERROR_PCT` | `30.0` | Error rate % for a specific tool |
| Analytics | `ANALYTICS_DETECTOR_TOOL_LATENCY_MULTIPLIER` | `3.0` | Multiplier of peer average → latency anomaly |
| Analytics | `ANALYTICS_DETECTOR_TOOL_TIMEOUT_SECONDS` | `60.0` | Absolute tool timeout threshold (s) |
| Analytics | `ANALYTICS_DETECTOR_REDUNDANT_TOOL_THRESHOLD` | `3` | Identical calls (tool+args+result) → redundant |
| Analytics | `ANALYTICS_DETECTOR_COST_BASELINE_MULTIPLIER` | `2.0` | Multiplier of version avg → cost anomaly |
| Analytics | `ANALYTICS_DETECTOR_COST_MIN_BASELINE_RUNS` | `5` | Min runs for a meaningful baseline |
| Analytics | `ANALYTICS_DETECTOR_COST_VS_BASELINE_MULTIPLIER` | `2.0` | Cost vs. baseline multiplier |
| Analytics | `ANALYTICS_DETECTOR_COST_PER_TOOL_HIGH` | `0.50` | Per-tool-call cost considered expensive (USD) |
| Analytics | `ANALYTICS_DETECTOR_COST_EFFICIENCY_MAX_CALLS` | `20` | Max tool calls for a successful run |
| Analytics | `ANALYTICS_DETECTOR_TOKEN_EXPLOSION_MULTIPLIER` | `3.0` | Token growth early→late half of run |
| Analytics | `ANALYTICS_DETECTOR_PER_TOOL_COST_MULTIPLIER` | `2.0` | Per-tool cost multiplier |
| Analytics | `ANALYTICS_DETECTOR_WASTED_TOOL_THRESHOLD` | `3` | Wasted/inconsequential tool calls |
| Analytics | `ANALYTICS_DETECTOR_RUN_DURATION_MULTIPLIER` | `5.0` | Multiplier of avg run duration |
| Analytics | `ANALYTICS_DETECTOR_STEP_EFFICIENCY_MAX_CALLS` | `20` | Max tool calls per step |
| Analytics | `ANALYTICS_DETECTOR_INACTIVITY_GAP_SECONDS` | `30.0` | Idle time between spans → gap anomaly (s) |
| Analytics | `ANALYTICS_DETECTOR_TRANSIENT_RETRY_THRESHOLD` | `3` | Transient retries before flagging |
| Analytics | `ANALYTICS_DETECTOR_RECOVERY_PATH_THRESHOLD` | `5` | Extra tool calls after first error → complex recovery |
| Analytics | `ANALYTICS_DETECTOR_INTERVENTION_FREQUENCY_THRESHOLD` | `3` | Human interventions per run → struggling agent |
| Analytics | `ANALYTICS_DETECTOR_ESCALATION_RATE_MULTIPLIER` | `2.0` | Multiplier of baseline escalation rate |
| Analytics | `ANALYTICS_DETECTOR_APPROVAL_LATENCY_SECONDS` | `60.0` | Human-in-the-loop approval delay (s) |
| Analytics | `ANALYTICS_DETECTOR_INTERVENTION_REJECTION_THRESHOLD` | `2` | Repeated human overrides → misalignment |
| Analytics | `ANALYTICS_DETECTOR_LOW_OUTPUT_MIN_CHARS` | `50` | Minimum output length (chars) |
| Analytics | `ANALYTICS_DETECTOR_OUTPUT_DRIFT_MULTIPLIER` | `3.0` | Output length deviation from baseline |
| Analytics | `ANALYTICS_DETECTOR_ANOMALY_CLUSTER_MIN_TYPES` | `3` | Distinct anomaly types → cluster |
| Analytics | `ANALYTICS_DETECTOR_RUN_FREQUENCY_MIN_RUNS` | `5` | Min runs for frequency assessment |
| Analytics | `ANALYTICS_DETECTOR_RUN_FREQUENCY_MAX_MULTIPLIER` | `3.0` | Max multiplier of normal run frequency |
| Analytics | `ANALYTICS_DETECTOR_DISABLED` | `set()` | Set of disabled anomaly types (JSON array) |
| API | `API_DB_DSN` | `postgresql://analytics:analytics@localhost:5432/analytics` | PostgreSQL connection string |
| API | `API_DB_POOL_MIN_SIZE` | `2` | Min DB connection pool size |
| API | `API_DB_POOL_MAX_SIZE` | `10` | Max DB connection pool size |
| API | `API_HOST` | `0.0.0.0` | HTTP server bind address |
| API | `API_PORT` | `8000` | HTTP server listen port |
| API | `API_CORS_ORIGINS` | `["http://localhost:5173", "http://localhost:3000"]` | Allowed CORS origins (JSON array) |
| API | `API_OTEL_SERVICE_NAME` | `api-service` | OTel service name for the API |
| API | `API_LOG_LEVEL` | `INFO` | Logging level |
| Web | `VITE_API_URL` | `""` (empty) | API base URL for the frontend |
| Web | `VITE_PROXY_TARGET` | *(falls back to `VITE_API_URL` then `http://localhost:8000`)* | Vite dev server proxy target |

---

## 1. SDK Configuration

**Source:** `packages/python-sdk/src/agent_exec_trace/config.py`

The SDK uses a **frozen (immutable) dataclass** as its central configuration object.
A single `SDKConfig` instance can be shared safely across threads, adapters, and span
helpers without copy-on-write concerns.

The recommended entry point is:

```python
from agent_exec_trace.config import SDKConfig, default_config
from agent_exec_trace.tracer import configure_tracing

# Safe-by-default (metadata-only privacy posture)
configure_tracing(default_config())

# Full control
cfg = SDKConfig(
    service_name="my-agent",
    redaction=RedactionConfig(mode=PrivacyMode.TRUNCATED, capture_tool_args=True),
)
configure_tracing(cfg)
```

### SDKConfig Fields

| Field | Env Var | Python Type | Default | Description |
|---|---|---|---|---|
| `service_name` | `AET_SERVICE_NAME` | `str` | `"agent-exec-trace"` | OTel service name attached to the trace resource. Shows up as the service column in Jaeger/Tempo and as the `service.name` resource attribute on every exported span. |
| `otlp_endpoint` | `AET_OTLP_ENDPOINT` | `str` | `"http://localhost:4317"` | OTLP gRPC endpoint for the OpenTelemetry exporter. |
| `default_agent_name` | `AET_DEFAULT_AGENT_NAME` | `str` | `"unnamed_agent"` | Fallback agent name used when a run provides none. |
| `default_agent_version` | `AET_DEFAULT_AGENT_VERSION` | `str \| None` | `None` | Fallback agent version when a run provides none. |
| `default_workload_type` | `AET_DEFAULT_WORKLOAD_TYPE` | `str \| None` | `None` | Fallback workload classification when none is given. |
| `redaction` | *(composite)* | `RedactionConfig` | `RedactionConfig()` | Privacy and content-capture policy. See below. |

### Module Constants

The module exposes two canonical constants referenced by tests and docs:

| Constant | Value | Purpose |
|---|---|---|
| `DEFAULT_SERVICE_NAME` | `"agent-exec-trace"` | Default OTel service name |
| `DEFAULT_OTLP_ENDPOINT` | `"http://localhost:4317"` | Default OTLP gRPC endpoint |

### RedactionConfig

**Source:** `packages/python-sdk/src/agent_exec_trace/redact.py`

A frozen dataclass that controls how (and whether) sensitive content reaches span
payloads. Uses a **double-gate** design: the `PrivacyMode` acts as a global gate,
and per-field flags (`capture_prompts`, `capture_tool_args`, `capture_memory`)
act as field-specific gates. Both must pass for content to be recorded.

#### PrivacyMode (`str, Enum`)

| Member | Value | Behavior |
|---|---|---|
| `METADATA_ONLY` | `"metadata_only"` | **Default.** No content ever written to spans. Structural telemetry (timings, counts, IDs) is still emitted. `apply()` returns `None` immediately. |
| `TRUNCATED` | `"truncated"` | Content is kept but capped at `truncate_at` characters. A `"[...]"` marker is appended when truncation occurs so consumers can distinguish naturally-short values from cut-off ones. |
| `HASHED` | `"hashed"` | Content is replaced by a **salted** SHA-256 hex digest — deterministic, non-reversible, and useful for correlating repeated payloads in analytics without revealing the payload itself. |

#### RedactionConfig Fields

| Field | Env Var | Python Type | Default | Description |
|---|---|---|---|---|
| `mode` | `AET_REDACTION_MODE` | `PrivacyMode` | `METADATA_ONLY` | Overall privacy mode. |
| `capture_prompts` | `AET_CAPTURE_PROMPTS` | `bool` | `False` | When `True` AND mode is not metadata-only, model prompts are captured. |
| `capture_tool_args` | `AET_CAPTURE_TOOL_ARGS` | `bool` | `False` | When `True` AND mode is not metadata-only, tool arguments are captured. |
| `capture_memory` | `AET_CAPTURE_MEMORY` | `bool` | `False` | When `True` AND mode is not metadata-only, memory content is captured. |
| `truncate_at` | `AET_TRUNCATE_AT` | `int` | `512` | Max characters (inclusive) kept in truncated mode. Values longer than this are sliced and the `"[...]"` marker is appended. |
| `hash_salt` | `AET_HASH_SALT` | `str` | `""` | Salt prepended to values before hashing in hashed mode. Different salts produce different digests for the same plaintext. |

#### Double-Gate Rationale

The original implementation had a single flag controlling all content paths —
enabling prompt capture could accidentally leak tool arguments or memory contents.
The double-gate design enforces:

1. **Field opt-in** (`capture_prompts`, `capture_tool_args`, `capture_memory`):
   enables capture for ONE specific field without enabling others.
2. **Mode gate** (`PrivacyMode`): metadata-only turns everything off globally.

Both must pass for content to reach a span.

---

## 2. Analytics Configuration

**Source:** `services/analytics/src/analytics/config.py`

The analytics service uses a Pydantic `BaseSettings` class with the `ANALYTICS_`
prefix for all environment variables. A local `.env` file is also loaded when
present for development convenience. The module exports a singleton `settings`
instance imported throughout the service.

### Database

| Field | Env Var | Default | Description |
|---|---|---|---|
| `db_dsn` | `ANALYTICS_DB_DSN` | `postgresql://analytics:analytics@localhost:5432/analytics` | PostgreSQL connection string for the analytics database. |
| `db_pool_min_size` | `ANALYTICS_DB_POOL_MIN_SIZE` | `2` | Minimum connection pool size. |
| `db_pool_max_size` | `ANALYTICS_DB_POOL_MAX_SIZE` | `10` | Maximum connection pool size. |

### Trace Sources

| Field | Env Var | Default | Description |
|---|---|---|---|
| `jaeger_endpoint` | `ANALYTICS_JAEGER_ENDPOINT` | `http://localhost:16686` | Base URL for the Jaeger API (trace fetching). |
| `collector_endpoint` | `ANALYTICS_COLLECTOR_ENDPOINT` | `http://localhost:4318` | OTLP HTTP endpoint for the OpenTelemetry Collector. |
| `trace_query_service` | `ANALYTICS_TRACE_QUERY_SERVICE` | `demo-agent` | The Jaeger service name to query for traces. |

### Worker

| Field | Env Var | Default | Description |
|---|---|---|---|
| `polling_interval_seconds` | `ANALYTICS_POLLING_INTERVAL_SECONDS` | `30` | How often (in seconds) the worker fetches new traces. |

### Legacy Detector Thresholds

These thresholds are referenced by the original `LoopDetector`,
`RetryStormDetector`, and `CostSpikeDetector` which pre-date the expanded
detector configuration. Kept for backward compatibility.

| Field | Env Var | Default | Description |
|---|---|---|---|
| `loop_threshold` | `ANALYTICS_LOOP_THRESHOLD` | `5` | Consecutive identical tool calls that trigger a loop anomaly. |
| `retry_threshold` | `ANALYTICS_RETRY_THRESHOLD` | `5` | Total retries in a run that trigger a retry storm anomaly. |
| `cost_threshold_usd` | `ANALYTICS_COST_THRESHOLD_USD` | `5.0` | Absolute cost threshold (USD) for cost spike detection. |

### Observability

| Field | Env Var | Default | Description |
|---|---|---|---|
| `otel_metric_export_interval` | `ANALYTICS_OTEL_METRIC_EXPORT_INTERVAL` | `60` | OTel metric export interval in seconds. |
| `otel_service_name` | `ANALYTICS_OTEL_SERVICE_NAME` | `analytics-service` | OTel service name for the analytics service itself. |

### Logging

| Field | Env Var | Default | Description |
|---|---|---|---|
| `log_level` | `ANALYTICS_LOG_LEVEL` | `INFO` | Logging level (`INFO`, `DEBUG`, etc.). |
| `log_format` | `ANALYTICS_LOG_FORMAT` | `json` | Structured log format (`json` or `text`). |

### Alerting

| Field | Env Var | Default | Description |
|---|---|---|---|
| `webhook_url` | `ANALYTICS_WEBHOOK_URL` | `""` | Optional webhook URL for anomaly alerts. Empty string disables webhook alerts. |

### LLM Client

Settings for the MLX / OpenAI-compatible LLM endpoint used by the analytics service.

| Field | Env Var | Default | Description |
|---|---|---|---|
| `llm_base_url` | `ANALYTICS_LLM_BASE_URL` | `http://127.0.0.1:8000/v1` | LLM API base URL (OpenAI-compatible endpoint). |
| `llm_api_key` | `ANALYTICS_LLM_API_KEY` | `omlx-test` | LLM API key. |
| `llm_chat_model` | `ANALYTICS_LLM_CHAT_MODEL` | `Qwen3.5-4B-4bit` | LLM chat model name. |
| `llm_embed_model` | `ANALYTICS_LLM_EMBED_MODEL` | `all-MiniLM-L6-v2` | LLM embedding model name. |
| `llm_timeout_seconds` | `ANALYTICS_LLM_TIMEOUT_SECONDS` | `30.0` | LLM request timeout in seconds. |

### Detector Thresholds

All thresholds below have been chosen through empirical observation of agent trace
data. They are intentionally conservative (high thresholds) to minimize false
positives. Each threshold can be tuned independently via its own environment variable.

For production tuning: start with the defaults, observe the anomaly fire rate per
detector via validation reports, then adjust thresholds where the fire rate exceeds
5–10% (indicating too many false positives) or where critical anomalies are missed.

#### Tool Execution Detectors

| Field | Env Var | Default | Rationale |
|---|---|---|---|
| `detector_pattern_loop_window` | `ANALYTICS_DETECTOR_PATTERN_LOOP_WINDOW` | `4` | A 4-tool pattern repeating twice is a strong signal of a loop (e.g., `read → search → read → search`). |
| `detector_argument_loop_threshold` | `ANALYTICS_DETECTOR_ARGUMENT_LOOP_THRESHOLD` | `3` | Argument loops are stronger (same tool + same args), so the threshold is lower than pattern loops. |
| `detector_tool_error_rate_pct` | `ANALYTICS_DETECTOR_TOOL_ERROR_RATE_PCT` | `30.0` | 30% error rate across all tool calls is well above normal (<5%). |
| `detector_specific_tool_error_pct` | `ANALYTICS_DETECTOR_SPECIFIC_TOOL_ERROR_PCT` | `30.0` | 30% error rate for a specific tool indicates a failing integration. |
| `detector_tool_latency_multiplier` | `ANALYTICS_DETECTOR_TOOL_LATENCY_MULTIPLIER` | `3.0` | A tool call taking 3× the average of its peers is suspicious. |
| `detector_tool_timeout_seconds` | `ANALYTICS_DETECTOR_TOOL_TIMEOUT_SECONDS` | `60.0` | 60 seconds is a generous tool timeout; real tools should finish faster. |
| `detector_redundant_tool_threshold` | `ANALYTICS_DETECTOR_REDUNDANT_TOOL_THRESHOLD` | `3` | 3 identical calls (same tool + same args + same result) are redundant. |

#### Cost & Resource Detectors

| Field | Env Var | Default | Rationale |
|---|---|---|---|
| `detector_cost_baseline_multiplier` | `ANALYTICS_DETECTOR_COST_BASELINE_MULTIPLIER` | `2.0` | A run costing 2× the version average is worth investigating. |
| `detector_cost_min_baseline_runs` | `ANALYTICS_DETECTOR_COST_MIN_BASELINE_RUNS` | `5` | Need at least 5 runs to compute a meaningful baseline average. |
| `detector_cost_vs_baseline_multiplier` | `ANALYTICS_DETECTOR_COST_VS_BASELINE_MULTIPLIER` | `2.0` | Cost vs. baseline comparison multiplier. |
| `detector_cost_per_tool_high` | `ANALYTICS_DETECTOR_COST_PER_TOOL_HIGH` | `0.50` | \$0.50 per tool call is considered expensive for a single tool invocation. |
| `detector_cost_efficiency_max_calls` | `ANALYTICS_DETECTOR_COST_EFFICIENCY_MAX_CALLS` | `20` | 20 tool calls for a successful run suggests inefficiency. |
| `detector_token_explosion_multiplier` | `ANALYTICS_DETECTOR_TOKEN_EXPLOSION_MULTIPLIER` | `3.0` | 3× token growth from early to late half of the run is an explosion. |
| `detector_per_tool_cost_multiplier` | `ANALYTICS_DETECTOR_PER_TOOL_COST_MULTIPLIER` | `2.0` | 2× the per-tool cost average indicates expensive tool usage. |
| `detector_wasted_tool_threshold` | `ANALYTICS_DETECTOR_WASTED_TOOL_THRESHOLD` | `3` | 3+ inconsequential tool calls suggest wasted effort. |

#### Runtime & Completion Detectors

| Field | Env Var | Default | Rationale |
|---|---|---|---|
| `detector_run_duration_multiplier` | `ANALYTICS_DETECTOR_RUN_DURATION_MULTIPLIER` | `5.0` | 5× the average duration is definitely anomalous. |
| `detector_step_efficiency_max_calls` | `ANALYTICS_DETECTOR_STEP_EFFICIENCY_MAX_CALLS` | `20` | More than 20 tool calls per step suggests inefficiency. |
| `detector_inactivity_gap_seconds` | `ANALYTICS_DETECTOR_INACTIVITY_GAP_SECONDS` | `30.0` | 30 seconds of idle time between consecutive spans is a long gap. |

#### Retry & Recovery Detectors

| Field | Env Var | Default | Rationale |
|---|---|---|---|
| `detector_transient_retry_threshold` | `ANALYTICS_DETECTOR_TRANSIENT_RETRY_THRESHOLD` | `3` | 3 transient retries is common; beyond that it's worth flagging. |
| `detector_recovery_path_threshold` | `ANALYTICS_DETECTOR_RECOVERY_PATH_THRESHOLD` | `5` | 5 extra tool calls after the first error is a complex recovery. |

#### Interaction & Control Detectors

| Field | Env Var | Default | Rationale |
|---|---|---|---|
| `detector_intervention_frequency_threshold` | `ANALYTICS_DETECTOR_INTERVENTION_FREQUENCY_THRESHOLD` | `3` | 3+ human interventions per run suggests the agent is struggling. |
| `detector_escalation_rate_multiplier` | `ANALYTICS_DETECTOR_ESCALATION_RATE_MULTIPLIER` | `2.0` | 2× the baseline escalation rate is anomalous. |
| `detector_approval_latency_seconds` | `ANALYTICS_DETECTOR_APPROVAL_LATENCY_SECONDS` | `60.0` | 60 seconds to approve is a long human-in-the-loop delay. |
| `detector_intervention_rejection_threshold` | `ANALYTICS_DETECTOR_INTERVENTION_REJECTION_THRESHOLD` | `2` | 2+ repeated human overrides suggests agent/human misalignment. |

#### Output Quality Detectors

| Field | Env Var | Default | Rationale |
|---|---|---|---|
| `detector_low_output_min_chars` | `ANALYTICS_DETECTOR_LOW_OUTPUT_MIN_CHARS` | `50` | 50 chars is about one sentence — anything less is suspiciously short. |
| `detector_output_drift_multiplier` | `ANALYTICS_DETECTOR_OUTPUT_DRIFT_MULTIPLIER` | `3.0` | 3× deviation from baseline output length is significant drift. |

#### Cross-Run Pattern Detectors

| Field | Env Var | Default | Rationale |
|---|---|---|---|
| `detector_anomaly_cluster_min_types` | `ANALYTICS_DETECTOR_ANOMALY_CLUSTER_MIN_TYPES` | `3` | 3+ distinct anomaly types firing on the same run is a cluster. |
| `detector_run_frequency_min_runs` | `ANALYTICS_DETECTOR_RUN_FREQUENCY_MIN_RUNS` | `5` | Need at least 5 runs to assess frequency normality. |
| `detector_run_frequency_max_multiplier` | `ANALYTICS_DETECTOR_RUN_FREQUENCY_MAX_MULTIPLIER` | `3.0` | A run firing at 3× the normal frequency is anomalous. |

### Per-Detector Toggle

| Field | Env Var | Default | Description |
|---|---|---|---|
| `detector_disabled` | `ANALYTICS_DETECTOR_DISABLED` | `set()` | Set of anomaly type names to disable. Set via a JSON array, e.g. `ANALYTICS_DETECTOR_DISABLED='["loop","retry_storm"]'`. Detectors not in this set are enabled by default. |

---

## 3. API Configuration

**Source:** `services/api/src/api/config.py`

The API service uses a Pydantic `BaseSettings` class with the `API_` prefix for
all environment variables. A local `.env` file is also loaded when present.
The module exports a singleton `settings` instance imported throughout the service.

| Field | Env Var | Python Type | Default | Description |
|---|---|---|---|---|
| `db_dsn` | `API_DB_DSN` | `str` | `postgresql://analytics:analytics@localhost:5432/analytics` | PostgreSQL connection string. Override for staging/production environments. |
| `db_pool_min_size` | `API_DB_POOL_MIN_SIZE` | `int` | `2` | Minimum DB connection pool size. Conservative default for local dev and CI. Scale up in production. |
| `db_pool_max_size` | `API_DB_POOL_MAX_SIZE` | `int` | `10` | Maximum DB connection pool size. |
| `host` | `API_HOST` | `str` | `"0.0.0.0"` | Host address the HTTP server binds to. Bind to all interfaces so Docker port mapping works out of the box. |
| `port` | `API_PORT` | `int` | `8000` | Port the HTTP server listens on. |
| `cors_origins` | `API_CORS_ORIGINS` | `list[str]` | `["http://localhost:5173", "http://localhost:3000"]` | Allowed CORS origins. Covers the Vite dev server (port 5173) and a typical React dev server (port 3000). Extend for additional frontend origins. |
| `otel_service_name` | `API_OTEL_SERVICE_NAME` | `str` | `"api-service"` | OTel service name used in trace/metric instrumentation for this process. |
| `log_level` | `API_LOG_LEVEL` | `str` | `"INFO"` | Standard Python logging level. Override with `API_LOG_LEVEL=DEBUG` for development. |

The Pydantic-settings v2 `model_config` uses `extra="ignore"` so unknown
environment variables (e.g., unrelated system vars) are silently ignored rather
than raising validation errors.

---

## 4. Web Application Configuration

**Source:** `apps/web/vite.config.ts`, `apps/web/.env.example`

The web frontend is a Vite + React application. Configuration is driven by
Vite environment variables.

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `VITE_API_URL` | `""` (empty) | The base URL for the API backend. When empty, the app uses relative `/api` paths and relies on the Vite dev server proxy (in development) or a reverse proxy (in production). |
| `VITE_PROXY_TARGET` | Falls back to `VITE_API_URL`, then `http://localhost:8000` | Override for the Vite dev server proxy target. Only relevant in development. |

### `.env.example`

```
VITE_API_URL=http://localhost:8000
```

Copy `apps/web/.env.example` to `apps/web/.env` and adjust `VITE_API_URL` to
match your API deployment.

### Vite Dev Server Proxy

In development, the Vite dev server (port `5173`) proxies all `/api` requests to
the backend:

```ts
const proxyTarget =
  process.env.VITE_PROXY_TARGET ||
  process.env.VITE_API_URL ||
  "http://localhost:8000";
```

The proxy chain resolves `VITE_PROXY_TARGET` first, then `VITE_API_URL`, then
falls back to `http://localhost:8000`. This means:

- In development, you can leave `VITE_API_URL` empty and the proxy will forward
  `/api/*` requests to `http://localhost:8000`.
- To proxy to a different backend, set `VITE_PROXY_TARGET` (takes highest
  priority) or `VITE_API_URL`.
- In production, set `VITE_API_URL` to the deployed API origin (e.g.
  `https://api.example.com`), and serve the built static assets through a CDN
  or reverse proxy.
