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

## Assumptions Register

| Assumption | Why it matters |
|---|---|
| LangGraph exposes enough lifecycle hooks to create useful behavior spans | If false, adapter scope changes materially |
| Jaeger trace access is sufficient for early normalization and replay workflows | If false, ingestion strategy needs redesign |
| Cost estimation can be computed consistently enough to support cost-spike detection | If false, cost anomaly scope may narrow |
| Metadata-only mode still leaves enough evidence for useful run debugging | If false, privacy defaults and view design need adjustment |
| One demo workload plus one more realistic workload is enough for early product validation | If false, field-test scope expands sooner |

## Open Questions Register

| Question | Current stance |
|---|---|
| What exact Jaeger read/query path should analytics use in `v0.1.0`? | Open; implementation detail to resolve during analytics work |
| How much run detail should be stored in Postgres vs fetched from backend on demand? | Open; likely hybrid approach |
| Should drift scoring be a placeholder field or minimally implemented in `v0.1.0`? | Open; fleet summaries should at least leave room for it |
| How should estimated cost be derived when provider billing detail is incomplete? | Open; likely documented best-effort logic |
| What is the minimum acceptable replay/rebuild flow for first release? | Open; must be good enough for seeded scenarios and detector reprocessing |

## Configuration Surface Inventory

The implementation should treat configuration as a deliberate product surface.

### SDK config

- OTLP endpoint
- agent name default
- agent version default
- workload type
- privacy mode
- content capture toggles

### Analytics config

- Postgres DSN
- backend read endpoint
- loop threshold
- retry threshold
- cost thresholds
- polling interval / replay controls
- webhook target and credentials if used

### API config

- Postgres DSN
- service host/port
- pagination defaults

### Web config

- API base URL
- local stack routing values

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

### LLM Use in Anomaly Detection

`v0.1.0` does not require an LLM for anomaly detection.

Rules:

- detection logic must be deterministic and reproducible
- alert firing must not depend on model judgment
- operators must be able to explain why an anomaly fired from stored evidence alone

Allowed later:

- LLM-assisted explanation of anomaly context
- LLM-assisted clustering or summarization of many anomaly records
- LLM-assisted operator guidance layered on top of deterministic detections

Not allowed in `v0.1.0`:

- model-only anomaly classification
- opaque anomaly scoring that cannot be inspected or tuned

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

## Security Model

`v0.1.0` does not need enterprise-grade security breadth, but it does need a clear stance.

Rules:

- metadata-only is the default trace content posture
- secrets, prompts, tool args, and memory contents must not be logged casually in local service logs
- webhook integrations should assume authenticated or signed delivery will be needed later
- local stack docs should call out where sensitive data could leak if content capture is enabled

## Not Yet List

These are legitimate product ideas, but they are intentionally not required for `v0.1.0`:

- LLM-assisted anomaly explanation
- multi-agent topology maps
- policy overlay and governance review views
- full memory audit UI
- pluggable detector ecosystem
- PydanticAI adapter

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

### Field testing

- seeded demo scenarios must validate each detector against expected outcomes
- at least one more realistic workload beyond the smallest happy-path demo should be instrumented before release sign-off
- detector usefulness and false-positive behavior must be reviewed as part of release validation
