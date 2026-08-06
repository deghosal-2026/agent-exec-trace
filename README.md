<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License">
</p>

# agent-exec-trace

**Execution traces for agent behavior — OpenTelemetry-style observability for AI agent workflows.**

---

## The Problem

Most teams can tell you if a service is up. They cannot tell you why an agent made a bad decision, called a tool eight times, or quietly drifted into expensive low-value behavior.

Traditional observability shows you what your services did — latency, errors, dependency calls. It does not show you what an agent *thought* it was doing: where it changed plans, where it looped, where it overused tools, where it burned budget without adding value.

`agent-exec-trace` makes agent behavior inspectable at runtime. Every agent run emits an execution trace that reads as a behavioral story — planning, tool calls, memory mutations, retries, approvals, and cost accumulation.

---

## What It Does

| Feature | Description |
|---|---|
| Behavior trace schema | Defines span/event types for planning, tool use, memory, validation, approvals, and escalations |
| Instrumentation SDK | Wraps LangGraph and raw Python agents to emit behavior events |
| OTLP export | Uses OpenTelemetry/OTLP to pipe behavior data into Tempo, Jaeger, or any OTel-compatible backend |
| Loop detection | Automatically identifies retry spirals and tool-call loops from trace data |
| Cost anomaly detection | Flags runs where cost-per-success spikes or deviates from baseline |
| Run explorer UI | Timeline view, event detail, and filters for inspecting individual agent runs |
| Version comparison | Side-by-side trace diff between agent versions to see what actually changed |
| Fleet dashboards | Cross-agent views for drift, tool mix, cost-per-success, and intervention patterns |

---

## Features

`agent-exec-trace` ships a deterministic anomaly detection engine with **35 detectors** organized across **7 behavioral categories**:

| Category | Count | Detects |
|---|---|---|
| **Tool Execution** | 8 | Loops, error rates, latency spikes, redundant calls |
| **Cost & Resource** | 6 | Cost spikes, token explosion, per-tool cost, wasted calls |
| **Runtime & Completion** | 5 | Duration anomalies, step exhaustion, inactivity, early stops |
| **Retry & Recovery** | 5 | Retry storms, cascading retries, recovery path complexity |
| **Interaction & Control** | 4 | Intervention frequency, escalation rate, approval latency |
| **Output Quality** | 4 | Empty/low output, indeterminate status, output drift |
| **Cross-Run Patterns** | 3 | Anomaly clusters, run frequency, first-run heuristics |

All detectors are deterministic (rule-based, zero LLM dependency) and produce structured anomaly records with severity, explanation, and evidence payloads. Configurable thresholds per detector per workload with graceful degradation for missing data and edge cases.

## What It Is Not

| Not | Why |
|---|---|
| A log dashboard | It does not replace your existing logging — it layers behavior semantics on top of traces |
| An evaluation framework | It shows you what happened, not whether it was correct (complements tools like EvalForge) |
| Tied to one framework | Instrumentation works across LangGraph, raw Python agents, and is designed to extend |
| A full trace backend | Built on existing OTel backends (Tempo, Jaeger) — not a replacement for them |

---

## Repository Layout

```
agent-exec-trace/
├── packages/python-sdk/     # Instrumentation SDK (OTel spans, adapters)
├── services/api/            # Product read API (FastAPI)
├── services/analytics/      # Behavior analytics service (summaries, anomalies)
├── apps/web/                # Operator UI (React)
├── deploy/                  # Compose configs, collector configs, local stack
├── examples/                # Demo agents and seeded scenarios
├── tests/                   # Cross-cutting / end-to-end tests
├── docs/                    # Architecture, design, field-test, test, WBS, reference
│   ├── architecture/        # spec, architecture diagram, DB schema
│   ├── design/              # PRD, agent designs, CLI plans, demo scenarios
│   ├── field-test/          # field-test plan and reports
│   ├── test/                # e2e test plan, seed data, test reports
│   ├── reference/           # developer setup guide
│   └── wbs/                 # detailed WBS (4 parts + table of contents)
└── Makefile                 # setup / lint / test / stack entrypoints
```

