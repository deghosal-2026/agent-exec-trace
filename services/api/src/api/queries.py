"""Database query functions for the REST API.

Each function in this module encapsulates a single database query pattern used by
the API routes.  They return raw row dicts from asyncpg, which the route handlers
then transform into Pydantic response models.

The module also provides builder functions (``build_run_timeline``,
``build_fleet_row``, ``build_version_compare``, ``build_anomaly_item``) that
convert raw database rows into the API response shapes defined in ``api.models``.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from asyncpg import Pool  # type: ignore[import-untyped]

from api.models import (
    AnomalyInboxItem,
    AnomalyInfo,
    FleetRow,
    RunSummaryInfo,
    RunSummaryStats,
    ToolDelta,
    VersionCohort,
    VersionDeltas,
)


def _to_float(val: object) -> float | None:
    """Safely convert a database value to float, handling Decimal and None."""
    if val is None:
        return None
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, int | float):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val)
        except (ValueError, TypeError):
            return None
    return None


def _to_int(val: object, default: int = 0) -> int:
    """Safely convert a database value to int, handling Decimal and None."""
    if val is None:
        return default
    if isinstance(val, int):
        return val
    if isinstance(val, Decimal):
        return int(val)
    if isinstance(val, str):
        try:
            return int(val)
        except (ValueError, TypeError):
            return default
    return default


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Convert an asyncpg row to a plain dict."""
    return dict(row)


async def get_run_summary(pool: Pool, run_id: str) -> dict[str, Any] | None:
    """Fetch a single run summary row by run_id."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM run_summaries WHERE run_id = $1", run_id
        )
        if row is None:
            return None
        return _row_to_dict(row)


async def get_run_anomalies(pool: Pool, run_id: str) -> list[dict[str, Any]]:
    """Fetch all anomalies for a given run, newest first."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM anomalies WHERE run_id = $1 ORDER BY detected_at DESC",
            run_id,
        )
        return [_row_to_dict(r) for r in rows]


async def get_fleet_rollups(
    pool: Pool,
    agent_name: str | None = None,
    agent_version: str | None = None,
    workload_type: str | None = None,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Fetch fleet rollups with optional filters and pagination.

    Returns a tuple of (rows, total_count).
    """
    conditions: list[str] = []
    params: list[object] = []
    param_idx = 1

    if agent_name:
        conditions.append(f"agent_name = ${param_idx}")
        params.append(agent_name)
        param_idx += 1
    if agent_version:
        conditions.append(f"agent_version = ${param_idx}")
        params.append(agent_version)
        param_idx += 1
    if workload_type:
        conditions.append(f"workload_type = ${param_idx}")
        params.append(workload_type)
        param_idx += 1
    if period_start:
        conditions.append(f"period_start >= ${param_idx}")
        params.append(period_start)
        param_idx += 1
    if period_end:
        conditions.append(f"period_end <= ${param_idx}")
        params.append(period_end)
        param_idx += 1

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

    async with pool.acquire() as conn:
        count_row = await conn.fetchval(
            f"SELECT COUNT(*) FROM fleet_rollups{where_clause}", *params
        )
        total = _to_int(count_row, 0)

        rows = await conn.fetch(
            f"SELECT * FROM fleet_rollups{where_clause}"
            f" ORDER BY agent_name, agent_version"
            f" LIMIT ${param_idx} OFFSET ${param_idx + 1}",
            *params,
            limit,
            offset,
        )
        return [_row_to_dict(r) for r in rows], total


async def get_version_cohort(
    pool: Pool, agent_name: str, agent_version: str
) -> dict[str, Any] | None:
    """Fetch a single version cohort summary by agent name and version."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM version_cohort_summaries WHERE agent_name = $1 AND agent_version = $2",
            agent_name,
            agent_version,
        )
        if row is None:
            return None
        return _row_to_dict(row)


