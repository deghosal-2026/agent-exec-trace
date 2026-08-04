"""Anomaly detection algorithms for agent execution traces.

Three detectors map to the product's key anomaly types:

  * ``LoopDetector``: identifies runs where the same tool is called many times
    consecutively, indicating the agent is stuck in a loop.
  * ``RetryStormDetector``: flags runs with excessive retries, suggesting a
    persistent error condition.
  * ``CostSpikeDetector``: catches runs whose cost exceeds either an absolute
    threshold or a multiplier of the version cohort's baseline.

Each detector returns an ``Anomaly`` when triggered, or ``None`` for a healthy run.
"""

from __future__ import annotations

import logging
from typing import Any

from analytics.config import settings
from analytics.models import Anomaly, RunSummary, SpanNode

logger = logging.getLogger(__name__)


class LoopDetector:
    """Detect runs where the same tool is called consecutively beyond a threshold.

    Walks the span tree, extracts tool call names in order, and counts consecutive
    repeats.  A sequence of identical tool calls exceeding the threshold produces
    a loop anomaly.
    """

    def __init__(self, threshold: int | None = None) -> None:
        self.threshold = threshold or settings.loop_threshold

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        """Scan the span tree for consecutive identical tool calls.

        Args:
            summary: the run summary (used for metadata like run_id/agent_name).
            spans: root-level span nodes from the parsed trace tree.

        Returns:
            An ``Anomaly`` with type ``"loop"`` if the threshold is exceeded,
            or ``None`` otherwise.
        """
        tool_calls: list[str] = []

        def walk(nodes: list[SpanNode]) -> None:
            for node in nodes:
                if node.operation_name == "execute_tool":
                    tool_name = str(node.attributes.get("gen_ai.tool.name", ""))
                    tool_calls.append(tool_name)
                walk(node.child_spans)

        walk(spans)

        max_consecutive = 0
        current = 0
        last_tool = ""
        repeated_tool = ""

        for tool_name in tool_calls:
            if tool_name == last_tool and tool_name:
                current += 1
                if current > max_consecutive:
                    max_consecutive = current
                    repeated_tool = tool_name
            else:
                current = 1
                last_tool = tool_name

        if max_consecutive >= self.threshold:
            # Severity scales with the number of consecutive calls: 10+ is critical.
            severity = "critical" if max_consecutive >= 10 else "warning"

            return Anomaly(
                run_id=summary.run_id,
                agent_name=summary.agent_name,
                anomaly_type="loop",
                severity=severity,
                explanation=(
                    f"Tool '{repeated_tool}' called {max_consecutive} times consecutively"
                ),
                evidence={
                    "tool_name": repeated_tool,
                    "consecutive_calls": max_consecutive,
                    "threshold": self.threshold,
                },
            )

        return None


class RetryStormDetector:
    """Detect runs with an excessive number of retries.

    Retries are counted from the ``total_retries`` field in the run summary, which
    is populated by the SDK's retry-count attribute.
    """

    def __init__(self, threshold: int | None = None) -> None:
        self.threshold = threshold or settings.retry_threshold

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        """Check if the run's retry count exceeds the threshold.

        Args:
            summary: run summary containing ``total_retries``.
            spans: unused (kept for interface consistency across detectors).

        Returns:
            An ``Anomaly`` with type ``"retry_storm"`` if the threshold is exceeded,
            or ``None`` otherwise.
        """
        retries = summary.total_retries

        if retries >= self.threshold:
            severity = "critical" if retries >= 10 else "warning"

            return Anomaly(
                run_id=summary.run_id,
                agent_name=summary.agent_name,
                anomaly_type="retry_storm",
                severity=severity,
                explanation=(
                    f"Run had {retries} retries (threshold: {self.threshold})"
                ),
                evidence={
                    "total_retries": retries,
                    "threshold": self.threshold,
                },
            )

        return None


class CostSpikeDetector:
    """Detect runs whose cost exceeds thresholds.

    Two independent checks: an absolute threshold (any run over $X is flagged) and a
    relative threshold (a run that costs more than N times the version cohort's
    baseline).  The relative check requires a database pool to query the baseline.
    """

    def __init__(
        self,
        absolute_threshold: float | None = None,
        baseline_multiplier: float | None = None,
    ) -> None:
        self.absolute_threshold = (
            absolute_threshold if absolute_threshold is not None else settings.cost_threshold_usd
        )
        self.baseline_multiplier = baseline_multiplier if baseline_multiplier is not None else 2.0

    async def detect(
        self,
        summary: RunSummary,
        spans: list[SpanNode],
        pool: Any = None,
    ) -> Anomaly | None:
        """Check if the run's estimated cost exceeds thresholds.

        Args:
            summary: run summary containing ``estimated_cost``.
            spans: unused (kept for interface consistency).
            pool: optional asyncpg pool for querying version cohort baselines.

        Returns:
            An ``Anomaly`` with type ``"cost_spike"`` if any threshold is exceeded,
            or ``None`` otherwise.
        """
        cost = summary.estimated_cost
        if cost is None:
            return None

        reasons: list[str] = []

        if cost > self.absolute_threshold:
            reasons.append(
                f"absolute spike: ${cost:.2f} exceeds ${self.absolute_threshold:.2f}"
            )

        baseline: float | None = None
        if pool is not None and summary.agent_version:
            from analytics.ingest import _get_version_cohort_baseline

            baseline = await _get_version_cohort_baseline(
                pool, summary.agent_name, summary.agent_version
            )
            if baseline is not None and cost > baseline * self.baseline_multiplier:
                reasons.append(
                    f"relative spike: ${cost:.2f} is {cost / baseline:.1f}x "
                    f"baseline ${baseline:.2f} (multiplier: {self.baseline_multiplier})"
                )

        if not reasons:
            return None

        severity: str = "warning"
        if cost > self.absolute_threshold * 3:
            severity = "critical"

        evidence: dict[str, object] = {
            "cost": cost,
            "absolute_threshold": self.absolute_threshold,
        }

        if baseline is not None:
            evidence["baseline_cost"] = baseline
            evidence["baseline_multiplier"] = self.baseline_multiplier

        return Anomaly(
            run_id=summary.run_id,
            agent_name=summary.agent_name,
            anomaly_type="cost_spike",
            severity=severity,
            explanation="; ".join(reasons),
            evidence=evidence,
        )