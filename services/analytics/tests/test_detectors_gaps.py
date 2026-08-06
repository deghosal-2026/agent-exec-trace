"""Gap-coverage tests for detectors with low coverage.

Covers edge cases and branch paths that remain uncovered in the main
test suite.  Each test builds SpanNode trees and RunSummary objects,
calls det.detect(summary, spans), and asserts the expected anomaly type.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from analytics.detectors import create_all_detectors
from analytics.detectors.base import BaseDetector
from analytics.models import Anomaly, RunSummary, SpanNode


# ---------------------------------------------------------------------------
# Minimal helpers — kept inline so the test file is self-contained.
# ---------------------------------------------------------------------------

class _Acquire:
    def __init__(self, conn: Any) -> None:
        self._conn = conn

    async def __aenter__(self) -> Any:
        return self._conn

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None


class _Pool:
    """Minimal asyncpg-pool stand-in with real acquire method (no return_value attr)."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def acquire(self) -> _Acquire:
        return _Acquire(self._conn)


class _BadPool:
    """Pool-like object that is detected as a mock (has return_value)."""

    acquire: Any = None
    return_value: Any = None


def _summary(**kwargs: Any) -> RunSummary:
    defaults: dict[str, Any] = {
        "run_id": "run-1",
        "agent_name": "test-agent",
        "agent_version": "v1",
    }
    defaults.update(kwargs)
    return RunSummary(**defaults)


def _root(children: list[SpanNode], *, op: str = "invoke_agent") -> list[SpanNode]:
    return [
        SpanNode(
            span_id="root",
            trace_id="t",
            operation_name=op,
            child_spans=children,
        )
    ]


def _tool(span_id: str, name: str, **attrs: Any) -> SpanNode:
    status: str | None = attrs.pop("status", None)  # type: ignore[assignment]
    duration_ms: int | None = attrs.pop("duration_ms", None)  # type: ignore[assignment]
    attributes: dict[str, object] = {"gen_ai.tool.name": name}
    attributes.update(attrs)
    return SpanNode(
        span_id=span_id,
        trace_id="t",
        operation_name="execute_tool",
        parent_span_id="root",
        status=status,
        duration_ms=duration_ms,
        attributes=attributes,
    )


def _detect_sync(detector: BaseDetector, summary: RunSummary, spans: list[SpanNode]) -> object:
    try:
        return detector.detect(summary, spans)
    except NotImplementedError:
        return asyncio.run(detector.detect_async(summary, spans))


# ============================================================================
# cross_run.py
# ============================================================================


class TestAnomalyClusterDetector:
    def test_sync_returns_none(self) -> None:
        from analytics.detectors.cross_run import AnomalyClusterDetector

        d = AnomalyClusterDetector(min_anomaly_types=3)
        assert d.detect(_summary(), []) is None

    @pytest.mark.asyncio
    async def test_pool_none_returns_none(self) -> None:
        from analytics.detectors.cross_run import AnomalyClusterDetector

        d = AnomalyClusterDetector(min_anomaly_types=3)
        assert await d.detect_async(_summary(), [], pool=None) is None

    @pytest.mark.asyncio
    async def test_mock_pool_returns_none(self) -> None:
        from analytics.detectors.cross_run import AnomalyClusterDetector

        d = AnomalyClusterDetector(min_anomaly_types=3)
        assert await d.detect_async(_summary(), [], pool=_BadPool()) is None

    @pytest.mark.asyncio
    async def test_below_threshold_returns_none(self) -> None:
        from analytics.detectors.cross_run import AnomalyClusterDetector

        d = AnomalyClusterDetector(min_anomaly_types=5)
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[
            {"anomaly_type": "loop"},
            {"anomaly_type": "retry_storm"},
        ])
        pool = _Pool(conn)
        assert await d.detect_async(_summary(), [], pool=pool) is None

    @pytest.mark.asyncio
    async def test_db_exception_returns_empty_list(self) -> None:
        from analytics.detectors.cross_run import AnomalyClusterDetector

        d = AnomalyClusterDetector(min_anomaly_types=1)
        conn = AsyncMock()
        conn.fetch = AsyncMock(side_effect=RuntimeError("db down"))
        pool = _Pool(conn)
        assert await d.detect_async(_summary(), [], pool=pool) is None


class TestRunFrequencyAnomalyDetector:
    def test_sync_returns_none(self) -> None:
        from analytics.detectors.cross_run import RunFrequencyAnomalyDetector

        d = RunFrequencyAnomalyDetector(min_runs=5, max_multiplier=2.0)
        assert d.detect(_summary(), []) is None

    @pytest.mark.asyncio
    async def test_no_agent_name_returns_none(self) -> None:
        from analytics.detectors.cross_run import RunFrequencyAnomalyDetector

        d = RunFrequencyAnomalyDetector(min_runs=5, max_multiplier=2.0)
        s = _summary(agent_version="v1", agent_name="")
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"cnt": 3})
        pool = _Pool(conn)
        assert await d.detect_async(s, [], pool=pool) is None

    @pytest.mark.asyncio
    async def test_mock_pool_returns_none(self) -> None:
        from analytics.detectors.cross_run import RunFrequencyAnomalyDetector

        d = RunFrequencyAnomalyDetector(min_runs=5, max_multiplier=2.0)
        assert await d.detect_async(_summary(), [], pool=_BadPool()) is None

    @pytest.mark.asyncio
    async def test_count_zero_returns_none(self) -> None:
        from analytics.detectors.cross_run import RunFrequencyAnomalyDetector

        d = RunFrequencyAnomalyDetector(min_runs=5, max_multiplier=2.0)
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"cnt": 0})
        pool = _Pool(conn)
        assert await d.detect_async(_summary(), [], pool=pool) is None

    @pytest.mark.asyncio
    async def test_count_none_returns_none(self) -> None:
        from analytics.detectors.cross_run import RunFrequencyAnomalyDetector

        d = RunFrequencyAnomalyDetector(min_runs=5, max_multiplier=2.0)
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)
        pool = _Pool(conn)
        assert await d.detect_async(_summary(), [], pool=pool) is None

    @pytest.mark.asyncio
    async def test_low_run_count_fires(self) -> None:
        from analytics.detectors.cross_run import RunFrequencyAnomalyDetector

        d = RunFrequencyAnomalyDetector(min_runs=5, max_multiplier=2.0)
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"cnt": 2})
        pool = _Pool(conn)
        result = await d.detect_async(_summary(), [], pool=pool)
        assert result is not None
        assert result.anomaly_type == "run_frequency_anomaly"
        assert result.severity == "warning"
        assert "Low run count" in (result.explanation or "")

    @pytest.mark.asyncio
    async def test_high_run_frequency_fires_critical(self) -> None:
        from analytics.detectors.cross_run import RunFrequencyAnomalyDetector

        d = RunFrequencyAnomalyDetector(min_runs=5, max_multiplier=2.0)
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"cnt": 25})
        pool = _Pool(conn)
        result = await d.detect_async(_summary(), [], pool=pool)
        assert result is not None
        assert result.anomaly_type == "run_frequency_anomaly"
        assert result.severity == "critical"

    @pytest.mark.asyncio
    async def test_high_run_frequency_fires_warning(self) -> None:
        from analytics.detectors.cross_run import RunFrequencyAnomalyDetector

        d = RunFrequencyAnomalyDetector(min_runs=5, max_multiplier=2.0)
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"cnt": 12})
        pool = _Pool(conn)
        result = await d.detect_async(_summary(), [], pool=pool)
        assert result is not None
        assert result.severity == "warning"

    @pytest.mark.asyncio
    async def test_within_bounds_returns_none(self) -> None:
        from analytics.detectors.cross_run import RunFrequencyAnomalyDetector

        d = RunFrequencyAnomalyDetector(min_runs=5, max_multiplier=2.0)
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"cnt": 7})
        pool = _Pool(conn)
        assert await d.detect_async(_summary(), [], pool=pool) is None

    @pytest.mark.asyncio
    async def test_no_agent_version_query_path(self) -> None:
        from analytics.detectors.cross_run import RunFrequencyAnomalyDetector

        d = RunFrequencyAnomalyDetector(min_runs=5, max_multiplier=2.0)
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"cnt": 3})
        pool = _Pool(conn)
        s = _summary(agent_version=None)
        result = await d.detect_async(s, [], pool=pool)
        assert result is not None

    @pytest.mark.asyncio
    async def test_db_exception_returns_none(self) -> None:
        from analytics.detectors.cross_run import RunFrequencyAnomalyDetector

        d = RunFrequencyAnomalyDetector(min_runs=5, max_multiplier=2.0)
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(side_effect=RuntimeError("db down"))
        pool = _Pool(conn)
        assert await d.detect_async(_summary(), [], pool=pool) is None


