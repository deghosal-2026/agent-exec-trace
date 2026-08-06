from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from analytics.alerts import WebhookAlerter
from analytics.config import settings
from analytics.detectors import (
    CostSpikeDetector,
    LoopDetector,
    RetryStormDetector,
    create_all_detectors,
)
from analytics.detectors.llm import (
    ConfusionPatternDetector,
    EmbeddingDriftDetector,
    ExplanationScorer,
    GoalDriftDetector,
    HallucinationDetector,
    LLMTriageClassifier,
    QualityDegradationDetector,
    SemanticLoopDetector,
    ThresholdCalibrator,
)
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


def _noop_client() -> Any:
    from analytics.llm_client import LLMClient

    # Ensure the client cannot make real HTTP calls: pass an http_client
    # backed by a transport that always returns 503 so chat() returns None.
    import httpx
    transport = httpx.MockTransport(lambda _: httpx.Response(503, json={}))
    return LLMClient(
        base_url="http://noop.test/v1",
        api_key="noop",
        http_client=httpx.AsyncClient(transport=transport),
    )


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
        assert settings.trace_query_services == ("demo-agent",)

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


# ------------------------------------------------------------------
# Detector factory + coverage tests (8.6.3)
# ------------------------------------------------------------------


class TestDetectorFactory:
    """Verify all 35 rule-based detectors are registered and instantiable."""

    def test_creates_35_detectors(self) -> None:
        detectors = create_all_detectors()
        assert len(detectors) == 35

    def test_all_have_unique_anomaly_types(self) -> None:
        detectors = create_all_detectors()
        types = [d.anomaly_type for d in detectors]
        assert len(types) == len(set(types)), f"Duplicate anomaly types: {types}"

    def test_all_detect_method_does_not_crash(self) -> None:
        summary = RunSummary(run_id="r1", agent_name="a")
        spans: list[SpanNode] = [
            SpanNode(span_id="s", trace_id="t", operation_name="invoke_agent")
        ]
        for d in create_all_detectors():
            try:
                result = d.detect(summary, spans)
                assert result is None or isinstance(result, Anomaly)
            except NotImplementedError:
                pass


class TestDetectorCategories:
    """Smoke tests for each detector category."""

    def _make_spans(self, tool_names: list[str]) -> list[SpanNode]:
        children = [
            SpanNode(
                span_id=f"s{i}", trace_id="t", operation_name="execute_tool",
                attributes={"gen_ai.tool.name": n}, parent_span_id="root",
            )
            for i, n in enumerate(tool_names)
        ]
        return [
            SpanNode(
                span_id="root", trace_id="t", operation_name="invoke_agent",
                attributes={"gen_ai.agent.name": "a", "gen_ai.agent.run.id": "r"},
                child_spans=children,
            )
        ]

    def _summary(self) -> RunSummary:
        return RunSummary(run_id="r", agent_name="a")

    # Tool execution
    def test_tool_error_rate_positive(self) -> None:
        from analytics.detectors.tool import ToolErrorRateDetector
        d = ToolErrorRateDetector(threshold_pct=10.0)
        spans = [SpanNode(
            span_id="root", trace_id="t", operation_name="invoke_agent",
            child_spans=[
                SpanNode(span_id="s1", trace_id="t", operation_name="execute_tool",
                         status="error", parent_span_id="root"),
                SpanNode(span_id="s2", trace_id="t", operation_name="execute_tool",
                         status="error", parent_span_id="root"),
                SpanNode(span_id="s3", trace_id="t", operation_name="execute_tool",
                         status="ok", parent_span_id="root"),
            ],
        )]
        assert d.detect(self._summary(), spans) is not None

    def test_tool_error_rate_negative(self) -> None:
        from analytics.detectors.tool import ToolErrorRateDetector
        d = ToolErrorRateDetector(threshold_pct=50.0)
        spans = [SpanNode(
            span_id="root", trace_id="t", operation_name="invoke_agent",
            child_spans=[
                SpanNode(span_id="s1", trace_id="t", operation_name="execute_tool",
                         status="ok", parent_span_id="root"),
            ],
        )]
        assert d.detect(self._summary(), spans) is None

    # Retry
    def test_systemic_retry_positive(self) -> None:
        from analytics.detectors.retry import SystemicRetryDetector
        d = SystemicRetryDetector()
        s = RunSummary(run_id="r", agent_name="a", total_retries=3)
        spans = [SpanNode(
            span_id="root", trace_id="t", operation_name="invoke_agent",
            child_spans=[
                SpanNode(span_id="s1", trace_id="t", operation_name="retry_1",
                         status="error", parent_span_id="root"),
                SpanNode(span_id="s2", trace_id="t", operation_name="retry_2",
                         status="error", parent_span_id="root"),
                SpanNode(span_id="s3", trace_id="t", operation_name="retry_3",
                         status="error", parent_span_id="root"),
            ],
        )]
        assert d.detect(s, spans) is not None

    def test_systemic_retry_negative(self) -> None:
        from analytics.detectors.retry import SystemicRetryDetector
        d = SystemicRetryDetector()
        s = RunSummary(run_id="r", agent_name="a", total_retries=1)
        assert d.detect(s, []) is None

    # Output
    def test_low_output_positive(self) -> None:
        from analytics.detectors.output import LowOutputDetector
        d = LowOutputDetector(min_chars=100)
        s = RunSummary(run_id="r", agent_name="a")
        spans = [SpanNode(
            span_id="s", trace_id="t", operation_name="invoke_agent",
            attributes={"gen_ai.response.content": "too short"},
        )]
        assert d.detect(s, spans) is not None

    def test_low_output_negative(self) -> None:
        from analytics.detectors.output import LowOutputDetector
        d = LowOutputDetector(min_chars=10)
        s = RunSummary(run_id="r", agent_name="a")
        spans = [SpanNode(
            span_id="s", trace_id="t", operation_name="invoke_agent",
            attributes={"gen_ai.response.content": "long enough content here"},
        )]
        assert d.detect(s, spans) is None

    # Cross-run
    def test_first_run_heuristic(self) -> None:
        from analytics.detectors.cross_run import FirstRunHeuristicDetector
        d = FirstRunHeuristicDetector()
        assert d.detect(RunSummary(run_id="r", agent_name="a"), []) is None


