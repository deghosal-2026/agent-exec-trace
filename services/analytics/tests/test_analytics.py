from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from analytics.alerts import WebhookAlerter
from analytics.config import settings
from analytics.detectors import CostSpikeDetector, LoopDetector, RetryStormDetector
from analytics.ingest import (
    RunSummaryBuilder,
    SpanTreeBuilder,
    TraceParser,
    _to_bool,
    _to_float,
    _to_int,
    is_run_processed,
    persist_run_summary,
)
from analytics.metrics import AnalyticsMetrics
from analytics.models import Anomaly, FleetRollup, RunSummary, SpanNode, VersionCohortSummary
from analytics.worker import AnalyticsWorker


class TestModels:
    def test_run_summary_defaults(self) -> None:
        s = RunSummary(run_id="test_1", agent_name="agent")
        assert s.run_id == "test_1"
        assert s.agent_name == "agent"
        assert s.total_tool_calls == 0
        assert s.loop_detected is False

    def test_anomaly_generates_id(self) -> None:
        a = Anomaly(run_id="r1", agent_name="a1", anomaly_type="loop")
        assert a.id is not None
        assert len(a.id) > 0

    def test_fleet_rollup(self) -> None:
        now = datetime.now(timezone.utc)
        f = FleetRollup(
            agent_name="a1",
            period_start=now,
            period_end=now,
        )
        assert f.total_runs == 0

    def test_version_cohort(self) -> None:
        v = VersionCohortSummary(agent_name="a1", agent_version="v1")
        assert v.total_runs == 0
        assert v.success_count == 0

    def test_span_node_defaults(self) -> None:
        n = SpanNode(span_id="s1", trace_id="t1", operation_name="test")
        assert n.child_spans == []
        assert n.attributes == {}


class TestIngestHelpers:
    def test_to_float(self) -> None:
        assert _to_float(3.14) == 3.14
        assert _to_float("2.5") == 2.5
        assert _to_float(None) is None
        assert _to_float("invalid") is None

    def test_to_int(self) -> None:
        assert _to_int(42) == 42
        assert _to_int("7") == 7
        assert _to_int(None) == 0
        assert _to_int("bad") == 0
        assert _to_int(None, default=5) == 5

    def test_to_bool(self) -> None:
        assert _to_bool(True) is True
        assert _to_bool(False) is False
        assert _to_bool("true") is True
        assert _to_bool("false") is False
        assert _to_bool(None) is False
        assert _to_bool(1) is True
        assert _to_bool(0) is False


class TestTraceParser:
    def test_parse_empty_trace(self) -> None:
        parser = TraceParser()
        result = parser.parse_jaeger_trace({"spans": []})
        assert result == []

    def test_parse_single_span(self) -> None:
        raw = {
            "traceID": "abc123",
            "spans": [
                {
                    "spanID": "span1",
                    "traceID": "abc123",
                    "operationName": "invoke_agent",
                    "startTime": 1_000_000_000_000,
                    "duration": 10_000_000,
                    "tags": [
                        {"key": "gen_ai.agent.name", "value": "test-agent"},
                        {"key": "gen_ai.agent.run.id", "value": "run_1"},
                    ],
                    "references": [],
                }
            ],
        }
        parser = TraceParser()
        roots = parser.parse_jaeger_trace(raw)
        assert len(roots) == 1
        assert roots[0].operation_name == "invoke_agent"

    def test_parse_with_parent_child(self) -> None:
        raw = {
            "traceID": "abc123",
            "spans": [
                {
                    "spanID": "span1",
                    "traceID": "abc123",
                    "operationName": "invoke_agent",
                    "startTime": 1_000_000_000_000,
                    "duration": 20_000_000,
                    "tags": [],
                    "references": [],
                },
                {
                    "spanID": "span2",
                    "traceID": "abc123",
                    "operationName": "execute_tool",
                    "startTime": 1_000_000_001_000,
                    "duration": 5_000_000,
                    "tags": [],
                    "references": [{"refType": "CHILD_OF", "spanID": "span1"}],
                },
            ],
        }
        parser = TraceParser()
        roots = parser.parse_jaeger_trace(raw)
        assert len(roots) == 1
        assert len(roots[0].child_spans) == 1
        assert roots[0].child_spans[0].operation_name == "execute_tool"


