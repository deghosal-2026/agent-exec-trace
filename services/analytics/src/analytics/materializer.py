"""Materialized view builders for fleet rollups and version cohort summaries.

Materializers run after the ingestion pipeline to aggregate raw run summaries into
pre-computed views that serve the fleet health dashboard and version comparison page.

  * ``FleetRollupMaterializer``: groups runs by agent/version/workload and computes
    aggregate stats (success rate, average cost, anomaly count).
  * ``VersionCohortMaterializer``: groups runs by agent version and computes
    per-version aggregates for side-by-side comparison.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from analytics.ingest import persist_fleet_rollup, persist_version_cohort
from analytics.models import FleetRollup, VersionCohortSummary

logger = logging.getLogger(__name__)


class FleetRollupMaterializer:
    """Aggregate run summaries into fleet-level rollups grouped by agent/version/workload.

    Queries the ``run_summaries`` table, groups by the three dimensions, and
    computes aggregated metrics.  Anomaly counts are fetched separately with a
    correlated subquery against the ``anomalies`` table.
    """

    async def materialize_fleet_rollups(
        self,
        pool: Any,
        agent_name: str | None = None,
        workload_type: str | None = None,
        period_hours: int = 24,
    ) -> int:
        """Build and persist fleet rollups from the run_summaries table.

        Args:
            pool: asyncpg connection pool.
            agent_name: optional filter to a single agent.
            workload_type: optional filter to a single workload type.
            period_hours: rolling time window for the rollup (default 24h).

        Returns:
            Number of rollup rows persisted.
        """
        now = datetime.now(timezone.utc)
        period_start = now
        period_end = now

        conditions: list[str] = []
        params: list[object] = []
        idx = 1

        if agent_name:
            conditions.append(f"agent_name = ${idx}")
            params.append(agent_name)
            idx += 1

        if workload_type:
            conditions.append(f"workload_type = ${idx}")
            params.append(workload_type)
            idx += 1

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        query = f"""
            SELECT
                agent_name,
                agent_version,
                workload_type,
                COUNT(*) AS total_runs,
                COUNT(*) FILTER (WHERE status = 'success') AS success_count,
                COUNT(*) FILTER (WHERE status = 'error') AS error_count,
                COUNT(*) FILTER (WHERE loop_detected = TRUE) AS loop_count,
                AVG(duration_ms)::BIGINT AS avg_duration_ms,
                AVG(estimated_cost) AS avg_cost
            FROM run_summaries
            WHERE {where_clause}
            GROUP BY agent_name, agent_version, workload_type
        """

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        count = 0
        for row in rows:
            agent = row["agent_name"]
            version = row["agent_version"]
            workload = row["workload_type"]

            # Anomaly count is fetched separately because anomalies are in a
            # different table.  We build a filtered query matching the same
            # agent/version/workload dimensions.
            anomaly_count = 0
            if agent:
                anom_params: list[object] = [agent]
                anom_conditions = "agent_name = $1"
                anom_idx = 2
                if workload:
                    anom_conditions += (
                        " AND run_id IN ("
                        "SELECT run_id FROM run_summaries"
                        " WHERE workload_type = $" + str(anom_idx) + ")"
                    )
                    anom_params.append(workload)
                    anom_idx += 1
                if version:
                    anom_conditions += (
                        " AND run_id IN ("
                        "SELECT run_id FROM run_summaries"
                        " WHERE agent_version = $" + str(anom_idx) + ")"
                    )
                    anom_params.append(version)

                async with pool.acquire() as conn:
                    anomaly_count = await conn.fetchval(
                        f"SELECT COUNT(*) FROM anomalies WHERE {anom_conditions}",
                        *anom_params,
                    ) or 0

            rollup = FleetRollup(
                agent_name=agent,
                agent_version=version,
                workload_type=workload,
                period_start=period_start,
                period_end=period_end,
                total_runs=row["total_runs"],
                success_count=row["success_count"],
                error_count=row["error_count"],
                loop_count=row["loop_count"],
                anomaly_count=anomaly_count,
                avg_duration_ms=row["avg_duration_ms"],
                avg_cost=row["avg_cost"],
            )
            await persist_fleet_rollup(pool, rollup)
            count += 1

        logger.info("Materialized %d fleet rollups", count)
        return count


class VersionCohortMaterializer:
    """Aggregate run summaries into per-version cohort summaries.

    Groups by ``agent_name`` and ``agent_version``, computing aggregate metrics
    that the version comparison page displays side by side.
    """

    async def materialize_version_cohorts(
        self,
        pool: Any,
        agent_name: str | None = None,
    ) -> int:
        """Build and persist version cohort summaries from run_summaries.

        Args:
            pool: asyncpg connection pool.
            agent_name: optional filter to a single agent.

        Returns:
            Number of cohort rows persisted.
        """
        conditions: list[str] = []
        params: list[object] = []
        idx = 1

        if agent_name:
            conditions.append(f"agent_name = ${idx}")
            params.append(agent_name)
            idx += 1

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        query = f"""
            SELECT
                agent_name,
                agent_version,
                COUNT(*) AS total_runs,
                COUNT(*) FILTER (WHERE status = 'success') AS success_count,
                COUNT(*) FILTER (WHERE status = 'error') AS error_count,
                COUNT(*) FILTER (WHERE loop_detected = TRUE) AS loop_count,
                AVG(duration_ms)::BIGINT AS avg_duration_ms,
                AVG(estimated_cost) AS avg_cost,
                SUM(total_tool_calls) AS total_tool_calls,
                SUM(total_retries) AS total_retries
            FROM run_summaries
            WHERE agent_version IS NOT NULL
              AND {where_clause}
            GROUP BY agent_name, agent_version
        """

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        count = 0
        for row in rows:
            agent = row["agent_name"]
            version = row["agent_version"]

            anomaly_count = 0
            if agent and version:
                anomaly_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM anomalies WHERE agent_name = $1 AND run_id IN "
                    "(SELECT run_id FROM run_summaries WHERE agent_version = $2)",
                    agent,
                    version,
                ) or 0

            cohort = VersionCohortSummary(
                agent_name=agent,
                agent_version=version,
                total_runs=row["total_runs"],
                success_count=row["success_count"],
                error_count=row["error_count"],
                loop_count=row["loop_count"],
                anomaly_count=anomaly_count,
                avg_duration_ms=row["avg_duration_ms"],
                avg_cost=row["avg_cost"],
                total_tool_calls=row["total_tool_calls"],
                total_retries=row["total_retries"],
                top_tools=None,
            )
            await persist_version_cohort(pool, cohort)
            count += 1

        logger.info("Materialized %d version cohorts", count)
        return count