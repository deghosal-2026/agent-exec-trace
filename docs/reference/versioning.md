# Versioning Rules

How `agent-exec-trace` uses version labels to group agent runs, power the Fleet
view, and enable cross-version comparison in the Version Compare feature.

## The required `agent_version` field

Every instrumented agent run **should** carry an `agent_version` string. This is
the primary cohorting dimension for the product. Without it, runs still
aggregate under the agent name, but there is nothing to compare and the Fleet
view shows a single flat cohort.

### How it flows through the system

1. **SDK**: The caller sets `agent_version` via `RunContext` (LangGraph adapter
   or raw Python decorator). The SDK writes it as two OTel span attributes:
   `gen_ai.agent.version` (standard OTel key) and `gen_ai.agent.version.label`
   (the stable key used by version-compare cohorts).

2. **Ingest**: The analytics worker reads `agent_version` from spans and stores
   it in `run_summaries.agent_version`.

3. **Materialization**: `VersionCohortMaterializer` groups
   `run_summaries` rows by `(agent_name, agent_version)` and writes one
   aggregate row per cohort into `version_cohort_summaries`.

4. **API**: The Fleet view serves all known versions per agent from
   `version_cohort_summaries`. The Version Compare endpoint fetches two cohort
   rows and computes per-run-average deltas.

5. **Web UI**: Fleet dropdowns list every version for the selected agent.
   Compare renders delta cards (cost, retry rate, success rate) and a
   tool-usage comparison table between the two chosen versions.

### SDK integration

**LangGraph adapter (TracedGraph / trace_graph)**:

```python
from agent_exec_trace.langgraph import trace_graph

graph = trace_graph(
    compiled_graph,
    agent_name="request-triage",
    agent_version="v1.3.0",
)
```

**LangGraph adapter (RunContext)**:

```python
from agent_exec_trace.context import RunContext
from agent_exec_trace.langgraph import TracedGraph

ctx = RunContext(
    agent_name="request-triage",
    agent_version="v1.3.0",
    workload_type="support",
)
traced = TracedGraph(compiled_graph, run_context=ctx)
```

**Raw Python decorator**:

```python
from agent_exec_trace.raw import trace_agent

@trace_agent("request-triage", agent_version="v1.3.0")
def run_agent(query: str) -> dict:
    ...
```

**Global default fallback**:

If every run in your deployment uses the same version, you can set a global
default via `AgentExecTraceConfig.default_agent_version` instead of threading
it through every call site. The per-run `RunContext.agent_version` always takes
precedence over the global default.

```python
from agent_exec_trace.config import AgentExecTraceConfig

AgentExecTraceConfig.default_agent_version = "v1.3.0"
```

## Optional secondary version dimensions

In addition to the primary `agent_version`, the SDK accepts three optional
attributes that provide finer-grained tracking. These are **not** used as
cohort dimensions in `v0.1.0` but are stored on spans and available for
future analytics:

| Attribute | Set via | Purpose |
|---|---|---|
| `prompt_version` | `RunContext(prompt_version=...)` | Track prompt template changes independently of agent code changes. |
| `model_version` | `RunContext(model=...)` | Identify which LLM model served the run (stored as `gen_ai.request.model`). |
| `tool_schema_version` | `RunContext(tool_schema_version=...)` | Track tool schema changes that affect agent behaviour. |

These are written as span attributes and persisted in `run_summaries`. They
can be queried directly in the database but do not currently appear in the
Fleet or Compare views.

## How version cohorts are formed

A version cohort is a group of runs that share the same `(agent_name,
agent_version, workload_type)` tuple. The analytics worker computes one
aggregate row per cohort in the `version_cohort_summaries` table with these
metrics:

| Metric | Source |
|---|---|
| `total_runs` | `COUNT(*)` |
| `success_count` / `error_count` | `COUNT(*) FILTER (WHERE status = ...)` |
| `loop_count` | `COUNT(*) FILTER (WHERE loop_detected = TRUE)` |
| `avg_duration_ms` | `AVG(duration_ms)` |
| `avg_cost` | `AVG(estimated_cost)` |
| `total_tool_calls` | `SUM(total_tool_calls)` |
| `total_retries` | `SUM(total_retries)` |
| `anomaly_count` | Correlated from `anomalies` table via `run_id` |
| `top_tools` | Dict of `tool_name → count` (JSONB) |

Cohorts exclude runs where `agent_version IS NULL` because un-versioned runs
cannot be meaningfully compared.

## How Version Compare works

The `/api/compare` endpoint accepts `agent_name`, `version_a`, and `version_b`.
It fetches the two cohort rows from `version_cohort_summaries` and computes
per-run-average deltas:

| Delta Card | Formula |
|---|---|
| **Cost Delta** | `avg_cost(Version B) − avg_cost(Version A)` |
| **Retry Rate Delta** | `avg_retries(Version B) − avg_retries(Version A)` |
| **Success Rate Delta** | `success_rate(Version B) − success_rate(Version A)` |

The tool-usage comparison is computed as `(tool_count / run_count)` for each
version and rendered as a per-tool delta table.

## Cohort size considerations

The analytics pipeline imposes no minimum cohort size, but the Version Compare
endpoint emits a warning when either cohort has **fewer than 5 runs**:

```
"warning": "sparse_cohorts",
"note": "One or both version cohorts have fewer than 5 runs. Deltas may not be statistically meaningful."
```

**Recommendation:** Aim for **≥30 runs** per cohort before drawing conclusions
from the comparison. Below 30 runs, a single outlier can dominate the
per-run average. This is a guideline, not a hard block — the comparison always
renders, but the sparse-cohort warning helps flag low-confidence deltas.

## What happens without versioning

If you never set `agent_version`:

- `RunContext.agent_version` defaults to `None`.
- `None` is not written as a span attribute (the SDK only emits non-`None`
  optional fields).
- `run_summaries.agent_version` is `NULL`.
- The `VersionCohortMaterializer` excludes `NULL`-version runs entirely.
- `version_cohort_summaries` contains no rows for the agent.
- The Fleet view shows the agent with zero version dropdowns.
- Version Compare returns a "no versions found" note.

In short: versioning is optional but strongly recommended. Without it, you
get anomaly detection and run-level detail but lose Fleet rollups and
cross-version comparison.

## Caveats

### Temporal order is not enforced

Version Compare assumes `version_a` is the baseline (usually the older
version) and `version_b` is the comparison (usually the newer version), but
the system does **not** enforce this. If you select `v1.3` as Version A and
`v1.2` as Version B, the deltas will still compute — but the direction
(green/red colour coding in the UI) will be inverted from what you'd expect.
The operator is responsible for picking a meaningful pair.

### Workloads are independent

Cohorts are scoped by `(agent_name, agent_version, workload_type)`. The
Version Compare endpoint currently ignores `workload_type` — it compares
cohorts by `(agent_name, agent_version)` only. Comparing a "qa" workload
against a "support" workload produces misleading results because the
underlying traces are fundamentally different. The `workload_type` parameter
is accepted by the API endpoint but reserved for future use.

**Do not compare across workloads.** Select two versions of the same agent
that serve the same workload type for meaningful deltas.

### Cost derivation is best-effort

`avg_cost` is derived from estimated token counts stored in span attributes.
It is an approximation, not an invoice. Factors that limit accuracy:

- Providers that do not expose token counts produce zero-cost runs.
- Streaming models may report partial token counts.
- Pricing rates are hardcoded and may lag provider price changes.

Use cost deltas for directional insight (is this version cheaper or more
expensive?) rather than exact billing reconciliation.