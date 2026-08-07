"""Interaction and control anomaly detectors (4 detectors).

These detectors analyze human-agent interaction patterns: intervention
frequency, escalation rates, approval latency, and repeated human overrides.

**Overview**: When agents interact with humans (for approval, clarification,
or escalation), the pattern of those interactions provides signals about
agent reliability and alignment.  Too many interventions suggests the agent
is uncertain; too few escalations when needed suggests over-confidence.

**Detectors in this module:**

1. **InterventionFrequencyDetector**: Detects excessive human interventions
   per run (≥3 by default).  High intervention count means the agent needed
   constant human guidance.

2. **EscalationRateDetector**: Compares the current run's intervention count
   to the version cohort baseline.  2x baseline suggests the agent is
   escalating too often.

3. **ApprovalLatencyDetector**: Detects when human approval took too long
   (>60s default).  Slow approvals suggest the human-in-the-loop is a
   bottleneck.

4. **InterventionRejectionDetector**: Detects when the human repeatedly
   overrides the agent's decisions (intervention → retry → intervention
   pattern).  Indicates misalignment between agent decisions and human
   expectations.
"""

from __future__ import annotations

import logging
from typing import Any

from analytics.config import settings
from analytics.detectors.base import BaseDetector, _has_valid_pool
from analytics.models import Anomaly, RunSummary, SpanNode

logger = logging.getLogger(__name__)


class InterventionFrequencyDetector(BaseDetector):
    """Detect excessive human interventions per run.

    **What it catches**: A run where the agent needed human input 3+ times.
    This suggests the agent is uncertain, making poor decisions that require
    correction, or operating in a domain where automation is insufficient.

    **False-positive risks**:
    - Agents designed for high-interaction workflows (e.g., pair programming,
      document review).  The threshold should be tuned per workload type.
    - The detector uses ``total_interventions`` from the run summary, which
      is an aggregate set by the trace instrumentation.  If instruments
      count differently, the threshold may need adjustment.

    **Threshold rationale**: 3 interventions is a conservative threshold.
    A single intervention is common (approval gates).  2 might be a
    clarification and an approval.  3+ suggests persistent human dependency.

    **Evidence produced**: ``interventions`` (count), ``threshold``.
    """

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
    """Detect agent escalated to human too often vs baseline.

    **What it catches**: The current run's intervention count exceeds the
    version cohort baseline by 2x.  This means this particular run required
    far more human involvement than is typical for this agent version.

    **Why compare to baseline?**  Different agent versions have different
    natural intervention rates.  An agent that always needs 2 interventions
    should not be flagged every run — only runs that deviate significantly
    from the norm should fire.

    **False-positive risks**:
    - Requires a baseline with intervention data (``total_interventions > 0``
      in the database).  If no baseline exists, the detector returns None
      (no false positive, but also no signal).
    - Small sample sizes in the baseline.

    **Evidence produced**: ``interventions``, ``baseline_avg``, ``ratio``,
    ``multiplier``.
    """

    anomaly_type = "escalation_rate"

    def __init__(self, multiplier: float | None = None) -> None:
        self.multiplier = multiplier or settings.detector_escalation_rate_multiplier

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        # REQUIRES database pool for baseline computation.
        return None

    async def detect_async(
        self,
        summary: RunSummary,
        spans: list[SpanNode],
        pool: Any = None,
    ) -> Anomaly | None:
        interventions = summary.total_interventions
        if interventions == 0:
            return None  # No interventions to compare.
        if pool is None or not summary.agent_name:
            return None
        if not _has_valid_pool(pool):
            return None

        baseline_avg = await self._get_avg_interventions(
            pool, summary.agent_name, summary.agent_version
        )
        if baseline_avg is None or baseline_avg <= 0:
            return None  # No baseline yet.

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
        """Compute average intervention count for a version cohort.

        Includes only runs with at least 1 intervention so the baseline
        represents "when interventions happen, how many?" rather than
        the diluted average across all runs (most of which have 0).
        """
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
    """Detect human approval took too long (>60s default).

    **What it catches**: When the agent waits for human approval and the
    human takes longer than the configured threshold to respond.  This
    indicates the human-in-the-loop is a bottleneck for the agent.

    **How it finds approval spans**: Walks the span tree looking for
    spans with operation names ``human_intervention``, ``await_approval``,
    or ``ask_user``.  The span's ``duration_ms`` represents the total
    time the agent spent waiting for the human.

    **False-positive risks**:
    - Humans may legitimately need time to review complex decisions.
      The threshold should be tuned to your approval SLA.
    - If the human never responds (stale approval), the span duration
      may be extremely large, which this detector WILL catch.

    **Evidence produced**: ``approval_duration_ms``, ``threshold_ms``,
    ``span_id``, ``total_intervention_spans``.
    """

    anomaly_type = "approval_latency"

    def __init__(self, max_seconds: float | None = None) -> None:
        # Convert to milliseconds for comparison with span.duration_ms.
        self.max_ms = (max_seconds or settings.detector_approval_latency_seconds) * 1000

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        intervention_spans = self._find_intervention_spans(spans)
        if not intervention_spans:
            return None

        # Find the slowest approval span (not just any slow one).
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
        """Recursively find all spans related to human intervention/waiting."""
        result: list[SpanNode] = []
        for node in spans:
            if node.operation_name in ("human_intervention", "await_approval", "ask_user"):
                result.append(node)
            result.extend(ApprovalLatencyDetector._find_intervention_spans(node.child_spans))
        return result


class InterventionRejectionDetector(BaseDetector):
    """Detect human repeatedly overrides agent decisions.

    **What it catches**: A pattern where the agent makes a decision, the
    human intervenes (rejects/corrects it), the agent retries, and the
    human intervenes AGAIN.  This is the "back and forth" pattern that
    indicates the agent is not learning from human corrections.

    **How it works**: Scans the flattened span list for the pattern:
    intervention → retry_* (or retry attribute) → intervention.  This
    three-span sequence represents: human says "no" → agent tries again
    → human says "no" again.

    **False-positive risks**:
    - Complex multi-step human interactions (human approves part A, agent
      moves to part B, human approves part B).  The detector may count
      these as rejections.  Mitigated by requiring the threshold (2+ by
      default).

    **Evidence produced**: ``rejection_count``, ``total_interventions``,
    ``threshold``.
    """

    anomaly_type = "intervention_rejection"

    def __init__(self, threshold: int | None = None) -> None:
        self.threshold = threshold or settings.detector_intervention_rejection_threshold

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        interventions = summary.total_interventions
        if interventions < self.threshold:
            return None  # Not enough interventions to have a rejection pattern.

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
        """Count intervention→retry→intervention triples in the span sequence.

        The algorithm flattens the tree and scans for triples where:
        - span[i] is an intervention operation
        - span[i+1] is a retry (operation starts with "retry_" or has retry count)
        - span[i+2] is an intervention operation
        """
        # Flatten the span tree into an ordered list.
        all_spans: list[SpanNode] = []
        for node in spans:
            all_spans.append(node)
            all_spans.extend(InterventionRejectionDetector._flatten(node.child_spans))

        rejection_count = 0
        # Scan sliding window of 3 consecutive spans.
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
        """Recursively flatten a span subtree."""
        result: list[SpanNode] = []
        for node in spans:
            result.append(node)
            result.extend(InterventionRejectionDetector._flatten(node.child_spans))
        return result


# Recognized intervention operation names shared across interaction detectors.
_INTERVENTION_OPS = ("human_intervention", "await_approval", "ask_user")