class TestRunSummaryBuilder:
    def test_build_from_span_tree(self) -> None:
        root = SpanNode(
            span_id="root",
            trace_id="t1",
            operation_name="invoke_agent",
            start_time=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            duration_ms=1000,
            attributes={
                "gen_ai.agent.name": "test-agent",
                "gen_ai.agent.run.id": "run_1",
                "gen_ai.agent.version": "v1",
                "gen_ai.agent.loop.count": 3,
                "gen_ai.agent.retry.count": 2,
            },
            child_spans=[
                SpanNode(
                    span_id="tool1",
                    trace_id="t1",
                    operation_name="execute_tool",
                    parent_span_id="root",
                    attributes={},
                ),
                SpanNode(
                    span_id="tool2",
                    trace_id="t1",
                    operation_name="execute_tool",
                    parent_span_id="root",
                    attributes={},
                ),
            ],
        )
        builder = RunSummaryBuilder()
        summary = builder.build_from_span_tree([root], "t1")
        assert summary is not None
        assert summary.agent_name == "test-agent"
        assert summary.run_id == "run_1"
        assert summary.agent_version == "v1"
        assert summary.total_tool_calls == 2
        assert summary.loop_count == 3
        assert summary.total_retries == 2
        assert summary.duration_ms == 1000

    def test_build_empty_returns_none(self) -> None:
        builder = RunSummaryBuilder()
        assert builder.build_from_span_tree([], "t1") is None

    def test_build_with_cost_attribute(self) -> None:
        root = SpanNode(
            span_id="root",
            trace_id="t1",
            operation_name="invoke_agent",
            attributes={
                "gen_ai.agent.name": "test-agent",
                "gen_ai.agent.run.id": "run_2",
                "gen_ai.agent.run.cost.total": 1.23,
            },
        )
        builder = RunSummaryBuilder()
        summary = builder.build_from_span_tree([root], "t1")
        assert summary is not None
        assert summary.estimated_cost == 1.23


class TestSpanTreeBuilder:
    def test_build_tree_orders_roots(self) -> None:
        spans = [
            SpanNode(span_id="s1", trace_id="t1", operation_name="a", parent_span_id=None),
            SpanNode(span_id="s2", trace_id="t1", operation_name="b", parent_span_id="s1"),
        ]
        builder = SpanTreeBuilder()
        roots = builder.build_tree(spans)
        assert len(roots) == 1
        assert roots[0].span_id == "s1"
        assert len(roots[0].child_spans) == 1


class TestMetrics:
    def test_initial_counts(self) -> None:
        m = AnalyticsMetrics()
        snap = m.snapshot()
        assert snap["processed_run_count"] == 0
        assert snap["failed_run_count"] == 0
        assert snap["duplicate_skip_count"] == 0
        assert snap["replay_rebuild_count"] == 0

    def test_increment(self) -> None:
        m = AnalyticsMetrics()
        m.inc_processed(3)
        m.inc_failed(1)
        m.inc_duplicate_skip(2)
        m.inc_replay_rebuild(1)
        snap = m.snapshot()
        assert snap["processed_run_count"] == 3
        assert snap["failed_run_count"] == 1
        assert snap["duplicate_skip_count"] == 2
        assert snap["replay_rebuild_count"] == 1

    def test_freshness(self) -> None:
        import datetime

        m = AnalyticsMetrics()
        assert m.read_model_freshness is None
        now = datetime.datetime.now(datetime.timezone.utc)
        m.read_model_freshness = now
        assert m.read_model_freshness == now


class TestConfig:
    def test_defaults(self) -> None:
        assert settings.polling_interval_seconds == 30
        assert settings.log_level == "INFO"
        assert settings.trace_query_service == "demo-agent"

    def test_db_dsn_default(self) -> None:
        assert "postgresql" in settings.db_dsn