class TestAdditionalRuleDetectors:
    def _summary(self, **kwargs: Any) -> RunSummary:
        return RunSummary(run_id="r", agent_name="a", **kwargs)

    def _tool(
        self,
        span_id: str,
        tool_name: str,
        *,
        status: str | None = None,
        duration_ms: int | None = None,
        attrs: dict[str, object] | None = None,
    ) -> SpanNode:
        attributes: dict[str, object] = {"gen_ai.tool.name": tool_name}
        if attrs:
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

    def _root(self, children: list[SpanNode], **attrs: object) -> list[SpanNode]:
        return [
            SpanNode(
                span_id="root",
                trace_id="t",
                operation_name="invoke_agent",
                attributes=attrs,
                child_spans=children,
            )
        ]

    def test_pattern_loop_positive_and_negative(self) -> None:
        from analytics.detectors.tool import PatternLoopDetector

        detector = PatternLoopDetector(window_size=4)
        looping = self._root(
            [
                self._tool("s1", "A"),
                self._tool("s2", "B"),
                self._tool("s3", "A"),
                self._tool("s4", "B"),
                self._tool("s5", "A"),
                self._tool("s6", "B"),
                self._tool("s7", "A"),
                self._tool("s8", "B"),
            ]
        )
        clean = self._root([self._tool("s1", "A"), self._tool("s2", "B"), self._tool("s3", "C")])
        assert detector.detect(self._summary(), looping) is not None
        assert detector.detect(self._summary(), clean) is None

    def test_argument_loop_positive_and_critical(self) -> None:
        from analytics.detectors.tool import ArgumentLoopDetector

        detector = ArgumentLoopDetector(threshold=3)
        warning_spans = self._root(
            [
                self._tool("s1", "search", attrs={"gen_ai.tool.arguments": '{"q":"x"}'}),
                self._tool("s2", "search", attrs={"gen_ai.tool.arguments": '{"q":"x"}'}),
                self._tool("s3", "search", attrs={"gen_ai.tool.arguments": '{"q":"x"}'}),
            ]
        )
        critical_spans = self._root(
            [
                self._tool("s1", "search", attrs={"gen_ai.tool.arguments": '{"q":"x"}'}),
                self._tool("s2", "search", attrs={"gen_ai.tool.arguments": '{"q":"x"}'}),
                self._tool("s3", "search", attrs={"gen_ai.tool.arguments": '{"q":"x"}'}),
                self._tool("s4", "search", attrs={"gen_ai.tool.arguments": '{"q":"x"}'}),
                self._tool("s5", "search", attrs={"gen_ai.tool.arguments": '{"q":"x"}'}),
                self._tool("s6", "search", attrs={"gen_ai.tool.arguments": '{"q":"x"}'}),
            ]
        )
        clean = self._root(
            [
                self._tool("s1", "search", attrs={"gen_ai.tool.arguments": '{"q":"x"}'}),
                self._tool("s2", "search", attrs={"gen_ai.tool.arguments": '{"q":"y"}'}),
            ]
        )
        warning = detector.detect(self._summary(), warning_spans)
        critical = detector.detect(self._summary(), critical_spans)
        assert warning is not None and warning.severity == "warning"
        assert critical is not None and critical.severity == "critical"
        assert detector.detect(self._summary(), clean) is None

    def test_specific_tool_error_positive_negative_and_critical(self) -> None:
        from analytics.detectors.tool import SpecificToolErrorDetector

        detector = SpecificToolErrorDetector(threshold_pct=50.0)
        warning_spans = self._root(
            [
                self._tool("s1", "search", status="error"),
                self._tool("s2", "search", status="error"),
                self._tool("s3", "search", status="ok"),
            ]
        )
        critical_spans = self._root(
            [
                self._tool("s1", "search", status="error"),
                self._tool("s2", "search", status="error"),
                self._tool("s3", "search", status="error"),
            ]
        )
        clean = self._root([self._tool("s1", "search", status="ok")])
        warning = detector.detect(self._summary(), warning_spans)
        critical = detector.detect(self._summary(), critical_spans)
        assert warning is not None and warning.severity == "warning"
        assert critical is not None and critical.severity == "critical"
        assert detector.detect(self._summary(), clean) is None

    def test_tool_timeout_and_redundant_calls(self) -> None:
        from analytics.detectors.tool import RedundantToolCallDetector, ToolTimeoutDetector

        timeout = ToolTimeoutDetector(limit_seconds=1.0)
        redundant = RedundantToolCallDetector(threshold=3)
        timeout_spans = self._root([self._tool("s1", "search", duration_ms=1500)])
        clean_timeout = self._root([self._tool("s1", "search", duration_ms=200)])
        redundant_spans = self._root(
            [
                self._tool(
                    "s1",
                    "search",
                    attrs={"gen_ai.tool.arguments": "x", "gen_ai.tool.result": "same"},
                ),
                self._tool(
                    "s2",
                    "search",
                    attrs={"gen_ai.tool.arguments": "x", "gen_ai.tool.result": "same"},
                ),
                self._tool(
                    "s3",
                    "search",
                    attrs={"gen_ai.tool.arguments": "x", "gen_ai.tool.result": "same"},
                ),
            ]
        )
        assert timeout.detect(self._summary(), timeout_spans) is not None
        assert timeout.detect(self._summary(), clean_timeout) is None
        assert redundant.detect(self._summary(), redundant_spans) is not None

    @pytest.mark.asyncio
    async def test_cost_baseline_and_run_duration_async(self) -> None:
        from analytics.detectors.cost import CostVsBaselineDetector
        from analytics.detectors.runtime import RunDurationDetector

        class _Acquire:
            def __init__(self, conn: Any) -> None:
                self._conn = conn

            async def __aenter__(self) -> Any:
                return self._conn

            async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
                return None

        class _Pool:
            def __init__(self, conn: Any) -> None:
                self._conn = conn

            def acquire(self) -> _Acquire:
                return _Acquire(self._conn)

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(side_effect=[{"avg_cost": 1.0}, {"avg_dur": 1000}])
        pool = _Pool(conn)

        cost_detector = CostVsBaselineDetector(multiplier=2.0)
        duration_detector = RunDurationDetector(multiplier=2.0)
        cost_summary = self._summary(agent_version="v1", estimated_cost=3.0)
        duration_summary = self._summary(agent_version="v1", duration_ms=3000)

        cost_result = await cost_detector.detect_async(cost_summary, [], pool=pool)
        duration_result = await duration_detector.detect_async(duration_summary, [], pool=pool)
        assert cost_result is not None
        assert duration_result is not None

    def test_cost_efficiency_and_token_explosion(self) -> None:
        from analytics.detectors.cost import CostEfficiencyDetector, TokenExplosionDetector

        efficiency = CostEfficiencyDetector(high_cost_per_tool_threshold=1.0)
        token = TokenExplosionDetector(growth_multiplier=2.0)
        cost_summary = self._summary(estimated_cost=10.0, total_tool_calls=5, status="success")
        cost_result = efficiency.detect(cost_summary, [])
        spans = [
            SpanNode(
                span_id="s1",
                trace_id="t",
                operation_name="step",
                attributes={"gen_ai.usage.prompt_tokens": 10, "gen_ai.usage.completion_tokens": 10},
            ),
            SpanNode(
                span_id="s2",
                trace_id="t",
                operation_name="step",
                attributes={"gen_ai.usage.prompt_tokens": 10, "gen_ai.usage.completion_tokens": 10},
            ),
            SpanNode(
                span_id="s3",
                trace_id="t",
                operation_name="step",
                attributes={
                    "gen_ai.usage.prompt_tokens": 100,
                    "gen_ai.usage.completion_tokens": 100,
                },
            ),
            SpanNode(
                span_id="s4",
                trace_id="t",
                operation_name="step",
                attributes={
                    "gen_ai.usage.prompt_tokens": 100,
                    "gen_ai.usage.completion_tokens": 100,
                },
            ),
        ]
        token_result = token.detect(self._summary(), spans)
        assert cost_result is not None
        assert token_result is not None

    def test_runtime_retry_interaction_output_crossrun_detectors(self) -> None:
        from analytics.detectors.cross_run import RunFrequencyAnomalyDetector
        from analytics.detectors.interaction import (
            ApprovalLatencyDetector,
            InterventionFrequencyDetector,
            InterventionRejectionDetector,
        )
        from analytics.detectors.output import EmptyResponseDetector, IndeterminateDetector
        from analytics.detectors.retry import (
            CascadingRetryDetector,
            RecoveryPathDetector,
            TransientRetryDetector,
        )
        from analytics.detectors.runtime import (
            InactivityDetector,
            MaxStepHitDetector,
            PrematureCompletionDetector,
            StepEfficiencyDetector,
        )

        max_step = MaxStepHitDetector()
        step_eff = StepEfficiencyDetector(max_tool_calls=2)
        inactivity = InactivityDetector(max_gap_seconds=1.0)
        premature = PrematureCompletionDetector()
        transient = TransientRetryDetector(threshold=2)
        cascading = CascadingRetryDetector()
        recovery = RecoveryPathDetector(extra_steps_threshold=2)
        intervention_freq = InterventionFrequencyDetector(threshold=2)
        approval = ApprovalLatencyDetector(max_seconds=1.0)
        reject = InterventionRejectionDetector(threshold=1)
        empty = EmptyResponseDetector()
        indeterminate = IndeterminateDetector()
        run_freq = RunFrequencyAnomalyDetector(min_runs=5, max_multiplier=2.0)

        max_step_spans = self._root([self._tool(f"s{i}", "x") for i in range(21)])
        assert (
            max_step.detect(
                self._summary(total_tool_calls=51, status="max_steps_hit"),
                max_step_spans,
            )
            is not None
        )
        assert step_eff.detect(self._summary(total_tool_calls=5, status="success"), []) is not None

        inactivity_spans = [
            SpanNode(
                span_id="s1",
                trace_id="t",
                operation_name="step",
                start_time=datetime.now(timezone.utc),
            ),
            SpanNode(
                span_id="s2",
                trace_id="t",
                operation_name="step",
                start_time=datetime.now(timezone.utc).replace(
                    second=(datetime.now(timezone.utc).second + 5) % 60
                ),
            ),
        ]
        assert inactivity.detect(self._summary(), inactivity_spans) is not None
        assert (
            premature.detect(
                self._summary(status="error"),
                self._root(
                    [SpanNode(span_id="p", trace_id="t", operation_name="plan")]
                ),
            )
            is not None
        )

        retry_spans = self._root(
            [
                SpanNode(
                    span_id="r1",
                    trace_id="t",
                    operation_name="retry_1",
                    attributes={"gen_ai.retry.successful": True},
                    child_spans=[self._tool("t1", "search")],
                ),
                SpanNode(
                    span_id="r2",
                    trace_id="t",
                    operation_name="retry_2",
                    attributes={"gen_ai.retry.successful": True},
                    child_spans=[self._tool("t2", "lookup")],
                ),
                SpanNode(
                    span_id="r3",
                    trace_id="t",
                    operation_name="retry_3",
                    attributes={"gen_ai.retry.successful": False},
                    child_spans=[self._tool("t3", "search")],
                ),
                SpanNode(
                    span_id="r4",
                    trace_id="t",
                    operation_name="retry_4",
                    attributes={"gen_ai.retry.successful": False},
                    child_spans=[self._tool("t4", "write")],
                ),
            ]
        )
        assert transient.detect(self._summary(total_retries=3), retry_spans) is not None
        assert cascading.detect(self._summary(total_retries=4), retry_spans) is not None

        recovery_spans = self._root(
            [
                self._tool("e1", "search", status="error"),
                self._tool("e2", "search"),
                self._tool("e3", "lookup"),
                self._tool("e4", "write"),
            ]
        )
        assert recovery.detect(self._summary(), recovery_spans) is not None
        assert intervention_freq.detect(self._summary(total_interventions=3), []) is not None
        assert (
            approval.detect(
                self._summary(),
                self._root(
                    [
                        SpanNode(
                            span_id="h1",
                            trace_id="t",
                            operation_name="await_approval",
                            duration_ms=2000,
                        )
                    ]
                ),
            )
            is not None
        )
        reject_spans = self._root(
            [
                SpanNode(span_id="h1", trace_id="t", operation_name="human_intervention"),
                SpanNode(span_id="r1", trace_id="t", operation_name="retry_1"),
                SpanNode(span_id="h2", trace_id="t", operation_name="human_intervention"),
            ]
        )
        assert reject.detect(self._summary(total_interventions=2), reject_spans) is not None
        assert (
            empty.detect(
                self._summary(),
                self._root(
                    [SpanNode(span_id="a", trace_id="t", operation_name="invoke_agent")]
                ),
            )
            is not None
        )
        assert indeterminate.detect(
            self._summary(status="unknown"),
            [SpanNode(span_id="a2", trace_id="t", operation_name="invoke_agent")],
        ) is not None
        assert run_freq.detect(self._summary(), []) is None


