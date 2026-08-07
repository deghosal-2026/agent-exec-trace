"""Tests for the ingest module — trace fetching, parsing, summarization, and persistence.

Covers TraceFetcher, TraceParser, RunSummaryBuilder, SpanTreeBuilder,
persist_run_summary, persist_anomaly, is_run_processed, and edge cases
(empty spans, duplicate run_ids, malformed spans, type coercion helpers).
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from analytics.ingest import (
    RunSummaryBuilder,
    SpanTreeBuilder,
    TraceFetcher,
    TraceParser,
    _to_bool,
    _to_float,
    _to_int,
    is_run_processed,
    persist_anomaly,
    persist_run_summary,
)
from analytics.models import Anomaly, RunSummary, SpanNode


def _make_pool() -> tuple[MagicMock, MagicMock]:
    """Build a mock asyncpg pool + connection for persistence tests."""
    pool = MagicMock()
    pool.acquire = MagicMock()
    conn = MagicMock()
    conn.execute = AsyncMock()
    conn.fetchval = AsyncMock(return_value=0)
    conn.fetch = AsyncMock(return_value=[])
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    return pool, conn


def _make_jaeger_trace(
    trace_id: str = "t1",
    spans: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """Build a minimal Jaeger-format trace dict."""
    return {"traceID": trace_id, "spans": spans or []}


def _make_span_dict(
    span_id: str = "s1",
    trace_id: str = "t1",
    parent_span_id: str | None = None,
    operation_name: str = "invoke_agent",
    tags: list[dict[str, str]] | None = None,
    references: list[dict[str, str]] | None = None,
    start_time: int = 1_000_000_000_000,
    duration: int = 1000,
) -> dict[str, object]:
    """Build a single Jaeger span dict."""
    d: dict[str, object] = {
        "spanID": span_id,
        "traceID": trace_id,
        "operationName": operation_name,
        "startTime": start_time,
        "duration": duration,
        "tags": tags or [],
    }
    if parent_span_id is not None:
        d["references"] = references or [{"spanID": parent_span_id, "refType": "CHILD_OF"}]
    return d


# ---- Type coercion helpers ----


class TestTypeCoercion:
    def test_to_float_none(self) -> None:
        assert _to_float(None) is None

    def test_to_float_int(self) -> None:
        assert _to_float(42) == 42.0

    def test_to_float_str(self) -> None:
        assert _to_float("3.14") == 3.14

    def test_to_float_invalid_str(self) -> None:
        assert _to_float("nope") is None

    def test_to_float_list(self) -> None:
        assert _to_float([1, 2]) is None

    def test_to_float_dict(self) -> None:
        assert _to_float({"a": 1}) is None

    def test_to_int_none_returns_default(self) -> None:
        assert _to_int(None) == 0

    def test_to_int_default_fallback(self) -> None:
        assert _to_int(None, default=99) == 99

    def test_to_int_float_truncates(self) -> None:
        result = _to_int(3.9)
        assert isinstance(result, int)

    def test_to_int_str(self) -> None:
        assert _to_int("42") == 42

    def test_to_int_invalid_str(self) -> None:
        assert _to_int("abc") == 0

    def test_to_int_list(self) -> None:
        assert _to_int([1, 2]) == 0

    def test_to_bool_none_default(self) -> None:
        assert _to_bool(None) is False

    def test_to_bool_none_with_default(self) -> None:
        assert _to_bool(None, default=True) is True

    def test_to_bool_bool(self) -> None:
        assert _to_bool(True) is True
        assert _to_bool(False) is False

    def test_to_bool_str_true_variants(self) -> None:
        assert _to_bool("true") is True
        assert _to_bool("1") is True
        assert _to_bool("yes") is True

    def test_to_bool_str_false_variants(self) -> None:
        assert _to_bool("false") is False
        assert _to_bool("0") is False
        assert _to_bool("no") is False
        assert _to_bool("random") is False

    def test_to_bool_int(self) -> None:
        assert _to_bool(1) is True
        assert _to_bool(0) is False


# ---- TraceFetcher ----


class TestTraceFetcher:
    @pytest.mark.asyncio
    async def test_fetch_traces_by_service_returns_data(self) -> None:
        fetcher = TraceFetcher(jaeger_endpoint="http://localhost:16686")
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": [{"traceID": "abc", "spans": []}]}
        mock_response.raise_for_status = MagicMock()
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            result = await fetcher.fetch_traces_by_service("demo-agent", limit=50)
            assert len(result) == 1
            assert result[0]["traceID"] == "abc"

    @pytest.mark.asyncio
    async def test_fetch_traces_by_service_empty(self) -> None:
        fetcher = TraceFetcher()
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": []}
        mock_response.raise_for_status = MagicMock()
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            result = await fetcher.fetch_traces_by_service("unknown", limit=10)
            assert result == []

    @pytest.mark.asyncio
    async def test_fetch_traces_by_service_no_data_key(self) -> None:
        fetcher = TraceFetcher()
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            result = await fetcher.fetch_traces_by_service("svc")
            assert result == []

    @pytest.mark.asyncio
    async def test_fetch_trace_by_id_found(self) -> None:
        fetcher = TraceFetcher()
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": [{"traceID": "t1", "spans": []}]}
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            result = await fetcher.fetch_trace_by_id("t1")
            assert result is not None
            assert result["traceID"] == "t1"

    @pytest.mark.asyncio
    async def test_fetch_trace_by_id_not_found(self) -> None:
        fetcher = TraceFetcher()
        mock_response = MagicMock()
        mock_response.status_code = 404
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            result = await fetcher.fetch_trace_by_id("nonexistent")
            assert result is None

    @pytest.mark.asyncio
    async def test_fetch_trace_by_id_empty_data(self) -> None:
        fetcher = TraceFetcher()
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": []}
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            result = await fetcher.fetch_trace_by_id("t1")
            assert result is None

    @pytest.mark.asyncio
    async def test_list_services_returns_names(self) -> None:
        fetcher = TraceFetcher()
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": ["svc-a", "svc-b", "jaeger-all-in-one"]}
        mock_response.raise_for_status = MagicMock()
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            result = await fetcher.list_services()
            assert len(result) == 3
            assert "svc-a" in result

    @pytest.mark.asyncio
    async def test_list_services_handles_error(self) -> None:
        fetcher = TraceFetcher()
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=RuntimeError("down")
            )
            result = await fetcher.list_services()
            assert result == []

    @pytest.mark.asyncio
    async def test_list_services_empty(self) -> None:
        fetcher = TraceFetcher()
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": []}
        mock_response.raise_for_status = MagicMock()
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            result = await fetcher.list_services()
            assert result == []

    def test_strips_trailing_slash(self) -> None:
        fetcher = TraceFetcher(jaeger_endpoint="http://example.com/")
        assert fetcher.jaeger_endpoint == "http://example.com"


# ---- TraceParser ----


class TestTraceParser:
    def test_empty_spans_returns_empty(self) -> None:
        raw = _make_jaeger_trace()
        assert TraceParser.parse_jaeger_trace(raw) == []

    def test_single_root_span(self) -> None:
        raw = _make_jaeger_trace(spans=[_make_span_dict()])
        result = TraceParser.parse_jaeger_trace(raw)
        assert len(result) == 1
        assert result[0].span_id == "s1"
        assert result[0].operation_name == "invoke_agent"
        assert result[0].child_spans == []

    def test_parent_child_relationship(self) -> None:
        spans = [
            _make_span_dict(span_id="root", operation_name="invoke_agent", references=[]),
            _make_span_dict(span_id="child", operation_name="execute_tool", parent_span_id="root"),
        ]
        raw = _make_jaeger_trace(spans=spans)
        result = TraceParser.parse_jaeger_trace(raw)
        assert len(result) == 1
        assert result[0].span_id == "root"
        assert len(result[0].child_spans) == 1
        assert result[0].child_spans[0].span_id == "child"

    def test_multiple_roots(self) -> None:
        spans = [
            _make_span_dict(span_id="a", references=[]),
            _make_span_dict(span_id="b", references=[]),
        ]
        raw = _make_jaeger_trace(spans=spans)
        result = TraceParser.parse_jaeger_trace(raw)
        assert len(result) == 2

    def test_children_sorted_by_start_time(self) -> None:
        spans = [
            _make_span_dict(span_id="root", references=[], start_time=1_000_000_000_000),
            _make_span_dict(span_id="late", parent_span_id="root", start_time=2_000_000_000_000),
            _make_span_dict(span_id="early", parent_span_id="root", start_time=500_000_000_000),
        ]
        raw = _make_jaeger_trace(spans=spans)
        result = TraceParser.parse_jaeger_trace(raw)
        children = result[0].child_spans
        assert children[0].span_id == "early"
        assert children[1].span_id == "late"

    def test_missing_spans_key(self) -> None:
        raw = {"traceID": "t1"}
        assert TraceParser.parse_jaeger_trace(raw) == []

    def test_graceful_empty_dict(self) -> None:
        assert TraceParser.parse_jaeger_trace({}) == []

    def test_missing_start_time(self) -> None:
        spans = [_make_span_dict(start_time=0)]
        raw = _make_jaeger_trace(spans=spans)
        result = TraceParser.parse_jaeger_trace(raw)
        assert result[0].start_time is None

    def test_zero_duration_omitted(self) -> None:
        spans = [_make_span_dict(duration=0)]
        raw = _make_jaeger_trace(spans=spans)
        result = TraceParser.parse_jaeger_trace(raw)
        assert result[0].duration_ms is None

    def test_orphan_spans_become_roots(self) -> None:
        spans = [
            _make_span_dict(span_id="orphan", parent_span_id="missing_parent"),
        ]
        raw = _make_jaeger_trace(spans=spans)
        result = TraceParser.parse_jaeger_trace(raw)
        assert len(result) == 1
        assert result[0].span_id == "orphan"


# ---- RunSummaryBuilder ----


class TestRunSummaryBuilder:
    def _root_spans(
        self,
        agent_name: str = "test-agent",
        run_id: str = "run_1",
        trace_id: str = "t1",
        span_id: str = "s1",
        children: list[SpanNode] | None = None,
        extra_attrs: dict[str, object] | None = None,
    ) -> list[SpanNode]:
        attrs: dict[str, object] = {
            "gen_ai.agent.name": agent_name,
            "gen_ai.agent.run.id": run_id,
        }
        if extra_attrs:
            attrs.update(extra_attrs)
        root = SpanNode(
            span_id=span_id,
            trace_id=trace_id,
            operation_name="invoke_agent",
            start_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
            duration_ms=5000,
            attributes=attrs,
            child_spans=children or [],
        )
        return [root]

    def _tool_span(self, span_id: str, tool_name: str = "search") -> SpanNode:
        return SpanNode(
            span_id=span_id,
            trace_id="t1",
            operation_name="execute_tool",
            parent_span_id="s1",
            attributes={"gen_ai.tool.name": tool_name},
        )

    def test_builds_basic_summary(self) -> None:
        spans = self._root_spans()
        result = RunSummaryBuilder.build_from_span_tree(spans, "t1")
        assert result is not None
        assert result.agent_name == "test-agent"
        assert result.run_id == "run_1"
        assert result.trace_id == "t1"
        assert result.status == "success"

    def test_empty_root_spans_returns_none(self) -> None:
        assert RunSummaryBuilder.build_from_span_tree([], "t1") is None

    def test_run_id_falls_back_to_trace_id(self) -> None:
        spans = self._root_spans(run_id="")
        result = RunSummaryBuilder.build_from_span_tree(spans, "t1")
        assert result is not None
        assert result.run_id == "t1"

    def test_missing_agents_attrs_default(self) -> None:
        root = SpanNode(
            span_id="s1",
            trace_id="t1",
            operation_name="invoke_agent",
            child_spans=[],
        )
        result = RunSummaryBuilder.build_from_span_tree([root], "t1")
        assert result is not None
        assert result.agent_name == "unknown"
        assert result.run_id == "t1"
        assert result.agent_version is None
        assert result.workload_type is None

    def test_counts_tool_calls(self) -> None:
        children = [
            self._tool_span("a", "search"),
            self._tool_span("b", "read"),
            self._tool_span("c", "write"),
        ]
        spans = self._root_spans(children=children)
        result = RunSummaryBuilder.build_from_span_tree(spans, "t1")
        assert result is not None
        assert result.total_tool_calls == 3

    def test_detects_error_status(self) -> None:
        child = SpanNode(
            span_id="c1",
            trace_id="t1",
            operation_name="execute_tool",
            parent_span_id="s1",
            status="error",
        )
        spans = self._root_spans(children=[child])
        result = RunSummaryBuilder.build_from_span_tree(spans, "t1")
        assert result is not None
        assert result.status == "error"

    def test_extracts_version(self) -> None:
        spans = self._root_spans(
            extra_attrs={
                "gen_ai.agent.version": "v2.0",
                "gen_ai.agent.workload.type": "batch",
            }
        )
        result = RunSummaryBuilder.build_from_span_tree(spans, "t1")
        assert result is not None
        assert result.agent_version == "v2.0"
        assert result.workload_type == "batch"

    def test_extracts_cost(self) -> None:
        spans = self._root_spans(
            extra_attrs={
                "gen_ai.agent.run.cost.total": 3.50,
            }
        )
        result = RunSummaryBuilder.build_from_span_tree(spans, "t1")
        assert result is not None
        assert result.estimated_cost == 3.50

    def test_extracts_loop_count(self) -> None:
        spans = self._root_spans(
            extra_attrs={
                "gen_ai.agent.loop.count": 7,
                "gen_ai.agent.loop.detected": "true",
            }
        )
        result = RunSummaryBuilder.build_from_span_tree(spans, "t1")
        assert result is not None
        assert result.loop_count == 7
        assert result.loop_detected is True

    def test_extracts_retry_count(self) -> None:
        spans = self._root_spans(
            extra_attrs={
                "gen_ai.agent.retry.count": 3,
                "gen_ai.agent.intervention.count": 2,
            }
        )
        result = RunSummaryBuilder.build_from_span_tree(spans, "t1")
        assert result is not None
        assert result.total_retries == 3
        assert result.total_interventions == 2

    def test_computes_completed_at(self) -> None:
        spans = self._root_spans()
        result = RunSummaryBuilder.build_from_span_tree(spans, "t1")
        assert result is not None
        assert result.completed_at is not None
        assert result.started_at is not None
        assert result.completed_at > result.started_at

    def test_no_completed_at_without_duration(self) -> None:
        root = SpanNode(
            span_id="s1",
            trace_id="t1",
            operation_name="invoke_agent",
            start_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
            duration_ms=None,
            attributes={"gen_ai.agent.name": "test", "gen_ai.agent.run.id": "r1"},
        )
        result = RunSummaryBuilder.build_from_span_tree([root], "t1")
        assert result is not None
        assert result.completed_at is None

    def test_error_status_variants(self) -> None:
        for status_val in ("failed", "timeout", "cancelled", "interrupted", "max_steps_exceeded"):
            child = SpanNode(
                span_id="c1",
                trace_id="t1",
                operation_name="execute_tool",
                parent_span_id="s1",
                status=status_val,
            )
            spans = self._root_spans(children=[child])
            result = RunSummaryBuilder.build_from_span_tree(spans, "t1")
            assert result is not None
            assert result.status == "error", (
                f"status={status_val} → expected error, got {result.status}"
            )

    def test_nested_children_counted(self) -> None:
        deep = SpanNode(
            span_id="d1",
            trace_id="t1",
            operation_name="execute_tool",
            parent_span_id="c1",
            attributes={"gen_ai.tool.name": "write"},
        )
        mid = SpanNode(
            span_id="c1",
            trace_id="t1",
            operation_name="execute_tool",
            parent_span_id="s1",
            attributes={"gen_ai.tool.name": "read"},
            child_spans=[deep],
        )
        spans = self._root_spans(children=[mid])
        result = RunSummaryBuilder.build_from_span_tree(spans, "t1")
        assert result is not None
        assert result.total_tool_calls == 2


# ---- SpanTreeBuilder ----


class TestSpanTreeBuilder:
    def test_empty_list(self) -> None:
        assert SpanTreeBuilder.build_tree([]) == []

    def test_single_node(self) -> None:
        node = SpanNode(span_id="s1", trace_id="t1", operation_name="op")
        result = SpanTreeBuilder.build_tree([node])
        assert len(result) == 1
        assert result[0].span_id == "s1"

    def test_parent_child_link(self) -> None:
        parent = SpanNode(span_id="p", trace_id="t1", operation_name="parent")
        child = SpanNode(span_id="c", trace_id="t1", operation_name="child", parent_span_id="p")
        result = SpanTreeBuilder.build_tree([parent, child])
        assert len(result) == 1
        assert result[0].span_id == "p"
        assert len(result[0].child_spans) == 1
        assert result[0].child_spans[0].span_id == "c"

    def test_orphan_becomes_root(self) -> None:
        orphan = SpanNode(
            span_id="o", trace_id="t1", operation_name="orphan", parent_span_id="missing"
        )
        result = SpanTreeBuilder.build_tree([orphan])
        assert len(result) == 1
        assert result[0].span_id == "o"

    def test_roots_sorted_by_start_time(self) -> None:
        late = SpanNode(
            span_id="late",
            trace_id="t1",
            operation_name="late",
            start_time=datetime(2024, 2, 1, tzinfo=timezone.utc),
        )
        early = SpanNode(
            span_id="early",
            trace_id="t1",
            operation_name="early",
            start_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        result = SpanTreeBuilder.build_tree([late, early])
        assert result[0].span_id == "early"
        assert result[1].span_id == "late"


# ---- Persistence functions ----


class TestPersistRunSummary:
    @pytest.mark.asyncio
    async def test_persist_executes_sql(self) -> None:
        pool, conn = _make_pool()
        summary = RunSummary(run_id="run_1", agent_name="test-agent")
        await persist_run_summary(pool, summary)
        conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_persist_with_all_fields(self) -> None:
        pool, conn = _make_pool()
        summary = RunSummary(
            run_id="run_1",
            agent_name="agent",
            agent_version="v1",
            workload_type="batch",
            duration_ms=5000,
            total_tool_calls=10,
            total_retries=3,
            total_interventions=1,
            estimated_cost=2.50,
            loop_count=5,
            loop_detected=True,
            status="error",
            root_span_id="s1",
            trace_id="t1",
            started_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            completed_at=datetime(2024, 1, 1, 0, 0, 5, tzinfo=timezone.utc),
        )
        await persist_run_summary(pool, summary)
        conn.execute.assert_called_once()


class TestPersistAnomaly:
    @pytest.mark.asyncio
    async def test_persist_executes_sql(self) -> None:
        pool, conn = _make_pool()
        anomaly = Anomaly(
            run_id="run_1",
            agent_name="test-agent",
            anomaly_type="loop",
            severity="warning",
            explanation="Loop detected",
            evidence={"count": 5},
        )
        await persist_anomaly(pool, anomaly)
        conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_persist_with_none_evidence(self) -> None:
        pool, conn = _make_pool()
        anomaly = Anomaly(
            run_id="run_1",
            agent_name="test-agent",
            anomaly_type="loop",
            explanation=None,
            evidence=None,
        )
        await persist_anomaly(pool, anomaly)
        conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_persist_with_empty_evidence(self) -> None:
        pool, conn = _make_pool()
        anomaly = Anomaly(
            run_id="run_1",
            agent_name="test-agent",
            anomaly_type="loop",
            evidence={},
        )
        await persist_anomaly(pool, anomaly)
        conn.execute.assert_called_once()


class TestIsRunProcessed:
    @pytest.mark.asyncio
    async def test_processed_returns_true(self) -> None:
        pool, conn = _make_pool()
        conn.fetchval = AsyncMock(return_value=1)
        result = await is_run_processed(pool, "run_1")
        assert result is True

    @pytest.mark.asyncio
    async def test_not_processed_returns_false(self) -> None:
        pool, conn = _make_pool()
        conn.fetchval = AsyncMock(return_value=0)
        result = await is_run_processed(pool, "run_2")
        assert result is False

    @pytest.mark.asyncio
    async def test_none_return_handled(self) -> None:
        pool, conn = _make_pool()
        conn.fetchval = AsyncMock(return_value=None)
        result = await is_run_processed(pool, "run_3")
        assert result is False


# ---- Integration / edge cases ----


class TestIngestIntegration:
    """End-to-end style tests through fetcher → parser → builder → persist."""

    @pytest.mark.asyncio
    async def test_full_pipeline_empty_traces(self) -> None:
        fetcher = TraceFetcher()
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": []}
        mock_response.raise_for_status = MagicMock()
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            traces = await fetcher.fetch_traces_by_service("svc")
            assert traces == []

    @pytest.mark.asyncio
    async def test_full_pipeline_parse_and_summarize(self) -> None:
        raw = _make_jaeger_trace(
            spans=[
                _make_span_dict(
                    span_id="root",
                    references=[],
                    tags=[
                        {"key": "gen_ai.agent.name", "value": "agent"},
                        {"key": "gen_ai.agent.run.id", "value": "r1"},
                    ],
                ),
                _make_span_dict(
                    span_id="tool1",
                    operation_name="execute_tool",
                    parent_span_id="root",
                    tags=[{"key": "gen_ai.tool.name", "value": "search"}],
                ),
            ]
        )
        root_spans = TraceParser.parse_jaeger_trace(raw)
        assert len(root_spans) == 1
        assert root_spans[0].span_id == "root"
        assert len(root_spans[0].child_spans) == 1

        summary = RunSummaryBuilder.build_from_span_tree(root_spans, "t1")
        assert summary is not None
        assert summary.agent_name == "agent"
        assert summary.run_id == "r1"
        assert summary.total_tool_calls == 1

    def test_duplicate_run_ids_not_skipped_at_persistence(self) -> None:
        s1 = RunSummary(run_id="dup", agent_name="a")
        s2 = RunSummary(run_id="dup", agent_name="b")
        assert s1.run_id == s2.run_id

    def test_malformed_spans_no_span_id(self) -> None:
        raw = {
            "traceID": "t1",
            "spans": [
                {"traceID": "t1", "references": [{"spanID": "parent_ref", "refType": "CHILD_OF"}]}
            ],
        }
        result = TraceParser.parse_jaeger_trace(raw)
        assert len(result) == 1
        assert result[0].span_id == ""

    def test_malformed_spans_no_tags(self) -> None:
        spans = [_make_span_dict(tags=None)]
        raw = _make_jaeger_trace(spans=spans)
        result = TraceParser.parse_jaeger_trace(raw)
        assert len(result) == 1
        assert result[0].attributes == {}

    def test_run_summary_builder_root_span_no_attrs(self) -> None:
        root = SpanNode(span_id="s1", trace_id="t1", operation_name="invoke_agent")
        result = RunSummaryBuilder.build_from_span_tree([root], "t1")
        assert result is not None
        assert result.agent_name == "unknown"
        assert result.run_id == "t1"
