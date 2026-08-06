<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License">
  <img src="https://img.shields.io/badge/version-0.1.0-orange.svg" alt="v0.1.0">
</p>

# agent-exec-trace

**Execution traces for agent behavior — OpenTelemetry-style observability for AI agent workflows.**

---

## The Problem

Most teams can tell you if a service is up. They cannot tell you why an agent made a bad decision, called a tool eight times, or quietly drifted into expensive low-value behavior.

Traditional observability shows you what your services did — latency, errors, dependency calls. It does not show you what an agent *thought* it was doing: where it changed plans, where it looped, where it overused tools, where it burned budget without adding value.

`agent-exec-trace` makes agent behavior inspectable at runtime. Every agent run emits an execution trace that reads as a behavioral story — planning, tool calls, memory mutations, retries, approvals, and cost accumulation.

---

## Quickstart

```bash
git clone https://github.com/deghosal-2026/agent-exec-trace.git
cd agent-exec-trace

make setup        # install SDK + services in editable mode
make stack-up     # boot Postgres, Jaeger, Collector, API, Analytics, Web
make seed-e2e     # seed 96 runs, ~240 anomalies, 4 agents

open http://localhost:5173   # the operator UI
```

See the [User Guide](docs/explanation/user-guide.md) for a full tour of the UI and investigation workflows, or the [Quickstart Guide](docs/reference/quickstart.md) for a step-by-step developer walkthrough.

---

## What It Does

| Feature | Description |
|---|---|
| Behavior trace schema | Defines span/event types for planning, tool use, memory, validation, approvals, and escalations |
| Instrumentation SDK | Wraps LangGraph and raw Python agents to emit behavior events |
| OTLP export | Uses OpenTelemetry/OTLP to pipe behavior data into Tempo, Jaeger, or any OTel-compatible backend |
| 35 anomaly detectors | Deterministic rule-based engine across 7 behavioral categories (tool, cost, runtime, retry, interaction, output, cross-run) |
| 5 LLM detectors | Semantic-level anomaly detection for loops, hallucinations, goal drift, quality degradation, confusion patterns |
| Run Timeline | Span tree with expand/collapse, anomaly markers, duration bars, and attribute inspection |
| Fleet Dashboard | Cross-agent views grouped by agent/version/workload with summary cards, filters, and drill-down |
| Version Compare | Side-by-side delta analysis between two version cohorts (cost, retry rate, success rate, tool usage) |
| Anomaly Inbox | Prioritized triage list with severity/type/agent filters and one-click drill-down to the run |

---

## Features

`agent-exec-trace` ships **35 deterministic anomaly detectors** across **7 behavioral categories**:

| Category | Count | Detects |
|---|---|---|
| **Tool Execution** | 8 | Loops, error rates, latency spikes, redundant calls |
| **Cost & Resource** | 6 | Cost spikes, token explosion, per-tool cost, wasted calls |
| **Runtime & Completion** | 5 | Duration anomalies, step exhaustion, inactivity, early stops |
| **Retry & Recovery** | 5 | Retry storms, cascading retries, recovery path complexity |
| **Interaction & Control** | 4 | Intervention frequency, escalation rate, approval latency |
| **Output Quality** | 4 | Empty/low output, indeterminate status, output drift |
| **Cross-Run Patterns** | 3 | Anomaly clusters, run frequency, first-run heuristics |

All detectors are deterministic (rule-based, zero LLM dependency) and produce structured anomaly records with severity, explanation, and evidence payloads. **5 LLM-augmented detectors** (SemanticLoop, Hallucination, GoalDrift, QualityDegradation, ConfusionPattern) provide semantic analysis via local MLX models.

