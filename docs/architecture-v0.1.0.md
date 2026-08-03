# agent-exec-trace v0.1.0 Architecture

## Goal

Build an OTel-first, local-first runtime observability system for AI agents that makes one bad run explainable, makes a fleet of agents reviewable, and does so without requiring users to replace their existing tracing backend.

v0.1.0 is not a full AI platform. It is a focused architecture for:

- capturing agent behavior as standard OpenTelemetry traces
- enriching those traces with a small, documented set of provisional agent behavior extensions
- computing useful operator signals from those traces
- presenting standardized views for run debugging, fleet review, version comparison, and anomaly triage

---

## Architectural Priorities

1. **OTel first**
   - Use OpenTelemetry GenAI semantic conventions wherever available.
   - Only introduce custom `gen_ai.agent.*` extension fields where the standard is incomplete.

2. **Interop first**
   - Treat Tempo, Jaeger, OpenTelemetry Collector, Grafana, and Prometheus as first-class peers, not replacement targets.

3. **View-first product design**
   - Architecture exists to support standard operator views, not just to store traces.

4. **Incremental adoption**
   - One developer should be able to instrument one agent locally and see useful traces in under 30 minutes.

5. **Framework-agnostic shape**
   - LangGraph and raw Python land in v0.1.0, but the model must not be structurally dependent on LangGraph internals.

---

## System Context

At a high level, the product has five architectural zones:

1. **Runtime instrumentation layer**
2. **Trace transport and storage layer**
3. **Behavior analytics layer**
4. **Application API layer**
5. **Operator UI layer**

### Monorepo Shape

`v0.1.0` should use a monorepo with explicit product boundaries and simple tooling:

- `packages/python-sdk/`
- `services/api/`
- `services/analytics/`
- `apps/web/`
- `deploy/`
- `examples/`
- `docs/`

This is the best path toward `1.0` because SDK, API, analytics, and web are already distinct product units.