class TestWorker:
    @pytest.mark.asyncio
    async def test_process_cycle_empty(self) -> None:
        worker = AnalyticsWorker()
        worker.fetcher.fetch_traces_by_service = AsyncMock(return_value=[])  # type: ignore[method-assign]
        pool = MagicMock()
        with (
            patch("analytics.worker.get_pool", return_value=pool),
            patch.object(worker.fleet_materializer, "materialize_fleet_rollups", AsyncMock()),
            patch.object(worker.cohort_materializer, "materialize_version_cohorts", AsyncMock()),
        ):
            await worker._process_cycle()
            worker.metrics.inc_processed(0)
            assert worker.metrics.snapshot()["processed_run_count"] == 0

    @pytest.mark.asyncio
    async def test_process_trace_not_found(self) -> None:
        worker = AnalyticsWorker()
        worker.fetcher.fetch_trace_by_id = AsyncMock(return_value=None)  # type: ignore[method-assign]
        result = await worker.process_trace("nonexistent")
        assert result is False

    def _make_pool(self, async_conn: bool = False) -> MagicMock:
        pool = MagicMock()
        pool.acquire = MagicMock()
        conn = MagicMock()
        conn.fetch = AsyncMock(return_value=[])
        conn.fetchval = AsyncMock(return_value=0)
        conn.execute = AsyncMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
        return pool

    @pytest.mark.asyncio
    async def test_duplicate_skip(self) -> None:
        worker = AnalyticsWorker()
        worker.fetcher.fetch_traces_by_service = AsyncMock(  # type: ignore[method-assign]
            return_value=[
                {
                    "traceID": "t1",
                    "spans": [
                        {
                            "spanID": "s1",
                            "traceID": "t1",
                            "operationName": "invoke_agent",
                            "startTime": 1_000_000_000_000,
                            "duration": 1000,
                            "tags": [
                                {"key": "gen_ai.agent.name", "value": "test"},
                                {"key": "gen_ai.agent.run.id", "value": "run_1"},
                            ],
                            "references": [],
                        }
                    ],
                }
            ]
        )
        pool = self._make_pool()
        with (
            patch("analytics.worker.get_pool", return_value=pool),
            patch("analytics.worker.is_run_processed", AsyncMock(return_value=True)),
            patch.object(worker.fleet_materializer, "materialize_fleet_rollups", AsyncMock()),
            patch.object(worker.cohort_materializer, "materialize_version_cohorts", AsyncMock()),
        ):
            await worker._process_cycle()
            assert worker.metrics.snapshot()["duplicate_skip_count"] == 1

    @pytest.mark.asyncio
    async def test_process_trace_success(self) -> None:
        worker = AnalyticsWorker()
        worker.fetcher.fetch_trace_by_id = AsyncMock(  # type: ignore[method-assign]
            return_value={
                "traceID": "t1",
                "spans": [
                    {
                        "spanID": "s1",
                        "traceID": "t1",
                        "operationName": "invoke_agent",
                        "startTime": 1_000_000_000_000,
                        "duration": 1000,
                        "tags": [
                            {"key": "gen_ai.agent.name", "value": "test"},
                            {"key": "gen_ai.agent.run.id", "value": "run_1"},
                        ],
                        "references": [],
                    }
                ],
            }
        )
        pool = self._make_pool()
        with (
            patch("analytics.worker.get_pool", return_value=pool),
            patch("analytics.worker.is_run_processed", AsyncMock(return_value=False)),
            patch("analytics.worker.persist_run_summary", AsyncMock()),
        ):
            result = await worker.process_trace("t1")
            assert result is True