class TestFirstRunHeuristicDetector:
    def test_sync_returns_none(self) -> None:
        from analytics.detectors.cross_run import FirstRunHeuristicDetector

        d = FirstRunHeuristicDetector()
        assert d.detect(_summary(), []) is None

    @pytest.mark.asyncio
    async def test_no_agent_name_returns_none(self) -> None:
        from analytics.detectors.cross_run import FirstRunHeuristicDetector

        d = FirstRunHeuristicDetector()
        s = _summary(agent_name="", agent_version="v1")
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"cnt": 1, "first_run": "run-1"})
        pool = _Pool(conn)
        assert await d.detect_async(s, [], pool=pool) is None

    @pytest.mark.asyncio
    async def test_no_agent_version_returns_none(self) -> None:
        from analytics.detectors.cross_run import FirstRunHeuristicDetector

        d = FirstRunHeuristicDetector()
        s = _summary(agent_version=None)
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"cnt": 1, "first_run": "run-1"})
        pool = _Pool(conn)
        assert await d.detect_async(s, [], pool=pool) is None

    @pytest.mark.asyncio
    async def test_mock_pool_returns_none(self) -> None:
        from analytics.detectors.cross_run import FirstRunHeuristicDetector

        d = FirstRunHeuristicDetector()
        assert await d.detect_async(_summary(), [], pool=_BadPool()) is None

    @pytest.mark.asyncio
    async def test_is_first_fires_info(self) -> None:
        from analytics.detectors.cross_run import FirstRunHeuristicDetector

        d = FirstRunHeuristicDetector()
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"cnt": 1, "first_run": "run-1"})
        pool = _Pool(conn)
        result = await d.detect_async(_summary(), [], pool=pool)
        assert result is not None
        assert result.anomaly_type == "first_run_heuristic"
        assert result.severity == "info"

    @pytest.mark.asyncio
    async def test_not_first_returns_none(self) -> None:
        from analytics.detectors.cross_run import FirstRunHeuristicDetector

        d = FirstRunHeuristicDetector()
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"cnt": 5, "first_run": "other-run"})
        pool = _Pool(conn)
        assert await d.detect_async(_summary(), [], pool=pool) is None

    @pytest.mark.asyncio
    async def test_row_none_treated_as_first(self) -> None:
        from analytics.detectors.cross_run import FirstRunHeuristicDetector

        d = FirstRunHeuristicDetector()
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)
        pool = _Pool(conn)
        result = await d.detect_async(_summary(), [], pool=pool)
        assert result is not None
        assert result.severity == "info"

    @pytest.mark.asyncio
    async def test_db_exception_returns_none(self) -> None:
        from analytics.detectors.cross_run import FirstRunHeuristicDetector

        d = FirstRunHeuristicDetector()
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(side_effect=RuntimeError("db down"))
        pool = _Pool(conn)
        assert await d.detect_async(_summary(), [], pool=pool) is None


# ============================================================================
# interaction.py
# ============================================================================


class TestInterventionFrequencyDetector:
    def test_at_threshold_fires_warning(self) -> None:
        from analytics.detectors.interaction import InterventionFrequencyDetector

        d = InterventionFrequencyDetector(threshold=3)
        s = _summary(total_interventions=3)
        result = d.detect(s, [])
        assert result is not None
        assert result.anomaly_type == "intervention_frequency"
        assert result.severity == "warning"

    def test_double_threshold_fires_critical(self) -> None:
        from analytics.detectors.interaction import InterventionFrequencyDetector

        d = InterventionFrequencyDetector(threshold=3)
        s = _summary(total_interventions=6)
        result = d.detect(s, [])
        assert result is not None
        assert result.severity == "critical"

    def test_below_threshold_returns_none(self) -> None:
        from analytics.detectors.interaction import InterventionFrequencyDetector

        d = InterventionFrequencyDetector(threshold=3)
        s = _summary(total_interventions=2)
        assert d.detect(s, []) is None


class TestEscalationRateDetector:
    def test_sync_returns_none(self) -> None:
        from analytics.detectors.interaction import EscalationRateDetector

        d = EscalationRateDetector(multiplier=2.0)
        assert d.detect(_summary(), []) is None

    @pytest.mark.asyncio
    async def test_zero_interventions_returns_none(self) -> None:
        from analytics.detectors.interaction import EscalationRateDetector

        d = EscalationRateDetector(multiplier=2.0)
        s = _summary(total_interventions=0, agent_version="v1")
        assert await d.detect_async(s, [], pool=None) is None

    @pytest.mark.asyncio
    async def test_no_pool_returns_none(self) -> None:
        from analytics.detectors.interaction import EscalationRateDetector

        d = EscalationRateDetector(multiplier=2.0)
        s = _summary(total_interventions=5, agent_version="v1")
        assert await d.detect_async(s, [], pool=None) is None

    @pytest.mark.asyncio
    async def test_mock_pool_returns_none(self) -> None:
        from analytics.detectors.interaction import EscalationRateDetector

        d = EscalationRateDetector(multiplier=2.0)
        s = _summary(total_interventions=5, agent_version="v1")
        assert await d.detect_async(s, [], pool=_BadPool()) is None

    @pytest.mark.asyncio
    async def test_baseline_none_returns_none(self) -> None:
        from analytics.detectors.interaction import EscalationRateDetector

        d = EscalationRateDetector(multiplier=2.0)
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)
        pool = _Pool(conn)
        s = _summary(total_interventions=5, agent_version="v1")
        assert await d.detect_async(s, [], pool=pool) is None

    @pytest.mark.asyncio
    async def test_baseline_zero_returns_none(self) -> None:
        from analytics.detectors.interaction import EscalationRateDetector

        d = EscalationRateDetector(multiplier=2.0)
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"avg_int": 0})
        pool = _Pool(conn)
        s = _summary(total_interventions=5, agent_version="v1")
        assert await d.detect_async(s, [], pool=pool) is None

    @pytest.mark.asyncio
    async def test_ratio_below_multiplier_returns_none(self) -> None:
        from analytics.detectors.interaction import EscalationRateDetector

        d = EscalationRateDetector(multiplier=2.0)
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"avg_int": 4})
        pool = _Pool(conn)
        s = _summary(total_interventions=5, agent_version="v1")
        assert await d.detect_async(s, [], pool=pool) is None

    @pytest.mark.asyncio
    async def test_ratio_above_multiplier_fires(self) -> None:
        from analytics.detectors.interaction import EscalationRateDetector

        d = EscalationRateDetector(multiplier=2.0)
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"avg_int": 1})
        pool = _Pool(conn)
        s = _summary(total_interventions=5, agent_version="v1")
        result = await d.detect_async(s, [], pool=pool)
        assert result is not None
        assert result.anomaly_type == "escalation_rate"

    @pytest.mark.asyncio
    async def test_no_agent_version_query_path(self) -> None:
        from analytics.detectors.interaction import EscalationRateDetector

        d = EscalationRateDetector(multiplier=2.0)
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"avg_int": 1})
        pool = _Pool(conn)
        s = _summary(total_interventions=5, agent_version=None)
        result = await d.detect_async(s, [], pool=pool)
        assert result is not None

    @pytest.mark.asyncio
    async def test_db_exception_returns_none(self) -> None:
        from analytics.detectors.interaction import EscalationRateDetector

        d = EscalationRateDetector(multiplier=2.0)
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(side_effect=RuntimeError("db down"))
        pool = _Pool(conn)
        s = _summary(total_interventions=5, agent_version="v1")
        assert await d.detect_async(s, [], pool=pool) is None


class TestApprovalLatencyDetector:
    def test_no_intervention_spans_returns_none(self) -> None:
        from analytics.detectors.interaction import ApprovalLatencyDetector

        d = ApprovalLatencyDetector(max_seconds=60.0)
        spans = _root([
            SpanNode(span_id="s1", trace_id="t", operation_name="execute_tool"),
        ])
        assert d.detect(_summary(), spans) is None

    def test_slowest_below_threshold_returns_none(self) -> None:
        from analytics.detectors.interaction import ApprovalLatencyDetector

        d = ApprovalLatencyDetector(max_seconds=60.0)
        spans = _root([
            SpanNode(
                span_id="h1", trace_id="t",
                operation_name="await_approval",
                duration_ms=30000,
            ),
        ])
        assert d.detect(_summary(), spans) is None

    def test_nested_intervention_spans(self) -> None:
        from analytics.detectors.interaction import ApprovalLatencyDetector

        d = ApprovalLatencyDetector(max_seconds=30.0)
        spans = _root([
            SpanNode(
                span_id="outer", trace_id="t",
                operation_name="plan",
                child_spans=[
                    SpanNode(
                        span_id="inner", trace_id="t",
                        operation_name="await_approval",
                        duration_ms=45000,
                    ),
                ],
            ),
        ])
        result = d.detect(_summary(), spans)
        assert result is not None
        assert result.anomaly_type == "approval_latency"

    def test_human_intervention_span_detected(self) -> None:
        from analytics.detectors.interaction import ApprovalLatencyDetector

        d = ApprovalLatencyDetector(max_seconds=10.0)
        spans = _root([
            SpanNode(
                span_id="h1", trace_id="t",
                operation_name="human_intervention",
                duration_ms=20000,
            ),
        ])
        result = d.detect(_summary(), spans)
        assert result is not None

    def test_ask_user_span_detected(self) -> None:
        from analytics.detectors.interaction import ApprovalLatencyDetector

        d = ApprovalLatencyDetector(max_seconds=5.0)
        spans = _root([
            SpanNode(
                span_id="h1", trace_id="t",
                operation_name="ask_user",
                duration_ms=10000,
            ),
        ])
        result = d.detect(_summary(), spans)
        assert result is not None

    def test_multiple_interventions_picks_slowest(self) -> None:
        from analytics.detectors.interaction import ApprovalLatencyDetector

        d = ApprovalLatencyDetector(max_seconds=10.0)
        spans = _root([
            SpanNode(
                span_id="h1", trace_id="t",
                operation_name="await_approval",
                duration_ms=5000,
            ),
            SpanNode(
                span_id="h2", trace_id="t",
                operation_name="human_intervention",
                duration_ms=25000,
            ),
        ])
        result = d.detect(_summary(), spans)
        assert result is not None
        assert result.evidence is not None
        assert result.evidence["approval_duration_ms"] == 25000


