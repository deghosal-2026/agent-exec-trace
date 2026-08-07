"""Database query functions for the REST API.

Each function in this module encapsulates a single database query pattern used by
the API routes.  They return raw row dicts from asyncpg, which the route handlers
then transform into Pydantic response models.

The module also provides builder functions (``build_run_timeline``,
``build_fleet_row``, ``build_version_compare``, ``build_anomaly_item``) that
convert raw database rows into the API response shapes defined in ``api.models``.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Any

from asyncpg import Pool  # type: ignore[import-untyped]

from api.models import (
    AnomalyInboxItem,
    AnomalyInfo,
    AnomalyType,
    FleetRow,
    RunSummaryInfo,
    RunSummaryStats,
    ToolDelta,
    VersionCohort,
    VersionDeltas,
)


def _to_float(val: object) -> float | None:
    """Safely convert a database value to float, handling Decimal and None.

    asyncpg returns ``NUMERIC`` columns as ``Decimal`` objects, and nullable
    columns as ``None``.  This helper normalizes both into ``float | None``
    so callers don't need to care about the database representation.

    Args:
        val: A value from an asyncpg row (may be Decimal, int, float, str, or None).

    Returns:
        The float equivalent, or None if the value was None or a non-parsable string.
    """
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
    """Safely convert a database value to int, handling Decimal and None.

    Args:
        val: A value from an asyncpg row.
        default: Value to return when conversion fails (default 0).

    Returns:
        The integer equivalent, or ``default`` on failure.
    """
    if val is None:
        return default
    if isinstance(val, int):
        return val
    if isinstance(val, Decimal):
        # Truncation (floor toward zero) is acceptable for counts/costs
        # since we never need fractional precision in int columns.
        return int(val)
    if isinstance(val, str):
        try:
            return int(val)
        except (ValueError, TypeError):
            return default
    return default


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Convert an asyncpg row to a plain dict.

    asyncpg ``Record`` objects support ``dict(row)`` which produces a
    ``dict[str, Any]`` with column-name keys.
    """
    return dict(row)


def _parse_json_object(val: object) -> dict[str, Any] | None:
    """Parse a JSON object stored as either a dict or a JSON string.

    PostgreSQL ``JSON`` / ``JSONB`` columns may come back from asyncpg as
    already-parsed Python dicts or as raw strings depending on the driver
    setup.  This handles both cases.

    Args:
        val: The raw database value for a JSON column.

    Returns:
        A dict if parsing succeeded, or None if the value is None,
        not a dict, or unparsable JSON.
    """
    if isinstance(val, dict):
        # Already a Python dict (asyncpg decoded it for us).
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, dict):
            return parsed
    return None


# ── Query functions ────────────────────────────────────────────────────────────


async def get_run_summary(pool: Pool, run_id: str) -> dict[str, Any] | None:
    """Fetch a single run summary row by run_id.

    Args:
        pool: Database connection pool.
        run_id: The run's unique identifier.

    Returns:
        A dict of column-name to value, or None if no matching run exists.
    """
    async with pool.acquire() as conn:
        # ``fetchrow`` returns a single Record or None.
        row = await conn.fetchrow(
            "SELECT * FROM run_summaries WHERE run_id = $1", run_id
        )
        if row is None:
            return None
        return _row_to_dict(row)


async def get_run_anomalies(pool: Pool, run_id: str) -> list[dict[str, Any]]:
    """Fetch all anomalies for a given run, newest first.

    Args:
        pool: Database connection pool.
        run_id: The run whose anomalies to fetch.

    Returns:
        A list of anomaly dicts, ordered by ``detected_at DESC``.
        Empty list if the run has no anomalies.
    """
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

    All filter parameters are optional; when None, that filter is skipped.
    The WHERE clause is built dynamically to avoid unnecessary conjuncts.

    Args:
        pool: Database connection pool.
        agent_name: Optional agent name filter.
        agent_version: Optional agent version filter.
        workload_type: Optional workload type filter.
        period_start: Lower bound for the rollup period start timestamp.
        period_end: Upper bound for the rollup period end timestamp.
        limit: Maximum number of rows to return.
        offset: Number of rows to skip (for pagination).

    Returns:
        A tuple of ``(rows: list[dict], total_count: int)``.
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

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

    async with pool.acquire() as conn:
        count_row = await conn.fetchval(
            f"""SELECT COUNT(*) FROM (
                SELECT 1 FROM run_summaries{where_clause}
                GROUP BY agent_name, agent_version, workload_type
            ) sub""",
            *params,
        )
        total = _to_int(count_row, 0)

        rows = await conn.fetch(
            f"""SELECT
                agent_name,
                agent_version,
                workload_type,
                COUNT(*) AS total_runs,
                COUNT(*) FILTER (WHERE status = 'success') AS success_count,
                COUNT(*) FILTER (WHERE status NOT IN ('success')) AS error_count,
                0 AS loop_count,
COALESCE((SELECT COUNT(*) FROM anomalies a WHERE a.run_id IN
                (SELECT run_id FROM run_summaries r2 WHERE r2.agent_name = run_summaries.agent_name
                 AND r2.agent_version = run_summaries.agent_version
                 AND r2.workload_type IS NOT DISTINCT FROM run_summaries.workload_type
                )), 0) AS anomaly_count,
                COALESCE(AVG(duration_ms), 0) AS avg_duration_ms,
                COALESCE(AVG(estimated_cost), 0) AS avg_cost
            FROM run_summaries{where_clause}
            GROUP BY agent_name, agent_version, workload_type
            ORDER BY anomaly_count DESC, agent_name, agent_version
            LIMIT ${param_idx} OFFSET ${param_idx + 1}""",
            *params,
            limit,
            offset,
        )
        return [_row_to_dict(r) for r in rows], total


