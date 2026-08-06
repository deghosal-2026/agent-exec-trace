# Developer Quickstart

Get `agent-exec-trace` running locally in under 10 minutes. This guide covers
the full loop: boot the stack, seed demo data, explore traces.

## Prerequisites

- **Python 3.10+** — `python3 --version`
- **Node.js 20+** — `node --version`
- **Docker** with Docker Compose — `docker compose version`
- `uv` or `pip` for Python packaging (the Makefile uses `pip install -e`)

## Step 1 — Clone and setup

```bash
git clone https://github.com/deghosal-2026/agent-exec-trace.git
cd agent-exec-trace
make setup
```

`make setup` installs three Python packages in editable mode:

| Package | Path | Purpose |
|---|---|---|
| **python-sdk** | `packages/python-sdk/` | Instrumentation SDK (OTel spans, LangGraph + raw adapters) |
| **api** | `services/api/` | Product read API (FastAPI) |
| **analytics** | `services/analytics/` | Behavior analytics worker (summaries, anomaly detectors) |

## Step 2 — Boot the local stack

```bash
make stack-up
```

This boots six containers via `docker-compose.yml`:

| Service | Port | Role |
|---|---|---|
| **Jaeger** | `16686` | Trace backend + UI; receives OTLP gRPC on `4317` |
| **OTel Collector** | `4318` | Optional collector-mediated export path |
| **Postgres** | `5433` | Read-model database (analytics materialized state) |
| **API** | `8000` | FastAPI read API for the web UI |
| **Analytics** | — | Worker: polls Jaeger, runs 35 detectors, persists to Postgres |
| **Web** | `5173` | React + Vite operator UI |

Wait ~30 seconds for all services to report healthy (`docker compose ps`).

## Step 3 — Seed demo data

```bash
make seed-e2e
```

Inserts mock data into Postgres: **96 runs, ~240 anomalies, 4 agents** across
normal, loop, cost-spike, and retry-storm scenarios. Every product view will
show non-empty data.

To reset and re-seed:

```bash
docker compose down -v    # destroys Postgres volume
make stack-up
make seed-e2e
```

## Step 4 — Open the UI

Navigate to **http://localhost:5173**. You should see:

- **Fleet Health** — agent cohorts, run counts, anomaly counts, filtering
- **Run Timeline** — span tree + anomalies for a single trace
- **Version Compare** — side-by-side delta between two agent versions
- **Anomaly Inbox** — triage surface with type/severity filters

## Step 5 — Run the demo agent

```bash
cd examples/demo-agent
python3 run_demo.py
```

The demo agent (`request-triage`) exercises three behavioral paths:

| Scenario | What happens | Expected outcome |
|---|---|---|
| **Normal** | Known query, valid account → single search + lookup → resolves | Clean span tree, no anomalies |
| **Loop** | Missing account → repeated `search_kb` + `lookup_account` cycles | Loop detector fires |
| **High-cost** | Open-ended query → many tool turns, no early exit | Cost spike detector fires |

Traces flow: **SDK → OTLP gRPC (`:4317`) → Jaeger → Analytics worker polls → Postgres → API → Web UI**.

## Step 6 — Verify traces in Jaeger

Open **http://localhost:16686** in your browser.

- Select the `agent-exec-trace` service from the dropdown
- Click **Find Traces** — you should see root `invoke_agent` spans
- Drill into a trace to inspect child spans: `plan`, `execute_tool`, `retrieval`

Traces may take 15–30 seconds to appear after running the demo agent (the
analytics worker polls Jaeger on a configurable interval).

## Step 7 — Check quality gates

```bash
make lint       # ruff check — zero violations required
make typecheck  # mypy --strict — zero errors required
make test       # pytest with coverage — >90% required
```

All three must pass before merging. The WBS quality gates are non-negotiable.

## Project structure

```
agent-exec-trace/
├── packages/python-sdk/     # Instrumentation SDK
│   └── src/agent_exec_trace/
├── services/api/            # FastAPI read API
├── services/analytics/      # Analytics worker + 35 detectors
├── apps/web/                # React + Vite operator UI
├── deploy/                  # Collector config, compose overrides
├── examples/demo-agent/     # request-triage demo agent
├── tests/                   # Cross-cutting tests
├── docs/                    # Architecture, design, WBS, reference
├── scripts/                 # seed-e2e-data.py, migrate-db.py
├── docker-compose.yml       # Local dev stack
├── Makefile                 # Entry point for all dev commands
└── pyproject.toml           # Shared ruff, pytest, mypy config
```

## Makefile targets reference

| Target | Command | What it does |
|---|---|---|
| `setup` | `pip install -e` × 3 | Installs SDK, API, analytics in editable mode |
| `format` | `ruff format && ruff check --fix` | Auto-format + fix lint across all packages |
| `lint` | `ruff check` | Lint check only (no fixes) |
| `typecheck` | `mypy --strict` | Strict type checking |
| `test` | `pytest --cov` | Run tests with coverage |
| `stack-up` | `docker compose up -d` | Boot all 6 containers |
| `stack-down` | `docker compose down` | Tear down the stack |
| `migrate` | `alembic upgrade head` | Run analytics DB migrations |
| `migrate-db` | `scripts/migrate-db.py` | Create read-model tables in compose Postgres |
| `seed-e2e` | `scripts/seed-e2e-data.py` | Seed mock data for e2e testing |
| `api` | `uvicorn api.main:app` | Run API locally (outside Docker) |
| `clean` | `find -exec rm` | Remove `__pycache__`, `.pytest_cache`, etc. |

## Tempo (alternative backend)

The default stack is Jaeger-first. To boot with Tempo instead:

```bash
docker compose --profile tempo up -d
```

The Tempo UI is at `http://localhost:3200` and OTLP ingestion on `:4319`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `make stack-up` fails with port conflict | Check `5433`, `8000`, `5173`, `16686`, `4317` are free |
| API returns empty arrays | Run `make seed-e2e` to populate Postgres |
| Jaeger shows no traces | Wait for analytics worker poll cycle or restart with `docker compose restart analytics` |
| `make test` fails on coverage | Coverage threshold is 90%; check `pytest --cov-report=term-missing` |
| Web UI shows CORS errors | Ensure `VITE_API_URL` is empty and proxy target is `http://api:8000` |
