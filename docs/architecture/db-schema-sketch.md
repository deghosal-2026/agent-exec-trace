# DB Schema Sketch — Read-Model Tables

## `run_summaries`

Stores one row per processed run. Populated by `RunSummaryBuilder` during ingestion.

| Column | Type | Key | Notes |
|--------|------|-----|-------|
| `run_id` | text | PK | Unique run identifier |
| `agent_name` | text | Indexed | |
| `agent_version` | text | Indexed | Nullable |
| `workload_type` | text | Indexed | Nullable |
| `duration_ms` | bigint | | |
| `total_tool_calls` | int | | |
| `total_retries` | int | | |
| `total_interventions` | int | | |
| `estimated_cost` | float | | |
| `loop_count` | int | | |
| `loop_detected` | boolean | | |
| `status` | text | | e.g. "success", "error" |
| `root_span_id` | text | | |
| `trace_id` | text | | |
| `started_at` | timestamptz | | |
| `completed_at` | timestamptz | | |
| `created_at` | timestamptz | | Auto-set |
| `updated_at` | timestamptz | | Auto-set |

**Primary lookup keys:** `run_id`, `agent_name + agent_version`, `trace_id`

**Owned by:** Ingest path (`RunSummaryBuilder` + `persist_run_summary`)

---

## `anomalies`

Stores one row per detected anomaly across a run. Populated by the anomaly detectors (Milestone 6).

| Column | Type | Key | Notes |
|--------|------|-----|-------|
| `id` | text | PK | UUID hex |
| `run_id` | text | FK → run_summaries | |
| `agent_name` | text | Indexed | |
| `anomaly_type` | text | | "loop", "retry_storm", "cost_spike" |
| `severity` | text | | "warning", "critical" |
| `explanation` | text | | Human-readable explanation |
| `evidence` | jsonb | | Structured evidence dict |
| `detected_at` | timestamptz | | Auto-set |

**Primary lookup keys:** `id`, `run_id`, `agent_name + anomaly_type`

**Owned by:** Anomaly detectors (`LoopDetector`, `RetryStormDetector`, `CostSpikeDetector` → `persist_anomaly`)

---

## `fleet_rollups`

Pre-computed aggregate rows grouped by `(agent_name, agent_version, workload_type, period_start, period_end)`. Populated by `FleetRollupMaterializer`.

| Column | Type | Key | Notes |
|--------|------|-----|-------|
| `agent_name` | text | PK (composite) | |
| `agent_version` | text | PK (composite) | |
| `workload_type` | text | PK (composite) | |
| `period_start` | timestamptz | PK (composite) | |
| `period_end` | timestamptz | PK (composite) | |
| `total_runs` | int | | |
| `success_count` | int | | |
| `error_count` | int | | |
| `loop_count` | int | | |
| `anomaly_count` | int | | |
| `avg_duration_ms` | bigint | | |
| `avg_cost` | float | | |

**Primary lookup keys:** Composite `(agent_name, agent_version, workload_type, period_start, period_end)`

**Owned by:** `FleetRollupMaterializer` (Materializer)

---

## `version_cohort_summaries`

Pre-computed aggregate rows grouped by `(agent_name, agent_version)`. Populated by `VersionCohortMaterializer`.

| Column | Type | Key | Notes |
|--------|------|-----|-------|
| `agent_name` | text | PK (composite) | |
| `agent_version` | text | PK (composite) | |
| `total_runs` | int | | |
| `success_count` | int | | |
| `error_count` | int | | |
| `loop_count` | int | | |
| `anomaly_count` | int | | |
| `avg_duration_ms` | bigint | | |
| `avg_cost` | float | | |
| `total_tool_calls` | int | | |
| `total_retries` | int | | |
| `top_tools` | jsonb | | Dict of tool_name → count |

**Primary lookup keys:** Composite `(agent_name, agent_version)`

**Owned by:** `VersionCohortMaterializer` (Materializer)