class TestInterventionRejectionDetector:
    def test_below_threshold_interventions_returns_none(self) -> None:
        from analytics.detectors.interaction import InterventionRejectionDetector

        d = InterventionRejectionDetector(threshold=2)
        s = _summary(total_interventions=1)
        assert d.detect(s, []) is None

    def test_rejection_using_retry_operation_name(self) -> None:
        from analytics.detectors.interaction import InterventionRejectionDetector

        d = InterventionRejectionDetector(threshold=1)
        s = _summary(total_interventions=2)
        spans = _root([
            SpanNode(span_id="h1", trace_id="t", operation_name="human_intervention"),
            SpanNode(span_id="r1", trace_id="t", operation_name="retry_fix"),
            SpanNode(span_id="h2", trace_id="t", operation_name="ask_user"),
        ])
        result = d.detect(s, spans)
        assert result is not None
        assert result.anomaly_type == "intervention_rejection"

    def test_rejection_using_retry_count_attribute(self) -> None:
        from analytics.detectors.interaction import InterventionRejectionDetector

        d = InterventionRejectionDetector(threshold=1)
        s = _summary(total_interventions=2)
        spans = _root([
            SpanNode(span_id="h1", trace_id="t", operation_name="human_intervention"),
            SpanNode(
                span_id="r1", trace_id="t",
                operation_name="some_operation",
                attributes={"gen_ai.retry.count": 1},
            ),
            SpanNode(span_id="h2", trace_id="t", operation_name="ask_user"),
        ])
        result = d.detect(s, spans)
        assert result is not None

    def test_rejection_patterns_below_threshold_returns_none(self) -> None:
        from analytics.detectors.interaction import InterventionRejectionDetector

        d = InterventionRejectionDetector(threshold=3)
        s = _summary(total_interventions=4)
        spans = _root([
            SpanNode(span_id="h1", trace_id="t", operation_name="human_intervention"),
            SpanNode(span_id="r1", trace_id="t", operation_name="retry_1"),
            SpanNode(span_id="h2", trace_id="t", operation_name="ask_user"),
        ])
        assert d.detect(s, spans) is None


# ============================================================================
# output.py
# ============================================================================


class TestEmptyResponseDetector:
    def test_no_spans_returns_none(self) -> None:
        from analytics.detectors.output import EmptyResponseDetector

        d = EmptyResponseDetector()
        spans: list[SpanNode] = []
        assert d.detect(_summary(), spans) is None

    def test_non_empty_returns_none(self) -> None:
        from analytics.detectors.output import EmptyResponseDetector

        d = EmptyResponseDetector()
        spans = _root([
            SpanNode(
                span_id="s1", trace_id="t",
                operation_name="invoke_agent",
                attributes={"gen_ai.response.content": "Hello world"},
            ),
        ])
        assert d.detect(_summary(), spans) is None

    def test_whitespace_only_output_fires(self) -> None:
        from analytics.detectors.output import EmptyResponseDetector

        d = EmptyResponseDetector()
        spans = _root([
            SpanNode(
                span_id="s1", trace_id="t",
                operation_name="invoke_agent",
                attributes={"gen_ai.response.content": "   \n\t  "},
            ),
        ])
        result = d.detect(_summary(), spans)
        assert result is not None
        assert result.anomaly_type == "empty_response"


class TestLowOutputDetector:
    def test_no_spans_returns_none(self) -> None:
        from analytics.detectors.output import LowOutputDetector

        d = LowOutputDetector(min_chars=50)
        assert d.detect(_summary(), []) is None

    def test_no_output_content_returns_none(self) -> None:
        from analytics.detectors.output import LowOutputDetector

        d = LowOutputDetector(min_chars=50)
        spans = _root([
            SpanNode(
                span_id="s1", trace_id="t",
                operation_name="invoke_agent",
                attributes={},
            ),
        ])
        assert d.detect(_summary(), spans) is None

    def test_at_or_above_threshold_returns_none(self) -> None:
        from analytics.detectors.output import LowOutputDetector

        d = LowOutputDetector(min_chars=50)
        spans = _root([
            SpanNode(
                span_id="s1", trace_id="t",
                operation_name="invoke_agent",
                attributes={"gen_ai.response.content": "A" * 50},
            ),
        ])
        assert d.detect(_summary(), spans) is None

    def test_very_short_output_fires_critical(self) -> None:
        from analytics.detectors.output import LowOutputDetector

        d = LowOutputDetector(min_chars=100)
        spans = _root([
            SpanNode(
                span_id="s1", trace_id="t",
                operation_name="invoke_agent",
                attributes={"gen_ai.response.content": "Hi"},
            ),
        ])
        result = d.detect(_summary(), spans)
        assert result is not None
        assert result.severity == "critical"


class TestIndeterminateDetector:
    def test_no_spans_returns_none(self) -> None:
        from analytics.detectors.output import IndeterminateDetector

        d = IndeterminateDetector()
        assert d.detect(_summary(), []) is None

    def test_status_none_fires(self) -> None:
        from analytics.detectors.output import IndeterminateDetector

        d = IndeterminateDetector()
        s = _summary(status=None)
        spans = [SpanNode(span_id="x", trace_id="t", operation_name="invoke_agent")]
        result = d.detect(s, spans)
        assert result is not None
        assert result.anomaly_type == "indeterminate_status"

    def test_status_empty_string_fires(self) -> None:
        from analytics.detectors.output import IndeterminateDetector

        d = IndeterminateDetector()
        s = _summary(status="  ")
        spans = [SpanNode(span_id="x", trace_id="t", operation_name="invoke_agent")]
        result = d.detect(s, spans)
        assert result is not None

    def test_ambiguous_status_pending_fires(self) -> None:
        from analytics.detectors.output import IndeterminateDetector

        d = IndeterminateDetector()
        s = _summary(status="pending")
        spans = [SpanNode(span_id="x", trace_id="t", operation_name="invoke_agent")]
        result = d.detect(s, spans)
        assert result is not None

    def test_ambiguous_status_n_a_fires(self) -> None:
        from analytics.detectors.output import IndeterminateDetector

        d = IndeterminateDetector()
        s = _summary(status="n/a")
        spans = [SpanNode(span_id="x", trace_id="t", operation_name="invoke_agent")]
        result = d.detect(s, spans)
        assert result is not None

    def test_ambiguous_status_case_insensitive(self) -> None:
        from analytics.detectors.output import IndeterminateDetector

        d = IndeterminateDetector()
        s = _summary(status="UNKNOWN")
        spans = [SpanNode(span_id="x", trace_id="t", operation_name="invoke_agent")]
        result = d.detect(s, spans)
        assert result is not None

    def test_non_ambiguous_returns_none(self) -> None:
        from analytics.detectors.output import IndeterminateDetector

        d = IndeterminateDetector()
        s = _summary(status="success")
        spans = [SpanNode(span_id="x", trace_id="t", operation_name="invoke_agent")]
        assert d.detect(s, spans) is None