See the [User Guide → Reference: Anomaly Types](docs/explanation/user-guide.md#reference-anomaly-types) for the full 40-type catalog with thresholds, evidence payloads, and false-positive risks.

---

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
├── scripts/                 # DB migrations, e2e seed data
├── .github/                 # Issue/PR templates, contributing guide
├── docs/
│   ├── explanation/         # user guide, screenshots
│   ├── reference/           # setup, quickstart, instrumentation, config, limitations, releases
│   ├── architecture/        # spec, architecture diagram, DB schema
│   ├── design/              # PRD, agent designs, CLI plans, demo scenarios
│   ├── test/                # e2e test plan, seed data, test report
│   ├── field-test/          # field-test plan and reports
│   └── wbs/                 # detailed WBS (4 parts + table of contents)
├── Makefile                 # setup / lint / test / stack entrypoints
├── CHANGELOG.md
├── CONTRIBUTING.md          # → .github/CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
└── MAINTAINERS.md
```

---

## Documentation

| Doc | Audience | Purpose |
|---|---|---|
| [User Guide](docs/explanation/user-guide.md) | Operators | Full UI tour, anomaly type catalog, investigation workflows |
| [Quickstart Guide](docs/reference/quickstart.md) | Developers | Step-by-step: clone → setup → boot → seed → run demo |
| [Instrumentation Guide](docs/reference/instrumentation.md) | Developers | How to instrument LangGraph and raw Python agents |
| [Configuration Reference](docs/reference/configuration.md) | Operators / Developers | All 70+ env vars across SDK, analytics, API, web |
| [Developer Setup](docs/reference/developer-setup.md) | Contributors | Dev environment, quality gates, conventions |
| [Known Limitations](docs/reference/limitations.md) | Everyone | v0.1.0 limitations and planned resolutions |
| [Release Notes v0.1.0](docs/reference/release-notes-v0.1.0.md) | Everyone | What's in the first release |
| [CHANGELOG](CHANGELOG.md) | Everyone | Keep-a-Changelog format |
| [Architecture](docs/architecture/architecture-v0.1.0.md) | Contributors | System design and data flow |
| [Specification](docs/architecture/spec-v0.1.0.md) | Contributors | Technical spec, assumptions, open questions |
| [WBS](docs/wbs/wbs-v0.1.0.md) | Contributors | Complete work breakdown structure |
| [Test Plan](docs/test/e2e-testing-plan.md) | Contributors | E2E test plan, CUJs, screenshot strategy |
| [Test Report](docs/test/e2e-test-report-v1.md) | Contributors | M11 results: 34/34 Playwright tests pass |

---

## Testing

```bash
make test        # Python unit tests (pytest --cov)
make lint        # ruff check
make typecheck   # mypy --strict

# E2E (requires running stack)
make seed-e2e                         # seed Postgres with demo data
cd apps/web && npx playwright test    # 34 UI tests across 6 spec files
```

| Doc | Purpose |
|---|---|
| [docs/test/e2e-testing-plan.md](docs/test/e2e-testing-plan.md) | Test plan: scope, CUJs, test catalog, screenshot strategy |
| [docs/test/e2e-seed-data.md](docs/test/e2e-seed-data.md) | Mock data shape: 4 agents, 96 runs, ~240 anomalies |
| [docs/test/e2e-test-report-v1.md](docs/test/e2e-test-report-v1.md) | v0.1.0 (M11) test report — 34/34 pass, findings, v0.2.0 takeaways |

---

## Architecture

```
Agent Runtime (LangGraph / Python)
        │
        ▼
  Instrumentation SDK ─── emits behavior spans (OTLP)
        │
        ▼
  OpenTelemetry Collector
        │
        ▼
  Jaeger (raw trace storage)
        │
        ▼
  Analytics Service ─── reads traces, runs 35+ detectors
        │                  writes summaries + anomalies to Postgres
        ▼
  Postgres ◄── API Service (FastAPI) ◄── React UI (Vite)
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
| Traces | Jaeger (Tempo-compatible) |
| API / UI | FastAPI + React (Vite) |
| Analytics | Async Python worker + 35 detectors |
| Database | PostgreSQL (read-model) |
| Sample workloads | LangGraph + raw Python agents |

Everything runs locally via `docker compose up -d`. Demoable with seeded bad runs.

---

## Roadmap

### v0.1.0 — Current
- [x] Monorepo with SDK, analytics, API, web, deploy, examples
- [x] Behavior trace schema (8 semantic span types)
- [x] LangGraph + raw Python instrumentation adapters
- [x] OTLP export → Jaeger + Tempo
- [x] 35 deterministic anomaly detectors (7 categories)
- [x] 5 LLM-augmented detectors (MLX via local models)
- [x] Run Timeline with span tree, expand/collapse, anomaly markers
- [x] Fleet Health table with agent/version/workload filters
- [x] Version Compare with cost/retry/success deltas + tool usage
- [x] Anomaly Inbox with severity/type/agent triage filters
- [x] 150K real trace corpus ingested and validated (42.2% per-trace compatibility)
- [x] 34/34 Playwright e2e tests pass
- [x] Local compose stack: 6 services, 1 command

### v0.2.0
- [ ] PydanticAI adapter
- [ ] Policy overlay and memory audit views
- [ ] Span tree materialization (real spans in API, not stubbed)
- [ ] Cross-browser Playwright smoke tests
- [ ] `make e2e` wired to CI
- [ ] Event-based waits replacing `waitForTimeout` in tests
- [ ] LLM detector validation against production workloads
- [ ] Streaming trace ingestion

### Roadmap Notes

- [Semconv extension proposals](docs/architecture/spec-v0.1.0.md) should be discussed in GitHub issues and tracked in `docs/architecture/`.
- Multi-agent topology views, drift scoring, and benchmark-driven diagnostics are on the long-term radar but not committed to a specific release.

---

## Design Principles

- **Vendor-neutral** — built on OpenTelemetry, works with any OTLP-compatible backend
- **Behavior-first** — traces capture what the agent *did*, not just what it called
- **Human-readable** — default views should make bad runs obvious, not require a query language
- **Local-first** — everything runs on a laptop before it needs a cluster
- **Not framework-locked** — SDK wraps any agent runtime, starting with LangGraph and raw Python
- **Deterministic** — every detector output is reproducible given the same trace and config (LLM detectors degrade gracefully)

---

## License

MIT — see [LICENSE](LICENSE).