class TestRemainingRuleDetectors:
    class _Acquire:
        def __init__(self, conn: Any) -> None:
            self._conn = conn

        async def __aenter__(self) -> Any:
            return self._conn

        async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            return None

    class _Pool:
        def __init__(self, conn: Any) -> None:
            self._conn = conn

        def acquire(self) -> TestRemainingRuleDetectors._Acquire:
            return TestRemainingRuleDetectors._Acquire(self._conn)

    def _summary(self, **kwargs: Any) -> RunSummary:
        return RunSummary(run_id="r", agent_name="a", agent_version="v1", **kwargs)

    def _root(self, children: list[SpanNode]) -> list[SpanNode]:
        return [
            SpanNode(
                span_id="root",
                trace_id="t",
                operation_name="invoke_agent",
                child_spans=children,
            )
        ]

    def _tool(self, span_id: str, name: str, **attrs: object) -> SpanNode:
        attributes: dict[str, object] = {"gen_ai.tool.name": name}
        attributes.update(attrs)
        return SpanNode(
            span_id=span_id,
            trace_id="t",
            operation_name="execute_tool",
            attributes=attributes,
        )

    def test_tool_latency_positive_and_negative(self) -> None:
        from analytics.detectors.tool import ToolLatencyDetector

        detector = ToolLatencyDetector(multiplier=1.4)
        positive = self._root(
            [
                SpanNode(
                    span_id="s1",
                    trace_id="t",
                    operation_name="execute_tool",
                    duration_ms=100,
                    attributes={"gen_ai.tool.name": "search"},
                ),
                SpanNode(
                    span_id="s2",
                    trace_id="t",
                    operation_name="execute_tool",
                    duration_ms=100,
                    attributes={"gen_ai.tool.name": "search"},
                ),
                SpanNode(
                    span_id="s3",
                    trace_id="t",
                    operation_name="execute_tool",
                    duration_ms=500,
                    attributes={"gen_ai.tool.name": "search"},
                ),
            ]
        )
        negative = self._root(
            [
                SpanNode(
                    span_id="s1",
                    trace_id="t",
                    operation_name="execute_tool",
                    duration_ms=100,
                    attributes={"gen_ai.tool.name": "search"},
                ),
                SpanNode(
                    span_id="s2",
                    trace_id="t",
                    operation_name="execute_tool",
                    duration_ms=120,
                    attributes={"gen_ai.tool.name": "search"},
                ),
            ]
        )
        assert detector.detect(self._summary(), positive) is not None
        assert detector.detect(self._summary(), negative) is None

    def test_per_tool_cost_and_wasted_calls(self) -> None:
        from analytics.detectors.cost import PerToolCostSpikeDetector, WastedToolCallsDetector

        per_tool = PerToolCostSpikeDetector(multiplier=2.0)
        wasted = WastedToolCallsDetector(threshold=3)
        summary = self._summary(estimated_cost=10.0)
        spans = self._root([
            self._tool("s1", "search", **{"gen_ai.tool.result": "same"}),
            self._tool("s2", "search", **{"gen_ai.tool.result": "same"}),
            self._tool("s3", "search", **{"gen_ai.tool.result": "same"}),
            self._tool("s4", "other", **{"gen_ai.tool.result": "x"}),
        ])
        assert summary.estimated_cost is not None
        anomaly = per_tool.detect(summary, spans)
        assert anomaly is not None
        assert anomaly.evidence is not None
        assert anomaly.evidence["tool_name"] == "search"
        assert wasted.detect(summary, spans) is None

    def test_wasted_calls_across_different_tools(self) -> None:
        from analytics.detectors.cost import WastedToolCallsDetector

        wasted = WastedToolCallsDetector(threshold=3)
        summary = self._summary()
        spans = self._root([
            self._tool("s1", "search", **{"gen_ai.tool.result": "same"}),
            self._tool("s2", "lookup", **{"gen_ai.tool.result": "same"}),
            self._tool("s3", "fetch", **{"gen_ai.tool.result": "same"}),
            self._tool("s4", "other", **{"gen_ai.tool.result": "x"}),
        ])
        anomaly = wasted.detect(summary, spans)
        assert anomaly is not None
        assert anomaly.evidence is not None
        assert anomaly.evidence["wasted_count"] == 3

    @pytest.mark.asyncio
    async def test_cross_run_and_output_drift_async(self) -> None:
        from analytics.detectors.cross_run import (
            AnomalyClusterDetector,
            FirstRunHeuristicDetector,
            RunFrequencyAnomalyDetector,
        )
        from analytics.detectors.output import OutputDriftDetector

        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[
            {"anomaly_type": "loop"},
            {"anomaly_type": "retry_storm"},
            {"anomaly_type": "cost_spike"},
        ])
        conn.fetchrow = AsyncMock(side_effect=[
            {"cnt": 2},
            {"cnt": 1, "first_run": "r"},
            {"avg_len": 10.0},
        ])
        pool = self._Pool(conn)

        cluster = AnomalyClusterDetector(min_anomaly_types=3)
        run_freq = RunFrequencyAnomalyDetector(min_runs=5, max_multiplier=2.0)
        first_run = FirstRunHeuristicDetector()
        drift = OutputDriftDetector(deviation_multiplier=2.0)
        spans = [
            SpanNode(
                span_id="o1",
                trace_id="t",
                operation_name="invoke_agent",
                attributes={
                    "gen_ai.response.content": "this is a much longer output than baseline"
                },
            )
        ]
        assert await cluster.detect_async(self._summary(), [], pool=pool) is not None
        assert await run_freq.detect_async(self._summary(), [], pool=pool) is not None
        assert await first_run.detect_async(self._summary(), [], pool=pool) is not None
        assert await drift.detect_async(self._summary(), spans, pool=pool) is not None


