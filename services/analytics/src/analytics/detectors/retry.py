"""Retry and recovery anomaly detectors (5 detectors).

These detectors analyze retry behavior: count, success rate, cascading
effects, and recovery complexity.

**Detectors in this module:**

1. **RetryStormDetector**: Detects runs with an excessive total number of
   retries (>5 by default).  The simplest retry detector — a pure count
   threshold.

2. **SystemicRetryDetector**: Detects when ALL retries failed (0% success
   rate).  A systemic retry failure suggests the underlying issue is not
   transient (e.g., permanent auth failure, misconfigured tool).

3. **TransientRetryDetector**: Detects many retries where all/most succeeded
   (≥50% success rate).  Downgraded to "info" severity because retries
   that succeed are annoying (latency, cost) but not broken.

4. **CascadingRetryDetector**: Detects retry chains across different tools
   — retry in tool A triggers retry in tool B.  This suggests the failure
   is propagating across the tool chain.

5. **RecoveryPathDetector**: Detects unusually complex recovery after an
   error — the agent took many extra tool calls (>5 by default) after the
   first error.  Suggests the agent struggled to recover gracefully.
"""

from __future__ import annotations

import logging

from analytics.config import settings
from analytics.detectors.base import BaseDetector
from analytics.models import Anomaly, RunSummary, SpanNode

logger = logging.getLogger(__name__)


class RetryStormDetector(BaseDetector):
    """Detect runs with an excessive number of retries.

    **What it catches**: Any run where ``total_retries >= threshold`` (5 by
    default).  This is the most basic retry anomaly — a pure count that
    doesn't differentiate between successful and failed retries.

    **False-positive risks**:
    - Rates: agents that intentionally retry as part of their workflow
      (e.g., generating multiple candidate responses).  The threshold (5)
      is set to capture only unusually retry-heavy runs.

    **Threshold rationale**: 5 retries represent significant wasted effort.
    Most healthy runs have 0-2 retries.

    **Evidence produced**: ``total_retries``, ``threshold``.
    """

    anomaly_type = "retry_storm"

    def __init__(self, threshold: int | None = None) -> None:
        self.threshold = threshold or settings.retry_threshold

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        retries = summary.total_retries

        if retries >= self.threshold:
            severity = self._severity(float(retries), float(self.threshold))
            return self._build_anomaly(
                summary,
                severity,
                f"Run had {retries} retries (threshold: {self.threshold})",
                {
                    "total_retries": retries,
                    "threshold": self.threshold,
                },
            )
        return None


class SystemicRetryDetector(BaseDetector):
    """Detect when all retries failed (0% success rate).

    **What it catches**: Every retry attempt failed — the agent kept trying
    but never succeeded.  This is distinct from RetryStormDetector, which
    only cares about count.  A systemic failure with 3 retries at 0% is
    more concerning than a transient storm with 10 retries at 90%.

    **How retry outcomes are determined**:
    1. If a span has ``gen_ai.retry.successful`` attribute, use it directly.
    2. Otherwise, if the span's operation_name starts with "retry_", treat
       status "ok"/"OK"/None/" as success, anything else as failure.

    **Why require 2+ retries?**  A single failed retry is just an error.
    Multiple failed retries indicate a pattern of systemic failure.

    **Evidence produced**: ``total_retries``, ``retry_events``, ``success_rate`` (always 0.0).

    **False-positive risks**: Low — a 0% success rate across multiple retries
    is almost always a genuine systemic issue.
    """

    anomaly_type = "systemic_retry"

    def __init__(self) -> None:
        pass

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        retries = summary.total_retries
        if retries < 2:
            return None  # Need at least 2 retries to claim "systemic".

        retry_outcomes = self._collect_retry_outcomes(spans)
        if not retry_outcomes:
            return None  # No retry spans found to evaluate.

        # If ALL retries failed, it's systemic.
        success_rate = sum(retry_outcomes) / len(retry_outcomes)
        if success_rate == 0.0:
            return self._build_anomaly(
                summary,
                "critical",  # Systemic failure is always critical.
                f"Systemic retry failure: 0/{len(retry_outcomes)} "
                f"retries succeeded ({retries} total retries)",
                {
                    "total_retries": retries,
                    "retry_events": len(retry_outcomes),
                    "success_rate": 0.0,
                },
            )
        return None

    @staticmethod
    def _collect_retry_outcomes(spans: list[SpanNode]) -> list[bool]:
        """Collect boolean success outcomes from retry spans.

        Returns:
            A list of ``bool`` values where ``True`` = retry succeeded,
            ``False`` = retry failed.
        """
        outcomes: list[bool] = []
        for span in SystemicRetryDetector._walk_spans_local(spans):
            # Direct attribute: explicit success/failure marker.
            retry_attr = span.attributes.get("gen_ai.retry.successful")
            if retry_attr is not None:
                outcomes.append(bool(retry_attr))
            # Operation name heuristic: spans starting with "retry_" that have
            # a non-error status are considered successful.
            elif span.operation_name.startswith("retry_"):
                outcomes.append(span.status in ("ok", "OK", None, ""))
        return outcomes

    @staticmethod
    def _walk_spans_local(spans: list[SpanNode]) -> list[SpanNode]:
        """Recursive span walker (local copy, same as BaseDetector._walk_spans)."""
        result: list[SpanNode] = []
        for node in spans:
            result.append(node)
            result.extend(SystemicRetryDetector._walk_spans_local(node.child_spans))
        return result


