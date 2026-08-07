"""Cross-run pattern anomaly detectors (3 detectors).

These detectors analyze patterns across multiple runs, requiring database
access to query historical run data.

**Detectors in this module:**

1. **AnomalyClusterDetector**: Detects when multiple distinct anomaly types
   fire on the same run (≥3 types).  A cluster of different anomaly types
   suggests the run is fundamentally problematic, not just a single issue.

2. **RunFrequencyAnomalyDetector**: Detects when a version cohort has too
   few or too many runs relative to expectations.  Too few runs suggests
   deployment issues; too many suggests runaway automation.

3. **FirstRunHeuristicDetector**: Flags the first run of a new agent version
   for human review.  Informational (severity: "info") — not an anomaly
   per se, but worth attention since new versions may have unexpected
   behavior patterns.
"""

from __future__ import annotations

import logging
from typing import Any

from analytics.config import settings
from analytics.detectors.base import BaseDetector, _has_valid_pool
from analytics.models import Anomaly, RunSummary, SpanNode

logger = logging.getLogger(__name__)


class AnomalyClusterDetector(BaseDetector):
    """Detect multiple anomaly types firing in the same run (≥3 by default).

    **What it catches**: A run that triggers 3+ different anomaly types
    simultaneously.  This is a meta-detector: it doesn't analyze the trace
    directly but queries the ``anomalies`` table for the run to count
    distinct anomaly types.

    **Why this matters**: A single anomaly type (e.g., "loop") might be
    a false positive.  But 3+ different types firing on the SAME run strongly
    suggests the run is genuinely problematic — it's failing in multiple
    independent ways.

    **Severity**: Always "critical" because multiple simultaneous anomalies
    indicate a severely compromised run.

    **When this fires**: After all other detectors have run and persisted
    their anomalies.  This detector is ordered last in the worker's
    detection pass, ensuring it queries the anomalies table after other
    detectors have written to it.

    **Evidence produced**: ``distinct_anomaly_types`` (count), ``anomaly_types``
    (list of type names), ``threshold`` (minimum for clustering).
    """

    anomaly_type = "anomaly_cluster"

    def __init__(self, min_anomaly_types: int | None = None) -> None:
        self.min_anomaly_types = min_anomaly_types or settings.detector_anomaly_cluster_min_types

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        # Sync path returns None — this detector requires a database pool.
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

        # Query all anomaly types for this run.
        anomaly_types = await self._get_run_anomaly_types(pool, summary.run_id)
        unique_types = set(anomaly_types)

        if len(unique_types) >= self.min_anomaly_types:
            return self._build_anomaly(
                summary,
                "critical",  # Clusters are always critical.
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
        """Fetch all anomaly_type values for a given run_id from the database.

        Returns an empty list on any error (detector should not crash on
        database failures).
        """
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
    """Detect too many or too few runs for a version cohort.

    **What it catches**:
    - Too few runs (<5 by default): suggests deployment issues, agent
      configuration problems, or that the version is not being used.
    - Too many runs (>5 * 3 = 15 by default): suggests runaway automation,
      excessive retries, or a deployment bug causing repeated execution.

    **How it works**: Queries the ``run_summaries`` table for the count of
    runs matching the same ``agent_name`` + ``agent_version``.  Compares
    the count to the threshold range [min_runs, min_runs * max_multiplier].

    **False-positive risks**:
    - New versions naturally have few runs.  This is intentional — the
      detector flags low counts so operators can verify the version is
      healthy.  The FirstRunHeuristicDetector provides a similar but
      more specific signal.
    - High-traffic versions may legitimately have many runs.  The max
      multiplier (3x) is intentionally high to avoid false positives on
      busy agents.

    **Evidence produced**:
    - ``run_count``, ``min_expected`` (or ``threshold``), ``agent_version``.
    """

    anomaly_type = "run_frequency_anomaly"

    def __init__(
        self,
        min_runs: int | None = None,
        max_multiplier: float | None = None,
    ) -> None:
        self.min_runs = min_runs or settings.detector_run_frequency_min_runs
        self.max_multiplier = max_multiplier or settings.detector_run_frequency_max_multiplier

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        # REQUIRES database pool — sync path returns None.
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

        count = await self._get_run_count(pool, summary.agent_name, summary.agent_version)
        if count is None:
            return None

        # Case 1: Too few runs (but >0 — a count of 0 means the version
        # hasn't been deployed yet, which isn't anomalous).
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

        # Case 2: Too many runs (exceeding max_multiplier * min_runs).
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
    async def _get_run_count(pool: Any, agent_name: str, agent_version: str | None) -> int | None:
        """Query the database for the number of runs matching agent+version.

        Returns ``None`` on any error (detector degrades gracefully).
        """
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
                        "SELECT COUNT(*) AS cnt FROM run_summaries WHERE agent_name = $1",
                        agent_name,
                    )
                if row is None:
                    return None
                return int(row["cnt"])
        except Exception:
            logger.debug("Failed to fetch run count", exc_info=True)
            return None


class FirstRunHeuristicDetector(BaseDetector):
    """Flag first run of a new agent version for review.

    **What it catches**: The very first run of a specific agent + version
    combination.  This is always worth reviewing because:
    - New versions may behave differently.
    - Initial instrumentation may be incorrect.
    - Baseline metrics don't exist yet for this version.

    **Severity**: Always "info" — this is not an anomaly, just a flag for
    attention.  It's informational rather than warning/critical because
    the first run being first is expected.

    **How it works**: Queries the database for runs matching the same
    agent_name + agent_version.  If only 1 run exists and its run_id
    matches the current run, this is the first run.

    **Evidence produced**: ``agent_version``, ``agent_name``.
    """

    anomaly_type = "first_run_heuristic"

    def __init__(self) -> None:
        pass

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        # REQUIRES database pool.
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
                "info",  # Informational — not an anomaly, just a flag.
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
        """Check if this run_id is the only run for its agent+version cohort.

        Uses MIN(run_id) as a tiebreaker: even if the count is 1, we also
        verify the run_id matches to prevent race conditions where the count
        changes between query and check.
        """
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT COUNT(*) AS cnt, MIN(run_id) AS first_run FROM run_summaries "
                    "WHERE agent_name = $1 AND agent_version = $2",
                    agent_name,
                    agent_version,
                )
                if row is None:
                    return True  # No data = this is the first run.
                count = int(row["cnt"])
                first_run = row["first_run"]
                return bool(count <= 1 and first_run == current_run_id)
        except Exception:
            logger.debug("Failed to check first run", exc_info=True)
            return False