class TestOutputDriftDetector:
    def test_sync_returns_none(self) -> None:
        from analytics.detectors.output import OutputDriftDetector

        d = OutputDriftDetector(deviation_multiplier=2.0)
        assert d.detect(_summary(), []) is None

    @pytest.mark.asyncio
    async def test_no_output_returns_none(self) -> None:
        from analytics.detectors.output import OutputDriftDetector

        d = OutputDriftDetector(deviation_multiplier=2.0)
        spans = _root([
            SpanNode(span_id="s", trace_id="t", operation_name="step"),
        ])
        assert await d.detect_async(_summary(), spans, pool=None) is None

    @pytest.mark.asyncio
    async def test_no_pool_returns_none(self) -> None:
        from analytics.detectors.output import OutputDriftDetector

        d = OutputDriftDetector(deviation_multiplier=2.0)
        spans = _root([
            SpanNode(
                span_id="s", trace_id="t",
                operation_name="invoke_agent",
                attributes={"gen_ai.response.content": "Long enough output text here"},
            ),
        ])
        assert await d.detect_async(_summary(), spans, pool=None) is None

    @pytest.mark.asyncio
    async def test_mock_pool_returns_none(self) -> None:
        from analytics.detectors.output import OutputDriftDetector

        d = OutputDriftDetector(deviation_multiplier=2.0)
        spans = _root([
            SpanNode(
                span_id="s", trace_id="t",
                operation_name="invoke_agent",
                attributes={"gen_ai.response.content": "some output"},
            ),
        ])
        assert await d.detect_async(_summary(), spans, pool=_BadPool()) is None

    @pytest.mark.asyncio
    async def test_baseline_none_returns_none(self) -> None:
        from analytics.detectors.output import OutputDriftDetector

        d = OutputDriftDetector(deviation_multiplier=2.0)
        spans = _root([
            SpanNode(
                span_id="s", trace_id="t",
                operation_name="invoke_agent",
                attributes={"gen_ai.response.content": "some output here"},
            ),
        ])
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)
        pool = _Pool(conn)
        assert await d.detect_async(_summary(), spans, pool=pool) is None

    @pytest.mark.asyncio
    async def test_baseline_zero_returns_none(self) -> None:
        from analytics.detectors.output import OutputDriftDetector

        d = OutputDriftDetector(deviation_multiplier=2.0)
        spans = _root([
            SpanNode(
                span_id="s", trace_id="t",
                operation_name="invoke_agent",
                attributes={"gen_ai.response.content": "some output"},
            ),
        ])
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"avg_len": 0})
        pool = _Pool(conn)
        assert await d.detect_async(_summary(), spans, pool=pool) is None

    @pytest.mark.asyncio
    async def test_output_much_longer_than_baseline_fires(self) -> None:
        from analytics.detectors.output import OutputDriftDetector

        d = OutputDriftDetector(deviation_multiplier=3.0)
        spans = _root([
            SpanNode(
                span_id="s", trace_id="t",
                operation_name="invoke_agent",
                attributes={"gen_ai.response.content": "a" * 100},
            ),
        ])
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"avg_len": 10.0})
        pool = _Pool(conn)
        result = await d.detect_async(_summary(), spans, pool=pool)
        assert result is not None
        assert result.anomaly_type == "output_drift"
        assert "longer" in (result.explanation or "")

    @pytest.mark.asyncio
    async def test_output_much_shorter_than_baseline_fires(self) -> None:
        from analytics.detectors.output import OutputDriftDetector

        d = OutputDriftDetector(deviation_multiplier=3.0)
        spans = _root([
            SpanNode(
                span_id="s", trace_id="t",
                operation_name="invoke_agent",
                attributes={"gen_ai.response.content": "hi"},
            ),
        ])
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"avg_len": 100.0})
        pool = _Pool(conn)
        result = await d.detect_async(_summary(), spans, pool=pool)
        assert result is not None
        assert "shorter" in (result.explanation or "")

    @pytest.mark.asyncio
    async def test_output_within_bounds_returns_none(self) -> None:
        from analytics.detectors.output import OutputDriftDetector

        d = OutputDriftDetector(deviation_multiplier=3.0)
        spans = _root([
            SpanNode(
                span_id="s", trace_id="t",
                operation_name="invoke_agent",
                attributes={"gen_ai.response.content": "a" * 50},
            ),
        ])
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"avg_len": 40.0})
        pool = _Pool(conn)
        assert await d.detect_async(_summary(), spans, pool=pool) is None

    def test_compute_entropy_empty_text(self) -> None:
        from analytics.detectors.output import OutputDriftDetector

        assert OutputDriftDetector._compute_entropy("") == 0.0


# ============================================================================
# runtime.py
# ============================================================================


class TestRunDurationDetector:
    def test_sync_returns_none(self) -> None:
        from analytics.detectors.runtime import RunDurationDetector

        d = RunDurationDetector(multiplier=2.0)
        assert d.detect(_summary(), []) is None

    @pytest.mark.asyncio
    async def test_duration_none_returns_none(self) -> None:
        from analytics.detectors.runtime import RunDurationDetector

        d = RunDurationDetector(multiplier=2.0)
        s = _summary(duration_ms=None, agent_version="v1")
        assert await d.detect_async(s, [], pool=None) is None

    @pytest.mark.asyncio
    async def test_duration_zero_returns_none(self) -> None:
        from analytics.detectors.runtime import RunDurationDetector

        d = RunDurationDetector(multiplier=2.0)
        s = _summary(duration_ms=0, agent_version="v1")
        assert await d.detect_async(s, [], pool=None) is None

    @pytest.mark.asyncio
    async def test_no_pool_returns_none(self) -> None:
        from analytics.detectors.runtime import RunDurationDetector

        d = RunDurationDetector(multiplier=2.0)
        s = _summary(duration_ms=5000, agent_version="v1")
        assert await d.detect_async(s, [], pool=None) is None

    @pytest.mark.asyncio
    async def test_no_agent_name_returns_none(self) -> None:
        from analytics.detectors.runtime import RunDurationDetector

        d = RunDurationDetector(multiplier=2.0)
        s = _summary(duration_ms=5000, agent_name="", agent_version="v1")
        assert await d.detect_async(s, [], pool=None) is None

    @pytest.mark.asyncio
    async def test_mock_pool_returns_none(self) -> None:
        from analytics.detectors.runtime import RunDurationDetector

        d = RunDurationDetector(multiplier=2.0)
        s = _summary(duration_ms=5000, agent_version="v1")
        assert await d.detect_async(s, [], pool=_BadPool()) is None

    @pytest.mark.asyncio
    async def test_baseline_none_returns_none(self) -> None:
        from analytics.detectors.runtime import RunDurationDetector

        d = RunDurationDetector(multiplier=2.0)
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)
        pool = _Pool(conn)
        s = _summary(duration_ms=5000, agent_version="v1")
        assert await d.detect_async(s, [], pool=pool) is None

    @pytest.mark.asyncio
    async def test_baseline_zero_returns_none(self) -> None:
        from analytics.detectors.runtime import RunDurationDetector

        d = RunDurationDetector(multiplier=2.0)
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"avg_dur": 0})
        pool = _Pool(conn)
        s = _summary(duration_ms=5000, agent_version="v1")
        assert await d.detect_async(s, [], pool=pool) is None

    @pytest.mark.asyncio
    async def test_ratio_below_multiplier_returns_none(self) -> None:
        from analytics.detectors.runtime import RunDurationDetector

        d = RunDurationDetector(multiplier=5.0)
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"avg_dur": 500})
        pool = _Pool(conn)
        s = _summary(duration_ms=1000, agent_version="v1")
        assert await d.detect_async(s, [], pool=pool) is None

    @pytest.mark.asyncio
    async def test_ratio_above_multiplier_fires(self) -> None:
        from analytics.detectors.runtime import RunDurationDetector

        d = RunDurationDetector(multiplier=2.0)
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"avg_dur": 500})
        pool = _Pool(conn)
        s = _summary(duration_ms=3000, agent_version="v1")
        result = await d.detect_async(s, [], pool=pool)
        assert result is not None
        assert result.anomaly_type == "run_duration"

    @pytest.mark.asyncio
    async def test_no_agent_version_query_path(self) -> None:
        from analytics.detectors.runtime import RunDurationDetector

        d = RunDurationDetector(multiplier=2.0)
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"avg_dur": 500})
        pool = _Pool(conn)
        s = _summary(duration_ms=3000, agent_version=None)
        result = await d.detect_async(s, [], pool=pool)
        assert result is not None

    @pytest.mark.asyncio
    async def test_db_exception_returns_none(self) -> None:
        from analytics.detectors.runtime import RunDurationDetector

        d = RunDurationDetector(multiplier=2.0)
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(side_effect=RuntimeError("db down"))
        pool = _Pool(conn)
        s = _summary(duration_ms=3000, agent_version="v1")
        assert await d.detect_async(s, [], pool=pool) is None


