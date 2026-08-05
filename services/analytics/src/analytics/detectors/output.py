"""Output quality anomaly detectors (4 detectors)."""

from __future__ import annotations

import logging
import math
from typing import Any

from analytics.config import settings
from analytics.detectors.base import BaseDetector, _has_valid_pool
from analytics.models import Anomaly, RunSummary, SpanNode

logger = logging.getLogger(__name__)


class EmptyResponseDetector(BaseDetector):
    """Detect when agent produced no output."""

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
    """Detect output below minimum expected size."""

    anomaly_type = "low_output"

    def __init__(self, min_chars: int | None = None) -> None:
        self.min_chars = min_chars or settings.detector_low_output_min_chars

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        all_spans = self._walk_spans(spans)
        if not all_spans:
            return None

        output_content = self._extract_output(all_spans)
        if not output_content:
            return None

        output_len = len(output_content)
        if 0 < output_len < self.min_chars:
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
    """Detect ambiguous or unclear run status."""

    anomaly_type = "indeterminate_status"

    def __init__(self) -> None:
        pass

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        all_spans = self._walk_spans(spans)
        if not all_spans:
            return None

        status = summary.status
        if status is None or status.strip() == "":
            return self._build_anomaly(
                summary,
                "warning",
                "Run has no status — indeterminate outcome",
                {
                    "status": None,
                },
            )

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
    """Detect output characteristics changed (length/entropy-based vs baseline)."""

    anomaly_type = "output_drift"

    def __init__(
        self,
        deviation_multiplier: float | None = None,
    ) -> None:
        self.deviation_multiplier = (
            deviation_multiplier or settings.detector_output_drift_multiplier
        )

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
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
            return None

        ratio = output_len / baseline_len
        if ratio >= self.deviation_multiplier or ratio <= (1.0 / self.deviation_multiplier):
            direction = "longer" if ratio > 1 else "shorter"
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
