# Developer Setup

This is the entry point for working on `agent-exec-trace` locally.

## Prerequisites

- Python 3.10+ (`python3 --version`)
- Node.js 20+ for the web app (`node --version`)
- Docker with Docker Compose for the local stack (`docker compose version`)
- [`uv`](https://docs.astral.sh/uv/) or `pip` for Python packaging

## Repository Layout

| Path | What lives here |
|---|---|
| `packages/python-sdk/` | Instrumentation SDK (OTel spans, adapters) |
| `services/api/` | Product read API (FastAPI) |
| `services/analytics/` | Behavior analytics service (summaries, anomalies) |
| `apps/web/` | Operator UI (React) |
| `deploy/` | Compose configs, collector configs, local stack |
| `examples/` | Demo agents and seeded scenarios |
| `tests/` | Cross-cutting / end-to-end tests |
| `docs/` | PRD, architecture, spec, WBS, planning |

## Getting Started

1. Install the SDK and services in editable mode:

   ```bash
   make setup
   ```

2. Verify the quality gates:

   ```bash
   make format     # ruff format + fix
   make lint       # ruff check
   make typecheck  # mypy --strict
   make test       # pytest with coverage
   ```

3. Boot the local stack (once services are added):

   ```bash
   make stack-up
   ```

## Conventions

- Python targets 3.10+. Formatting and linting use `ruff`. Type checking uses `mypy --strict`.
- The web app targets Node 20+. Linting/formatting for the web app is defined in `apps/web/`.
- Every component must pass the quality gates in `docs/wbs-v0.1.0.md` before merge:
  ruff zero violations, mypy strict clean, tests green, coverage > 90%.

## Assumptions and Open Questions

Planning uncertainty is tracked explicitly in the spec. Keep these registers current as
implementation proceeds:

- **Assumptions register:** [`docs/spec-v0.1.0.md#assumptions-register`](spec-v0.1.0.md)
- **Open questions register:** [`docs/spec-v0.1.0.md#open-questions-register`](spec-v0.1.0.md)
- **Decision log / ADRs:** [`docs/architecture-v0.1.0.md`](architecture-v0.1.0.md)

### Deferrable past v0.1.0

These open questions are safe to defer past `v0.1.0`; they do not block the demo-first slice:

- Drift scoring as a fully implemented signal (leave room in fleet summaries only)
- Provider-accurate cost derivation (use documented best-effort logic)
