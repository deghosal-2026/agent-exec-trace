# Changelog

All notable changes to agent-exec-trace will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **Async `@trace_agent` bug** (`packages/python-sdk/`) — top-level `@trace_agent` on `async def` agents returned the coroutine without awaiting inside the span context, producing duplicate root spans (one parsed as `agent_name='unknown'`) and flat children. Wrapper now infers coroutine functions via `inspect.iscoroutinefunction` and awaits inside the invocation span.

- **Worker trace fetch cap** (`services/analytics/`) — the poll loop fetched at most 50 traces per service per cycle, silently capping high-volume agents. Fetch limit is now configurable via `AnalyticsSettings.trace_fetch_limit` (default 1000).

- **Fleet rollup NULL counts** (`services/api/`) — fleet anomaly counts returned 0 when `workload_type` was NULL by comparing with `=` instead of `IS NOT DISTINCT FROM`.

- **Dashboard/inbox pagination caps** (`services/api/`, `apps/web/`) — raised the anomaly and trace page limits to 1000 to match ingestion volume.

- **OSS tests** (`services/analytics/tests/test_worker.py`) — updated `test_auto_discovery_falls_back_on_failure` to assert the configurable `trace_fetch_limit` instead of the removed hard-coded `50`.

## [0.1.0] — 2026-08-05

### Added

- **Instrumentation SDK** (`packages/python-sdk/`)
  - Raw Python decorator (`@trace_agent`) with `plan_span`, `tool_span`, `retrieval_span`, `memory_span`, `approval_span` context managers
  - LangGraph adapter (`TracedGraph`) for automatic node-level instrumentation
  - Direct OTLP export via `AgentTracer` API
  - Four privacy modes: Metadata-only (default), Truncated, Hashed, Full
  - Version and workload metadata propagation (`agent_name`, `agent_version`, `workload_type`)
  - Optional secondary version dimensions (`prompt_version`, `model_version`, `tool_schema_version`)

- **35 rule-based anomaly detectors** (`services/analytics/`)
  - Tool Execution (8): argument_loop, tool_loop, tool_error_rate, tool_latency_spike, redundant_tool_call, wasted_tool_calls, tool_count_exhaustion, tool_mix_anomaly
  - Cost & Resource (6): cost_spike, token_explosion, per_tool_cost, wasted_cost, cost_vs_baseline, step_efficiency
  - Runtime & Completion (5): duration_anomaly, premature_completion, step_exhaustion, inactivity, early_stop
  - Retry & Recovery (5): retry_storm, cascading_retry, recovery_complexity, retry_success_rate, escalation_rate
  - Interaction & Control (4): intervention_frequency, approval_latency, human_loop_count, control_surface_anomaly
  - Output Quality (4): empty_response, low_output, indeterminate_status, output_drift
  - Cross-Run Patterns (3): anomaly_cluster, run_frequency_anomaly, first_run_heuristic

- **5 optional LLM-augmented detectors** (feature-flagged, disabled by default)
  - SemanticLoop, Hallucination, GoalDrift, QualityDegradation, ConfusionPattern

- **Analytics pipeline** (`services/analytics/`)
  - Jaeger polling for trace ingestion
  - Run summary materialization into Postgres
  - Fleet rollup and version cohort summary computation
  - Structured anomaly records with severity, explanation, and evidence payloads
  - Configurable thresholds per detector per workload

- **FastAPI read API** (`services/api/`)
  - `/api/runs` — run list with filtering
  - `/api/runs/{id}` — single run timeline
  - `/api/fleet` — fleet health rollups
  - `/api/compare` — version-to-version deltas
  - `/api/anomalies` — anomaly inbox with type/severity filtering

- **React web UI** (`apps/web/`)
  - Fleet Health view — agent cohorts, run counts, anomaly counts, status/name filters
  - Run Timeline view — span tree, anomaly badges, run metadata
  - Version Compare view — side-by-side delta between two agent versions
  - Anomaly Inbox view — triage surface with type/severity filters
  - Agent Detail view — per-agent metrics, tool mix, cost trend, anomaly history

- **Demo agent** (`examples/demo-agent/`)
  - `request-triage` LangGraph agent with three deterministic behavioral paths (normal, loop, high-cost)
  - `run_demo.py` script for one-command demo execution

- **Seed and replay workflow** (`scripts/seed-e2e-data.py`)
  - 96 mock runs, ~240 anomalies, 4 agents across normal/loop/cost-spike/retry-storm scenarios

- **Documentation** (`docs/`)
  - Architecture spec (spec-v0.1.0.md), architecture diagrams (architecture-v0.1.0.md)
  - PRD, synthetic agent design, demo scenario, trace dataset sources
  - Field test plan, reports (v1, v2, synthetic), anomaly validation matrix
  - Developer setup guide, quickstart guide, instrumentation guide
  - Known limitations, release notes
  - Complete WBS (4 parts)

- **E2E Playwright tests** (`apps/web/tests/e2e/`)
  - Fleet Health, Run Timeline, Version Compare, Anomaly Inbox view tests
  - Automated screenshot capture for user guide
  - Demo acceptance assertion suite

- **Field testing**
  - 100K-trace Hugging Face corpus validation (7/35 detectors firing)
  - 10-trace LLM detector sample (Qwen2.5-1.5B-4bit)
  - Synthetic corpus validation (99.2% compatibility score)
  - Compatibility audit pipeline with per-trace/per-detector reporting

### Infrastructure

- Monorepo structure: `packages/`, `services/`, `apps/`, `deploy/`, `examples/`, `tests/`, `docs/`
- Docker Compose local stack (6 services): Jaeger, OTel Collector, Postgres, API, Analytics, Web
- Jaeger-first trace backend with Tempo compatibility profile
- `Makefile` with targets: setup, format, lint, typecheck, test, stack-up, stack-down, seed-e2e, migrate-db, migrate, api, clean
- Shared `pyproject.toml` with ruff, pytest, mypy configuration
- `.pre-commit-config.yaml` for pre-commit hooks
- `.python-version` (3.10) and `.node-version` (20)
- Quality gates: ruff zero violations, mypy strict clean, tests green, coverage > 90%

### Known Issues

See [docs/reference/limitations.md](docs/reference/limitations.md) for full details.

- No streaming trace ingestion (batch polling only, ~30s delay)
- No distributed trace correlation across services
- No multi-tenant isolation
- LLM detectors are research-grade only (10-trace sample, not production-validated)
- 28/35 detectors silent on HF field-test corpus (structurally dependent on tool-use semantics)
- 42.2% per-trace compatibility score on HF corpus
- No PydanticAI adapter
- No policy overlay view or memory audit UI
- Stubbed span trees in e2e tests (seeded data only, no live trace e2e)
- Trace replay depends on running Jaeger instance

[Unreleased]: https://github.com/deghosal-2026/agent-exec-trace/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/deghosal-2026/agent-exec-trace/releases/tag/v0.1.0