class TransientRetryDetector(BaseDetector):
    """Detect many retries (>threshold) where all succeeded — downgrade to info.

    **What it catches**: A "retry storm" where every retry succeeded.  This
    means the agent recovered, but at the cost of latency and tokens.  The
    severity is "info" because no actual failure occurred.

    **Why different from RetryStormDetector?**  RetryStormDetector catches
    all storms regardless of outcome.  This detector adds nuance: storms
    where everything succeeded are informative (high retry cost but no
    failures) vs. storms where things failed (genuine problems).

    **Success rate threshold**: ≥50% means most retries succeeded.  This is
    intentionally lower than 100% to catch "mostly successful" storms where
    the agent recovered after a few tries.

    **Evidence produced**: ``total_retries``, ``retry_events``, ``success_rate``.
    """

    anomaly_type = "transient_retry"

    def __init__(self, threshold: int | None = None) -> None:
        self.threshold = threshold or settings.detector_transient_retry_threshold

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        retries = summary.total_retries
        if retries < self.threshold:
            return None

        # Reuse SystemicRetryDetector's outcome collection (same logic).
        retry_outcomes = SystemicRetryDetector._collect_retry_outcomes(spans)
        if not retry_outcomes:
            return None

        success_rate = sum(retry_outcomes) / len(retry_outcomes)
        if success_rate >= 0.5:
            return self._build_anomaly(
                summary,
                "info",  # Informational severity — retries succeeded.
                f"Transient retry storm: {retries} retries "
                f"but {success_rate:.0%} succeeded",
                {
                    "total_retries": retries,
                    "retry_events": len(retry_outcomes),
                    "success_rate": round(success_rate, 2),
                },
            )
        return None