async def get_version_cohort(
    pool: Pool, agent_name: str, agent_version: str
) -> dict[str, Any] | None:
    """Fetch a single version cohort summary by agent name and version.

    Args:
        pool: Database connection pool.
        agent_name: The agent name to look up.
        agent_version: The agent version to look up.

    Returns:
        A dict of the cohort row, or None if no matching cohort exists.
    """
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

    Args:
        pool: Database connection pool.
        severity: Optional severity filter (``"warning"``, ``"critical"``).
        anomaly_type: Optional anomaly type filter (e.g. ``"loop"``).
        agent_name: Optional agent name filter.
        limit: Maximum number of rows to return.
        offset: Number of rows to skip.

    Returns:
        A tuple of ``(rows: list[dict], total_count: int)``.  Rows are ordered
        by ``detected_at DESC`` (newest first).
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


# ── Builder functions ──────────────────────────────────────────────────────────


def build_run_timeline(
    run_data: dict[str, Any], anomalies_data: list[dict[str, Any]]
) -> dict[str, Any]:
    """Build a timeline response dict from a run summary row and its anomalies.

    Combines summary info, statistics, and anomalies into the shape expected by
    ``RunTimelineResponse`` (serialized with aliases for the frontend).

    Args:
        run_data: A dict from the ``run_summaries`` table (one row).
        anomalies_data: A list of dicts from the ``anomalies`` table linked
            to this run.

    Returns:
        A dict with keys ``run``, ``summary``, ``spans`` (empty), and ``anomalies``.
        All values are serialized with frontend-friendly field aliases.
    """
    # Build the run info model from the raw DB dict.
    # ``.get()`` is used for nullable columns in the database.
    run = RunSummaryInfo(
        run_id=run_data["run_id"],
        agent_name=run_data["agent_name"],
        agent_version=run_data.get("agent_version"),
        status=run_data.get("status"),
        estimated_cost=_to_float(run_data.get("estimated_cost")),
        total_retries=_to_int(run_data.get("total_retries")),
        total_interventions=_to_int(run_data.get("total_interventions")),
    )

    # Build the stats model. ``loop_detected`` defaults to False when the
    # column is NULL in the database (handled by ``bool(None) == False``).
    summary = RunSummaryStats(
        total_tool_calls=_to_int(run_data.get("total_tool_calls")),
        loop_detected=bool(run_data.get("loop_detected", False)),
        duration_ms=run_data.get("duration_ms"),
    )

    # Map each database anomaly row into an AnomalyInfo model.
    # ``summary`` and ``explanation`` both use the DB ``explanation`` column
    # as a fallback; they may diverge in future versions.
    anomalies = [
        AnomalyInfo(
            id=str(a["id"]),
            anomaly_type=AnomalyType(str(a["anomaly_type"])),
            severity=str(a.get("severity", "warning")),
            agent_name=str(a["agent_name"]),
            run_id=str(a["run_id"]),
            summary=str(a.get("explanation") or ""),
            explanation=str(a.get("explanation") or ""),
            detected_at=a.get("detected_at"),
        )
        for a in anomalies_data
    ]

    # Serialize with aliases so the frontend receives ``estimated_cost_usd``
    # instead of ``estimated_cost``, etc.
    return {
        "run": run.model_dump(by_alias=True),
        "summary": summary.model_dump(by_alias=True),
        "spans": [],  # Span tree reconstruction is a future feature.
        "anomalies": [a.model_dump(by_alias=True) for a in anomalies],
    }


