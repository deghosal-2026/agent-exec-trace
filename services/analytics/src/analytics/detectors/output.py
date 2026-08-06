"""Output quality anomaly detectors (4 detectors).

These detectors analyze the agent's final output: whether it's empty, too
short, indeterminate, or has drifted from baseline expectations.

**Detectors in this module:**

1. **EmptyResponseDetector**: Detects when the agent produced no measurable
   output.  This catches agents that silently failed, crashed, or entered
   an infinite loop without producing results.

2. **LowOutputDetector**: Detects output below a minimum character threshold
   (50 chars by default).  Catches agents that produced something, but too
   little to be useful.

3. **IndeterminateDetector**: Detects runs with ambiguous, unclear, or
   unparseable status values.  When the run status is "unknown", "null",
   or similar, the outcome cannot be reliably evaluated.

4. **OutputDriftDetector**: Detects when output length deviates significantly
   (3x by default) from the baseline for this version cohort.  A sudden
   change in output length suggests the agent's behavior has changed.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from analytics.config import settings
from analytics.detectors.base import BaseDetector, _has_valid_pool
from analytics.models import Anomaly, RunSummary, SpanNode

logger = logging.getLogger(__name__)


class EmptyResponseDetector(BaseDetector):
    """Detect when agent produced no output.

    **What it catches**: The agent's trace has spans but no extractable
    output text.  This means the agent either:
    - Failed silently (all tool calls failed).
    - Entered an infinite loop and was terminated.
    - Had a logic error that prevented producing output.
    - All LLM responses were filtered or empty.

    **How it works**: Uses ``_extract_output()`` from BaseDetector to find
    the first meaningful output across all spans.  If nothing is found,
    the response is empty.

    **False-positive risks**:
    - Agents whose output is in a format not recognized by ``_extract_output``
      (the method checks a specific set of attribute keys).  Traces using
      non-standard attribute keys may be considered "empty" when they
      actually have output.  This can be addressed by extending the key
      list in ``BaseDetector._extract_output``.
    - Scratchpad-only traces: some agent traces contain only internal
      reasoning (scratchpad/reasoning attributes) with no final output.
      These are handled by the validator's ``_is_output_unavailable_trace``
      check, which skips empty_response detection for such traces.

    **Evidence produced**: ``output_length`` (always 0), ``total_spans``.
    """

    anomaly_type = "empty_response"

    def __init__(self) -> None:
        pass

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        all_spans = self._walk_spans(spans)
        if not all_spans:
            return None

        output_content = self._extract_output(all_spans)

        if not output_content.strip():
            return self._build_anomaly(
                summary,
                "warning",
                "Agent produced no output — empty response detected",
                {
                    "output_length": 0,
                    "total_spans": len(all_spans),
                },
            )
        return None


class LowOutputDetector(BaseDetector):
    """Detect output below minimum expected size.

    **What it catches**: The agent produced SOME output, but it's shorter
    than the minimum expected length (50 chars by default).  This catches
    agents that "gave up" and returned a short, unhelpful response like
    "I couldn't complete the task" or "Error occurred".

    **False-positive risks**:
    - Tasks where short output is appropriate (e.g., "what time is it?")
      may produce <50 chars legitimately.  The threshold should be tuned
      per workload type.
    - Truncated responses: if the agent's output was truncated by the
      instrumentation (e.g., 500-char truncation in llm_client.py), the
      output may be shorter than expected.  This is actually a signal
      that something went wrong.

    **Threshold rationale**: 50 chars is approximately one sentence.  Any
    agent response shorter than a sentence is unlikely to be useful as a
    final answer to a task.

    **Evidence produced**: ``output_length``, ``min_expected``.
    """

    anomaly_type = "low_output"

    def __init__(self, min_chars: int | None = None) -> None:
        self.min_chars = min_chars or settings.detector_low_output_min_chars

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        all_spans = self._walk_spans(spans)
        if not all_spans:
            return None

        output_content = self._extract_output(all_spans)
        if not output_content:
            return None  # Empty is handled by EmptyResponseDetector.

        output_len = len(output_content)
        if 0 < output_len < self.min_chars:
            # Severity scaling: shorter output is more severe.
            # The _severity helper works with thresholds, so we invert the
            # relationship: a very short output (e.g., 5 chars) against a
            # min threshold of 50 should produce a higher severity.
            severity = self._severity(float(self.min_chars), float(max(output_len, 1)))
            return self._build_anomaly(
                summary,
                severity,
                f"Low output: {output_len} chars (minimum expected: {self.min_chars})",
                {
                    "output_length": output_len,
                    "min_expected": self.min_chars,
                },
            )
        return None

class IndeterminateDetector(BaseDetector):
    """Detect ambiguous or unclear run status.

    **What it catches**: Runs whose status field is None, empty, or in a
    known set of ambiguous values: "unknown", "undefined", "null", "none",
    "unclear", "indeterminate", "pending", "na", "n/a".

    **Why this matters**: If the run status is ambiguous, the analytics
    pipeline cannot reliably determine whether the run succeeded or failed.
    This affects rollup calculations (success/error counts) and downstream
    decision-making.  Flagging indeterminate statuses helps operators
    identify traces with missing or broken status instrumentation.

    **False-positive risks**:
    - Traces that use "pending" as a legitimate interim status.  If your
      instrumentation uses "pending" to mean "still running", exclude it
      from the ambiguous set or handle it separately.
    - Statuses are case-insensitive: "UNKNOWN" and "unknown" are both caught.

    **Evidence produced**: ``status`` (the original value, or None).
    """

    anomaly_type = "indeterminate_status"

    def __init__(self) -> None:
        pass

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        all_spans = self._walk_spans(spans)
        if not all_spans:
            return None

        status = summary.status
        # Case 1: No status at all.
        if status is None or status.strip() == "":
            return self._build_anomaly(
                summary,
                "warning",
                "Run has no status — indeterminate outcome",
                {
                    "status": None,
                },
            )

        # Case 2: Status is in the known ambiguous set.
        status_lower = status.lower().strip()
        ambiguous_statuses = {
            "unknown", "undefined", "null", "none", "unclear",
            "indeterminate", "pending", "na", "n/a",
        }
        if status_lower in ambiguous_statuses:
            return self._build_anomaly(
                summary,
                "warning",
                f"Run status is ambiguous: '{status}'",
                {
                    "status": status,
                },
            )
        return None


class OutputDriftDetector(BaseDetector):
    """Detect output characteristics changed (length-based vs baseline).

    **What it catches**: When the current run's output length deviates
    significantly (3x or 1/3x by default) from the version cohort
    baseline output length.  Both longer and shorter outputs are flagged.

    **How it works**:
    1. Computes the current run's output length.
    2. Queries the database for the average output length of runs in the
       same version cohort.
    3. If the ratio exceeds the multiplier or falls below 1/multiplier,
       fires an anomaly.

    **Also computes entropy** (Shannon entropy of character distribution)
    but currently only uses length for comparison.  Entropy is included
    in the evidence for future use or manual review.

    **False-positive risks**:
    - Tasks with inherently varying output lengths (e.g., generating a
      short summary vs. a long report).  The baseline naturally accounts
      for some variance, but extreme outliers will fire.

    **Evidence produced**: ``output_length``, ``baseline_length``, ``ratio``,
    ``entropy``, ``multiplier``.
    """

    anomaly_type = "output_drift"

    def __init__(
        self,
        deviation_multiplier: float | None = None,
    ) -> None:
        self.deviation_multiplier = (
            deviation_multiplier or settings.detector_output_drift_multiplier
        )

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        # REQUIRES database pool for baseline computation.
        return None

    async def detect_async(
        self,
        summary: RunSummary,
        spans: list[SpanNode],
        pool: Any = None,
    ) -> Anomaly | None:
        all_spans = self._walk_spans(spans)
        output_content = self._extract_output(all_spans)
        if not output_content:
            return None
        if pool is None or not summary.agent_name:
            return None
        if not _has_valid_pool(pool):
            return None

        output_len = len(output_content)
        entropy = self._compute_entropy(output_content)

        baseline_len = await self._get_output_baseline(
            pool, summary.agent_name, summary.agent_version
        )
        if baseline_len is None or baseline_len <= 0:
            return None  # No baseline yet — can't compare.

        ratio = output_len / baseline_len
        # Check both directions: too long (>multiplier) AND too short (<1/multiplier).
        if ratio >= self.deviation_multiplier or ratio <= (1.0 / self.deviation_multiplier):
            direction = "longer" if ratio > 1 else "shorter"
            # For severity, use the more extreme direction.
            severity_val = max(ratio, 1.0 / max(ratio, 0.0001))
            severity = self._severity(severity_val, self.deviation_multiplier)
            return self._build_anomaly(
                summary,
                severity,
                f"Output drift: {output_len} chars is {ratio:.1f}x "
                f"baseline {baseline_len:.0f} chars ({direction})",
                {
                    "output_length": output_len,
                    "baseline_length": round(baseline_len, 0),
                    "ratio": round(ratio, 2),
                    "entropy": round(entropy, 3),
                    "multiplier": self.deviation_multiplier,
                },
            )
        return None

    @staticmethod
    def _compute_entropy(text: str) -> float:
        """Compute Shannon entropy of character distribution.

        High entropy = diverse character usage (complex/natural text).
        Low entropy = repetitive characters (e.g., "aaaaaa" or JSON).
        Included in evidence but not currently used for thresholding.

        Args:
            text: the text to analyze.

        Returns:
            Entropy value in bits.  0.0 for empty text.
        """
        if not text:
            return 0.0
        char_counts: dict[str, int] = {}
        for ch in text:
            char_counts[ch] = char_counts.get(ch, 0) + 1
        text_len = len(text)
        entropy = 0.0
        for count in char_counts.values():
            prob = count / text_len
            entropy -= prob * math.log2(prob)
        return entropy

    @staticmethod
    async def _get_output_baseline(
        pool: Any, agent_name: str, agent_version: str | None
    ) -> float | None:
        """Query the database for average output length of the version cohort.

        Uses the JSONB evidence column to extract output data from stored
        run summaries.  Returns None if no baseline data exists.
        """
        try:
            async with pool.acquire() as conn:
                if agent_version:
                    row = await conn.fetchrow(
                        "SELECT AVG(LENGTH(evidence->>'output')) AS avg_len "
                        "FROM run_summaries "
                        "WHERE agent_name = $1 AND agent_version = $2",
                        agent_name,
                        agent_version,
                    )
                else:
                    row = await conn.fetchrow(
                        "SELECT AVG(LENGTH(evidence->>'output')) AS avg_len "
                        "FROM run_summaries "
                        "WHERE agent_name = $1",
                        agent_name,
                    )
                if row is None:
                    return None
                val = row["avg_len"]
                if val is None:
                    return None
                return float(val)
        except Exception:
            logger.debug("Failed to fetch output baseline", exc_info=True)
            return None