class CascadingRetryDetector(BaseDetector):
    """Detect retry chains across different tools: retry in tool A triggers retry in tool B.

    **What it catches**: A failure propagation pattern where a retry in one
    tool leads to a retry in a different tool.  This suggests the failure is
    not isolated — it's cascading through the agent's workflow.

    **Algorithm**:
    1. Find all retry spans (span with "retry_" prefix or gen_ai.retry.count attr).
    2. For each retry span, find the associated tool name (from the span or
       its immediate children).
    3. If the retry chain spans >= 2 different tools and the chain length
       >= total_retries, flag it.

    **Why "length >= retries"?**  If the retry chain touches every retry,
    the entire retry behavior is cascading — no retry was isolated to a
    single tool.

    **Evidence produced**: ``total_retries``, ``affected_tools``, ``retry_chain``,
    ``unique_tool_count``.

    **False-positive risks**:
    - Complex workflows where failures naturally cascade (e.g., search fails
      → retrieval fails → generation fails).  These are legitimate cascading
      failures but may not be actionable.  The detector provides the evidence
      for the operator to decide.
    """

    anomaly_type = "cascading_retry"

    def __init__(self) -> None:
        pass

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        retries = summary.total_retries
        if retries < 3:
            return None  # Need at least 3 retries for a cascade.

        retry_tools = self._find_retry_tools(spans)
        # Must span at least 2 different tools.
        if len(set(retry_tools)) < 2:
            return None

        # The retry chain should touch most of the total retries.
        if len(retry_tools) >= retries:
            return self._build_anomaly(
                summary,
                "warning",
                f"Cascading retry chain across {len(set(retry_tools))} tools: {retry_tools}",
                {
                    "total_retries": retries,
                    "affected_tools": list(set(retry_tools)),
                    "retry_chain": retry_tools,
                    "unique_tool_count": len(set(retry_tools)),
                },
            )
        return None

    @staticmethod
    def _find_retry_tools(spans: list[SpanNode]) -> list[str]:
        """Find the tool names associated with each retry span.

        Walks the span tree looking for retry spans, then extracts the tool
        name from either the retry span's own attributes or its child
        span's attributes.
        """
        tools: list[str] = []
        for span in CascadingRetryDetector._walk_retry_spans(spans):
            tool_name = str(span.attributes.get("gen_ai.tool.name", ""))
            if tool_name:
                tools.append(tool_name)
            else:
                # Tool name might be on a child span (the actual tool call
                # is nested under the retry wrapper).
                for child in span.child_spans:
                    child_tool = str(child.attributes.get("gen_ai.tool.name", ""))
                    if child_tool:
                        tools.append(child_tool)
                        break
        return tools

    @staticmethod
    def _walk_retry_spans(spans: list[SpanNode]) -> list[SpanNode]:
        """Walk spans, collecting only those related to retries."""
        result: list[SpanNode] = []
        for node in spans:
            if (
                node.operation_name.startswith("retry_")
                or node.attributes.get("gen_ai.retry.count")
            ):
                result.append(node)
            result.extend(CascadingRetryDetector._walk_retry_spans(node.child_spans))
        return result


class RecoveryPathDetector(BaseDetector):
    """Detect unusually complex recovery path after an error.

    **What it catches**: After the first tool error, the agent took many
    extra tool calls to recover.  This suggests the agent struggled to find
    a working recovery path, wasting tokens and time.

    **Algorithm**:
    1. Walk tool spans in order.
    2. Find the index of the first error (status != "ok"/"OK").
    3. Count tool spans after that index.
    4. If >5 extra steps, fire anomaly.

    **Why "after first error"?**  The recovery path starts when the first
    error occurs.  Everything after that is part of the recovery attempt.

    **False-positive risks**:
    - Long-running workflows where an early error is followed by many
      unrelated successful tool calls.  The detector can't distinguish
      "recovery steps" from "unrelated subsequent steps" — it treats
      all post-error steps as recovery.

    **Evidence produced**: ``steps_after_error``, ``threshold``,
    ``total_tool_spans``, ``first_error_index``.
    """

    anomaly_type = "recovery_path"

    def __init__(self, extra_steps_threshold: int | None = None) -> None:
        self.extra_steps_threshold = (
            extra_steps_threshold or settings.detector_recovery_path_threshold
        )

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        tool_spans = self._walk_tool_spans(spans)
        if len(tool_spans) < 3:
            return None

        # Find the first tool span with an error status.
        first_error_idx: int | None = None
        for i, s in enumerate(tool_spans):
            if s.status and s.status not in ("ok", "OK"):
                first_error_idx = i
                break

        if first_error_idx is None:
            return None  # No errors at all — nothing to recover from.

        # Count tool calls after the first error.
        steps_after_error = len(tool_spans) - first_error_idx - 1
        if steps_after_error > self.extra_steps_threshold:
            severity = self._severity(float(steps_after_error), float(self.extra_steps_threshold))
            return self._build_anomaly(
                summary,
                severity,
                f"Complex recovery: {steps_after_error} extra steps "
                f"after first error (threshold: {self.extra_steps_threshold})",
                {
                    "steps_after_error": steps_after_error,
                    "threshold": self.extra_steps_threshold,
                    "total_tool_spans": len(tool_spans),
                    "first_error_index": first_error_idx,
                },
            )
        return None