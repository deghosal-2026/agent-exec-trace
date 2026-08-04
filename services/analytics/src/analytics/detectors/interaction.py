"""Interaction and control anomaly detectors (4 detectors)."""

from __future__ import annotations

import logging
from typing import Any

from analytics.config import settings
from analytics.detectors.base import BaseDetector, _has_valid_pool
from analytics.models import Anomaly, RunSummary, SpanNode

logger = logging.getLogger(__name__)


class InterventionFrequencyDetector(BaseDetector):
    """Detect excessive human interventions per run."""

    anomaly_type = "intervention_frequency"

    def __init__(self, threshold: int | None = None) -> None:
        self.threshold = threshold or settings.detector_intervention_frequency_threshold

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        interventions = summary.total_interventions
        if interventions >= self.threshold:
            severity = self._severity(float(interventions), float(self.threshold))
            return self._build_anomaly(
                summary,
                severity,
                f"High intervention frequency: {interventions} "
                f"interventions (threshold: {self.threshold})",
                {
                    "interventions": interventions,
                    "threshold": self.threshold,
                },
            )
        return None


class EscalationRateDetector(BaseDetector):
    """Detect agent escalated to human too often vs baseline."""

    anomaly_type = "escalation_rate"

    def __init__(self, multiplier: float | None = None) -> None:
        self.multiplier = multiplier or settings.detector_escalation_rate_multiplier

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        return None

    async def detect_async(
        self,
        summary: RunSummary,
        spans: list[SpanNode],
        pool: Any = None,
    ) -> Anomaly | None:
        interventions = summary.total_interventions
        if interventions == 0:
            return None
        if pool is None or not summary.agent_name:
            return None
        if not _has_valid_pool(pool):
            return None

        baseline_avg = await self._get_avg_interventions(
            pool, summary.agent_name, summary.agent_version
        )
        if baseline_avg is None or baseline_avg <= 0:
            return None

        ratio = interventions / baseline_avg
        if ratio >= self.multiplier:
            severity = self._severity(ratio, self.multiplier)
            return self._build_anomaly(
                summary,
                severity,
                f"Escalation rate {interventions} is {ratio:.1f}x baseline {baseline_avg:.1f}",
                {
                    "interventions": interventions,
                    "baseline_avg": round(baseline_avg, 1),
                    "ratio": round(ratio, 1),
                    "multiplier": self.multiplier,
                },
            )
        return None

    @staticmethod
    async def _get_avg_interventions(
        pool: Any, agent_name: str, agent_version: str | None
    ) -> float | None:
        try:
            async with pool.acquire() as conn:
                if agent_version:
                    row = await conn.fetchrow(
                        "SELECT AVG(total_interventions) AS avg_int FROM run_summaries "
                        "WHERE agent_name = $1 AND agent_version = $2 AND total_interventions > 0",
                        agent_name,
                        agent_version,
                    )
                else:
                    row = await conn.fetchrow(
                        "SELECT AVG(total_interventions) AS avg_int FROM run_summaries "
                        "WHERE agent_name = $1 AND total_interventions > 0",
                        agent_name,
                    )
                if row is None:
                    return None
                val = row["avg_int"]
                if val is None:
                    return None
                return float(val)
        except Exception:
            logger.debug("Failed to fetch intervention baseline", exc_info=True)
            return None


class ApprovalLatencyDetector(BaseDetector):
    """Detect human approval took too long (>60s default)."""

    anomaly_type = "approval_latency"

    def __init__(self, max_seconds: float | None = None) -> None:
        self.max_ms = (max_seconds or settings.detector_approval_latency_seconds) * 1000

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        intervention_spans = self._find_intervention_spans(spans)
        if not intervention_spans:
            return None

        slowest: SpanNode | None = None
        slowest_duration = 0

        for span in intervention_spans:
            if span.duration_ms and span.duration_ms > slowest_duration:
                slowest_duration = span.duration_ms
                slowest = span

        if slowest and slowest_duration > self.max_ms:
            severity = self._severity(float(slowest_duration), float(self.max_ms))
            return self._build_anomaly(
                summary,
                severity,
                f"Human approval took {slowest_duration}ms (threshold: {self.max_ms}ms)",
                {
                    "approval_duration_ms": slowest_duration,
                    "threshold_ms": self.max_ms,
                    "span_id": slowest.span_id,
                    "total_intervention_spans": len(intervention_spans),
                },
            )
        return None

    @staticmethod
    def _find_intervention_spans(spans: list[SpanNode]) -> list[SpanNode]:
        result: list[SpanNode] = []
        for node in spans:
            if node.operation_name in ("human_intervention", "await_approval", "ask_user"):
                result.append(node)
            result.extend(ApprovalLatencyDetector._find_intervention_spans(node.child_spans))
        return result


class InterventionRejectionDetector(BaseDetector):
    """Detect human repeatedly overrides agent decisions."""

    anomaly_type = "intervention_rejection"

    def __init__(self, threshold: int | None = None) -> None:
        self.threshold = threshold or settings.detector_intervention_rejection_threshold

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        interventions = summary.total_interventions
        if interventions < self.threshold:
            return None

        rejection_patterns = self._detect_rejection_patterns(spans)
        if rejection_patterns >= self.threshold:
            severity = self._severity(float(rejection_patterns), float(self.threshold))
            return self._build_anomaly(
                summary,
                severity,
                f"Human repeatedly overrode agent decisions: "
                f"{rejection_patterns} rejection patterns ({interventions} interventions)",
                {
                    "rejection_count": rejection_patterns,
                    "total_interventions": interventions,
                    "threshold": self.threshold,
                },
            )
        return None

    @staticmethod
    def _detect_rejection_patterns(spans: list[SpanNode]) -> int:
        all_spans: list[SpanNode] = []
        for node in spans:
            all_spans.append(node)
            all_spans.extend(InterventionRejectionDetector._flatten(node.child_spans))

        rejection_count = 0
        for i in range(len(all_spans) - 2):
            curr = all_spans[i]
            nxt = all_spans[i + 1]
            nnxt = all_spans[i + 2]

            if (
                curr.operation_name in _INTERVENTION_OPS
                and (
                    nxt.operation_name.startswith("retry_")
                    or nxt.attributes.get("gen_ai.retry.count")
                )
                and nnxt.operation_name in _INTERVENTION_OPS
            ):
                rejection_count += 1

        return rejection_count

    @staticmethod
    def _flatten(spans: list[SpanNode]) -> list[SpanNode]:
        result: list[SpanNode] = []
        for node in spans:
            result.append(node)
            result.extend(InterventionRejectionDetector._flatten(node.child_spans))
        return result


_INTERVENTION_OPS = ("human_intervention", "await_approval", "ask_user")