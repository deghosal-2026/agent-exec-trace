"""Base detector class with common logic for all anomaly detectors."""

from __future__ import annotations

from typing import Any

from analytics.models import Anomaly, RunSummary, SpanNode


def _has_valid_pool(pool: Any) -> bool:
    """Check if pool looks like a real asyncpg pool (not a mock)."""
    try:
        return (
            hasattr(pool, "acquire")
            and callable(pool.acquire)
            and not hasattr(pool, "return_value")
        )
    except Exception:
        return False


class BaseDetector:
    """Common base for all anomaly detectors.

    Subclasses must set ``anomaly_type`` and implement ``detect``.
    Async detectors can override ``detect_async``, which defaults to the
    sync path.
    """

    anomaly_type: str = ""

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        raise NotImplementedError

    async def detect_async(
        self,
        summary: RunSummary,
        spans: list[SpanNode],
        pool: Any = None,
    ) -> Anomaly | None:
        return self.detect(summary, spans)

    def _build_anomaly(
        self,
        summary: RunSummary,
        severity: str,
        explanation: str,
        evidence: dict[str, object],
    ) -> Anomaly:
        return Anomaly(
            run_id=summary.run_id,
            agent_name=summary.agent_name,
            anomaly_type=self.anomaly_type,
            severity=severity,
            explanation=explanation,
            evidence=evidence,
        )

    @staticmethod
    def _severity(value: float, threshold: float) -> str:
        if value >= threshold * 2:
            return "critical"
        return "warning"

    @staticmethod
    def _walk_tool_spans(spans: list[SpanNode]) -> list[SpanNode]:
        """Recursively collect all execute_tool spans."""
        result: list[SpanNode] = []
        for node in spans:
            if node.operation_name == "execute_tool":
                result.append(node)
            result.extend(BaseDetector._walk_tool_spans(node.child_spans))
        return result

    @staticmethod
    def _walk_spans(spans: list[SpanNode]) -> list[SpanNode]:
        """Recursively collect all spans (flat list)."""
        result: list[SpanNode] = []
        for node in spans:
            result.append(node)
            result.extend(BaseDetector._walk_spans(node.child_spans))
        return result

    @staticmethod
    def _walk_tool_names(spans: list[SpanNode]) -> list[str]:
        """Recursively collect ordered tool names from execute_tool spans."""
        tool_calls: list[str] = []
        for node in spans:
            if node.operation_name == "execute_tool":
                tool_name = str(node.attributes.get("gen_ai.tool.name", ""))
                tool_calls.append(tool_name)
            tool_calls.extend(BaseDetector._walk_tool_names(node.child_spans))
        return tool_calls