# Known Limitations — v0.1.0

This document tracks the honest boundaries of the `v0.1.0` release. Each
limitation includes its impact and, where known, the target resolution release.

## Data pipeline

### No streaming trace ingestion

Traces are ingested via batch polling only. The analytics worker polls
Jaeger's query API on a configurable interval (default 30s). Real-time
streaming ingestion via OTLP directly into the analytics pipeline is not
supported.

**Impact:** Anomalies may appear with 30–60s delay. Not suitable for
sub-second alerting.

**Planned:** Streaming ingestion path in `v0.2.0`.

### No distributed trace correlation across services

Traces are correlated within a single agent invocation only. If your agent
calls a downstream service that also emits OTel spans, those spans are not
linked or analyzed as part of the agent execution trace.

**Impact:** Cross-service causality (e.g. agent loops caused by slow
downstream dependency) is invisible.

**Planned:** Distributed trace linking in `v0.2.0`.

### Trace replay depends on Jaeger being available

The seed-and-replay workflow requires a running Jaeger instance. There is no
offline replay mode that operates directly from stored trace files.

**Impact:** Cannot demo or test without the full stack running.

**Planned:** File-based replay in `v0.2.0`.

## Multi-tenancy

### No multi-tenant isolation

All data in Postgres is stored in a single logical namespace. There is no
tenant ID partitioning, no per-tenant access control, and no tenant-scoped
views in the API or UI.

**Impact:** The stack is suitable for single-team use only. Multiple teams
must deploy separate instances.

**Planned:** Tenant isolation in `v0.2.0`.

## Detectors

### LLM detectors are optional and not validated against production workloads

The 5 LLM-augmented detectors (SemanticLoop, Hallucination, GoalDrift,
QualityDegradation, ConfusionPattern) require a running LLM endpoint and
were validated only against a 10-trace sample on a local Qwen2.5-1.5B-4bit
model. They are gated behind a feature flag and disabled by default.

**Impact:** LLM detectors may produce high false-positive rates on
production traces. They are research-grade in `v0.1.0`.

**Planned:** LLM detector hardening and broader field validation in `v0.2.0`.

### 28 detectors were silent on the HF field-test corpus

In the 100K-trace Hugging Face field test, only 7 of 35 rule-based detectors
fired. The remaining 28 are structurally dependent on tool-use semantics
(tool names, retry signals, cost metadata) that the HF corpus does not
contain.

**Impact:** Detectors are validated on synthetic traces only. Real-world
fire rates remain unknown for most detectors.

**Planned:** Expanded real-world trace corpus in `v0.2.0`.

### Field testing limited to HF corpus; 42.2% compatibility score

The compatibility audit measured a 42.2% per-trace compatibility score
against the Hugging Face trace corpus. 57.8% of traces were structurally
incompatible (0% had `has_tool_args`, 0% had `has_retry_semantics`, only
7.5% had `has_tool_name`). The synthetic corpus achieves 99.2%
compatibility.

**Impact:** The product works well on structured agent traces but degrades
on raw, unnormalized traces without tool semantics. Production compatibility
cannot be guaranteed without a field test against real agent workloads.

**Planned:** Broader real-agent trace corpus and compatibility improvements
in `v0.2.0`.

## Adapters

### No PydanticAI adapter

The SDK ships with LangGraph and raw Python adapters only. PydanticAI
instrumentation is deferred.

**Impact:** Teams using PydanticAI must use the raw Python decorator or
`AgentTracer` API directly.

**Planned:** PydanticAI adapter in `v0.2.0`.

## UI

### No policy overlay view

There is no UI surface for reviewing policy evaluations (e.g. guardrail
checks, content filters, approval rules) against agent traces.

**Impact:** Operators cannot audit which policies fired on which runs
within the product UI.

**Planned:** Policy overlay in `v0.2.0`.

### No memory audit UI

The API and UI do not surface memory read/write events from traces. The
SDK can emit `memory` spans, but there is no dedicated view for reviewing
agent memory state.

**Impact:** Cannot debug memory corruption, stale context, or unintended
memory persistence through the UI.

**Planned:** Memory audit view in `v0.2.0`.

## Testing

### Span trees are stubbed in e2e tests

The seeded e2e data includes run summaries and anomalies, but the actual
span trees returned by the API are empty for seeded runs. Real span trees
require live traces in Jaeger that have been processed by the analytics
worker — a flow not exercised by the seed script.

**Impact:** Playwright tests validate product views with anomaly data but
do not exercise the full span-tree rendering path.

**Planned:** Live-trace e2e tests in `v0.2.0`.

## Summary matrix

| Limitation | Category | Impact | Target |
|---|---|---|---|
| No streaming ingestion | Pipeline | 30-60s anomaly delay | v0.2.0 |
| No distributed trace correlation | Pipeline | Cross-service causality invisible | v0.2.0 |
| Jaeger-dependent replay | Pipeline | No offline demo | v0.2.0 |
| No multi-tenant isolation | Platform | Single-team only | v0.2.0 |
| LLM detectors not prod-validated | Detectors | Research-grade only | v0.2.0 |
| 28 detectors silent on HF corpus | Detectors | Synthetic-only validation | v0.2.0 |
| 42.2% HF compatibility score | Detectors | Degrades on raw traces | v0.2.0 |
| No PydanticAI adapter | SDK | Manual instrumentation required | v0.2.0 |
| No policy overlay view | UI | Policy audit gaps | v0.2.0 |
| No memory audit UI | UI | Memory state invisible | v0.2.0 |
| Stubbed span trees in e2e | Testing | Partial e2e coverage | v0.2.0 |
