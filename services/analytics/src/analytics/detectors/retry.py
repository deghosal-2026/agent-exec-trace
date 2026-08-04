"""Retry and recovery anomaly detectors (5 detectors)."""

from __future__ import annotations

import logging

from analytics.config import settings
from analytics.detectors.base import BaseDetector
from analytics.models import Anomaly, RunSummary, SpanNode

logger = logging.getLogger(__name__)


class RetryStormDetector(BaseDetector):
    """Detect runs with an excessive number of retries."""

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
    """Detect when all retries failed (0% success rate)."""

    anomaly_type = "systemic_retry"

    def __init__(self) -> None:
        pass

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        retries = summary.total_retries
        if retries < 2:
            return None

        retry_outcomes = self._collect_retry_outcomes(spans)
        if not retry_outcomes:
            return None

        success_rate = sum(retry_outcomes) / len(retry_outcomes)
        if success_rate == 0.0:
            return self._build_anomaly(
                summary,
                "critical",
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
        outcomes: list[bool] = []
        for span in SystemicRetryDetector._walk_spans_local(spans):
            retry_attr = span.attributes.get("gen_ai.retry.successful")
            if retry_attr is not None:
                outcomes.append(bool(retry_attr))
            elif span.operation_name.startswith("retry_"):
                outcomes.append(span.status in ("ok", "OK", None, ""))
        return outcomes

    @staticmethod
    def _walk_spans_local(spans: list[SpanNode]) -> list[SpanNode]:
        result: list[SpanNode] = []
        for node in spans:
            result.append(node)
            result.extend(SystemicRetryDetector._walk_spans_local(node.child_spans))
        return result


class TransientRetryDetector(BaseDetector):
    """Detect many retries (>threshold) where all succeeded — downgrade to info."""

    anomaly_type = "transient_retry"

    def __init__(self, threshold: int | None = None) -> None:
        self.threshold = threshold or settings.detector_transient_retry_threshold

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        retries = summary.total_retries
        if retries < self.threshold:
            return None

        retry_outcomes = SystemicRetryDetector._collect_retry_outcomes(spans)
        if not retry_outcomes:
            return None

        success_rate = sum(retry_outcomes) / len(retry_outcomes)
        if success_rate >= 0.5:
            return self._build_anomaly(
                summary,
                "info",
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
    """Detect retry chains across different tools: retry in tool A triggers retry in tool B."""

    anomaly_type = "cascading_retry"

    def __init__(self) -> None:
        pass

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        retries = summary.total_retries
        if retries < 3:
            return None

        retry_tools = self._find_retry_tools(spans)
        if len(set(retry_tools)) < 2:
            return None

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
        tools: list[str] = []
        for span in CascadingRetryDetector._walk_retry_spans(spans):
            tool_name = str(span.attributes.get("gen_ai.tool.name", ""))
            if tool_name:
                tools.append(tool_name)
            else:
                for child in span.child_spans:
                    child_tool = str(child.attributes.get("gen_ai.tool.name", ""))
                    if child_tool:
                        tools.append(child_tool)
                        break
        return tools

    @staticmethod
    def _walk_retry_spans(spans: list[SpanNode]) -> list[SpanNode]:
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
    """Detect unusually complex recovery path after an error."""

    anomaly_type = "recovery_path"

    def __init__(self, extra_steps_threshold: int | None = None) -> None:
        self.extra_steps_threshold = (
            extra_steps_threshold or settings.detector_recovery_path_threshold
        )

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        tool_spans = self._walk_tool_spans(spans)
        if len(tool_spans) < 3:
            return None

        first_error_idx: int | None = None
        for i, s in enumerate(tool_spans):
            if s.status and s.status not in ("ok", "OK"):
                first_error_idx = i
                break

        if first_error_idx is None:
            return None

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