class TestPersistenceFunctions:
    def _make_pool(self) -> tuple[MagicMock, MagicMock]:
        pool = MagicMock()
        pool.acquire = MagicMock()
        conn = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
        return pool, conn

    @pytest.mark.asyncio
    async def test_is_run_processed(self) -> None:
        pool, conn = self._make_pool()
        conn.fetchval = AsyncMock(return_value=1)
        result = await is_run_processed(pool, "run_1")
        assert result is True

    @pytest.mark.asyncio
    async def test_is_run_not_processed(self) -> None:
        pool, conn = self._make_pool()
        conn.fetchval = AsyncMock(return_value=None)
        result = await is_run_processed(pool, "run_2")
        assert result is False

    @pytest.mark.asyncio
    async def test_persist_run_summary(self) -> None:
        pool, conn = self._make_pool()
        conn.execute = AsyncMock()
        summary = RunSummary(run_id="run_1", agent_name="agent")
        await persist_run_summary(pool, summary)
        conn.execute.assert_called_once()


class TestLoopDetector:
    def _make_spans(self, tool_names: list[str]) -> list[SpanNode]:
        spans: list[SpanNode] = []
        for i, name in enumerate(tool_names):
            spans.append(
                SpanNode(
                    span_id=f"s{i}",
                    trace_id="t1",
                    operation_name="execute_tool",
                    attributes={"gen_ai.tool.name": name},
                    parent_span_id="root",
                )
            )
        return [
            SpanNode(
                span_id="root",
                trace_id="t1",
                operation_name="invoke_agent",
                attributes={
                    "gen_ai.agent.name": "test-agent",
                    "gen_ai.agent.run.id": "run_1",
                },
                child_spans=spans,
            )
        ]

    def _make_summary(self) -> RunSummary:
        return RunSummary(run_id="run_1", agent_name="test-agent")

    def test_detects_consecutive_repetition(self) -> None:
        detector = LoopDetector(threshold=3)
        spans = self._make_spans(["tool_a", "tool_a", "tool_a", "tool_a"])
        result = detector.detect(self._make_summary(), spans)
        assert result is not None
        assert result.anomaly_type == "loop"
        assert result.severity == "warning"
        assert "tool_a" in str(result.explanation)

    def test_critical_severity_at_10_plus(self) -> None:
        detector = LoopDetector(threshold=3)
        spans = self._make_spans(["tool_b"] * 10)
        result = detector.detect(self._make_summary(), spans)
        assert result is not None
        assert result.severity == "critical"

    def test_below_threshold_no_anomaly(self) -> None:
        detector = LoopDetector(threshold=5)
        spans = self._make_spans(["tool_a", "tool_a", "tool_a", "tool_a"])
        result = detector.detect(self._make_summary(), spans)
        assert result is None

    def test_alternating_tools_no_anomaly(self) -> None:
        detector = LoopDetector(threshold=3)
        spans = self._make_spans(["tool_a", "tool_b", "tool_a", "tool_b"])
        result = detector.detect(self._make_summary(), spans)
        assert result is None

    def test_empty_spans_no_anomaly(self) -> None:
        detector = LoopDetector(threshold=3)
        spans = [
            SpanNode(
                span_id="root",
                trace_id="t1",
                operation_name="invoke_agent",
                attributes={
                    "gen_ai.agent.name": "test-agent",
                    "gen_ai.agent.run.id": "run_1",
                },
                child_spans=[],
            )
        ]
        result = detector.detect(self._make_summary(), spans)
        assert result is None

    def test_not_consecutive_does_not_fire(self) -> None:
        detector = LoopDetector(threshold=3)
        spans = self._make_spans(["tool_a", "tool_a", "tool_b", "tool_a"])
        result = detector.detect(self._make_summary(), spans)
        assert result is None

    def test_configurable_threshold(self) -> None:
        detector = LoopDetector(threshold=2)
        spans = self._make_spans(["tool_a", "tool_a"])
        result = detector.detect(self._make_summary(), spans)
        assert result is not None
        assert result.evidence is not None
        assert result.evidence["threshold"] == 2


