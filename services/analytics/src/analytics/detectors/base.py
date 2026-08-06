"""Base detector class with common logic for all 35 anomaly detectors.

All detectors inherit from ``BaseDetector``, which provides:

- ``detect(summary, spans)``: abstract method that subclasses must implement.
- ``detect_async(summary, spans, pool)``: default async bridge that
  automatically handles both sync and async ``detect`` implementations.
- ``_build_anomaly(summary, severity, explanation, evidence)``: convenience
  method to construct an ``Anomaly`` with the detector's ``anomaly_type``.
- ``_severity(value, threshold)``: classifies as ``"critical"`` if value
  exceeds 2x threshold, ``"warning"`` otherwise.
- Tree-walking helpers: ``_walk_tool_spans``, ``_walk_spans``,
  ``_walk_tool_names``, ``_extract_output`` for traversing SpanNode trees.
- ``_has_valid_pool``: utility to detect real vs mock connection pools.

**Subclass contract:**
1. Set ``anomaly_type`` class attribute to the anomaly type string.
2. Implement ``detect(summary, spans)`` — the sync detection path.
3. Optionally override ``detect_async(summary, spans, pool)`` for async
   detection (e.g., database queries, LLM calls).

The default ``detect_async`` automatically detects whether ``detect`` returns
an awaitable and awaits it if needed, providing backward compatibility with
detectors that use the ``async def _run() -> Anomaly: ...; return _run()``
pattern (like ``CostSpikeDetector``).
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable
from typing import Any

from analytics.models import Anomaly, RunSummary, SpanNode


def _has_valid_pool(pool: Any) -> bool:
    """Check if pool looks like a real asyncpg pool (not a mock).

    Real asyncpg pools have an ``acquire`` method but do NOT have a
    ``return_value`` attribute (which is a signature of mock objects).
    This heuristic prevents detectors from attempting database queries
    against fake pools during testing.

    Args:
        pool: the pool object to inspect.

    Returns:
        ``True`` if the pool appears to be a real asyncpg pool, ``False``
        for mocks, None, or objects without ``acquire``.
    """
    try:
        return (
            hasattr(pool, "acquire")
            and callable(pool.acquire)
            and not hasattr(pool, "return_value")  # Mock detection heuristic.
        )
    except Exception:
        return False


class BaseDetector:
    """Common base for all anomaly detectors.

    Subclasses must set ``anomaly_type`` and implement ``detect``.
    Async detectors can override ``detect_async``, which defaults to
    the sync path with automatic awaitable detection.

    **Severity levels:**
    - ``"warning"``: standard anomaly (value passes threshold).
    - ``"critical"``: severe anomaly (value >= 2x threshold).
    - ``"info"``: informational anomaly (e.g., first-run heuristic).
    """

    # Subclasses MUST set this to their anomaly type string (e.g., "loop").
    anomaly_type: str = ""

    def detect(
        self, summary: RunSummary, spans: list[SpanNode]
    ) -> Anomaly | None | Awaitable[Anomaly | None]:
        """Detect anomalies in a run.  Must be implemented by subclasses.

        Args:
            summary: the run summary with aggregated metrics.
            spans: root-level span nodes from the trace tree.

        Returns:
            An ``Anomaly`` if detected, ``None`` otherwise.  May also return
            an awaitable for async detectors using the dual-mode pattern
            (see ``CostSpikeDetector.detect``).

        Raises:
            NotImplementedError: if the subclass does not implement this method.
        """
        raise NotImplementedError

    async def detect_async(
        self,
        summary: RunSummary,
        spans: list[SpanNode],
        pool: Any = None,
    ) -> Anomaly | None:
        """Default async path that bridges sync/async detect implementations.

        If a subclass's ``detect()`` returns an awaitable (like
        ``CostSpikeDetector`` which returns ``_run()``), we await it here.
        Otherwise, we return the sync result directly.

        Args:
            summary: the run summary with aggregated metrics.
            spans: root-level span nodes.
            pool: optional database connection pool for baseline queries.

        Returns:
            An ``Anomaly`` if detected, ``None`` otherwise.
        """
        result = self.detect(summary, spans)
        if inspect.isawaitable(result):
            return await result
        return result

    def _build_anomaly(
        self,
        summary: RunSummary,
        severity: str,
        explanation: str,
        evidence: dict[str, object],
    ) -> Anomaly:
        """Convenience: construct an Anomaly with the detector's anomaly_type.

        Args:
            summary: the run summary (for run_id and agent_name).
            severity: one of "info", "warning", "critical".
            explanation: human-readable description of the anomaly.
            evidence: free-form dict of detector-specific data.

        Returns:
            A fully constructed ``Anomaly`` ready for persistence.
        """
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
        """Classify severity based on how far the value exceeds the threshold.

        The 2x threshold multiplier is a standard rule of thumb: crossing
        the threshold is a warning; exceeding it by 2x or more indicates
        a critical situation.

        Args:
            value: the observed value (e.g., cost, count, ratio).
            threshold: the configured threshold.

        Returns:
            ``"critical"`` if value >= 2 * threshold, ``"warning"`` otherwise.
        """
        if value >= threshold * 2:
            return "critical"
        return "warning"

    @staticmethod
    def _walk_tool_spans(spans: list[SpanNode]) -> list[SpanNode]:
        """Recursively collect all spans with ``operation_name == "execute_tool"``.

        Performs a depth-first traversal, returning a flat list.  Used by
        most tool-execution detectors to find relevant spans for analysis.

        Args:
            spans: a list of SpanNode roots or children.

        Returns:
            A flat list of ``SpanNode`` objects representing tool calls.
        """
        result: list[SpanNode] = []
        for node in spans:
            if node.operation_name == "execute_tool":
                result.append(node)
            result.extend(BaseDetector._walk_tool_spans(node.child_spans))
        return result

    @staticmethod
    def _walk_spans(spans: list[SpanNode]) -> list[SpanNode]:
        """Recursively collect all spans (flat list, all operation types).

        Performs a depth-first traversal.  Used by detectors that need to
        analyze the full span tree (e.g., token explosion, inactivity).

        Args:
            spans: a list of SpanNode roots or children.

        Returns:
            A flat list of all ``SpanNode`` objects in the subtree.
        """
        result: list[SpanNode] = []
        for node in spans:
            result.append(node)
            result.extend(BaseDetector._walk_spans(node.child_spans))
        return result

    @staticmethod
    def _walk_tool_names(spans: list[SpanNode]) -> list[str]:
        """Recursively collect ordered tool names from ``execute_tool`` spans.

        Preserves the order of tool calls as they appear in the trace tree.
        Used by loop detectors to find consecutive repeated tool calls.

        Args:
            spans: a list of SpanNode roots or children.

        Returns:
            A list of tool name strings in execution order.
        """
        tool_calls: list[str] = []
        for node in spans:
            if node.operation_name == "execute_tool":
                tool_name = str(node.attributes.get("gen_ai.tool.name", ""))
                tool_calls.append(tool_name)
            tool_calls.extend(BaseDetector._walk_tool_names(node.child_spans))
        return tool_calls

    @staticmethod
    def _extract_output(spans: list[SpanNode]) -> str:
        """Extract the first user-visible output-like field from a span list.

        Searches spans in order (depth-first) for known output attribute keys.
        The key priority order reflects common OTel and agent framework
        conventions:
          1. ``gen_ai.response.content`` (LLM response standard)
          2. ``gen_ai.agent.output`` (agent output convention)
          3. ``assistant_response``, ``completion``, ``message_content``
          4. ``content``, ``answer`` (generic fallbacks)
          5. ``value`` when ``from`` role is assistant/model (legacy format)

        Args:
            spans: a list of SpanNode roots or children.

        Returns:
            The first non-empty output string found, or ``""`` if no output
            is found in any span.
        """
        for span in spans:
            # Try standardized OTel GenAI attribute keys first.
            for key in (
                "gen_ai.response.content",
                "gen_ai.agent.output",
                "assistant_response",
                "completion",
                "message_content",
                "content",
                "answer",
            ):
                value = span.attributes.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

            # Legacy format: "value" attribute with "from" role indicating source.
            value = span.attributes.get("value")
            role = str(span.attributes.get("from", "")).lower().strip()
            if (
                isinstance(value, str)
                and value.strip()
                and role in {"gpt", "assistant", "ai", "model"}
            ):
                return value.strip()
        return ""