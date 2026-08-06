"""FastAPI route definitions for the agent-exec-trace REST API.

Provides endpoints under ``/api/v1`` for:

  * ``GET /health`` -- database connectivity check.
  * ``GET /runs/{run_id}`` -- run timeline detail.
  * ``GET /fleet`` -- fleet health rollups (paginated, filterable).
  * ``GET /compare`` -- version comparison.
  * ``GET /anomalies`` -- anomaly inbox (paginated, filterable).

All endpoints use asyncpg connection pools injected via FastAPI's dependency
injection system.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from asyncpg import Pool  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, HTTPException, Query

from api.db import get_pool
from api.db import health_check as db_health
from api.models import PaginationMeta
from api.queries import (
    build_anomaly_item,
    build_fleet_row,
    build_run_timeline,
    build_version_compare,
    get_anomalies,
    get_fleet_rollups,
    get_run_anomalies,
    get_run_summary,
    get_version_cohort,
)

logger = logging.getLogger(__name__)

# All endpoints in this module share the ``/api/v1`` prefix.
router = APIRouter(prefix="/api/v1")


async def _get_pool() -> Pool:
    """FastAPI dependency that returns the shared database connection pool.

    Used via ``Depends(_get_pool)`` in endpoint signatures.  FastAPI calls
    this for each request; the pool itself is a singleton, so the call is
    cheap (just returns the cached pool reference).
    """
    return await get_pool()


# ── Health ─────────────────────────────────────────────────────────────────────


@router.get("/health")
async def health() -> dict[str, str]:
    """Health check: returns 200 when the database is reachable, 503 otherwise.

    Response shape (200):
        {"status": "ok"}

    Response shape (503):
        HTTPException detail "Database unavailable"

    This endpoint is consumed by Docker health checks, Kubernetes liveness
    probes, and load balancers.  It does NOT accept query parameters.
    """
    pool = await get_pool()
    ok = await db_health(pool)
    if not ok:
        # 503 Service Unavailable is the standard HTTP response for degraded
        # dependency states.  Load balancers should temporarily route traffic
        # away from this instance.
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"status": "ok"}


# ── Run Timeline ───────────────────────────────────────────────────────────────


@router.get("/runs/{run_id}")
async def get_run_timeline(
    run_id: str,
    pool: Pool = Depends(_get_pool),  # noqa: B008
) -> dict[str, Any]:
    """Return the full timeline for a single run: summary, stats, spans, anomalies.

    Path parameters:
        run_id: The unique run identifier (UUID or tracing run ID).

    Response shape (200):
        ``RunTimelineResponse`` serialized with frontend-friendly aliases:
        {
            "run": { "run_id", "agent_name", "estimated_cost_usd", ... },
            "summary": { "tool_call_count", "loop_detected", "duration_ms" },
            "spans": [ { "span_id", "parent_span_id", "operation_name", ... } ],
            "anomalies": [ { "anomaly_id", "type", "severity", ... } ]
        }

    Error case (404):
        When no run with this ID exists in ``run_summaries``.  Returns a
        JSON body with ``detail`` and ``code`` keys for structured frontend
        error handling:
        {
            "detail": "No run with this ID exists in the system",
            "code": "run_not_found"
        }

    Note:
        The ``spans`` list is currently empty; span-tree reconstruction from
        telemetry data is planned for a future milestone.
    """
    run_data = await get_run_summary(pool, run_id)
    if run_data is None:
        # Structured error response with ``detail`` and ``code`` so the
        # frontend can switch on ``code`` rather than parsing error strings.
        raise HTTPException(
            status_code=404,
            detail={
                "detail": "No run with this ID exists in the system",
                "code": "run_not_found",
            },
        )
    anomalies_data = await get_run_anomalies(pool, run_id)
    return build_run_timeline(run_data, anomalies_data)


# ── Fleet Health ───────────────────────────────────────────────────────────────


@router.get("/fleet")
async def get_fleet(
    agent_name: str | None = Query(None),  # noqa: B008
    version: str | None = Query(None, alias="agent_version"),  # noqa: B008
    workload_type: str | None = Query(None),  # noqa: B008
    period_start: datetime | None = Query(None),  # noqa: B008
    period_end: datetime | None = Query(None),  # noqa: B008
    page: int = Query(1, ge=1),  # noqa: B008
    page_size: int = Query(20, ge=1, le=100),  # noqa: B008
    pool: Pool = Depends(_get_pool),  # noqa: B008
) -> dict[str, Any]:
    """Return paginated fleet health rollups, optionally filtered by agent/version/workload.

    Query parameters (all optional):
        agent_name: Filter to a specific agent.
        agent_version: Filter to a specific agent version.
        workload_type: Filter to a specific workload category.
        period_start: ISO-8601 datetime; lower bound for the rollup period.
        period_end: ISO-8601 datetime; upper bound for the rollup period.
        page: 1-based page number (default 1, minimum 1).
        page_size: Items per page (default 20, range 1-100).

    Response shape (200):
        {
            "data": {
                "rows": [
                    { "agent_name", "agent_version", "run_count",
                      "success_rate", "avg_cost_usd", "anomaly_count" }
                ]
            },
            "meta": { "total": <int>, "page": <int>, "page_size": <int> }
        }

    Error cases:
        - 422: When query parameter types/constraints are violated (FastAPI
          auto-validates: page < 1, page_size > 100, invalid datetime format).
    """
    # Convert 1-based page to 0-based offset for SQL LIMIT/OFFSET.
    offset = (page - 1) * page_size
    rows, total = await get_fleet_rollups(
        pool,
        agent_name=agent_name,
        agent_version=version,
        workload_type=workload_type,
        period_start=period_start,
        period_end=period_end,
        limit=page_size,
        offset=offset,
    )
    # Transform each database row into the FleetRow shape with computed
    # success_rate and aliased cost field.
    built_rows = [build_fleet_row(r) for r in rows]
    meta = PaginationMeta(total=total, page=page, page_size=page_size).model_dump()
    return {
        "data": {"rows": built_rows},
        "meta": meta,
    }


# ── Version Compare ────────────────────────────────────────────────────────────


@router.get("/compare")
async def get_compare(
    agent_name: str = Query(...),  # noqa: B008
    version_a: str = Query(...),  # noqa: B008
    version_b: str = Query(...),  # noqa: B008
    workload_type: str | None = Query(None),  # noqa: B008
    pool: Pool = Depends(_get_pool),  # noqa: B008
) -> dict[str, Any]:
    """Compare two version cohorts side by side, returning deltas and tool usage.

    Query parameters:
        agent_name (required): The agent whose versions to compare.
        version_a (required): The "left" (baseline) version string.
        version_b (required): The "right" (candidate) version string.
        workload_type (optional): Further filter by workload.

    Response shape (200):
        {
            "left": { "version": "<vA>", "run_count": <int> },
            "right": { "version": "<vB>", "run_count": <int> },
            "deltas": {
                "avg_cost_usd": <float|None>,
                "retry_rate": <float|None>,
                "success_rate": <float|None>
            },
            "tool_deltas": [
                { "tool_name", "left_count", "right_count", "delta" }
            ],
            "warning": <str|None>,
            "note": <str|None>
        }

    Edge cases:
        - If either version cohort is missing, the response includes a
          ``warning: "sparse_cohorts"`` and a descriptive ``note``.
        - If both cohorts have fewer than 5 runs, ``sparse_cohorts`` warning
          is added because deltas may not be statistically meaningful.
        - If neither version is found (both None), a note is returned.
        - ``tool_deltas`` is empty when tool data is unavailable (JSON parse
          failure or missing ``top_tools`` column).
        - The ``workload_type`` parameter is accepted but not yet wired into
          the version_cohort lookup; it is reserved for future use.
    """
    left = await get_version_cohort(pool, agent_name, version_a)
    right = await get_version_cohort(pool, agent_name, version_b)
    return build_version_compare(left, right, version_a, version_b)


# ── Anomaly Inbox ──────────────────────────────────────────────────────────────


@router.get("/anomalies")
async def get_anomalies_endpoint(
    severity: str | None = Query(None),  # noqa: B008
    anomaly_type: str | None = Query(None),  # noqa: B008
    agent_name: str | None = Query(None),  # noqa: B008
    limit: int = Query(20, ge=1, le=100),  # noqa: B008
    offset: int = Query(0, ge=0),  # noqa: B008
    pool: Pool = Depends(_get_pool),  # noqa: B008
) -> dict[str, Any]:
    """Return paginated anomalies, optionally filtered by severity/type/agent.

    Query parameters (all optional):
        severity: Filter by anomaly severity (``"warning"``, ``"critical"``).
        anomaly_type: Filter by anomaly type string (e.g. ``"loop"``,
            ``"cost_spike"``).  Must match values in ``AnomalyType`` enum.
        agent_name: Filter to anomalies detected for a specific agent.
        limit: Items per page (default 20, range 1-100).
        offset: 0-based offset for pagination (default 0).

    Response shape (200):
        {
            "data": {
                "items": [
                    { "anomaly_id", "type", "severity", "agent_name",
                      "run_id", "summary", "explanation", "created_at" }
                ]
            },
            "meta": { "total": <int>, "page": <int>, "page_size": <int> }
        }

    Error cases:
        - 422: When constraint violations occur (limit < 1, limit > 100,
          offset < 0).
    """
    rows, total = await get_anomalies(
        pool,
        severity=severity,
        anomaly_type=anomaly_type,
        agent_name=agent_name,
        limit=limit,
        offset=offset,
    )
    # Transform each raw DB row into the AnomalyInboxItem shape with aliased
    # field names (e.g. ``id`` becomes ``anomaly_id`` in the response).
    items = [build_anomaly_item(r) for r in rows]

    # Compute 1-based page number from 0-based offset for the response meta.
    # This is a best-effort conversion: if limit is 0 (should never happen
    # due to validation), fallback to page 1.
    page = (offset // limit) + 1
    meta = PaginationMeta(total=total, page=page, page_size=limit).model_dump()
    return {
        "data": {"items": items},
        "meta": meta,
    }