class TestRetryStormDetector:
    def _make_summary(self, retries: int) -> RunSummary:
        return RunSummary(
            run_id="run_1",
            agent_name="test-agent",
            total_retries=retries,
        )

    def test_detects_at_threshold(self) -> None:
        detector = RetryStormDetector(threshold=5)
        summary = self._make_summary(5)
        spans: list[SpanNode] = []
        result = detector.detect(summary, spans)
        assert result is not None
        assert result.anomaly_type == "retry_storm"
        assert result.severity == "warning"

    def test_critical_at_10_plus(self) -> None:
        detector = RetryStormDetector(threshold=5)
        summary = self._make_summary(10)
        result = detector.detect(summary, [])
        assert result is not None
        assert result.severity == "critical"

    def test_below_threshold_no_anomaly(self) -> None:
        detector = RetryStormDetector(threshold=5)
        summary = self._make_summary(4)
        result = detector.detect(summary, [])
        assert result is None

    def test_zero_retries_no_anomaly(self) -> None:
        detector = RetryStormDetector(threshold=5)
        summary = self._make_summary(0)
        result = detector.detect(summary, [])
        assert result is None

    def test_configurable_threshold(self) -> None:
        detector = RetryStormDetector(threshold=2)
        summary = self._make_summary(2)
        result = detector.detect(summary, [])
        assert result is not None
        assert result.evidence is not None
        assert result.evidence["threshold"] == 2


class TestCostSpikeDetector:
    def _make_summary(self, cost: float | None) -> RunSummary:
        return RunSummary(
            run_id="run_1",
            agent_name="test-agent",
            agent_version="v1",
            estimated_cost=cost,
        )

    @pytest.mark.asyncio
    async def test_absolute_spike(self) -> None:
        detector = CostSpikeDetector(absolute_threshold=5.0)
        summary = self._make_summary(6.0)
        result = await detector.detect(summary, [], pool=None)
        assert result is not None
        assert result.anomaly_type == "cost_spike"
        assert "absolute spike" in (result.explanation or "")

    @pytest.mark.asyncio
    async def test_absolute_spike_critical(self) -> None:
        detector = CostSpikeDetector(absolute_threshold=5.0)
        summary = self._make_summary(16.0)
        result = await detector.detect(summary, [], pool=None)
        assert result is not None
        assert result.severity == "critical"

    @pytest.mark.asyncio
    async def test_below_threshold_no_anomaly(self) -> None:
        detector = CostSpikeDetector(absolute_threshold=5.0)
        summary = self._make_summary(4.0)
        result = await detector.detect(summary, [], pool=None)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_cost_no_anomaly(self) -> None:
        detector = CostSpikeDetector(absolute_threshold=5.0)
        summary = self._make_summary(None)
        result = await detector.detect(summary, [], pool=None)
        assert result is None

    @pytest.mark.asyncio
    async def test_relative_spike_with_baseline(self) -> None:
        detector = CostSpikeDetector(absolute_threshold=5.0, baseline_multiplier=2.0)
        summary = self._make_summary(1.0)
        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock()
        pool.acquire.return_value.__aexit__ = AsyncMock()
        conn = AsyncMock()
        pool.acquire.return_value.__aenter__.return_value = conn
        conn.fetchrow = AsyncMock(return_value={"avg_cost": 0.40})

        result = await detector.detect(summary, [], pool=pool)
        assert result is not None
        assert "relative spike" in (result.explanation or "")

    @pytest.mark.asyncio
    async def test_relative_spike_below_multiplier(self) -> None:
        detector = CostSpikeDetector(absolute_threshold=5.0, baseline_multiplier=2.0)
        summary = self._make_summary(0.60)
        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock()
        pool.acquire.return_value.__aexit__ = AsyncMock()
        conn = AsyncMock()
        pool.acquire.return_value.__aenter__.return_value = conn
        conn.fetchrow = AsyncMock(return_value={"avg_cost": 0.40})

        result = await detector.detect(summary, [], pool=pool)
        assert result is None