```
┌────────────────────────────────────────────────────────────────────┐
│  Agent Runtime Layer                                              │
│  - LangGraph agents                                               │
│  - Raw Python agents                                              │
└──────────────────────────────┬─────────────────────────────────────┘
                               │
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│  Instrumentation SDK                                              │
│  - OTel spans/events                                              │
│  - Semconv mapping                                                │
│  - Extension fields                                               │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ OTLP
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│  Collector / Backend Layer                                        │
│  - OTel Collector                                                 │
│  - Tempo / Jaeger                                                 │
│  - Prometheus-derived metrics                                     │
└──────────────────────────────┬─────────────────────────────────────┘
                               │
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│  Behavior Analytics Service                                       │
│  - loop detection                                                 │
│  - retry storm detection                                          │
│  - cost anomaly detection                                         │
│  - version and fleet aggregation                                  │
└──────────────────────────────┬─────────────────────────────────────┘
                               │
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│  API + UI                                                         │
│  - run timeline view                                              │
│  - fleet health board                                             │
│  - version comparison                                             │
│  - anomaly inbox                                                  │
└────────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Instrumentation SDK

**Responsibility:** create behavior-rich traces from agent execution.

**What it must do:**

- start a root span for each agent run
- emit child spans for planning, tool execution, retrieval, and memory operations
- attach version metadata, cost metadata, and correlation metadata
- emit structured events for anomaly hints, approvals, and notable state changes

**Supported inputs in v0.1.0:**

- LangGraph runtime wrapper
- raw Python decorator and helper API

**Design constraint:**
The SDK should be thin and deterministic. It should not contain fleet logic, alert rules, or UI-specific assumptions.

### 2. Semantic Convention Mapper

**Responsibility:** map runtime behaviors onto OTel GenAI semantic conventions plus documented extension fields.

**Standard fields to use first:**

- `gen_ai.operation.name`
- `gen_ai.agent.name`
- `gen_ai.agent.version`
- `gen_ai.provider.name`
- `gen_ai.request.model`
- `gen_ai.conversation.id`
- `gen_ai.data_source.id`

**Provisional extension fields in v0.1.0:**

- `gen_ai.agent.run.id`
- `gen_ai.agent.run.cost.total`
- `gen_ai.agent.loop.count`
- `gen_ai.agent.loop.detected`
- `gen_ai.agent.retry.count`
- `gen_ai.agent.version.label`
- `gen_ai.agent.workload.type`
- `gen_ai.agent.intervention.count`

These must be documented as temporary, reference-implementation extensions pending upstream OTel adoption.

### 3. Collector / Backend Layer

**Responsibility:** accept OTLP traces, store them in standard backends, and expose them for query/aggregation.

**v0.1.0 backends:**

- Jaeger as the primary trace backend for local demos
- Tempo as the compatibility backend

**Reasoning:**

- Jaeger is widely recognized, stable, and gives the project broader operational legitimacy for a first release.
- Tempo remains strategically important and must stay compatible through the OTel boundary.

The product must assume the backend is interchangeable behind an adapter/query layer.

### 4. Behavior Analytics Service

**Responsibility:** transform raw traces into operator-ready signals.

**Why it exists:**
The backend stores traces, but traces alone are not the product. The product is the extra layer that computes behaviorally meaningful signals.

**v0.1.0 signals:**

- loop detection
- retry storm detection
- cost spike detection
- per-run summaries
- per-agent fleet summaries
- version-cohort summaries

**Detection strategy in v0.1.0:**

- anomaly detection is deterministic-first
- no LLM is required to decide whether a loop, retry storm, or cost spike occurred
- any future LLM usage belongs in explanation, clustering, or operator assistance layers, not in the truth path for detection

**Design principle:**
Analytics should be computed from trace data, not from framework-specific side channels, so the logic remains portable.

**Service decision:**
Analytics is a separate service in `v0.1.0`, not embedded in the API.

That service is responsible for:

- reading traces from the backend path
- computing summaries and anomalies asynchronously
- writing materialized read models to Postgres

### 5. API Layer

**Responsibility:** expose stable, product-oriented read APIs for the UI and future integrations.

The API layer should not mirror Tempo or Jaeger directly. It should expose product concepts:

- get run timeline
- get run summary
- list anomalies
- get fleet health snapshot
- compare version cohorts

This protects the UI from backend-specific query syntax and lets the product swap backends more safely.

**Service decision:**
The API is a separate service from analytics and serves product read models rather than owning anomaly computation.

### 6. Operator UI

**Responsibility:** implement the standard views defined in the PRD.

**v0.1.0 UI views:**

- Run Timeline
- Run Summary
- Fleet Health
- Version Compare
- Anomaly Inbox

Each view must map to a distinct operator decision:

- where did the run degrade
- which agents need attention
- whether the new version is better
- which anomalies should be reviewed first

**Frontend decision:**
Use React from the start. The interaction complexity of trace drill-down, comparison, inbox triage, and fleet filtering justifies a real client application.

---

## Primary Data Flows

### Flow A: Single Run Debugging

1. Developer runs an instrumented agent.
2. SDK emits OTel spans and extension attributes.
3. Collector forwards traces to Tempo/Jaeger.
4. Analytics service reads trace records and computes run summary signals.
5. UI requests the run timeline and summary.
6. Operator identifies the failing or expensive segment.

### Flow B: Fleet Review

1. Multiple agents emit traces over time.
2. Analytics service aggregates runs into fleet summaries.
3. UI loads Fleet Health view by agent, workload, or version.
4. Operator identifies drift, cost concentration, or anomaly hotspots.

### Flow B1: Materialized Read Model

1. Traces land in Jaeger through the collector path.
2. Analytics service reads and normalizes trace data.
3. Analytics writes product records into Postgres:
   - run summaries
   - anomaly records
   - version cohort rollups
   - fleet summaries
4. API serves UI requests from Postgres-backed product objects.

This read-model layer is required to make standard views stable and backend-neutral.

### Flow C: Version Comparison

1. CI or runtime injects version metadata into spans.
2. Analytics service groups runs into version cohorts.
3. Compare API computes deltas in cost, retries, tool usage, and outcomes.
4. UI renders side-by-side comparison.

### Flow D: Anomaly Review

1. Analytics service evaluates traces against configured loop/retry/cost rules.
2. Matching runs produce anomaly records.
3. Alerts are exposed via API and optional webhook/export path.
4. Operator opens anomaly and jumps to exact trace.

### Flow E: Field Testing

1. Seeded demo runs are generated for normal, loop, retry-heavy, and high-cost scenarios.
2. Deterministic detectors are evaluated against expected outcomes.
3. At least one non-demo or more realistic workload is instrumented to confirm the model holds outside the happy path.
4. Detector usefulness, false positives, and trace readability are reviewed before claiming `v0.1.0` value.

---

## Standard View Architecture

The architecture should support stable, opinionated views rather than flexible-but-empty generic dashboards.

### Run Timeline

**Depends on:**

- ordered span hierarchy
- span duration
- tool/memory/retrieval attributes
- run-level summary overlays

**Needs architecture support for:**

- trace normalization across runtimes
- collapsed vs expanded span trees
- event overlays for anomaly and intervention markers

### Fleet Health

**Depends on:**

- aggregated per-run summaries
- grouping dimensions: agent, version, workload, environment
- stored or computed baseline metrics

**Needs architecture support for:**

- cohort aggregation
- summary materialization
- low-cost refresh for dashboard loads

### Version Compare

**Depends on:**

- consistent version identity
- cohort boundaries
- normalized metrics across groups

**Needs architecture support for:**

- stable version labeling
- compare-safe aggregation semantics

### Anomaly Inbox

**Depends on:**

- anomaly rules
- anomaly records linked to traces
- tunable thresholds

**Needs architecture support for:**

- asynchronous analytics evaluation
- explainable anomaly payloads

---

## Interoperability Architecture

### OTel Collector as the Primary Boundary

The collector is the key system boundary because it prevents the product from becoming a proprietary ingest path.

The SDK must emit OTLP in a way that works with:

- local collector configs
- direct Tempo ingestion
- direct Jaeger OTLP ingestion
- future OTLP vendor backends

### Backend-Neutral Query Strategy

The product should avoid binding UI behavior directly to backend-native query languages like TraceQL.

Instead:

- backend adapters retrieve normalized trace documents and aggregates
- the API layer serves product-level views
- backend-specific optimizations remain behind internal interfaces

This keeps the UI stable while still allowing Tempo-specific improvements later.

### Read Model Strategy

`v0.1.0` uses a normalized product read model stored in Postgres.

Why:

- fleet and comparison views should not depend on backend-native query semantics
- anomaly triage should be fast and product-oriented
- materialized summaries create cleaner API contracts
- Postgres is a better long-term foundation for `1.0` than SQLite given the chosen separate-services design

### Metrics Interop

The analytics layer should export derived metrics for Prometheus when possible, such as:

- anomaly counts by type
- runs by agent/version/workload
- cost totals by agent/version/workload
- intervention counts

This allows external dashboards and alert systems to coexist with the in-product views.

### Governance / Approval Interop

Even though policy enforcement is out of scope for v0.1.0, the architecture should reserve room for:

- intervention event capture
- approval metadata
- future policy overlay joins

This matters because a mature agent observability product needs to sit next to governance systems, not pretend they do not exist.

---

## Privacy and Safety Architecture

Because traces may include prompts, tool arguments, memory contents, and user data, the architecture must distinguish between:

- **structural metadata**: span names, timings, counts, cost, IDs
- **sensitive payloads**: prompts, tool args, retrieved text, memory contents

### Required default posture

- metadata-first visibility should work without storing full sensitive content
- content capture should be opt-in
- redaction and truncation hooks should exist at the SDK boundary
- summary views should still be useful when raw payloads are absent

**Locked privacy posture:** metadata-only by default.

This is important architecturally because privacy choices affect storage, indexing, API schemas, and UI expectations.

---

## Component Boundaries and Ownership

### SDK Boundary

**Owns:** runtime hooks, span creation, attribute mapping, redaction hooks

**Does not own:** analytics rules, UI behavior, backend storage logic

### Analytics Boundary

**Owns:** anomaly logic, rollups, summaries, comparisons, cohort logic

**Does not own:** runtime hooks, trace collection transport, frontend-specific formatting

### API Boundary

**Owns:** stable product queries and response shapes

**Does not own:** direct backend UI logic or framework-specific execution logic

### UI Boundary

**Owns:** interaction, visualization, operator workflows

**Does not own:** raw analytics or collector-facing concerns

---

## v0.1.0 Deployment Shape

For the first release, the architecture should be runnable in one local stack:

- instrumented sample agent app
- OTel Collector
- Jaeger (primary) or Tempo (compatible)
- analytics service
- API service
- React UI
- Postgres

This should be supportable with a single local compose setup.

That deployment shape is part of the product promise: local-first, proof-friendly, and easy to explain.

---

## Key Architectural Decisions

1. **Use OTel GenAI semconv as the canonical model**
2. **Treat custom fields as documented extensions, not a new schema**
3. **Separate analytics from instrumentation**
4. **Expose product APIs, not raw backend query APIs**
5. **Ship standardized views as first-class surfaces**
6. **Keep privacy controls near the instrumentation boundary**
7. **Design all view logic around normalized product concepts: run, version, anomaly, cohort**

---

## What We Start With

Start with the thinnest architecture slice that proves the whole loop:

1. instrument one LangGraph agent
2. emit standard OTel agent spans
3. store them in Jaeger locally
4. normalize them through analytics into Postgres
5. compute one run summary and one loop anomaly asynchronously
6. render one run timeline and one anomaly-linked drill-down

That first slice validates the architecture end to end before the product expands into fleet dashboards and version comparisons.
