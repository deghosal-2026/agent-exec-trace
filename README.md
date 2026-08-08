<p align="center">
  <img src="https://img.shields.io/badge/agent-exec-trace-0.1.0-orange.svg" alt="version v0.1.0">
  <a href="https://pypi.org/project/agent-exec-trace/"><img src="https://img.shields.io/pypi/v/agent-exec-trace.svg" alt="PyPI version"></a>
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License">
  <a href="https://www.bestpractices.dev/projects/13979"><img src="https://www.bestpractices.dev/projects/13979/badge" alt="OpenSSF Best Practices"></a>
  <img src="https://img.shields.io/github/stars/deghosal-2026/agent-exec-trace.svg" alt="GitHub stars">
  <img src="https://img.shields.io/github/forks/deghosal-2026/agent-exec-trace.svg" alt="GitHub forks">
</p>

# agent-exec-trace

**Observability for AI agent behavior.** OpenTelemetry-style execution traces that tell you *why* an agent looped, overused tools, or burned budget — not just *that* it did.

[Quickstart](#quickstart) · [Documentation](#documentation) · [Examples](docs/examples.md) · [Architecture](#architecture)

---

## Why

Traditional observability tells you a service is up and how fast it responds. It does not tell you why an agent called a tool eight times, changed plans mid-run, or quietly drifted into expensive low-value behavior.

`agent-exec-trace` makes agent behavior inspectable at runtime. Every run emits an execution trace that reads as a behavioral story — planning, tool calls, memory mutations, retries, approvals, and cost accumulation. A 40-detector analytics engine flags anomalies automatically; an operator UI surfaces them for triage.

---

## Quickstart

```bash
git clone https://github.com/deghosal-2026/agent-exec-trace.git
cd agent-exec-trace

make setup        # install SDK + services in editable mode
make stack-up     # boot Postgres, Jaeger, Collector, API, Analytics, Web
make seed-e2e     # seed 96 runs, ~240 anomalies, 4 agents

open http://localhost:5173   # operator UI
```

Instrument your own agent in two lines:

```python
from agent_exec_trace import AgentTracer, trace_agent, tool_span

AgentTracer.setup(otlp_endpoint="http://localhost:4317")

@trace_agent(agent_name="my-agent", agent_version="1.0.0")
async def handle(query: str) -> str:
    with tool_span("search", tool_args={"q": query}):
        return await search(query)
```

> The SDK is [on PyPI](https://pypi.org/project/agent-exec-trace/): `pip install agent-exec-trace`

Full walkthroughs: [Quickstart Guide](docs/reference/quickstart.md) · [Examples](docs/examples.md) · [Instrumentation Guide](docs/reference/instrumentation.md)

---

## What It Does

| Capability | Description |
|---|---|
| Behavior trace schema | Span/event types for planning, tool use, memory, validation, approvals, escalations |
| Instrumentation SDK | Wraps LangGraph and raw Python agents; async-first |
| OTLP export | Pipes behavior data into Jaeger, Tempo, or any OTel-compatible backend |
| 35 deterministic detectors | Rule-based anomaly engine across 7 behavioral categories |
| 5 LLM detectors | Semantic detection for loops, hallucinations, goal drift, quality degradation, confusion |
| Run Timeline | Span tree with expand/collapse, anomaly markers, duration bars, attribute inspection |
| Fleet Dashboard | Cross-agent views grouped by agent/version/workload with filters and drill-down |
| Version Compare | Side-by-side deltas between cohorts (cost, retry rate, success rate, tool usage) |
| Anomaly Inbox | Prioritized triage list with severity/type/agent filters and one-click drill-down |

### Detector catalog

35 deterministic detectors across 7 categories, plus 5 LLM-augmented semantic detectors:

| Category | Count | Detects |
|---|---|---|
| **Tool Execution** | 8 | Loops, error rates, latency spikes, redundant calls |
| **Cost & Resource** | 6 | Cost spikes, token explosion, per-tool cost, wasted calls |
| **Runtime & Completion** | 5 | Duration anomalies, step exhaustion, inactivity, early stops |
| **Retry & Recovery** | 5 | Retry storms, cascading retries, recovery path complexity |
| **Interaction & Control** | 4 | Intervention frequency, escalation rate, approval latency |
| **Output Quality** | 4 | Empty/low output, indeterminate status, output drift |
| **Cross-Run Patterns** | 3 | Anomaly clusters, run frequency, first-run heuristics |
| **LLM (semantic)** | 5 | Semantic loops, hallucination, goal drift, quality degradation, confusion |

All detectors produce structured records with severity, explanation, and evidence payloads. See the [User Guide](docs/explanation/user-guide.md) for the full 40-type catalog with thresholds and false-positive risks.

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
  Jaeger / Tempo (raw trace storage)
        │
        ▼
  Analytics Service ─── reads traces, runs 40 detectors
        │                  writes summaries + anomalies to Postgres
        ▼
  Postgres ◄── API Service (FastAPI) ◄── React UI (Vite)
```

Local-first stack — 6 services, one `docker compose up -d`:

| Component | Tech |
|---|---|
| Instrumentation | OpenTelemetry Python SDK |
| Collection | OpenTelemetry Collector |
| Traces | Jaeger (Tempo-compatible) |
| API / UI | FastAPI + React (Vite) |
| Analytics | Async Python worker + 40 detectors |
| Database | PostgreSQL (read-model) |

---

## Packages

Published on PyPI:

| Package | Install | Purpose |
|---|---|---|
| **agent-exec-trace** | `pip install agent-exec-trace` | Instrumentation SDK |
| agent-exec-trace-api | `pip install agent-exec-trace-api` | Read API service |
| agent-exec-trace-analytics | `pip install agent-exec-trace-analytics` | Analytics worker + detectors |

---

## Documentation

### Getting started
| Doc | Audience | Purpose |
|---|---|---|
| [Quickstart Guide](docs/reference/quickstart.md) | Developers | Clone → setup → boot → seed → run demo |
| [Examples](docs/examples.md) | Developers | Demo agent, instrumentation snippets, privacy modes |
| [User Guide](docs/explanation/user-guide.md) | Operators | Full UI tour, anomaly catalog, investigation workflows |
| [Instrumentation Guide](docs/reference/instrumentation.md) | Developers | Instrument LangGraph and raw Python agents |
| [Deployment Guide](docs/reference/deployment.md) | Operators | Compose stack, ports, env vars, production notes |

### Reference
| Doc | Audience | Purpose |
|---|---|---|
| [API Reference](docs/reference/api.md) | Integrators | REST endpoints: health, runs, fleet, compare, anomalies |
| [Configuration Reference](docs/reference/configuration.md) | All | 70+ env vars across SDK, analytics, API, web |
| [Troubleshooting](docs/reference/troubleshooting.md) | All | Common issues: empty data, Jaeger, migrations, lint |
| [Known Limitations](docs/reference/limitations.md) | All | v0.1.0 limitations and planned resolutions |
| [Release Notes v0.1.0](docs/reference/release-notes-v0.1.0.md) | All | What's in the first release |
| [CHANGELOG](CHANGELOG.md) | All | Keep-a-Changelog format |

### Engineering
| Doc | Audience | Purpose |
|---|---|---|
| [Architecture](docs/architecture/architecture-v0.1.0.md) | Contributors | System design and data flow |
| [Specification](docs/architecture/spec-v0.1.0.md) | Contributors | Technical spec, assumptions, open questions |
| [PRD](docs/design/prd.md) | All | Product requirements, goals, non-goals |
| [Developer Setup](docs/reference/developer-setup.md) | Contributors | Dev environment, quality gates, conventions |
| [WBS](docs/wbs/wbs-v0.1.0.md) | Contributors | Complete work breakdown structure |

### Testing & validation
| Doc | Audience | Purpose |
|---|---|---|
| [Test Plan](docs/test/e2e-testing-plan.md) | Contributors | E2E test plan, CUJs, screenshot strategy |
| [Test Report](docs/test/e2e-test-report-v1.md) | Contributors | M11: 34/34 Playwright tests pass |
| [Field-Test Plan](docs/field-test/field-test-plan.md) | Contributors | Real-agent field-test scenarios, 35-detector coverage |
| [Real-Agent Test Report v2](docs/real-agent-integration/m13-real-agent-report-v2.md) | All | M13: 400 real-agent traces, no-LLM vs LLM validation |

---

## Testing

```bash
make test        # Python unit tests (pytest --cov, 95% coverage)
make lint        # ruff check (src/)
make typecheck   # mypy --strict

# E2E (requires running stack)
make seed-e2e
cd apps/web && npx playwright test    # 34 UI tests across 6 spec files
```

CI runs on every push and PR — see [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

---

## Repository Layout

```
agent-exec-trace/
├── packages/python-sdk/         # Instrumentation SDK (OTel spans, adapters)
├── services/api/                # Product read API (FastAPI)
├── services/analytics/          # Behavior analytics service (detectors, worker)
├── apps/web/                    # Operator UI (React + Vite)
├── deploy/                      # Compose configs, collector configs
├── examples/                    # Demo agents and seeded scenarios
├── scripts/                     # DB migrations, e2e seed, export scripts
├── .github/                     # Issue/PR templates, CONTRIBUTING, CI workflow
├── docs/                        # All documentation (see table above)
├── Makefile                     # setup / lint / test / stack entrypoints
├── CHANGELOG.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
└── MAINTAINERS.md
```

---

## Who It's For

- **Teams operating AI agents** in internal platforms, DevOps, or knowledge systems
- **LLMOps and evaluation teams** comparing agent versions
- **Platform engineering teams** building AI observability standards
- **OSS maintainers** who need a vendor-neutral diagnostics layer

---

## Design Principles

- **Vendor-neutral** — built on OpenTelemetry; works with any OTLP-compatible backend
- **Behavior-first** — traces capture what the agent *did*, not just what it called
- **Human-readable** — default views make bad runs obvious, no query language required
- **Local-first** — everything runs on a laptop before it needs a cluster
- **Not framework-locked** — SDK wraps any agent runtime, starting with LangGraph and raw Python
- **Deterministic** — every detector output is reproducible given the same trace and config

---

## Roadmap

**v0.1.0 (current):** SDK, 40 detectors, full UI, 150K-trace validation, 34/34 e2e tests, local compose stack.

**v0.2.0 (planned):**
- [ ] PydanticAI adapter
- [ ] Policy overlay and memory audit views
- [ ] Span tree materialization (real spans in API, not stubbed)
- [ ] Cross-browser Playwright smoke tests
- [ ] `make e2e` wired to CI
- [ ] LLM detector validation against production workloads
- [ ] Streaming trace ingestion

See the [CHANGELOG](CHANGELOG.md) for the full history and the [Known Limitations](docs/reference/limitations.md) doc for current gaps.

---

## License

MIT — see [LICENSE](LICENSE).

---

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, conventions, and areas that need help. Everyone interacting in this project is expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