class TestMaxStepHitDetector:
    def test_too_few_tool_spans_returns_none(self) -> None:
        from analytics.detectors.runtime import MaxStepHitDetector

        d = MaxStepHitDetector()
        spans = _root([_tool(f"s{i}", "x") for i in range(10)])
        s = _summary(status="incomplete", total_tool_calls=10)
        assert d.detect(s, spans) is None

    def test_status_max_steps_exceeded_fires(self) -> None:
        from analytics.detectors.runtime import MaxStepHitDetector

        d = MaxStepHitDetector()
        spans = _root([_tool(f"s{i}", "x") for i in range(25)])
        s = _summary(status="max_steps_exceeded", total_tool_calls=25)
        result = d.detect(s, spans)
        assert result is not None
        assert result.anomaly_type == "max_step_hit"

    def test_status_max_steps_hit_fires(self) -> None:
        from analytics.detectors.runtime import MaxStepHitDetector

        d = MaxStepHitDetector()
        spans = _root([_tool(f"s{i}", "x") for i in range(25)])
        s = _summary(status="max_steps_hit", total_tool_calls=25)
        result = d.detect(s, spans)
        assert result is not None

    def test_plan_spans_and_many_tools_fires(self) -> None:
        from analytics.detectors.runtime import MaxStepHitDetector

        d = MaxStepHitDetector()
        children: list[SpanNode] = []
        children.extend(_tool(f"t{i}", "x") for i in range(60))
        children.append(
            SpanNode(span_id="plan1", trace_id="t", operation_name="plan"),
        )
        spans = _root(children)
        s = _summary(status="success", total_tool_calls=60)
        result = d.detect(s, spans)
        assert result is not None

    def test_regular_status_no_plans_returns_none(self) -> None:
        from analytics.detectors.runtime import MaxStepHitDetector

        d = MaxStepHitDetector()
        spans = _root([_tool(f"s{i}", "x") for i in range(25)])
        s = _summary(status="success", total_tool_calls=25)
        assert d.detect(s, spans) is None

    def test_plans_but_below_50_tools_returns_none(self) -> None:
        from analytics.detectors.runtime import MaxStepHitDetector

        d = MaxStepHitDetector()
        children: list[SpanNode] = [
            SpanNode(span_id="plan1", trace_id="t", operation_name="plan"),
        ]
        children.extend(_tool(f"t{i}", "x") for i in range(30))
        spans = _root(children)
        s = _summary(status="success", total_tool_calls=30)
        assert d.detect(s, spans) is None


class TestStepEfficiencyDetector:
    def test_below_threshold_returns_none(self) -> None:
        from analytics.detectors.runtime import StepEfficiencyDetector

        d = StepEfficiencyDetector(max_tool_calls=20)
        s = _summary(total_tool_calls=5, status="success")
        assert d.detect(s, []) is None

    def test_above_threshold_but_not_success_returns_none(self) -> None:
        from analytics.detectors.runtime import StepEfficiencyDetector

        d = StepEfficiencyDetector(max_tool_calls=5)
        s = _summary(total_tool_calls=15, status="error")
        assert d.detect(s, []) is None

    def test_above_threshold_and_success_fires_warning(self) -> None:
        from analytics.detectors.runtime import StepEfficiencyDetector

        d = StepEfficiencyDetector(max_tool_calls=5)
        s = _summary(total_tool_calls=9, status="success")
        result = d.detect(s, [])
        assert result is not None
        assert result.anomaly_type == "step_efficiency"
        assert result.severity == "warning"

    def test_above_double_threshold_fires_critical(self) -> None:
        from analytics.detectors.runtime import StepEfficiencyDetector

        d = StepEfficiencyDetector(max_tool_calls=5)
        s = _summary(total_tool_calls=20, status="success")
        result = d.detect(s, [])
        assert result is not None
        assert result.severity == "critical"


class TestInactivityDetector:
    def test_less_than_2_spans_returns_none(self) -> None:
        from analytics.detectors.runtime import InactivityDetector

        d = InactivityDetector(max_gap_seconds=1.0)
        spans = [
            SpanNode(span_id="s1", trace_id="t", operation_name="step"),
        ]
        assert d.detect(_summary(), spans) is None

    def test_no_start_times_skipped(self) -> None:
        from analytics.detectors.runtime import InactivityDetector

        d = InactivityDetector(max_gap_seconds=1.0)
        spans = [
            SpanNode(span_id="s1", trace_id="t", operation_name="step", start_time=None),
            SpanNode(span_id="s2", trace_id="t", operation_name="step", start_time=None),
        ]
        assert d.detect(_summary(), spans) is None

    def test_gap_below_threshold_returns_none(self) -> None:
        from analytics.detectors.runtime import InactivityDetector

        d = InactivityDetector(max_gap_seconds=10.0)
        now = datetime.now(timezone.utc)
        spans = [
            SpanNode(span_id="s1", trace_id="t", operation_name="step", start_time=now),
            SpanNode(
                span_id="s2", trace_id="t",
                operation_name="step",
                start_time=now + timedelta(seconds=2),
            ),
        ]
        assert d.detect(_summary(), spans) is None

    def test_gap_above_threshold_fires(self) -> None:
        from analytics.detectors.runtime import InactivityDetector

        d = InactivityDetector(max_gap_seconds=1.0)
        now = datetime.now(timezone.utc)
        spans = [
            SpanNode(span_id="s1", trace_id="t", operation_name="step", start_time=now),
            SpanNode(
                span_id="s2", trace_id="t",
                operation_name="step",
                start_time=now + timedelta(seconds=5),
            ),
        ]
        result = d.detect(_summary(), spans)
        assert result is not None
        assert result.anomaly_type == "inactivity"

    def test_mixed_none_start_times_still_detects_gap(self) -> None:
        from analytics.detectors.runtime import InactivityDetector

        d = InactivityDetector(max_gap_seconds=1.0)
        now = datetime.now(timezone.utc)
        spans = [
            SpanNode(span_id="s1", trace_id="t", operation_name="step", start_time=None),
            SpanNode(span_id="s2", trace_id="t", operation_name="step", start_time=now),
            SpanNode(
                span_id="s3", trace_id="t",
                operation_name="step",
                start_time=now + timedelta(seconds=5),
            ),
        ]
        result = d.detect(_summary(), spans)
        assert result is not None


class TestPrematureCompletionDetector:
    def test_error_status_with_error_spans_does_not_fire_first_path(self) -> None:
        from analytics.detectors.runtime import PrematureCompletionDetector

        d = PrematureCompletionDetector()
        spans = _root([
            SpanNode(
                span_id="e1", trace_id="t",
                operation_name="execute_tool",
                status="error",
            ),
        ])
        s = _summary(status="error")
        result = d.detect(s, spans)
        assert result is None

    def test_plan_with_incomplete_and_no_output_fires(self) -> None:
        from analytics.detectors.runtime import PrematureCompletionDetector

        d = PrematureCompletionDetector()
        spans = _root([
            SpanNode(span_id="s1", trace_id="t", operation_name="step"),
            SpanNode(span_id="plan1", trace_id="t", operation_name="plan"),
        ])
        s = _summary(status="incomplete")
        result = d.detect(s, spans)
        assert result is not None
        assert result.anomaly_type == "premature_completion"

    def test_plan_with_incomplete_but_has_output_returns_none(self) -> None:
        from analytics.detectors.runtime import PrematureCompletionDetector

        d = PrematureCompletionDetector()
        spans = _root([
            SpanNode(
                span_id="s1", trace_id="t",
                operation_name="step",
                attributes={"gen_ai.response.content": "some output"},
            ),
            SpanNode(span_id="plan1", trace_id="t", operation_name="plan"),
        ])
        s = _summary(status="incomplete")
        assert d.detect(s, spans) is None

    def test_plan_with_incomplete_but_successful_terminal_tool_returns_none(self) -> None:
        from analytics.detectors.runtime import PrematureCompletionDetector

        d = PrematureCompletionDetector()
        spans = _root([
            SpanNode(span_id="s1", trace_id="t", operation_name="step"),
            SpanNode(
                span_id="t1", trace_id="t",
                operation_name="execute_tool",
                status="success",
            ),
            SpanNode(span_id="plan1", trace_id="t", operation_name="plan"),
        ])
        s = _summary(status="incomplete")
        assert d.detect(s, spans) is None

    def test_status_error_no_error_spans_fires(self) -> None:
        from analytics.detectors.runtime import PrematureCompletionDetector

        d = PrematureCompletionDetector()
        spans = _root([
            SpanNode(span_id="clean", trace_id="t", operation_name="step", status="ok"),
        ])
        s = _summary(status="error")
        result = d.detect(s, spans)
        assert result is not None

    def test_clean_run_returns_none(self) -> None:
        from analytics.detectors.runtime import PrematureCompletionDetector

        d = PrematureCompletionDetector()
        spans = _root([
            SpanNode(
                span_id="s1", trace_id="t",
                operation_name="step",
                attributes={"gen_ai.response.content": "output here"},
            ),
        ])
        s = _summary(status="success")
        assert d.detect(s, spans) is None


# ============================================================================
# tool.py
# ============================================================================