For the complete work breakdown structure, see [docs/wbs/wbs-v0.1.0.md](docs/wbs/wbs-v0.1.0.md).

See [docs/reference/developer-setup.md](docs/reference/developer-setup.md) for the developer onboarding flow.

Traces are stored at `data/traces/processed/` with a `manifest.json` index.

---

## Quickstart

> Coming soon. Target flow:

```bash
pip install agent-exec-trace

# Instrument your agent
from agent_exec_trace import instrument
instrument(my_agent)

# Run your agent — traces flow to your OTLP backend
```

---

## Testing

End-to-end UI tests run against the seeded local stack via Playwright.

| Doc | Purpose |
|---|---|
| [docs/test/e2e-testing-plan.md](docs/test/e2e-testing-plan.md) | Test plan: scope, CUJs, test catalog, screenshot strategy |
| [docs/test/e2e-seed-data.md](docs/test/e2e-seed-data.md) | Mock data shape produced by `scripts/seed-e2e-data.py` |
| [docs/test/e2e-test-report-v1.md](docs/test/e2e-test-report-v1.md) | v0.1.0 (M11) test report — 34/34 pass, findings, v0.2.0 takeaways |

Run the suite:

```bash
make e2e   # boots stack, seeds, runs Playwright, captures screenshots
```

Specs live under `apps/web/tests/e2e/` and target Chromium.

---

## Architecture

```
Agent Runtime (LangGraph / Python)
        │
        ▼
  Instrumentation SDK ─── emits behavior spans
        │
        ▼
  OpenTelemetry Collector (OTLP)
        │
        ▼
  Trace Backend (Tempo / Jaeger)
        │
        ▼
  Run Explorer UI (FastAPI + React)
        │
        ▼
  Behavior Analytics
  • 35 deterministic detectors (7 categories)
  • loop detection, cost anomaly, retry storm, drift
  • structured anomaly records with evidence payloads
```

---

## Who It's For

- **Teams operating AI agents** in internal platforms, DevOps workflows, or knowledge systems
- **LLMOps and evaluation teams** comparing agent versions
- **Platform engineering teams** building AI observability standards
- **OSS maintainers** who need a vendor-neutral diagnostics layer

---

## Local-First OSS Stack

| Component | Tech |
|---|---|
| Instrumentation | OpenTelemetry Python SDK |
| Collection | OpenTelemetry Collector |
| Traces | Tempo or Jaeger |
| Metrics | Prometheus |
| Dashboards | Grafana |
| API / UI | FastAPI + React |
| Sample workloads | LangGraph + raw Python agents |

Everything runs locally. Demoable with your own agents and seeded bad runs.

---

## Roadmap

### v0.1.0 — First Release
- [ ] Behavior trace schema
- [ ] Instrumentation wrappers for LangGraph and raw Python agents
- [ ] OTLP export into local Tempo/Jaeger
- [ ] Timeline UI for single-run inspection
- [ ] Loop and cost anomaly detection
- [ ] Version metadata correlation

### v0.2.0
- [ ] Side-by-side run comparison UI
- [ ] Prompt/model correlation views
- [ ] Fleet behavior dashboards

### v0.3.0
- [ ] Drift detection hooks
- [ ] Approval/policy event overlays
- [ ] Control-plane integration

### v0.4.0
- [ ] Multi-agent interaction maps
- [ ] Public demo workload pack
- [ ] Benchmark-driven diagnostics stories

---

## Design Principles

- **Vendor-neutral** — built on OpenTelemetry, works with any OTLP-compatible backend
- **Behavior-first** — traces capture what the agent *did*, not just what it called
- **Human-readable** — default views should make bad runs obvious, not require a query language
- **Local-first** — everything runs on a laptop before it needs a cluster
- **Not framework-locked** — SDK wraps any agent runtime, starting with LangGraph and raw Python

---

## License

MIT — see [LICENSE](LICENSE).
