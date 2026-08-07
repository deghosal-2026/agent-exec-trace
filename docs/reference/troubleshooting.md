# Troubleshooting

Common issues and fixes when running `agent-exec-trace`.

---

## Stack won't boot

### `docker compose up` fails with port conflict

Ports 5173, 8100, 16686, 4317, 5433 are in use.

```bash
# find what's using a port
lsof -i :5433

# stop the local service occupying it, or remap in docker-compose.yml
```

### Postgres health check never passes

```bash
docker compose logs postgres
# ensure POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_DB are set (default: analytics)
docker compose down -v && docker compose up -d   # fresh start
```

---

## Empty dashboard / no data

### Fleet board shows nothing after seeding

The analytics worker may not have polled yet (30s default). Verify:

```bash
docker compose logs analytics --tail 50
curl http://localhost:8100/api/v1/health    # should return {"status":"ok"}
curl "http://localhost:8100/api/v1/fleet"   # check raw data
```

If Postgres is empty, re-seed:

```bash
make seed-e2e
```

### Traces not appearing in Jaeger

1. Confirm the OTLP endpoint is correct. Agents should export to `http://localhost:4317` (gRPC) or `http://localhost:4318` (HTTP).
2. Check the collector is forwarding:
   ```bash
   docker compose logs otel-collector --tail 50
   ```
3. Verify the service name appears in Jaeger UI → Service dropdown.

### Analytics worker logs "falling back to demo-agent"

`ANALYTICS_TRACE_QUERY_SERVICES` is set to `["*"]` (auto-discovery) but Jaeger's `/services` endpoint failed. Either fix Jaeger connectivity, or set the explicit list:

```bash
ANALYTICS_TRACE_QUERY_SERVICES='["my-agent"]'
```

---

## Database issues

### Migration errors

The analytics Docker image does not ship `alembic.ini`. Run migrations from the host:

```bash
make migrate-db
```

Or programmatically:

```python
import psycopg2, pathlib
conn = psycopg2.connect("postgresql://analytics:analytics@localhost:5433/analytics")
conn.autocommit = True
cur = conn.cursor()
cur.execute(pathlib.Path("services/analytics/src/analytics/migrations/versions/001_initial_schema.py").read_text())
```

### Reset the database completely

```bash
docker compose down -v   # destroys the pgdata volume
docker compose up -d
make migrate-db
make seed-e2e
```

---

## SDK / instrumentation

### `agent_name='unknown'` in traces

The `@trace_agent` decorator must wrap the actual `async def` function (not a sync wrapper that returns a coroutine). Ensure you're using a current SDK version:

```bash
pip install --upgrade agent-exec-trace
```

### Spans are flat (no parent-child nesting)

Nested `plan_span` / `tool_span` calls must run *inside* the `@trace_agent`-wrapped function body. If you spawn a task or thread, ensure OTel context is propagated.

### No spans exported at all

1. Verify the OTLP exporter is configured:
   ```python
   from agent_exec_trace import AgentTracer
   AgentTracer.setup(otlp_endpoint="http://localhost:4317")
   ```
2. Check `ANALYTICS_LLM_API_KEY` / privacy mode — `METADATA_ONLY` mode (default) still exports spans, just without argument content.

---

## Build / quality gates

### `make lint` reports errors

```bash
make format    # auto-fix with ruff
make lint      # re-check
```

Pre-existing lint errors in test files are known; CI lints `src/` only.

### `make typecheck` (mypy) fails

Most mypy strict failures are in test files. To check source only:

```bash
cd packages/python-sdk && mypy --strict src/
cd services/api && mypy --strict src/
cd services/analytics && mypy --strict src/
```

### `make test` fails

```bash
cd services/analytics && pytest -x --no-cov   # stop on first failure
```

---

## Still stuck?

- Check the [Known Limitations](limitations.md) doc.
- Open an issue using the [bug report template](https://github.com/deghosal-2026/agent-exec-trace/issues/new).
- See [SECURITY.md](../../SECURITY.md) for vulnerability reporting.