class TestLoopDetectorPollingReset:
    def test_polling_tool_resets_streak(self) -> None:
        from analytics.detectors.tool import LoopDetector

        d = LoopDetector(threshold=3, polling_tool_allowlist=["check_status"])
        spans = _root([
            _tool("s1", "search"),
            _tool("s2", "search"),
            _tool("s3", "check_status"),
            _tool("s4", "search"),
            _tool("s5", "search"),
        ])
        assert d.detect(_summary(), spans) is None

    def test_polling_tools_tracked_in_evidence(self) -> None:
        from analytics.detectors.tool import LoopDetector

        d = LoopDetector(threshold=2, polling_tool_allowlist=["check_status"])
        spans = _root([
            _tool("s1", "search"),
            _tool("s2", "search"),
            _tool("s3", "search"),
            _tool("s4", "check_status"),
            _tool("s5", "search"),
            _tool("s6", "search"),
            _tool("s7", "search"),
        ])
        result = d.detect(_summary(), spans)
        assert result is not None
        assert result.evidence is not None
        assert "polled_tools_skipped" in result.evidence


class TestPatternLoopDetectorEdge:
    def test_insufficient_tool_calls_returns_none(self) -> None:
        from analytics.detectors.tool import PatternLoopDetector

        d = PatternLoopDetector(window_size=4)
        spans = _root([
            _tool("s1", "A"), _tool("s2", "B"),
            _tool("s3", "A"), _tool("s4", "B"),
            _tool("s5", "A"), _tool("s6", "B"),
            _tool("s7", "C"),
        ])
        assert d.detect(_summary(), spans) is None

    def test_polling_tools_filtered_out(self) -> None:
        from analytics.detectors.tool import PatternLoopDetector

        d = PatternLoopDetector(window_size=2, polling_tool_allowlist=["poll"])
        spans = _root([
            _tool("s1", "A"), _tool("s2", "B"),
            _tool("s3", "poll"),
            _tool("s4", "A"), _tool("s5", "B"),
        ])
        result = d.detect(_summary(), spans)
        assert result is not None
        assert result.anomaly_type == "pattern_loop"


class TestArgumentLoopDetectorEdge:
    def test_no_arguments_resets_streak(self) -> None:
        from analytics.detectors.tool import ArgumentLoopDetector

        d = ArgumentLoopDetector(threshold=3)
        spans = _root([
            _tool("s1", "search", **{"gen_ai.tool.arguments": '{"q":"x"}'}),
            _tool("s2", "search"),
            _tool("s3", "search", **{"gen_ai.tool.arguments": '{"q":"x"}'}),
        ])
        assert d.detect(_summary(), spans) is None

    def test_dict_arguments_normalized(self) -> None:
        from analytics.detectors.tool import ArgumentLoopDetector

        d = ArgumentLoopDetector(threshold=3)
        spans = _root([
            _tool("s1", "search", **{"gen_ai.tool.arguments": {"b": 2, "a": 1}}),
            _tool("s2", "search", **{"gen_ai.tool.arguments": {"a": 1, "b": 2}}),
            _tool("s3", "search", **{"gen_ai.tool.arguments": {"b": 2, "a": 1}}),
            _tool("s4", "search", **{"gen_ai.tool.arguments": {"a": 1, "b": 2}}),
        ])
        # Detector serializes dict args with sort_keys=True, so all 4 produce
        # the same key: {"a": 1, "b": 2}
        result = d.detect(_summary(), spans)
        assert result is not None
        assert result.anomaly_type == "argument_loop"

    def test_non_serializable_args_resets_streak(self) -> None:
        from analytics.detectors.tool import ArgumentLoopDetector

        d = ArgumentLoopDetector(threshold=3)
        spans = _root([
            _tool("s1", "search", **{"gen_ai.tool.arguments": '{"q":"x"}'}),
            _tool("s2", "search", **{"gen_ai.tool.arguments": '{"q":"x"}'}),
            _tool("s3", "search", **{"gen_ai.tool.arguments": object()}),
            _tool("s4", "search", **{"gen_ai.tool.arguments": '{"q":"x"}'}),
        ])
        assert d.detect(_summary(), spans) is None

    def test_polling_tool_resets_argument_streak(self) -> None:
        from analytics.detectors.tool import ArgumentLoopDetector

        d = ArgumentLoopDetector(threshold=3, polling_tool_allowlist=["poll_status"])
        spans = _root([
            _tool("s1", "search", **{"gen_ai.tool.arguments": '{"q":"x"}'}),
            _tool("s2", "search", **{"gen_ai.tool.arguments": '{"q":"x"}'}),
            _tool("s3", "poll_status"),
            _tool("s4", "search", **{"gen_ai.tool.arguments": '{"q":"x"}'}),
            _tool("s5", "search", **{"gen_ai.tool.arguments": '{"q":"x"}'}),
        ])
        assert d.detect(_summary(), spans) is None

    def test_uses_gen_ai_tool_args_attribute(self) -> None:
        from analytics.detectors.tool import ArgumentLoopDetector

        d = ArgumentLoopDetector(threshold=3)
        spans = _root([
            _tool("s1", "search", **{"gen_ai.tool.args": '{"q":"x"}'}),
            _tool("s2", "search", **{"gen_ai.tool.args": '{"q":"x"}'}),
            _tool("s3", "search", **{"gen_ai.tool.args": '{"q":"x"}'}),
        ])
        result = d.detect(_summary(), spans)
        assert result is not None


class TestToolErrorRateDetectorEdge:
    def test_no_tool_spans_returns_none(self) -> None:
        from analytics.detectors.tool import ToolErrorRateDetector

        d = ToolErrorRateDetector(threshold_pct=50.0)
        spans: list[SpanNode] = [
            SpanNode(span_id="root", trace_id="t", operation_name="invoke_agent"),
        ]
        assert d.detect(_summary(), spans) is None


class TestSpecificToolErrorDetectorEdge:
    def test_tool_with_only_one_call_skipped(self) -> None:
        from analytics.detectors.tool import SpecificToolErrorDetector

        d = SpecificToolErrorDetector(threshold_pct=10.0)
        spans = _root([
            _tool("s1", "rare_tool", status="error"),
            _tool("s2", "common_tool", status="ok"),
            _tool("s3", "common_tool", status="ok"),
        ])
        assert d.detect(_summary(), spans) is None


class TestToolLatencyDetectorEdge:
    def test_tool_with_single_call_skipped(self) -> None:
        from analytics.detectors.tool import ToolLatencyDetector

        d = ToolLatencyDetector(multiplier=2.0)
        spans = _root([
            _tool("s1", "unique", duration_ms=100),
        ])
        assert d.detect(_summary(), spans) is None

    def test_average_zero_skipped(self) -> None:
        from analytics.detectors.tool import ToolLatencyDetector

        d = ToolLatencyDetector(multiplier=2.0)
        spans = _root([
            _tool("s1", "tool_a", duration_ms=0),
            _tool("s2", "tool_a", duration_ms=0),
        ])
        assert d.detect(_summary(), spans) is None


class TestRedundantToolCallDetectorEdge:
    def test_less_than_two_tool_spans_returns_none(self) -> None:
        from analytics.detectors.tool import RedundantToolCallDetector

        d = RedundantToolCallDetector(threshold=3)
        spans = _root([_tool("s1", "x")])
        assert d.detect(_summary(), spans) is None

    def test_no_arguments_resets_streak(self) -> None:
        from analytics.detectors.tool import RedundantToolCallDetector

        d = RedundantToolCallDetector(threshold=3)
        spans = _root([
            _tool("s1", "search", **{"gen_ai.tool.arguments": "x", "gen_ai.tool.result": "same"}),
            _tool("s2", "search", **{"gen_ai.tool.result": "same"}),
            _tool("s3", "search", **{"gen_ai.tool.arguments": "x", "gen_ai.tool.result": "same"}),
        ])
        assert d.detect(_summary(), spans) is None

    def test_non_serializable_result_uses_str(self) -> None:
        from analytics.detectors.tool import RedundantToolCallDetector

        class BadResult:
            def __repr__(self) -> str:
                return "BadResult()"

        d = RedundantToolCallDetector(threshold=3)
        spans = _root([
            _tool("s1", "search", **{
                "gen_ai.tool.arguments": '{"q":"x"}',
                "gen_ai.tool.result": BadResult(),
            }),
            _tool("s2", "search", **{
                "gen_ai.tool.arguments": '{"q":"x"}',
                "gen_ai.tool.result": BadResult(),
            }),
            _tool("s3", "search", **{
                "gen_ai.tool.arguments": '{"q":"x"}',
                "gen_ai.tool.result": BadResult(),
            }),
        ])
        result = d.detect(_summary(), spans)
        assert result is not None

    def test_dict_result_serialized(self) -> None:
        from analytics.detectors.tool import RedundantToolCallDetector

        d = RedundantToolCallDetector(threshold=3)
        spans = _root([
            _tool("s1", "search", **{
                "gen_ai.tool.arguments": "x",
                "gen_ai.tool.result": {"status": "ok", "count": 1},
            }),
            _tool("s2", "search", **{
                "gen_ai.tool.arguments": "x",
                "gen_ai.tool.result": {"count": 1, "status": "ok"},
            }),
            _tool("s3", "search", **{
                "gen_ai.tool.arguments": "x",
                "gen_ai.tool.result": {"status": "ok", "count": 1},
            }),
        ])
        result = d.detect(_summary(), spans)
        assert result is not None
        assert result.anomaly_type == "redundant_tool_call"