async def get_anomalies(
    pool: Pool,
    severity: str | None = None,
    anomaly_type: str | None = None,
    agent_name: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Fetch anomalies with optional filters and pagination.

    Returns a tuple of (rows, total_count).
    """
    conditions: list[str] = []
    params: list[object] = []
    param_idx = 1

    if severity:
        conditions.append(f"severity = ${param_idx}")
        params.append(severity)
        param_idx += 1
    if anomaly_type:
        conditions.append(f"anomaly_type = ${param_idx}")
        params.append(anomaly_type)
        param_idx += 1
    if agent_name:
        conditions.append(f"agent_name = ${param_idx}")
        params.append(agent_name)
        param_idx += 1

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

    async with pool.acquire() as conn:
        count_row = await conn.fetchval(
            f"SELECT COUNT(*) FROM anomalies{where_clause}", *params
        )
        total = _to_int(count_row, 0)

        rows = await conn.fetch(
            f"SELECT * FROM anomalies{where_clause}"
            f" ORDER BY detected_at DESC"
            f" LIMIT ${param_idx} OFFSET ${param_idx + 1}",
            *params,
            limit,
            offset,
        )
        return [_row_to_dict(r) for r in rows], total


def build_run_timeline(
    run_data: dict[str, Any], anomalies_data: list[dict[str, Any]]
) -> dict[str, Any]:
    """Build a timeline response dict from a run summary row and its anomalies.

    Combines summary info, statistics, and anomalies into the shape expected by
    ``RunTimelineResponse`` (serialized with aliases for the frontend).
    """
    run = RunSummaryInfo(
        run_id=run_data["run_id"],
        agent_name=run_data["agent_name"],
        agent_version=run_data.get("agent_version"),
        status=run_data.get("status"),
        estimated_cost=_to_float(run_data.get("estimated_cost")),
        total_retries=_to_int(run_data.get("total_retries")),
        total_interventions=_to_int(run_data.get("total_interventions")),
    )
    summary = RunSummaryStats(
        total_tool_calls=_to_int(run_data.get("total_tool_calls")),
        loop_detected=bool(run_data.get("loop_detected", False)),
        duration_ms=run_data.get("duration_ms"),
    )
    anomalies = [
        AnomalyInfo(
            id=str(a["id"]),
            anomaly_type=str(a["anomaly_type"]),
            severity=str(a.get("severity", "warning")),
            agent_name=str(a["agent_name"]),
            run_id=str(a["run_id"]),
            summary=str(a.get("explanation") or ""),
            explanation=str(a.get("explanation") or ""),
            detected_at=a.get("detected_at"),
        )
        for a in anomalies_data
    ]
    return {
        "run": run.model_dump(by_alias=True),
        "summary": summary.model_dump(by_alias=True),
        "spans": [],
        "anomalies": [a.model_dump(by_alias=True) for a in anomalies],
    }


def build_fleet_row(row: dict[str, Any]) -> dict[str, Any]:
    """Build a fleet row response dict from a database row.

    Computes the ``success_rate`` from ``total_runs`` and ``success_count``.
    """
    total = _to_int(row.get("total_runs"))
    success = _to_int(row.get("success_count"))
    success_rate = round(success / total, 4) if total > 0 else 0.0
    return FleetRow(
        agent_name=str(row["agent_name"]),
        agent_version=row.get("agent_version"),
        workload_type=row.get("workload_type"),
        run_count=total,
        success_rate=success_rate,
        avg_cost_usd=_to_float(row.get("avg_cost")),
        anomaly_count=_to_int(row.get("anomaly_count")),
    ).model_dump()


def build_version_compare(
    left: dict[str, Any] | None,
    right: dict[str, Any] | None,
    left_version: str,
    right_version: str,
) -> dict[str, Any]:
    """Build a version comparison response dict from two cohort rows.

    Computes deltas for cost, retry rate, success rate, and per-tool usage.
    Adds warnings when cohort sizes are too small for statistical significance.
    """
    left_cohort = VersionCohort(
        version=left_version,
        run_count=_to_int(left.get("total_runs")) if left else 0,
    )
    right_cohort = VersionCohort(
        version=right_version,
        run_count=_to_int(right.get("total_runs")) if right else 0,
    )

    result: dict[str, Any] = {
        "left": left_cohort.model_dump(),
        "right": right_cohort.model_dump(),
        "deltas": {},
        "tool_deltas": [],
    }

    if left and right:
        left_cost = _to_float(left.get("avg_cost")) or 0.0
        right_cost = _to_float(right.get("avg_cost")) or 0.0
        left_retries = _to_int(left.get("total_retries"))
        right_retries = _to_int(right.get("total_retries"))
        left_runs = _to_int(left.get("total_runs"), 1)
        right_runs = _to_int(right.get("total_runs"), 1)
        left_success = _to_int(left.get("success_count"))
        right_success = _to_int(right.get("success_count"))

        result["deltas"] = VersionDeltas(
            avg_cost_usd=round(right_cost - left_cost, 6),
            retry_rate=round(
                (right_retries / right_runs) - (left_retries / left_runs), 4
            ),
            success_rate=round(
                (right_success / right_runs) - (left_success / left_runs), 4
            ),
        ).model_dump()

        left_runs_max = max(left_runs, 1)
        right_runs_max = max(right_runs, 1)

        left_tools = left.get("top_tools")
        right_tools = right.get("top_tools")
        if isinstance(left_tools, dict) and isinstance(right_tools, dict):
            tool_deltas: list[dict[str, Any]] = []
            for tool in sorted(left_tools.keys() | right_tools.keys()):
                lc = _to_int(left_tools.get(tool, 0))
                rc = _to_int(right_tools.get(tool, 0))
                lc_rate = round(lc / left_runs_max, 2)
                rc_rate = round(rc / right_runs_max, 2)
                tool_deltas.append(
                    ToolDelta(
                        tool_name=str(tool),
                        left_count=lc,
                        right_count=rc,
                        delta=rc_rate - lc_rate,
                    ).model_dump()
                )
            result["tool_deltas"] = tool_deltas

        min_runs = min(left_runs, right_runs)
        if min_runs < 5:
            result["warning"] = "sparse_cohorts"
            result["note"] = "Cohorts are small; deltas may not be statistically meaningful"
    elif left is None and right is None:
        result["warning"] = "sparse_cohorts"
        result["note"] = "Neither version cohort was found"
    elif left is None:
        result["warning"] = "sparse_cohorts"
        result["note"] = f"Left version '{left_version}' not found"
    else:
        result["warning"] = "sparse_cohorts"
        result["note"] = f"Right version '{right_version}' not found"

    return result


def build_anomaly_item(row: dict[str, Any]) -> dict[str, Any]:
    """Build an anomaly inbox item dict from a database row."""
    explanation = str(row.get("explanation") or "")
    return AnomalyInboxItem(
        id=str(row["id"]),
        anomaly_type=str(row["anomaly_type"]),
        severity=str(row.get("severity", "warning")),
        agent_name=str(row["agent_name"]),
        run_id=str(row["run_id"]),
        summary=explanation,
        explanation=explanation,
        detected_at=row.get("detected_at"),
    ).model_dump(by_alias=True)