# API Reference

The `agent-exec-trace` API is a FastAPI service that serves product-facing views from the normalized Postgres read model. All endpoints are prefixed with `/api/v1`.

Base URL (local): `http://localhost:8100/api/v1`

---

## Endpoints

### `GET /api/v1/health`

Database connectivity check.

**Response 200:**
```json
{"status": "ok"}
```
**Response 503:** `Database unavailable` — Postgres is not reachable.

---

### `GET /api/v1/runs/{run_id}`

Full timeline for a single run: summary, stats, spans, and anomalies.

**Path parameters:**
| Name | Type | Description |
|---|---|---|
| `run_id` | string | Unique run identifier (UUID or tracing run ID). |

**Response 200:**
```json
{
  "run": { "run_id": "...", "agent_name": "...", "estimated_cost_usd": 0.0 },
  "summary": { "tool_call_count": 0, "loop_detected": false, "duration_ms": 0 },
  "spans": [ { "span_id": "...", "parent_span_id": null, "operation_name": "..." } ],
  "anomalies": [ { "anomaly_id": "...", "type": "loop", "severity": "warning" } ]
}
```
**Response 404:**
```json
{ "detail": "No run with this ID exists in the system", "code": "run_not_found" }
```

> Note: the `spans` list is currently empty; span-tree reconstruction is planned for a future milestone.

---

### `GET /api/v1/fleet`

Paginated fleet health rollups, optionally filtered by agent/version/workload.

**Query parameters (all optional):**
| Name | Type | Default | Description |
|---|---|---|---|
| `agent_name` | string | — | Filter to a specific agent. |
| `agent_version` | string | — | Filter to a specific agent version. |
| `workload_type` | string | — | Filter to a specific workload category. |
| `period_start` | ISO-8601 datetime | — | Lower bound for the rollup period. |
| `period_end` | ISO-8601 datetime | — | Upper bound for the rollup period. |
| `page` | int | `1` | 1-based page number (min 1). |
| `page_size` | int | `100` | Items per page (range 1–500). |

**Response 200:**
```json
{
  "data": {
    "rows": [
      { "agent_name": "...", "agent_version": "...", "run_count": 0,
        "success_rate": 0.0, "avg_cost_usd": 0.0, "anomaly_count": 0 }
    ]
  },
  "meta": { "total": 0, "page": 1, "page_size": 100 }
}
```
**Response 422:** Query parameter type/constraint violation (FastAPI auto-validates).

---

### `GET /api/v1/compare`

Compare two version cohorts side by side, returning deltas and tool usage.

**Query parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `agent_name` | string | yes | The agent whose versions to compare. |
| `version_a` | string | yes | The baseline ("left") version. |
| `version_b` | string | yes | The candidate ("right") version. |
| `workload_type` | string | no | Further filter by workload (reserved for future use). |

**Response 200:**
```json
{
  "left": { "version": "<vA>", "run_count": 0 },
  "right": { "version": "<vB>", "run_count": 0 },
  "deltas": { "avg_cost_usd": 0.0, "retry_rate": 0.0, "success_rate": 0.0 },
  "tool_deltas": [ { "tool_name": "...", "left_count": 0, "right_count": 0, "delta": 0 } ],
  "warning": null,
  "note": null
}
```

**Edge cases:**
- If either cohort is missing or both have fewer than 5 runs, `warning: "sparse_cohorts"` is returned with a descriptive `note`.
- `tool_deltas` is empty when tool data is unavailable.

---

### `GET /api/v1/anomalies`

Paginated anomaly inbox, optionally filtered by severity/type/agent.

**Query parameters (all optional):**
| Name | Type | Default | Description |
|---|---|---|---|
| `severity` | string | — | `"warning"` or `"critical"`. |
| `anomaly_type` | string | — | Anomaly type string (e.g. `"loop"`, `"cost_spike"`). |
| `agent_name` | string | — | Filter to anomalies for a specific agent. |
| `limit` | int | `20` | Items per page (range 1–1000). |
| `offset` | int | `0` | 0-based offset for pagination. |

**Response 200:**
```json
{
  "data": {
    "items": [
      { "anomaly_id": "...", "type": "loop", "severity": "warning",
        "agent_name": "...", "run_id": "...", "summary": "...",
        "explanation": "...", "created_at": "2026-01-01T00:00:00Z" }
    ]
  },
  "meta": { "total": 0, "page": 1, "page_size": 20 }
}
```
**Response 422:** Constraint violation (limit < 1, limit > 1000, offset < 0).

---

## Error conventions

All errors return JSON. Standard HTTP status codes are used:

| Code | Meaning |
|---|---|
| 200 | Success |
| 404 | Resource not found (structured `code` field for frontend handling) |
| 422 | Validation error (FastAPI auto-generated) |
| 503 | Downstream dependency unavailable (e.g. Postgres down) |

## Interactive docs

When the API service is running, FastAPI auto-generates interactive documentation:

- **Swagger UI:** `http://localhost:8100/docs`
- **ReDoc:** `http://localhost:8100/redoc`