def build_fleet_row(row: dict[str, Any]) -> dict[str, Any]:
    """Build a fleet row response dict from a database row.

    Computes the ``success_rate`` from ``total_runs`` and ``success_count``.
    The rate is rounded to 4 decimal places for display consistency.

    Args:
        row: A dict from the ``fleet_rollups`` table.

    Returns:
        A dict matching the ``FleetRow`` model shape (no aliases needed for
        fleet rows since field names match the frontend convention directly).
    """
    total = _to_int(row.get("total_runs"))

    # Compute success rate as a float between 0 and 1.
    # Guard against division by zero (empty cohort).
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

    Args:
        left: The left (baseline) version cohort row, or None if not found.
        right: The right (candidate) version cohort row, or None if not found.
        left_version: The version string for the left cohort (for display).
        right_version: The version string for the right cohort (for display).

    Returns:
        A dict matching the ``VersionCompareResponse`` shape with optional
        ``warning`` and ``note`` fields.

    Edge cases:
        - When either cohort is None, the response includes a ``sparse_cohorts``
          warning and skips delta computation.
        - When both cohorts exist but have fewer than 5 runs combined, a
          ``sparse_cohorts`` warning is appended because statistical power
          is insufficient for meaningful comparison.
        - ``tool_deltas`` requires ``top_tools`` to be a JSON dict in both
          cohorts; otherwise the list remains empty.
    """
    # Build cohort metadata regardless of data availability.
    # ``run_count`` is 0 when the cohort row doesn't exist.
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

    # Only compute deltas when both cohorts exist; otherwise skip to warnings.
    if left and right:
        # Extract and normalize all numeric values from the cohort rows.
        left_cost = _to_float(left.get("avg_cost")) or 0.0
        right_cost = _to_float(right.get("avg_cost")) or 0.0
        left_retries = _to_int(left.get("total_retries"))
        right_retries = _to_int(right.get("total_retries"))
        # Use 1 as the default for run count to avoid ZeroDivisionError below.
        left_runs = _to_int(left.get("total_runs"), 1)
        right_runs = _to_int(right.get("total_runs"), 1)
        left_success = _to_int(left.get("success_count"))
        right_success = _to_int(right.get("success_count"))

        # Compute per-metric deltas: right minus left.
        # Positive avg_cost delta = right is more expensive.
        # Positive success_rate delta = right is more successful.
        # Positive retry_rate delta = right retries more.
        result["deltas"] = VersionDeltas(
            avg_cost_usd=round(right_cost - left_cost, 6),
            retry_rate=round(
                (right_retries / right_runs) - (left_retries / left_runs), 4
            ),
            success_rate=round(
                (right_success / right_runs) - (left_success / left_runs), 4
            ),
        ).model_dump()

        # Use max(..., 1) to avoid division by zero when computing tool rates.
        left_runs_max = max(left_runs, 1)
        right_runs_max = max(right_runs, 1)

        # Parse and compare per-tool usage counts.
        # ``top_tools`` is a JSON column storing either a dict {tool: count}
        # or a list of tool names.  Only dict shapes produce meaningful deltas.
        left_tools = _parse_json_object(left.get("top_tools"))
        right_tools = _parse_json_object(right.get("top_tools"))
        if left_tools is not None and right_tools is not None:
            tool_deltas: list[dict[str, Any]] = []
            # Union all tool names from both cohorts so missing tools show
            # as zero-count on the other side.
            for tool in sorted(left_tools.keys() | right_tools.keys()):
                lc = _to_int(left_tools.get(tool, 0))
                rc = _to_int(right_tools.get(tool, 0))
                # Compute per-run rates for comparability when cohort sizes differ.
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

        # Statistical power check: fewer than 5 runs in either cohort is
        # unreliable for comparison.
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
    """Build an anomaly inbox item dict from a database row.

    Args:
        row: A dict from the ``anomalies`` table.

    Returns:
        A dict matching the ``AnomalyInboxItem`` shape with frontend aliases.
        Both ``summary`` and ``explanation`` use the DB ``explanation`` column;
        they may diverge in future versions when a dedicated short summary is
        added to the anomalies schema.
    """
    explanation = str(row.get("explanation") or "")
    return AnomalyInboxItem(
        id=str(row["id"]),
        anomaly_type=AnomalyType(str(row["anomaly_type"])),
        severity=str(row.get("severity", "warning")),
        agent_name=str(row["agent_name"]),
        run_id=str(row["run_id"]),
        summary=explanation,
        explanation=explanation,
        detected_at=row.get("detected_at"),
    ).model_dump(by_alias=True)