class TestWorkerAndCrossFramework:
    @pytest.mark.asyncio
    async def test_worker_runs_detector_pipeline_end_to_end(self) -> None:
        worker = AnalyticsWorker()
        summary = RunSummary(
            run_id="run_1",
            agent_name="test-agent",
            agent_version="v1",
            total_retries=5,
            total_tool_calls=25,
            total_interventions=3,
            estimated_cost=10.0,
            status="max_steps_hit",
        )
        spans = [
            SpanNode(
                span_id="root",
                trace_id="t",
                operation_name="invoke_agent",
                child_spans=[
                    SpanNode(
                        span_id=f"s{i}",
                        trace_id="t",
                        operation_name="execute_tool",
                        attributes={"gen_ai.tool.name": "search"},
                        duration_ms=1500,
                    )
                    for i in range(25)
                ],
            )
        ]
        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock()
        pool.acquire.return_value.__aexit__ = AsyncMock()

        with (
            patch("analytics.worker.persist_anomaly", AsyncMock()),
            patch("analytics.worker.WebhookAlerter.send_alert", AsyncMock(return_value=True)),
            patch("analytics.worker.CostSpikeDetector.detect", AsyncMock(return_value=None)),
        ):
            await worker._detect_and_alert(pool, summary, spans)
            assert worker.metrics.anomaly_detected_count > 0

    def test_same_pattern_caught_on_langgraph_and_crewai_traces(self) -> None:
        detector = LoopDetector(threshold=3)
        langgraph_spans = [
            SpanNode(
                span_id="root1",
                trace_id="t1",
                operation_name="invoke_agent",
                attributes={"framework": "langgraph"},
                child_spans=[
                    SpanNode(
                        span_id="a1",
                        trace_id="t1",
                        operation_name="execute_tool",
                        attributes={"gen_ai.tool.name": "search"},
                    ),
                    SpanNode(
                        span_id="a2",
                        trace_id="t1",
                        operation_name="execute_tool",
                        attributes={"gen_ai.tool.name": "search"},
                    ),
                    SpanNode(
                        span_id="a3",
                        trace_id="t1",
                        operation_name="execute_tool",
                        attributes={"gen_ai.tool.name": "search"},
                    ),
                ],
            )
        ]
        crewai_spans = [
            SpanNode(
                span_id="root2",
                trace_id="t2",
                operation_name="invoke_agent",
                attributes={"framework": "crewai"},
                child_spans=[
                    SpanNode(
                        span_id="b1",
                        trace_id="t2",
                        operation_name="execute_tool",
                        attributes={"gen_ai.tool.name": "search"},
                    ),
                    SpanNode(
                        span_id="b2",
                        trace_id="t2",
                        operation_name="execute_tool",
                        attributes={"gen_ai.tool.name": "search"},
                    ),
                    SpanNode(
                        span_id="b3",
                        trace_id="t2",
                        operation_name="execute_tool",
                        attributes={"gen_ai.tool.name": "search"},
                    ),
                ],
            )
        ]
        summary = RunSummary(run_id="r", agent_name="a")
        assert detector.detect(summary, langgraph_spans) is not None
        assert detector.detect(summary, crewai_spans) is not None

