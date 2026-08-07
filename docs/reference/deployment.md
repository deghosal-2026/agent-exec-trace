# Deployment Guide

This guide covers running the full `agent-exec-trace` stack locally with Docker Compose, and production-oriented notes for self-hosting.

---

## Local stack (Docker Compose)

The compose stack runs 6 services: Jaeger, OpenTelemetry Collector, Postgres, API, Analytics, and Web.

### Quickstart

```bash
git clone https://github.com/deghosal-2026/agent-exec-trace.git
cd agent-exec-trace

make setup        # install SDK + services in editable mode (optional, for dev)
make stack-up     # boot Postgres, Jaeger, Collector, API, Analytics, Web
make seed-e2e     # seed 96 runs, ~240 anomalies, 4 agents

open http://localhost:5173    # operator UI
```

### Service ports

| Service | Container port | Host port | URL |
|---|---|---|---|
| Web (React) | 5173 | 5173 | http://localhost:5173 |
| API (FastAPI) | 8000 | 8100 | http://localhost:8100 |
| Jaeger UI | 16686 | 16686 | http://localhost:16686 |
| OTLP gRPC | 4317 | 4317 | `localhost:4317` |
| OTLP HTTP | 4318 | 4318 | `localhost:4318` |
| Postgres | 5432 | 5433 | `localhost:5433` |

### Environment variables (compose)

Key environment variables are set in `docker-compose.yml`. Override any of them via a `.env` file or inline:

| Variable | Default | Service |
|---|---|---|
| `API_DB_DSN` | `postgresql://analytics:analytics@postgres:5432/analytics` | api |
| `API_CORS_ORIGINS` | `["http://localhost:5173","http://localhost:3000"]` | api |
| `ANALYTICS_DB_DSN` | `postgresql://analytics:analytics@postgres:5432/analytics` | analytics |
| `ANALYTICS_JAEGER_ENDPOINT` | `http://jaeger:16686` | analytics |
| `ANALYTICS_COLLECTOR_ENDPOINT` | `http://otel-collector:4318` | analytics |
| `ANALYTICS_TRACE_QUERY_SERVICES` | `["*"]` | analytics |
| `VITE_API_URL` | `""` | web |
| `VITE_PROXY_TARGET` | `http://api:8000` | web |

See the [Configuration Reference](configuration.md) for the full 70+ env vars.

### Database migrations

After a fresh `docker compose down -v`, re-create the read model:

```bash
make migrate-db    # creates run_summaries, anomalies, fleet_rollups, version_cohorts
```

### Tempo (alternative backend)

Grafana Tempo is available via a compose profile (default stack is Jaeger-first):

```bash
docker compose --profile tempo up -d
# OTLP endpoint for agents: http://localhost:4319
```

---

## Production notes

The local compose stack is optimized for development. For production self-hosting, consider the following:

### Postgres
- Use a managed Postgres instance (RDS, Cloud SQL, etc.) instead of the containerized one.
- Set strong credentials via `API_DB_DSN` / `ANALYTICS_DB_DSN`.
- Run migrations as part of your deploy step.

### Trace backend
- Jaeger all-in-one uses in-memory storage — not suitable for production. Deploy Jaeger with persistent storage (Elasticsearch/Cassandra) or use Grafana Tempo.
- Point `ANALYTICS_JAEGER_ENDPOINT` at your production backend.

### API and Analytics
- Run behind a reverse proxy (nginx, Caddy) with TLS.
- The API is stateless and horizontally scalable; place behind a load balancer.
- The analytics worker is a singleton poller — run one replica to avoid duplicate processing.

### Web
- Build the production bundle (`npm run build` in `apps/web`) and serve the static `dist/` via a CDN or reverse proxy.
- Set `VITE_API_URL` to the public API URL.

### Security
- See [SECURITY.md](../../SECURITY.md) for vulnerability reporting.
- Rotate the default `analytics` Postgres password before any non-local deployment.
- Restrict CORS origins to your actual front-end domain via `API_CORS_ORIGINS`.

---

## Teardown

```bash
make stack-down           # stop containers, keep data
docker compose down -v    # stop and delete volumes (fresh start)
```
