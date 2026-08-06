# Release Notes — v0.1.0

**Release date:** August 2026  
**License:** MIT  

`agent-exec-trace` v0.1.0 is the first public release. It provides
OpenTelemetry-based observability for AI agent workflows with a
deterministic anomaly detection engine, a React operator UI, and a
local-first OSS stack.

## What's in this release

### 35 deterministic anomaly detectors

35 rule-based detectors organized across 7 behavioral categories:

| Category | Count | Detects |
|---|---|---|
| Tool Execution | 8 | Loops, error rates, latency spikes, redundant calls |
| Cost & Resource | 6 | Cost spikes, token explosion, per-tool cost, wasted calls |
| Runtime & Completion | 5 | Duration anomalies, step exhaustion, inactivity, early stops |
| Retry & Recovery | 5 | Retry storms, cascading retries, recovery path complexity |
| Interaction & Control | 4 | Intervention frequency, escalation rate, approval latency |
| Output Quality | 4 | Empty/low output, indeterminate status, output drift |
| Cross-Run Patterns | 3 | Anomaly clusters, run frequency, first-run heuristics |

All detectors are deterministic (rule-based, zero LLM dependency) and
produce structured anomaly records with severity, explanation, and
evidence payloads.

### 5 optional LLM-augmented detectors

Gated behind a feature flag and disabled by default:

- SemanticLoop — semantic similarity-based loop detection
- Hallucination — content-vs-context consistency check
- GoalDrift — intention shift across plan spans
- QualityDegradation — output quality regression
- ConfusionPattern — repeated uncertainty signals

### Instrumentation SDK

- **LangGraph adapter** (`TracedGraph`) — automatic instrumentation of
  compiled graphs. Every node becomes a span with automatic classification.
- **Raw Python adapter** (`@trace_agent` + `plan_span`, `tool_span` context
  managers) — manual instrumentation for any Python agent.
- **Direct OTLP export** via `AgentTracer` — full control over span creation.
- **Privacy control** — four content-capture modes (Metadata-only,
  Truncated, Hashed, Full) with Metadata-only as the safe default.

### OTLP export

Traces export via OTLP gRPC to Jaeger (primary backend) or Tempo (compatibility
backend). An OpenTelemetry Collector is available for collector-mediated
export paths.

### React web UI with 5 views

| View | Purpose |
|---|---|
| **Fleet Health** | Cross-agent dashboard: cohorts, run counts, anomaly counts, filtering |
| **Run Timeline** | Single-run span tree with anomaly badges and metadata |
| **Version Compare** | Side-by-side delta between two agent versions |
| **Anomaly Inbox** | Triage surface with type/severity filters |
| **Agent Detail** | Per-agent metrics: tool mix, cost trend, anomaly history |

### Demo agent with seeded scenarios

The `request-triage` demo agent exercises three behavioral paths (normal,
loop, high-cost) with deterministic, reproducible traces. The seed script
populates 96 runs with ~240 anomalies across 4 agents for demo and testing.

### Analytics pipeline

The analytics worker polls Jaeger, runs all detectors, materializes run
summaries, fleet rollups, version cohort summaries, and anomaly records into
Postgres. The FastAPI read API serves all product views from this normalized
read model.

## Architecture

```
packages/python-sdk/     Instrumentation SDK (OTel spans, adapters)
services/api/            FastAPI read API
services/analytics/      Analytics worker (35 detectors, materialization)
apps/web/                React + Vite operator UI
deploy/                  Docker compose, collector configs
examples/demo-agent/     request-triage demo agent
```

## Getting started

```bash
git clone https://github.com/deghosal-2026/agent-exec-trace.git
cd agent-exec-trace
make setup          # install SDK + services in editable mode
make stack-up       # boot 6 containers (Jaeger, Postgres, API, analytics, web)
make seed-e2e       # seed demo data (96 runs, ~240 anomalies)
```

Open **http://localhost:5173** for the UI and **http://localhost:16686** for Jaeger.

See [docs/reference/quickstart.md](docs/reference/quickstart.md) for the full walkthrough.

## Known limitations

This is a `v0.1.0` release. Honest boundaries are documented in
[docs/reference/limitations.md](docs/reference/limitations.md). Key items:

- No streaming trace ingestion (batch polling only)
- No distributed trace correlation across services
- No multi-tenant isolation
- LLM detectors are research-grade, not production-validated
- No PydanticAI adapter
- No policy overlay or memory audit views
- Stubbed span trees in e2e tests
- Field testing limited to HF corpus (42.2% compatibility score)

## What's next — v0.2.0

Planned for the next release:

- Streaming trace ingestion (real-time anomaly detection)
- Distributed trace correlation across services
- Multi-tenant isolation
- PydanticAI adapter
- Policy overlay view and memory audit UI
- LLM detector hardening and production validation
- Expanded real-world trace corpus and field testing
- Live-trace e2e tests
- File-based trace replay

## License

MIT — see [LICENSE](../../LICENSE).