class TestWebhookAlerter:
    @pytest.mark.asyncio
    async def test_no_webhook_url(self) -> None:
        alerter = WebhookAlerter(webhook_url="")
        anomaly = Anomaly(run_id="r1", agent_name="a1", anomaly_type="loop")
        result = await alerter.send_alert(anomaly)
        assert result is False

    @pytest.mark.asyncio
    async def test_sends_alert_success(self) -> None:
        alerter = WebhookAlerter(webhook_url="http://example.com/hook")
        anomaly = Anomaly(run_id="r1", agent_name="a1", anomaly_type="loop")
        with patch("analytics.alerts.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_instance.post = AsyncMock(return_value=mock_response)

            result = await alerter.send_alert(anomaly)
            assert result is True
            mock_instance.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_alert_http_error(self) -> None:
        import httpx

        alerter = WebhookAlerter(webhook_url="http://example.com/hook")
        anomaly = Anomaly(run_id="r1", agent_name="a1", anomaly_type="loop")
        with patch("analytics.alerts.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_instance.post = AsyncMock(side_effect=httpx.HTTPError("HTTP error"))

            result = await alerter.send_alert(anomaly)
            assert result is False


class TestFleetRollupMaterializer:
    @pytest.mark.asyncio
    async def test_materialize_fleet_rollups(self) -> None:
        from analytics.materializer import FleetRollupMaterializer

        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock()
        pool.acquire.return_value.__aexit__ = AsyncMock()

        conn1 = AsyncMock()
        conn1.fetch = AsyncMock(
            return_value=[
                {
                    "agent_name": "test-agent",
                    "agent_version": "v1",
                    "workload_type": None,
                    "total_runs": 5,
                    "success_count": 4,
                    "error_count": 1,
                    "loop_count": 1,
                    "avg_duration_ms": 1000,
                    "avg_cost": 0.50,
                }
            ]
        )

        conn2 = AsyncMock()
        conn2.fetchval = AsyncMock(return_value=2)

        conns = iter([conn1, conn2])
        pool.acquire.return_value.__aenter__.side_effect = lambda: next(conns)

        mat = FleetRollupMaterializer()
        with patch("analytics.materializer.persist_fleet_rollup", AsyncMock()):
            count = await mat.materialize_fleet_rollups(pool)
            assert count == 1


class TestVersionCohortMaterializer:
    @pytest.mark.asyncio
    async def test_materialize_version_cohorts(self) -> None:
        from analytics.materializer import VersionCohortMaterializer

        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock()
        pool.acquire.return_value.__aexit__ = AsyncMock()

        conn = AsyncMock()
        conn.fetch = AsyncMock(
            return_value=[
                {
                    "agent_name": "test-agent",
                    "agent_version": "v1",
                    "total_runs": 5,
                    "success_count": 4,
                    "error_count": 1,
                    "loop_count": 1,
                    "avg_duration_ms": 1000,
                    "avg_cost": 0.50,
                    "total_tool_calls": 20,
                    "total_retries": 3,
                }
            ]
        )
        conn.fetchval = AsyncMock(return_value=2)

        pool.acquire.return_value.__aenter__.return_value = conn

        mat = VersionCohortMaterializer()
        with patch("analytics.materializer.persist_version_cohort", AsyncMock()):
            count = await mat.materialize_version_cohorts(pool)
            assert count == 1


class TestWorkerAnomalyIntegration:
    @pytest.mark.asyncio
    async def test_detect_and_alert_runs_detectors(self) -> None:
        worker = AnalyticsWorker()
        summary = RunSummary(
            run_id="run_1",
            agent_name="test-agent",
            total_retries=5,
        )
        spans: list[SpanNode] = []

        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock()
        pool.acquire.return_value.__aexit__ = AsyncMock()

        with (
            patch("analytics.worker.persist_anomaly", AsyncMock()),
            patch("analytics.worker.WebhookAlerter.send_alert", AsyncMock(return_value=True)),
            patch("analytics.worker.CostSpikeDetector.detect", AsyncMock(return_value=None)),
        ):
            await worker._detect_and_alert(pool, summary, spans)
            assert worker.metrics.anomaly_detected_count == 1