# agent-exec-trace v0.1.0 Technical Specification

## Scope

### Repository shape

`v0.1.0` will be built in a monorepo with these top-level units:

- `packages/python-sdk/`
- `services/api/`
- `services/analytics/`
- `apps/web/`
- `deploy/`
- `examples/`
- `docs/`

This specification covers only `v0.1.0`.

Included product capabilities:

- LangGraph instrumentation
- raw Python instrumentation
- OTel GenAI semantic convention mapping
- OTLP export
- Tempo / Jaeger local support
- run timeline view
- run summary view
- fleet health view
- version compare view
- anomaly inbox for loop / retry / cost anomalies

Excluded from `v0.1.0`:

- PydanticAI adapter
- policy overlays
- multi-agent topology views
- memory audit review surface
- intervention review dashboard
- pluggable custom detectors

---

## Product Entities

### Agent

A named runtime workload that is instrumented and versioned.

Required fields:

- `agent_name: str`
- `agent_version: str | None`
- `runtime_type: Literal["langgraph", "python"]`
- `provider_name: str | None`
- `model_name: str | None`

### Run

One end-to-end invocation of an agent.

Required fields:

- `run_id: str`
- `agent_name: str`
- `agent_version: str | None`
- `started_at: datetime`
- `ended_at: datetime | None`
- `status: Literal["ok", "error", "cancelled"]`
- `workload_type: str | None`
- `conversation_id: str | None`
- `estimated_cost_usd: float | None`
- `retry_count: int`
- `intervention_count: int`

### Span

One unit of behavior inside a run.

Supported `operation_name` values in `v0.1.0`:

- `invoke_agent`
- `plan`
- `execute_tool`
- `retrieval`
- `create_memory`
- `search_memory`
- `update_memory`
- `delete_memory`

### Anomaly

A computed signal linked to one run or one cohort.

Required fields:

- `anomaly_id: str`
- `type: Literal["loop", "retry_storm", "cost_spike"]`
- `severity: Literal["low", "medium", "high"]`
- `run_id: str | None`
- `agent_name: str`
- `summary: str`
- `explanation: str`
- `created_at: datetime`

---

## Runtime Instrumentation Requirements

### LangGraph Adapter

The LangGraph adapter must:

- start a root `invoke_agent` span per graph execution
- create child spans for planning/tool/retrieval/memory phases where observable
- propagate run-level metadata through the graph lifecycle
- capture repeated tool-call patterns that feed anomaly rules later

### Raw Python Adapter

The raw Python adapter must provide:

- `@trace_agent(...)` decorator for a full run
- helper context managers or functions for nested spans such as tool execution and planning

The raw Python path exists to guarantee the product is not trapped inside one framework.

---

## Service Topology Requirements

### API Service

The API service must:

- expose product-facing read endpoints
- read from the normalized Postgres read model
- avoid owning anomaly computation logic
- avoid coupling UI contracts to Jaeger or Tempo query syntax

### Analytics Service

The analytics service must:

- run separately from the API service
- process traces asynchronously
- compute and materialize summaries into Postgres
- compute anomaly records into Postgres
- support replay or reprocessing of seeded demo traces

### Read Model Database

The normalized product read model must use Postgres in `v0.1.0`.

Minimum stored entities:

- run summaries
- anomaly records
- fleet summary rows
- version cohort summary rows

---

## Semantic Convention Rules

### Standard attributes first

The system must emit OTel GenAI attributes whenever applicable.

Mandatory-first list:

- `gen_ai.operation.name`
- `gen_ai.agent.name`
- `gen_ai.agent.version` when available
- `gen_ai.provider.name` when available
- `gen_ai.request.model` when available
- `gen_ai.conversation.id` when available

### Extension attributes in v0.1.0

The following extensions are allowed and must be documented:

- `gen_ai.agent.run.id`
- `gen_ai.agent.run.cost.total`
- `gen_ai.agent.loop.count`
- `gen_ai.agent.loop.detected`
- `gen_ai.agent.retry.count`
- `gen_ai.agent.workload.type`
- `gen_ai.agent.intervention.count`

### Content capture defaults

Defaults:

- full prompt/message content: off
- full tool arguments: off
- full tool responses: off
- full memory values: off

Allowed by opt-in configuration:

- truncated prompt content
- hashed payload fields
- explicit allow-listed content capture

---

## Analytics Rules

### Loop Detection

Initial v0.1.0 rule:

- flag a loop when the same tool is called repeatedly above a configurable threshold within the same run without an intervening successful state transition that changes the execution path materially

Minimum configuration:

- `loop_same_tool_threshold: int`
- `loop_window_size: int`

### Retry Storm Detection

Initial v0.1.0 rule:

- flag when retries exceed a configurable threshold for a run

Minimum configuration:

- `retry_count_threshold: int`

### Cost Spike Detection

Initial v0.1.0 rule:

- flag when a run cost exceeds either a static threshold or a baseline multiplier for the same agent/workload cohort

Minimum configuration:

- `absolute_cost_threshold_usd: float | None`
- `baseline_multiplier_threshold: float | None`

---

## API Surfaces

### Run Timeline API

Purpose: return a normalized run and span tree for a single run.

Response must include:

- run summary
- ordered span tree
- anomaly markers linked to spans when possible
- aggregate counters: tool calls, retries, cost, interventions

### Fleet Health API

Purpose: return fleet-level rollups grouped by agent/version/workload.

Response must include:

- total runs
- success/error counts
- average cost per run
- anomaly counts
- drift-ready comparison fields even if drift scoring is not fully implemented yet

### Version Compare API

Purpose: compare two version cohorts.

Response must include:

- run count by version
- success/error deltas
- cost deltas
- retry deltas
- top tool usage deltas

### Anomaly Inbox API

Purpose: return anomaly records with enough context to triage.

Response must include:

- anomaly type
- severity
- run reference
- short explanation
- direct trace link key

---

## UI View Requirements

### Run Timeline

Must show:

- ordered span tree
- durations
- cost overlay when available
- tool call counts
- anomaly markers
- click-through detail panel per span

### Run Summary

Must show:

- run outcome
- total duration
- estimated cost
- retry count
- loop flag
- intervention count

### Fleet Health

Must show:

- agents ranked by anomaly count or recent change
- cost-per-run and success rate
- grouping by agent/version/workload

### Version Compare

Must show:

- version A vs version B
- runs compared
- cost delta
- retry delta
- top tool usage shifts

### Anomaly Inbox

Must show:

- anomaly type
- severity
- affected agent
- summary explanation
- click-through to exact run

---

## Deployment Requirements

`v0.1.0` must support one local reference stack with:

- sample instrumented app
- OTel Collector
- Jaeger as primary backend
- Tempo as compatibility backend
- analytics service
- API service
- React UI
- Postgres read-model database

The product is not done unless this stack can be run locally as a documented demo.

---

## Testable Acceptance Conditions

### Instrumentation

- one LangGraph demo emits valid OTel-style agent spans
- one raw Python demo emits valid OTel-style agent spans

### Storage / transport

- traces are visible in Tempo
- traces are visible in Jaeger

### Product views

- one bad run can be opened in the timeline view
- one synthetic loop anomaly appears in anomaly inbox
- fleet view loads grouped summaries for at least two agents or two workloads
- version compare returns a meaningful delta for two seeded cohorts

### Privacy defaults

- raw content is absent by default
- metadata-only mode still produces usable run and anomaly views