# ============================================================================
# cost.py
# ============================================================================


class TestCostSpikeDetectorEdge:
    def test_sync_raises_not_implemented(self) -> None:
        from analytics.detectors.cost import CostSpikeDetector

        d = CostSpikeDetector(absolute_threshold=5.0)
        with pytest.raises(NotImplementedError):
            d.detect(_summary(estimated_cost=10.0), [])

    @pytest.mark.asyncio
    async def test_cost_none_returns_none(self) -> None:
        from analytics.detectors.cost import CostSpikeDetector

        d = CostSpikeDetector(absolute_threshold=5.0)
        s = _summary(estimated_cost=None, agent_version="v1")
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"avg_cost": 1.0})
        pool = _Pool(conn)
        assert await d.detect_async(s, [], pool=pool) is None

    @pytest.mark.asyncio
    async def test_below_absolute_and_no_baseline_returns_none(self) -> None:
        from analytics.detectors.cost import CostSpikeDetector

        d = CostSpikeDetector(absolute_threshold=10.0, baseline_multiplier=2.0)
        s = _summary(estimated_cost=5.0, agent_version="v1")
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"avg_cost": 10.0})
        pool = _Pool(conn)
        assert await d.detect_async(s, [], pool=pool) is None

    @pytest.mark.asyncio
    async def test_relative_spike_no_absolute_fires(self) -> None:
        from analytics.detectors.cost import CostSpikeDetector

        d = CostSpikeDetector(absolute_threshold=100.0, baseline_multiplier=2.0)
        s = _summary(estimated_cost=5.0, agent_version="v1")
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"avg_cost": 1.0})
        pool = _Pool(conn)
        result = await d.detect_async(s, [], pool=pool)
        assert result is not None
        assert "relative spike" in (result.explanation or "")
        assert result.severity == "warning"


class TestCostVsBaselineDetector:
    def test_sync_returns_none(self) -> None:
        from analytics.detectors.cost import CostVsBaselineDetector

        d = CostVsBaselineDetector(multiplier=2.0)
        assert d.detect(_summary(estimated_cost=10.0, agent_version="v1"), []) is None

    @pytest.mark.asyncio
    async def test_cost_none_returns_none(self) -> None:
        from analytics.detectors.cost import CostVsBaselineDetector

        d = CostVsBaselineDetector(multiplier=2.0)
        s = _summary(estimated_cost=None, agent_version="v1")
        assert await d.detect_async(s, [], pool=None) is None

    @pytest.mark.asyncio
    async def test_cost_zero_returns_none(self) -> None:
        from analytics.detectors.cost import CostVsBaselineDetector

        d = CostVsBaselineDetector(multiplier=2.0)
        s = _summary(estimated_cost=0.0, agent_version="v1")
        assert await d.detect_async(s, [], pool=None) is None

    @pytest.mark.asyncio
    async def test_no_pool_returns_none(self) -> None:
        from analytics.detectors.cost import CostVsBaselineDetector

        d = CostVsBaselineDetector(multiplier=2.0)
        s = _summary(estimated_cost=10.0, agent_version="v1")
        assert await d.detect_async(s, [], pool=None) is None

    @pytest.mark.asyncio
    async def test_mock_pool_returns_none(self) -> None:
        from analytics.detectors.cost import CostVsBaselineDetector

        d = CostVsBaselineDetector(multiplier=2.0)
        s = _summary(estimated_cost=10.0, agent_version="v1")
        assert await d.detect_async(s, [], pool=_BadPool()) is None

    @pytest.mark.asyncio
    async def test_baseline_none_returns_none(self) -> None:
        from analytics.detectors.cost import CostVsBaselineDetector

        d = CostVsBaselineDetector(multiplier=2.0)
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)
        pool = _Pool(conn)
        s = _summary(estimated_cost=10.0, agent_version="v1")
        assert await d.detect_async(s, [], pool=pool) is None

    @pytest.mark.asyncio
    async def test_baseline_zero_returns_none(self) -> None:
        from analytics.detectors.cost import CostVsBaselineDetector

        d = CostVsBaselineDetector(multiplier=2.0)
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"avg_cost": 0.0})
        pool = _Pool(conn)
        s = _summary(estimated_cost=10.0, agent_version="v1")
        assert await d.detect_async(s, [], pool=pool) is None

    @pytest.mark.asyncio
    async def test_ratio_below_multiplier_returns_none(self) -> None:
        from analytics.detectors.cost import CostVsBaselineDetector

        d = CostVsBaselineDetector(multiplier=3.0)
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"avg_cost": 5.0})
        pool = _Pool(conn)
        s = _summary(estimated_cost=10.0, agent_version="v1")
        assert await d.detect_async(s, [], pool=pool) is None

    @pytest.mark.asyncio
    async def test_ratio_above_multiplier_fires(self) -> None:
        from analytics.detectors.cost import CostVsBaselineDetector

        d = CostVsBaselineDetector(multiplier=2.0)
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"avg_cost": 2.0})
        pool = _Pool(conn)
        s = _summary(estimated_cost=10.0, agent_version="v1")
        result = await d.detect_async(s, [], pool=pool)
        assert result is not None
        assert result.anomaly_type == "cost_vs_baseline"


class TestCostEfficiencyDetectorEdge:
    def test_cost_none_returns_none(self) -> None:
        from analytics.detectors.cost import CostEfficiencyDetector

        d = CostEfficiencyDetector()
        s = _summary(estimated_cost=None, status="success")
        assert d.detect(s, []) is None

    def test_cost_zero_returns_none(self) -> None:
        from analytics.detectors.cost import CostEfficiencyDetector

        d = CostEfficiencyDetector()
        s = _summary(estimated_cost=0.0, status="success")
        assert d.detect(s, []) is None

    def test_not_success_status_returns_none(self) -> None:
        from analytics.detectors.cost import CostEfficiencyDetector

        d = CostEfficiencyDetector()
        s = _summary(estimated_cost=10.0, total_tool_calls=5, status="error")
        assert d.detect(s, []) is None

    def test_zero_tool_calls_returns_none(self) -> None:
        from analytics.detectors.cost import CostEfficiencyDetector

        d = CostEfficiencyDetector()
        s = _summary(estimated_cost=10.0, total_tool_calls=0, status="success")
        assert d.detect(s, []) is None

    def test_high_cost_per_tool_fires(self) -> None:
        from analytics.detectors.cost import CostEfficiencyDetector

        d = CostEfficiencyDetector(high_cost_per_tool_threshold=0.50)
        s = _summary(estimated_cost=10.0, total_tool_calls=5, status="success")
        result = d.detect(s, [])
        assert result is not None
        assert result.anomaly_type == "cost_efficiency"

    def test_too_many_tool_calls_fires(self) -> None:
        from analytics.detectors.cost import CostEfficiencyDetector

        d = CostEfficiencyDetector(max_efficient_tool_calls=5)
        s = _summary(estimated_cost=0.10, total_tool_calls=25, status="success")
        result = d.detect(s, [])
        assert result is not None
        assert result.anomaly_type == "cost_efficiency"

    def test_normal_returns_none(self) -> None:
        from analytics.detectors.cost import CostEfficiencyDetector

        d = CostEfficiencyDetector()
        s = _summary(estimated_cost=1.0, total_tool_calls=5, status="success")
        assert d.detect(s, []) is None


