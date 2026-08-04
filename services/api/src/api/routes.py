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

router = APIRouter(prefix="/api/v1")


async def _get_pool() -> Pool:
    """FastAPI dependency that returns the shared database connection pool."""
    return await get_pool()


@router.get("/health")
async def health() -> dict[str, str]:
    """Health check: returns 200 when the database is reachable, 503 otherwise."""
    pool = await get_pool()
    ok = await db_health(pool)
    if not ok:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"status": "ok"}


@router.get("/runs/{run_id}")
async def get_run_timeline(
    run_id: str,
    pool: Pool = Depends(_get_pool),  # noqa: B008
) -> dict[str, Any]:
    """Return the full timeline for a single run: summary, stats, spans, anomalies."""
    run_data = await get_run_summary(pool, run_id)
    if run_data is None:
        raise HTTPException(
            status_code=404,
            detail={
                "detail": "No run with this ID exists in the system",
                "code": "run_not_found",
            },
        )
    anomalies_data = await get_run_anomalies(pool, run_id)
    return build_run_timeline(run_data, anomalies_data)


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
    """Return paginated fleet health rollups, optionally filtered by agent/version/workload."""
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
    built_rows = [build_fleet_row(r) for r in rows]
    meta = PaginationMeta(total=total, page=page, page_size=page_size).model_dump()
    return {
        "data": {"rows": built_rows},
        "meta": meta,
    }


@router.get("/compare")
async def get_compare(
    agent_name: str = Query(...),  # noqa: B008
    version_a: str = Query(...),  # noqa: B008
    version_b: str = Query(...),  # noqa: B008
    workload_type: str | None = Query(None),  # noqa: B008
    pool: Pool = Depends(_get_pool),  # noqa: B008
) -> dict[str, Any]:
    """Compare two version cohorts side by side, returning deltas and tool usage."""
    left = await get_version_cohort(pool, agent_name, version_a)
    right = await get_version_cohort(pool, agent_name, version_b)
    return build_version_compare(left, right, version_a, version_b)


@router.get("/anomalies")
async def get_anomalies_endpoint(
    severity: str | None = Query(None),  # noqa: B008
    anomaly_type: str | None = Query(None),  # noqa: B008
    agent_name: str | None = Query(None),  # noqa: B008
    limit: int = Query(20, ge=1, le=100),  # noqa: B008
    offset: int = Query(0, ge=0),  # noqa: B008
    pool: Pool = Depends(_get_pool),  # noqa: B008
) -> dict[str, Any]:
    """Return paginated anomalies, optionally filtered by severity/type/agent."""
    rows, total = await get_anomalies(
        pool,
        severity=severity,
        anomaly_type=anomaly_type,
        agent_name=agent_name,
        limit=limit,
        offset=offset,
    )
    items = [build_anomaly_item(r) for r in rows]
    page = (offset // limit) + 1
    meta = PaginationMeta(total=total, page=page, page_size=limit).model_dump()
    return {
        "data": {"items": items},
        "meta": meta,
    }