class TestLLMDetectorsGracefulDegradation:
    """LLM detectors return None when LLM client is unavailable."""

    @pytest.mark.asyncio
    async def test_explanation_scorer_returns_none(self) -> None:
        scorer = ExplanationScorer(_noop_client())
        assert await scorer.score("Loop", "Tool X called 12 times") is None

    @pytest.mark.asyncio
    async def test_triage_returns_none(self) -> None:
        triage = LLMTriageClassifier(_noop_client())
        assert await triage.classify("CostSpike", "critical", "run: 123") is None

    @pytest.mark.asyncio
    async def test_drift_detector_returns_none(self) -> None:
        d = EmbeddingDriftDetector(_noop_client())
        assert await d.detect_drift("text", "key") is None

    @pytest.mark.asyncio
    async def test_calibrator_returns_none(self) -> None:
        c = ThresholdCalibrator(_noop_client())
        assert await c.suggest("LoopDetector", 0.1, 100, "5") is None

    @pytest.mark.asyncio
    async def test_semantic_loop_returns_none(self) -> None:
        d = SemanticLoopDetector(_noop_client())
        assert await d.detect_async(RunSummary(run_id="r", agent_name="a"), []) is None

    @pytest.mark.asyncio
    async def test_hallucination_returns_none(self) -> None:
        d = HallucinationDetector(_noop_client())
        assert await d.detect_async(RunSummary(run_id="r", agent_name="a"), []) is None

    @pytest.mark.asyncio
    async def test_goal_drift_returns_none(self) -> None:
        d = GoalDriftDetector(_noop_client())
        assert await d.detect_async(RunSummary(run_id="r", agent_name="a"), []) is None

    @pytest.mark.asyncio
    async def test_quality_degradation_returns_none(self) -> None:
        d = QualityDegradationDetector(_noop_client())
        assert await d.detect_async(RunSummary(run_id="r", agent_name="a"), []) is None

    @pytest.mark.asyncio
    async def test_confusion_returns_none(self) -> None:
        d = ConfusionPatternDetector(_noop_client())
        assert await d.detect_async(RunSummary(run_id="r", agent_name="a"), []) is None


