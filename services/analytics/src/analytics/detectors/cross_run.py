"""Cross-run pattern anomaly detectors (3 detectors)."""

from __future__ import annotations

import logging
from typing import Any

from analytics.config import settings
from analytics.detectors.base import BaseDetector, _has_valid_pool
from analytics.models import Anomaly, RunSummary, SpanNode

logger = logging.getLogger(__name__)


class AnomalyClusterDetector(BaseDetector):
    """Detect multiple anomaly types firing in the same run (>=3)."""

    anomaly_type = "anomaly_cluster"

    def __init__(self, min_anomaly_types: int | None = None) -> None:
        self.min_anomaly_types = (
            min_anomaly_types or settings.detector_anomaly_cluster_min_types
        )

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        return None

    async def detect_async(
        self,
        summary: RunSummary,
        spans: list[SpanNode],
        pool: Any = None,
    ) -> Anomaly | None:
        if pool is None:
            return None
        if not _has_valid_pool(pool):
            return None

        anomaly_types = await self._get_run_anomaly_types(pool, summary.run_id)
        unique_types = set(anomaly_types)

        if len(unique_types) >= self.min_anomaly_types:
            severity = "critical"
            return self._build_anomaly(
                summary,
                severity,
                f"Anomaly cluster: {len(unique_types)} distinct "
                f"anomaly types on this run: {sorted(unique_types)}",
                {
                    "distinct_anomaly_types": len(unique_types),
                    "anomaly_types": sorted(unique_types),
                    "threshold": self.min_anomaly_types,
                },
            )
        return None

    @staticmethod
    async def _get_run_anomaly_types(pool: Any, run_id: str) -> list[str]:
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT DISTINCT anomaly_type FROM anomalies WHERE run_id = $1",
                    run_id,
                )
                return [row["anomaly_type"] for row in rows]
        except Exception:
            logger.debug("Failed to fetch anomaly types for run", exc_info=True)
            return []


class RunFrequencyAnomalyDetector(BaseDetector):
    """Detect too many or too few runs for a version."""

    anomaly_type = "run_frequency_anomaly"

    def __init__(
        self,
        min_runs: int | None = None,
        max_multiplier: float | None = None,
    ) -> None:
        self.min_runs = min_runs or settings.detector_run_frequency_min_runs
        self.max_multiplier = max_multiplier or settings.detector_run_frequency_max_multiplier

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        return None

    async def detect_async(
        self,
        summary: RunSummary,
        spans: list[SpanNode],
        pool: Any = None,
    ) -> Anomaly | None:
        if pool is None or not summary.agent_name:
            return None
        if not _has_valid_pool(pool):
            return None

        count = await self._get_run_count(
            pool, summary.agent_name, summary.agent_version
        )
        if count is None:
            return None

        if count < self.min_runs and count > 0:
            return self._build_anomaly(
                summary,
                "warning",
                f"Low run count for version cohort: "
                f"{summary.agent_version or 'latest'} has only {count} runs",
                {
                    "run_count": count,
                    "min_expected": self.min_runs,
                    "agent_version": summary.agent_version,
                },
            )

        if count > self.min_runs * self.max_multiplier:
            severity = self._severity(float(count), float(self.min_runs * self.max_multiplier))
            return self._build_anomaly(
                summary,
                severity,
                f"High run frequency: {count} runs for version {summary.agent_version or 'latest'}",
                {
                    "run_count": count,
                    "threshold": self.min_runs * self.max_multiplier,
                    "agent_version": summary.agent_version,
                },
            )
        return None

    @staticmethod
    async def _get_run_count(
        pool: Any, agent_name: str, agent_version: str | None
    ) -> int | None:
        try:
            async with pool.acquire() as conn:
                if agent_version:
                    row = await conn.fetchrow(
                        "SELECT COUNT(*) AS cnt FROM run_summaries "
                        "WHERE agent_name = $1 AND agent_version = $2",
                        agent_name,
                        agent_version,
                    )
                else:
                    row = await conn.fetchrow(
                        "SELECT COUNT(*) AS cnt FROM run_summaries "
                        "WHERE agent_name = $1",
                        agent_name,
                    )
                if row is None:
                    return None
                return int(row["cnt"])
        except Exception:
            logger.debug("Failed to fetch run count", exc_info=True)
            return None


class FirstRunHeuristicDetector(BaseDetector):
    """Flag first run of a new agent version for review."""

    anomaly_type = "first_run_heuristic"

    def __init__(self) -> None:
        pass

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        return None

    async def detect_async(
        self,
        summary: RunSummary,
        spans: list[SpanNode],
        pool: Any = None,
    ) -> Anomaly | None:
        if pool is None or not summary.agent_name or not summary.agent_version:
            return None
        if not _has_valid_pool(pool):
            return None

        is_first = await self._is_first_version_run(
            pool, summary.agent_name, summary.agent_version, summary.run_id
        )
        if is_first:
            return self._build_anomaly(
                summary,
                "info",
                f"First run of agent version {summary.agent_version} — flagged for review",
                {
                    "agent_version": summary.agent_version,
                    "agent_name": summary.agent_name,
                },
            )
        return None

    @staticmethod
    async def _is_first_version_run(
        pool: Any, agent_name: str, agent_version: str, current_run_id: str
    ) -> bool:
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT COUNT(*) AS cnt, MIN(run_id) AS first_run FROM run_summaries "
                    "WHERE agent_name = $1 AND agent_version = $2",
                    agent_name,
                    agent_version,
                )
                if row is None:
                    return True
                count = int(row["cnt"])
                first_run = row["first_run"]
                return bool(count <= 1 and first_run == current_run_id)
        except Exception:
            logger.debug("Failed to check first run", exc_info=True)
            return False