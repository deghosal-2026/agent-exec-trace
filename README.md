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

## What It Is Not

| Not | Why |
|---|---|
| A log dashboard | It does not replace your existing logging — it layers behavior semantics on top of traces |
| An evaluation framework | It shows you what happened, not whether it was correct (complements tools like EvalForge) |
| Tied to one framework | Instrumentation works across LangGraph, raw Python agents, and is designed to extend |
| A full trace backend | Built on existing OTel backends (Tempo, Jaeger) — not a replacement for them |

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
  Behavior Analytics (loop detection, cost anomaly, drift)
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