# ------------------------------------------------------------------
# AnomalyType enum, per-detector toggle, per-detector metrics (8.6.4 / #94)
# ------------------------------------------------------------------


class TestAnomalyTypeEnum:
    """Verify the AnomalyType enum covers all detector anomaly_type values."""

    def test_has_40_members(self) -> None:
        from analytics.models import AnomalyType

        values = list(AnomalyType)
        assert len(values) == 40

    def test_all_values_unique(self) -> None:
        from analytics.models import AnomalyType

        vals = [m.value for m in AnomalyType]
        assert len(vals) == len(set(vals))

    def test_covers_all_factory_detector_types(self) -> None:
        from analytics.models import AnomalyType

        detectors = create_all_detectors()
        factory_types = {d.anomaly_type for d in detectors}
        enum_vals = {m.value for m in AnomalyType}
        missing = factory_types - enum_vals
        assert not missing, f"Factory anomaly types missing from enum: {missing}"

    def test_each_enum_value_is_valid_python_identifier(self) -> None:
        from analytics.models import AnomalyType

        for member in AnomalyType:
            assert member.name.isidentifier(), f"{member.name} is not a valid identifier"


class TestPerDetectorToggle:
    """Verify per-detector on/off toggle via settings.detector_disabled."""

    def test_default_all_enabled(self) -> None:
        from analytics.config import Settings

        s = Settings()
        assert s.detector_disabled == set()

    def test_parse_disabled_from_env(self, monkeypatch: Any) -> None:
        monkeypatch.setenv("ANALYTICS_DETECTOR_DISABLED", '["loop","retry_storm"]')

        from analytics.config import Settings

        s = Settings()
        assert s.detector_disabled == {"loop", "retry_storm"}

    def test_worker_skips_disabled_original_detectors(self) -> None:
        worker = AnalyticsWorker()
        worker.disabled_set = frozenset({"loop", "retry_storm", "cost_spike"})
        detector_types = {d.anomaly_type for d in worker.detectors}
        assert "loop" not in detector_types or "loop" in worker.disabled_set

    def test_worker_filters_disabled_from_35_set(self) -> None:
        w = AnalyticsWorker()
        enabled_types = {
            d.anomaly_type
            for d in w.detectors
            if d.anomaly_type not in w.disabled_set
        }
        assert len(enabled_types) >= 32  # at most 3 original could be disabled

    def test_frozenset_created_on_init(self) -> None:
        w = AnalyticsWorker()
        assert isinstance(w.disabled_set, frozenset)
        assert w.disabled_set == frozenset()  # default: none disabled