class TestTokenExplosionDetectorEdge:
    def test_less_than_4_spans_returns_none(self) -> None:
        from analytics.detectors.cost import TokenExplosionDetector

        d = TokenExplosionDetector(growth_multiplier=2.0)
        spans = [
            SpanNode(span_id="s1", trace_id="t", operation_name="step",
                     attributes={"gen_ai.usage.prompt_tokens": 10}),
            SpanNode(span_id="s2", trace_id="t", operation_name="step",
                     attributes={"gen_ai.usage.prompt_tokens": 10}),
        ]
        assert d.detect(_summary(), spans) is None

    def test_no_tokens_in_early_half_returns_none(self) -> None:
        from analytics.detectors.cost import TokenExplosionDetector

        d = TokenExplosionDetector(growth_multiplier=2.0)
        spans = [
            SpanNode(span_id="s1", trace_id="t", operation_name="step"),
            SpanNode(span_id="s2", trace_id="t", operation_name="step"),
            SpanNode(span_id="s3", trace_id="t", operation_name="step",
                     attributes={"gen_ai.usage.prompt_tokens": 100}),
            SpanNode(span_id="s4", trace_id="t", operation_name="step",
                     attributes={"gen_ai.usage.prompt_tokens": 100}),
        ]
        assert d.detect(_summary(), spans) is None

    def test_no_tokens_in_late_half_returns_none(self) -> None:
        from analytics.detectors.cost import TokenExplosionDetector

        d = TokenExplosionDetector(growth_multiplier=2.0)
        spans = [
            SpanNode(span_id="s1", trace_id="t", operation_name="step",
                     attributes={"gen_ai.usage.prompt_tokens": 100}),
            SpanNode(span_id="s2", trace_id="t", operation_name="step",
                     attributes={"gen_ai.usage.prompt_tokens": 100}),
            SpanNode(span_id="s3", trace_id="t", operation_name="step"),
            SpanNode(span_id="s4", trace_id="t", operation_name="step"),
        ]
        assert d.detect(_summary(), spans) is None

    def test_early_average_zero_returns_none(self) -> None:
        from analytics.detectors.cost import TokenExplosionDetector

        d = TokenExplosionDetector(growth_multiplier=2.0)
        spans = [
            SpanNode(span_id="s1", trace_id="t", operation_name="step",
                     attributes={"gen_ai.usage.prompt_tokens": 0}),
            SpanNode(span_id="s2", trace_id="t", operation_name="step",
                     attributes={"gen_ai.usage.prompt_tokens": 0}),
            SpanNode(span_id="s3", trace_id="t", operation_name="step",
                     attributes={"gen_ai.usage.prompt_tokens": 100}),
            SpanNode(span_id="s4", trace_id="t", operation_name="step",
                     attributes={"gen_ai.usage.prompt_tokens": 100}),
        ]
        assert d.detect(_summary(), spans) is None

    def test_ratio_below_multiplier_returns_none(self) -> None:
        from analytics.detectors.cost import TokenExplosionDetector

        d = TokenExplosionDetector(growth_multiplier=3.0)
        spans = [
            SpanNode(span_id="s1", trace_id="t", operation_name="step",
                     attributes={"gen_ai.usage.prompt_tokens": 50}),
            SpanNode(span_id="s2", trace_id="t", operation_name="step",
                     attributes={"gen_ai.usage.prompt_tokens": 50}),
            SpanNode(span_id="s3", trace_id="t", operation_name="step",
                     attributes={"gen_ai.usage.prompt_tokens": 80}),
            SpanNode(span_id="s4", trace_id="t", operation_name="step",
                     attributes={"gen_ai.usage.prompt_tokens": 80}),
        ]
        assert d.detect(_summary(), spans) is None

    def test_string_token_values_parsed(self) -> None:
        from analytics.detectors.cost import TokenExplosionDetector

        d = TokenExplosionDetector(growth_multiplier=2.0)
        spans = [
            SpanNode(span_id="s1", trace_id="t", operation_name="step",
                     attributes={"gen_ai.usage.prompt_tokens": "10",
                                 "gen_ai.usage.completion_tokens": "5"}),
            SpanNode(span_id="s2", trace_id="t", operation_name="step",
                     attributes={"gen_ai.usage.prompt_tokens": "10",
                                 "gen_ai.usage.completion_tokens": "5"}),
            SpanNode(span_id="s3", trace_id="t", operation_name="step",
                     attributes={"gen_ai.usage.prompt_tokens": "100",
                                 "gen_ai.usage.completion_tokens": "50"}),
            SpanNode(span_id="s4", trace_id="t", operation_name="step",
                     attributes={"gen_ai.usage.prompt_tokens": "100",
                                 "gen_ai.usage.completion_tokens": "50"}),
        ]
        result = d.detect(_summary(), spans)
        assert result is not None
        assert result.anomaly_type == "token_explosion"


class TestPerToolCostSpikeDetectorEdge:
    def test_cost_none_returns_none(self) -> None:
        from analytics.detectors.cost import PerToolCostSpikeDetector

        d = PerToolCostSpikeDetector(multiplier=2.0)
        s = _summary(estimated_cost=None)
        assert d.detect(s, []) is None

    def test_cost_zero_returns_none(self) -> None:
        from analytics.detectors.cost import PerToolCostSpikeDetector

        d = PerToolCostSpikeDetector(multiplier=2.0)
        s = _summary(estimated_cost=0.0)
        assert d.detect(s, []) is None

    def test_no_tool_spans_returns_none(self) -> None:
        from analytics.detectors.cost import PerToolCostSpikeDetector

        d = PerToolCostSpikeDetector(multiplier=2.0)
        s = _summary(estimated_cost=10.0)
        spans: list[SpanNode] = [_root([])[0]]
        assert d.detect(s, spans) is None

    def test_share_below_50_percent_skipped(self) -> None:
        from analytics.detectors.cost import PerToolCostSpikeDetector

        d = PerToolCostSpikeDetector(multiplier=2.0)
        s = _summary(estimated_cost=10.0)
        spans = _root([
            _tool("s1", "A"),
            _tool("s2", "B"),
            _tool("s3", "B"),
        ])
        assert d.detect(s, spans) is None

    def test_count_below_3_skipped(self) -> None:
        from analytics.detectors.cost import PerToolCostSpikeDetector

        d = PerToolCostSpikeDetector(multiplier=2.0)
        s = _summary(estimated_cost=10.0)
        spans = _root([
            _tool("s1", "A"),
            _tool("s2", "A"),
            _tool("s3", "B"),
            _tool("s4", "B"),
            _tool("s5", "B"),
        ])
        # tool A: share=2/5=0.4 (below 0.5), tool B: share=3/5=0.6, count=3, dominance=1.5 < 2.0
        assert d.detect(s, spans) is None

    def test_dominance_ratio_below_multiplier_skipped(self) -> None:
        from analytics.detectors.cost import PerToolCostSpikeDetector

        d = PerToolCostSpikeDetector(multiplier=4.0)
        s = _summary(estimated_cost=10.0)
        spans = _root([
            _tool("s1", "search"),
            _tool("s2", "search"),
            _tool("s3", "search"),
            _tool("s4", "other"),
        ])
        # share=3/4=0.75, count=3, dominance=0.75/0.25=3.0 < 4.0
        assert d.detect(s, spans) is None


class TestWastedToolCallsDetectorEdge:
    def test_too_few_total_spans_returns_none(self) -> None:
        from analytics.detectors.cost import WastedToolCallsDetector

        d = WastedToolCallsDetector(threshold=3)
        spans = _root([
            _tool("s1", "A", **{"gen_ai.tool.result": "same"}),
            _tool("s2", "B", **{"gen_ai.tool.result": "same"}),
        ])
        assert d.detect(_summary(), spans) is None

    def test_only_one_tool_type_no_anomaly(self) -> None:
        from analytics.detectors.cost import WastedToolCallsDetector

        d = WastedToolCallsDetector(threshold=3)
        spans = _root([
            _tool("s1", "search", **{"gen_ai.tool.result": "same"}),
            _tool("s2", "search", **{"gen_ai.tool.result": "same"}),
            _tool("s3", "search", **{"gen_ai.tool.result": "same"}),
        ])
        assert d.detect(_summary(), spans) is None

    def test_no_matching_results_returns_none(self) -> None:
        from analytics.detectors.cost import WastedToolCallsDetector

        d = WastedToolCallsDetector(threshold=3)
        spans = _root([
            _tool("s1", "search", **{"gen_ai.tool.result": "a"}),
            _tool("s2", "lookup", **{"gen_ai.tool.result": "b"}),
            _tool("s3", "fetch", **{"gen_ai.tool.result": "c"}),
        ])
        assert d.detect(_summary(), spans) is None

    def test_dict_result_serialization(self) -> None:
        from analytics.detectors.cost import WastedToolCallsDetector

        d = WastedToolCallsDetector(threshold=3)
        spans = _root([
            _tool("s1", "search", **{"gen_ai.tool.result": {"err": "timeout"}}),
            _tool("s2", "lookup", **{"gen_ai.tool.result": {"err": "timeout"}}),
            _tool("s3", "fetch", **{"gen_ai.tool.result": {"err": "timeout"}}),
        ])
        result = d.detect(_summary(), spans)
        assert result is not None
        assert result.anomaly_type == "wasted_tool_calls"


# ============================================================================
# Factory / smoke — ensure all detectors from the listed modules are present
# ============================================================================


class TestDetectorGapsCoverageSmoke:
    """Verify that the factory produces all detectors from the target modules."""

    def test_all_detectors_from_target_modules_registered(self) -> None:
        expected_types = {
            "anomaly_cluster", "run_frequency_anomaly", "first_run_heuristic",
            "intervention_frequency", "escalation_rate", "approval_latency",
            "intervention_rejection",
            "empty_response", "low_output", "indeterminate_status", "output_drift",
            "run_duration", "max_step_hit", "step_efficiency", "inactivity",
            "premature_completion",
            "loop", "pattern_loop", "argument_loop", "tool_error_rate",
            "specific_tool_error", "tool_latency", "tool_timeout", "redundant_tool_call",
            "cost_spike", "cost_vs_baseline", "cost_efficiency", "token_explosion",
            "per_tool_cost_spike", "wasted_tool_calls",
        }
        detectors = create_all_detectors()
        factory_types = {d.anomaly_type for d in detectors}
        missing = expected_types - factory_types
        assert not missing, f"Missing detector types from factory: {missing}"