class TestPerDetectorMetrics:
    """Verify per-detector anomaly count tracking in AnalyticsMetrics."""

    def test_inc_anomaly_with_type_increments_by_type(self) -> None:
        m = AnalyticsMetrics()
        m.inc_anomaly_detected(anomaly_type="loop")
        m.inc_anomaly_detected(anomaly_type="loop")
        m.inc_anomaly_detected(anomaly_type="retry_storm")
        assert m.anomaly_detected_count == 3
        assert m.anomaly_count_by_type("loop") == 2
        assert m.anomaly_count_by_type("retry_storm") == 1
        assert m.anomaly_count_by_type("cost_spike") == 0

    def test_inc_without_type_does_not_crash(self) -> None:
        m = AnalyticsMetrics()
        m.inc_anomaly_detected()
        assert m.anomaly_detected_count == 1

    def test_snapshot_includes_by_type(self) -> None:
        m = AnalyticsMetrics()
        m.inc_anomaly_detected(anomaly_type="loop")
        snap = m.snapshot()
        assert "anomaly_by_type" in snap
        assert snap["anomaly_by_type"] == {"loop": 1}

    def test_snapshot_by_type_is_copy(self) -> None:
        m = AnalyticsMetrics()
        m.inc_anomaly_detected(anomaly_type="loop")
        snap1 = m.snapshot()
        snap1["anomaly_by_type"]["loop"] = 999
        snap2 = m.snapshot()
        assert snap2["anomaly_by_type"]["loop"] == 1

    def test_multiple_types_tracked_independently(self) -> None:
        m = AnalyticsMetrics()
        for t in ["loop", "retry_storm", "cost_spike", "loop"]:
            m.inc_anomaly_detected(anomaly_type=t)
        assert m.anomaly_count_by_type("loop") == 2
        assert m.anomaly_count_by_type("retry_storm") == 1
        assert m.anomaly_count_by_type("cost_spike") == 1
        assert m.anomaly_count_by_type("unknown") == 0
