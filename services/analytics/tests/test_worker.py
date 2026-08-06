"""Tests for the AnalyticsWorker — the core polling and processing loop.

Covers __init__, run, _process_cycle, process_trace, process_traces_in_range,
rebuild_all, shutdown, and edge cases (no traces, DB/Jaeger unavailable,
empty spans, auto-discovery, disabled detectors, metrics snapshots).
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from analytics.metrics import AnalyticsMetrics
from analytics.models import Anomaly, RunSummary, SpanNode
from analytics.worker import AnalyticsWorker


def _make_pool(extra_methods: dict | None = None) -> MagicMock:
    """Build a mock asyncpg pool that supports ``acquire`` async context manager."""
    pool = MagicMock()
    pool.acquire = MagicMock()
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=0)
    conn.execute = AsyncMock()
    if extra_methods:
        for name, val in extra_methods.items():
            setattr(conn, name, val)
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    return pool


def _make_trace_data(
    trace_id: str = "t1",
    span_id: str = "s1",
    agent_name: str = "test-agent",
    run_id: str = "run_1",
    operation: str = "invoke_agent",
    extra_tags: list[dict] | None = None,
    extra_spans: list[dict] | None = None,
) -> dict:
    """Build a minimal Jaeger-style trace dict for tests."""
    tags = [
        {"key": "gen_ai.agent.name", "value": agent_name},
        {"key": "gen_ai.agent.run.id", "value": run_id},
    ]
    if extra_tags:
        tags.extend(extra_tags)
    spans = [
        {
            "spanID": span_id,
            "traceID": trace_id,
            "operationName": operation,
            "startTime": 1_000_000_000_000,
            "duration": 1000,
            "tags": tags,
            "references": [],
        }
    ]
    if extra_spans:
        spans.extend(extra_spans)
    return {"traceID": trace_id, "spans": spans}


class TestWorkerInit:
    """Verify AnalyticsWorker.__init__ populates all fields correctly."""

    def test_default_init_populates_all_components(self) -> None:
        w = AnalyticsWorker()
        assert w.fetcher is not None
        assert w.parser is not None
        assert w.builder is not None
        assert w.metrics is not None
        assert isinstance(w.metrics, AnalyticsMetrics)
        assert w.loop_detector is not None
        assert w.retry_detector is not None
        assert w.cost_detector is not None
        assert w.detectors is not None
        assert len(w.detectors) == 35
        assert w.fleet_materializer is not None
        assert w.cohort_materializer is not None
        assert w.alerter is not None
        assert w._running is False

    def test_disabled_set_is_frozenset(self) -> None:
        w = AnalyticsWorker()
        assert isinstance(w.disabled_set, frozenset)
        assert w.disabled_set == frozenset()

    def test_detectors_have_unique_types(self) -> None:
        w = AnalyticsWorker()
        types = [d.anomaly_type for d in w.detectors]
        assert len(types) == len(set(types))


class TestWorkerRunLoop:
    """Tests for the run() polling loop."""

    @pytest.mark.asyncio
    async def test_run_loops_until_shutdown(self) -> None:
        w = AnalyticsWorker()
        cycle_count = 0

        async def counting_cycle() -> None:
            nonlocal cycle_count
            cycle_count += 1
            if cycle_count >= 3:
                w._running = False

        w._process_cycle = counting_cycle  # type: ignore[method-assign]
        with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
            await w.run()
            assert cycle_count == 3
            assert mock_sleep.call_count == 3

    @pytest.mark.asyncio
    async def test_run_continues_on_cycle_error(self) -> None:
        w = AnalyticsWorker()
        exc_cycles = [False]

        async def failing_then_ok() -> None:
            if not exc_cycles[0]:
                exc_cycles[0] = True
                raise RuntimeError("transient failure")
            w._running = False

        w._process_cycle = failing_then_ok  # type: ignore[method-assign]
        with patch("asyncio.sleep", AsyncMock()):
            await w.run()
            assert w.metrics.failed_run_count == 1

    @pytest.mark.asyncio
    async def test_run_handles_cancellation(self) -> None:
        w = AnalyticsWorker()

        async def cancelled_cycle() -> None:
            import asyncio
            raise asyncio.CancelledError()

        w._process_cycle = cancelled_cycle  # type: ignore[method-assign]
        with patch("asyncio.sleep", AsyncMock()):
            await w.run()


class TestProcessCycle:
    """Tests for _process_cycle — the main per-cycle ingestion logic."""

    @pytest.mark.asyncio
    async def test_empty_traces(self) -> None:
        w = AnalyticsWorker()
        w.fetcher.fetch_traces_by_service = AsyncMock(return_value=[])  # type: ignore[method-assign]
        pool = _make_pool()
        with (
            patch("analytics.worker.get_pool", return_value=pool),
            patch.object(w.fleet_materializer, "materialize_fleet_rollups", AsyncMock()),
            patch.object(w.cohort_materializer, "materialize_version_cohorts", AsyncMock()),
        ):
            await w._process_cycle()
            assert w.metrics.processed_run_count == 0

    @pytest.mark.asyncio
    async def test_single_trace_full_pipeline(self) -> None:
        w = AnalyticsWorker()
        w.fetcher.fetch_traces_by_service = AsyncMock(return_value=[_make_trace_data()])  # type: ignore[method-assign]
        pool = _make_pool()
        with (
            patch("analytics.worker.get_pool", return_value=pool),
            patch("analytics.worker.is_run_processed", AsyncMock(return_value=False)),
            patch("analytics.worker.persist_run_summary", AsyncMock()),
            patch("analytics.worker.persist_anomaly", AsyncMock()),
            patch.object(w.alerter, "send_alert", AsyncMock(return_value=True)),
            patch.object(w.fleet_materializer, "materialize_fleet_rollups", AsyncMock()),
            patch.object(w.cohort_materializer, "materialize_version_cohorts", AsyncMock()),
        ):
            await w._process_cycle()
            assert w.metrics.processed_run_count == 1

    @pytest.mark.asyncio
    async def test_duplicate_skip(self) -> None:
        w = AnalyticsWorker()
        w.fetcher.fetch_traces_by_service = AsyncMock(return_value=[_make_trace_data()])  # type: ignore[method-assign]
        pool = _make_pool()
        with (
            patch("analytics.worker.get_pool", return_value=pool),
            patch("analytics.worker.is_run_processed", AsyncMock(return_value=True)),
            patch.object(w.fleet_materializer, "materialize_fleet_rollups", AsyncMock()),
            patch.object(w.cohort_materializer, "materialize_version_cohorts", AsyncMock()),
        ):
            await w._process_cycle()
            assert w.metrics.duplicate_skip_count == 1

    @pytest.mark.asyncio
    async def test_no_trace_id_skipped(self) -> None:
        w = AnalyticsWorker()
        w.fetcher.fetch_traces_by_service = AsyncMock(return_value=[{"spans": []}])  # type: ignore[method-assign]
        pool = _make_pool()
        with (
            patch("analytics.worker.get_pool", return_value=pool),
            patch.object(w.fleet_materializer, "materialize_fleet_rollups", AsyncMock()),
            patch.object(w.cohort_materializer, "materialize_version_cohorts", AsyncMock()),
        ):
            await w._process_cycle()
            assert w.metrics.processed_run_count == 0

    @pytest.mark.asyncio
    async def test_empty_spans_skipped(self) -> None:
        w = AnalyticsWorker()
        w.fetcher.fetch_traces_by_service = AsyncMock(return_value=[{"traceID": "t1", "spans": []}])  # type: ignore[method-assign]
        pool = _make_pool()
        with (
            patch("analytics.worker.get_pool", return_value=pool),
            patch.object(w.fleet_materializer, "materialize_fleet_rollups", AsyncMock()),
            patch.object(w.cohort_materializer, "materialize_version_cohorts", AsyncMock()),
        ):
            await w._process_cycle()
            assert w.metrics.processed_run_count == 0

    @pytest.mark.asyncio
    async def test_jaeger_unavailable_continues_loop(self) -> None:
        w = AnalyticsWorker()
        w.fetcher.fetch_traces_by_service = AsyncMock(side_effect=RuntimeError("jaeger down"))  # type: ignore[method-assign]
        pool = _make_pool()
        with (
            patch("analytics.worker.get_pool", return_value=pool),
            patch.object(w.fleet_materializer, "materialize_fleet_rollups", AsyncMock()),
            patch.object(w.cohort_materializer, "materialize_version_cohorts", AsyncMock()),
        ):
            with pytest.raises(RuntimeError, match="jaeger down"):
                await w._process_cycle()
            assert w.metrics.processed_run_count == 0

    @pytest.mark.asyncio
    async def test_auto_discovery_star_service(self) -> None:
        w = AnalyticsWorker()
        w.fetcher.list_services = AsyncMock(return_value=["svc-a", "svc-b", "jaeger-all-in-one"])  # type: ignore[method-assign]
        w.fetcher.fetch_traces_by_service = AsyncMock(return_value=[])  # type: ignore[method-assign]
        pool = _make_pool()
        with (
            patch("analytics.worker.get_pool", return_value=pool),
            patch("analytics.worker.settings", trace_query_services=("*",)),
            patch.object(w.fleet_materializer, "materialize_fleet_rollups", AsyncMock()),
            patch.object(w.cohort_materializer, "materialize_version_cohorts", AsyncMock()),
        ):
            await w._process_cycle()
            assert w.fetcher.list_services.called
            assert w.fetcher.fetch_traces_by_service.call_count == 2

    @pytest.mark.asyncio
    async def test_auto_discovery_falls_back_on_failure(self) -> None:
        w = AnalyticsWorker()
        w.fetcher.list_services = AsyncMock(side_effect=RuntimeError("jaeger down"))  # type: ignore[method-assign]
        w.fetcher.fetch_traces_by_service = AsyncMock(return_value=[])  # type: ignore[method-assign]
        pool = _make_pool()
        with (
            patch("analytics.worker.get_pool", return_value=pool),
            patch("analytics.worker.settings", trace_query_services=("*",)),
            patch.object(w.fleet_materializer, "materialize_fleet_rollups", AsyncMock()),
            patch.object(w.cohort_materializer, "materialize_version_cohorts", AsyncMock()),
        ):
            await w._process_cycle()
            w.fetcher.fetch_traces_by_service.assert_called_with(service="demo-agent", limit=50)

    @pytest.mark.asyncio
    async def test_materializers_called_even_with_no_traces(self) -> None:
        w = AnalyticsWorker()
        w.fetcher.fetch_traces_by_service = AsyncMock(return_value=[])  # type: ignore[method-assign]
        pool = _make_pool()
        fleet_mock = AsyncMock()
        cohort_mock = AsyncMock()
        with (
            patch("analytics.worker.get_pool", return_value=pool),
            patch.object(w, "fleet_materializer") as fm,
            patch.object(w, "cohort_materializer") as cm,
        ):
            fm.materialize_fleet_rollups = fleet_mock
            cm.materialize_version_cohorts = cohort_mock
            await w._process_cycle()
            fleet_mock.assert_called_once()
            cohort_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_metrics_read_model_freshness_updated(self) -> None:
        w = AnalyticsWorker()
        w.fetcher.fetch_traces_by_service = AsyncMock(return_value=[_make_trace_data()])  # type: ignore[method-assign]
        pool = _make_pool()
        with (
            patch("analytics.worker.get_pool", return_value=pool),
            patch("analytics.worker.is_run_processed", AsyncMock(return_value=False)),
            patch("analytics.worker.persist_run_summary", AsyncMock()),
            patch("analytics.worker.persist_anomaly", AsyncMock()),
            patch.object(w.alerter, "send_alert", AsyncMock(return_value=True)),
            patch.object(w.fleet_materializer, "materialize_fleet_rollups", AsyncMock()),
            patch.object(w.cohort_materializer, "materialize_version_cohorts", AsyncMock()),
        ):
            assert w.metrics.read_model_freshness is None
            await w._process_cycle()
            assert w.metrics.read_model_freshness is not None


class TestProcessTrace:
    """Tests for process_trace — the ad-hoc single-trace reprocessing path."""

    @pytest.mark.asyncio
    async def test_not_found_returns_false(self) -> None:
        w = AnalyticsWorker()
        w.fetcher.fetch_trace_by_id = AsyncMock(return_value=None)  # type: ignore[method-assign]
        result = await w.process_trace("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_empty_spans_returns_false(self) -> None:
        w = AnalyticsWorker()
        w.fetcher.fetch_trace_by_id = AsyncMock(return_value={"traceID": "t1", "spans": []})  # type: ignore[method-assign]
        pool = _make_pool()
        with patch("analytics.worker.get_pool", return_value=pool):
            result = await w.process_trace("t1")
            assert result is False

    @pytest.mark.asyncio
    async def test_successful_process_returns_true(self) -> None:
        w = AnalyticsWorker()
        w.fetcher.fetch_trace_by_id = AsyncMock(return_value=_make_trace_data())  # type: ignore[method-assign]
        pool = _make_pool()
        with (
            patch("analytics.worker.get_pool", return_value=pool),
            patch("analytics.worker.persist_run_summary", AsyncMock()),
            patch("analytics.worker.persist_anomaly", AsyncMock()),
            patch.object(w.alerter, "send_alert", AsyncMock(return_value=True)),
        ):
            result = await w.process_trace("t1")
            assert result is True

    @pytest.mark.asyncio
    async def test_reprocess_increments_replay_rebuild(self) -> None:
        w = AnalyticsWorker()
        w.fetcher.fetch_trace_by_id = AsyncMock(return_value=_make_trace_data())  # type: ignore[method-assign]
        pool = _make_pool()
        with (
            patch("analytics.worker.get_pool", return_value=pool),
            patch("analytics.worker.persist_run_summary", AsyncMock()),
            patch("analytics.worker.persist_anomaly", AsyncMock()),
            patch.object(w.alerter, "send_alert", AsyncMock(return_value=True)),
        ):
            await w.process_trace("t1")
            assert w.metrics.replay_rebuild_count == 1

    @pytest.mark.asyncio
    async def test_summary_none_returns_false(self) -> None:
        w = AnalyticsWorker()
        trace = {"traceID": "t1", "spans": []}
        w.fetcher.fetch_trace_by_id = AsyncMock(return_value=trace)  # type: ignore[method-assign]
        pool = _make_pool()
        with patch("analytics.worker.get_pool", return_value=pool):
            result = await w.process_trace("t1")
            assert result is False

    @pytest.mark.asyncio
    async def test_always_reprocesses_duplicates(self) -> None:
        w = AnalyticsWorker()
        w.fetcher.fetch_trace_by_id = AsyncMock(return_value=_make_trace_data())  # type: ignore[method-assign]
        pool = _make_pool()
        with (
            patch("analytics.worker.get_pool", return_value=pool),
            patch("analytics.worker.persist_run_summary", AsyncMock()),
            patch("analytics.worker.persist_anomaly", AsyncMock()),
            patch.object(w.alerter, "send_alert", AsyncMock(return_value=True)),
        ):
            await w.process_trace("t1")
            assert w.metrics.processed_run_count == 1
            await w.process_trace("t1")
            assert w.metrics.processed_run_count == 2


class TestProcessTracesInRange:
    """Tests for process_traces_in_range — time-window reprocessing."""

    @pytest.mark.asyncio
    async def test_no_traces_returns_zero(self) -> None:
        w = AnalyticsWorker()
        w.fetcher.fetch_traces_by_service = AsyncMock(return_value=[])  # type: ignore[method-assign]
        now = datetime.now(timezone.utc)
        count = await w.process_traces_in_range(now, now)
        assert count == 0

    @pytest.mark.asyncio
    async def test_processes_traces_returns_count(self) -> None:
        w = AnalyticsWorker()
        w.fetcher.fetch_traces_by_service = AsyncMock(return_value=[_make_trace_data(), _make_trace_data(trace_id="t2", span_id="s2", run_id="run_2")])  # type: ignore[method-assign]
        w.fetcher.fetch_trace_by_id = AsyncMock(return_value=_make_trace_data())  # type: ignore[method-assign]
        pool = _make_pool()
        now = datetime.now(timezone.utc)
        with (
            patch("analytics.worker.get_pool", return_value=pool),
            patch("analytics.worker.persist_run_summary", AsyncMock()),
            patch("analytics.worker.persist_anomaly", AsyncMock()),
            patch.object(w.alerter, "send_alert", AsyncMock(return_value=True)),
        ):
            count = await w.process_traces_in_range(now, now)
            assert count == 2

    @pytest.mark.asyncio
    async def test_skips_traces_without_trace_id(self) -> None:
        w = AnalyticsWorker()
        w.fetcher.fetch_traces_by_service = AsyncMock(return_value=[{"spans": []}, _make_trace_data()])  # type: ignore[method-assign]
        w.fetcher.fetch_trace_by_id = AsyncMock(return_value=_make_trace_data())  # type: ignore[method-assign]
        pool = _make_pool()
        now = datetime.now(timezone.utc)
        with (
            patch("analytics.worker.get_pool", return_value=pool),
            patch("analytics.worker.persist_run_summary", AsyncMock()),
            patch("analytics.worker.persist_anomaly", AsyncMock()),
            patch.object(w.alerter, "send_alert", AsyncMock(return_value=True)),
        ):
            count = await w.process_traces_in_range(now, now)
            assert count == 1

    @pytest.mark.asyncio
    async def test_uses_configured_services(self) -> None:
        w = AnalyticsWorker()
        w.fetcher.fetch_traces_by_service = AsyncMock(return_value=[])  # type: ignore[method-assign]
        now = datetime.now(timezone.utc)
        with patch("analytics.worker.settings", trace_query_services=("svc-a", "svc-b")):
            await w.process_traces_in_range(now, now)
            assert w.fetcher.fetch_traces_by_service.call_count == 2


class TestRebuildAll:
    """Tests for rebuild_all — full re-ingestion of stored traces."""

    @pytest.mark.asyncio
    async def test_no_stored_traces_returns_zero(self) -> None:
        w = AnalyticsWorker()
        pool = _make_pool()
        pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(return_value=[])  # type: ignore[method-assign]
        with patch("analytics.worker.get_pool", return_value=pool):
            count = await w.rebuild_all()
            assert count == 0

    @pytest.mark.asyncio
    async def test_processes_stored_trace_ids(self) -> None:
        w = AnalyticsWorker()
        pool = _make_pool()
        pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(  # type: ignore[method-assign]
            return_value=[{"trace_id": "t1"}, {"trace_id": "t2"}]
        )
        w.fetcher.fetch_trace_by_id = AsyncMock(return_value=_make_trace_data())  # type: ignore[method-assign]
        with (
            patch("analytics.worker.get_pool", return_value=pool),
            patch("analytics.worker.persist_run_summary", AsyncMock()),
            patch("analytics.worker.persist_anomaly", AsyncMock()),
            patch.object(w.alerter, "send_alert", AsyncMock(return_value=True)),
        ):
            count = await w.rebuild_all()
            assert count == 2

    @pytest.mark.asyncio
    async def test_continues_on_individual_failure(self) -> None:
        w = AnalyticsWorker()
        pool = _make_pool()
        pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(  # type: ignore[method-assign]
            return_value=[{"trace_id": "t1"}, {"trace_id": "t2"}]
        )
        w.fetcher.fetch_trace_by_id = AsyncMock(side_effect=[RuntimeError("fail"), _make_trace_data()])  # type: ignore[method-assign]
        with (
            patch("analytics.worker.get_pool", return_value=pool),
            patch("analytics.worker.persist_run_summary", AsyncMock()),
            patch("analytics.worker.persist_anomaly", AsyncMock()),
            patch.object(w.alerter, "send_alert", AsyncMock(return_value=True)),
        ):
            count = await w.rebuild_all()
            assert count == 1
            assert w.metrics.failed_run_count == 1

    @pytest.mark.asyncio
    async def test_skips_null_trace_ids(self) -> None:
        w = AnalyticsWorker()
        pool = _make_pool()
        pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(  # type: ignore[method-assign]
            return_value=[{"trace_id": None}, {"trace_id": "t2"}]
        )
        async def fetch_by_id(trace_id: str) -> dict | None:
            if trace_id is None or trace_id == "":
                return None
            return _make_trace_data(trace_id=trace_id)
        w.fetcher.fetch_trace_by_id = AsyncMock(side_effect=fetch_by_id)  # type: ignore[method-assign]
        with (
            patch("analytics.worker.get_pool", return_value=pool),
            patch("analytics.worker.persist_run_summary", AsyncMock()),
            patch("analytics.worker.persist_anomaly", AsyncMock()),
            patch.object(w.alerter, "send_alert", AsyncMock(return_value=True)),
        ):
            count = await w.rebuild_all()
            assert count == 1


class TestShutdown:
    """Tests for shutdown — graceful worker stop."""

    @pytest.mark.asyncio
    async def test_shutdown_sets_running_false(self) -> None:
        w = AnalyticsWorker()
        w._running = True
        await w.shutdown()
        assert w._running is False

    def test_shutdown_does_not_raise_on_already_stopped(self) -> None:
        w = AnalyticsWorker()
        assert w._running is False


class TestDetectAndAlert:
    """Tests for _detect_and_alert — anomaly detection and alert dispatch."""

    def _summary(self, **kwargs: object) -> RunSummary:
        defaults: dict = {"run_id": "run_1", "agent_name": "test-agent"}
        defaults.update(kwargs)  # type: ignore[arg-type]
        return RunSummary(**defaults)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_detects_and_alerts(self) -> None:
        w = AnalyticsWorker()
        summary = self._summary(total_retries=5)
        spans: list[SpanNode] = []
        pool = _make_pool()
        with (
            patch("analytics.worker.persist_anomaly", AsyncMock()),
            patch.object(w.alerter, "send_alert", AsyncMock(return_value=True)),
            patch("analytics.worker.CostSpikeDetector.detect", AsyncMock(return_value=None)),
        ):
            await w._detect_and_alert(pool, summary, spans)
            assert w.metrics.anomaly_detected_count > 0

    @pytest.mark.asyncio
    async def test_persist_failure_does_not_crash(self) -> None:
        w = AnalyticsWorker()
        summary = self._summary(total_retries=5)
        spans: list[SpanNode] = []
        pool = _make_pool()
        with (
            patch("analytics.worker.persist_anomaly", AsyncMock(side_effect=RuntimeError("db down"))),
            patch.object(w.alerter, "send_alert", AsyncMock(return_value=True)),
            patch("analytics.worker.CostSpikeDetector.detect", AsyncMock(return_value=None)),
        ):
            await w._detect_and_alert(pool, summary, spans)

    @pytest.mark.asyncio
    async def test_alert_failure_does_not_crash(self) -> None:
        w = AnalyticsWorker()
        summary = self._summary(total_retries=5)
        spans: list[SpanNode] = []
        pool = _make_pool()
        with (
            patch("analytics.worker.persist_anomaly", AsyncMock()),
            patch.object(w.alerter, "send_alert", AsyncMock(side_effect=RuntimeError("webhook down"))),
            patch("analytics.worker.CostSpikeDetector.detect", AsyncMock(return_value=None)),
        ):
            await w._detect_and_alert(pool, summary, spans)

    @pytest.mark.asyncio
    async def test_disabled_detectors_skipped(self) -> None:
        w = AnalyticsWorker()
        w.disabled_set = frozenset({"loop", "retry_storm"})
        summary = self._summary(total_retries=5)
        spans: list[SpanNode] = []
        pool = _make_pool()
        with (
            patch("analytics.worker.persist_anomaly", AsyncMock()),
            patch.object(w.alerter, "send_alert", AsyncMock(return_value=True)),
            patch("analytics.worker.CostSpikeDetector.detect", AsyncMock(return_value=None)),
        ):
            await w._detect_and_alert(pool, summary, spans)
            assert w.metrics.anomaly_count_by_type("loop") == 0
            assert w.metrics.anomaly_count_by_type("retry_storm") == 0

    @pytest.mark.asyncio
    async def test_all_original_three_disabled(self) -> None:
        w = AnalyticsWorker()
        w.disabled_set = frozenset({"loop", "retry_storm", "cost_spike"})
        summary = self._summary(total_retries=5)
        spans: list[SpanNode] = []
        pool = _make_pool()
        with (
            patch("analytics.worker.persist_anomaly", AsyncMock()),
            patch.object(w.alerter, "send_alert", AsyncMock(return_value=True)),
        ):
            await w._detect_and_alert(pool, summary, spans)
            assert w.metrics.anomaly_count_by_type("loop") == 0
            assert w.metrics.anomaly_count_by_type("retry_storm") == 0
            assert w.metrics.anomaly_count_by_type("cost_spike") == 0

    @pytest.mark.asyncio
    async def test_detector_error_isolated(self) -> None:
        w = AnalyticsWorker()
        summary = self._summary()
        spans: list[SpanNode] = []
        pool = _make_pool()
        with (
            patch("analytics.worker.LoopDetector.detect", side_effect=RuntimeError("detector crash")),
            patch("analytics.worker.persist_anomaly", AsyncMock()),
            patch.object(w.alerter, "send_alert", AsyncMock(return_value=True)),
            patch("analytics.worker.CostSpikeDetector.detect", AsyncMock(return_value=None)),
        ):
            await w._detect_and_alert(pool, summary, spans)

    @pytest.mark.asyncio
    async def test_async_detectors_run_concurrently(self) -> None:
        import asyncio as aio_mod
        from analytics.detectors.base import BaseDetector as BD

        w = AnalyticsWorker()

        class AsyncTracker:
            running = 0
            max_running = 0

            async def detect_async(self, _summary, _spans, pool=None):
                self.running += 1
                self.max_running = max(self.max_running, self.running)
                await aio_mod.sleep(0.01)
                self.running -= 1
                return None

        tracker = AsyncTracker()
        for d in w.detectors:
            if getattr(type(d), "detect_async", None) is not BD.detect_async:
                continue
            d.detect = MagicMock()
            d.detect_async = tracker.detect_async  # type: ignore[method-assign]

        summary = self._summary()
        spans: list[SpanNode] = []
        pool = _make_pool()
        with (
            patch("analytics.worker.persist_anomaly", AsyncMock()),
            patch.object(w.alerter, "send_alert", AsyncMock(return_value=True)),
            patch("analytics.worker.CostSpikeDetector.detect", AsyncMock(return_value=None)),
        ):
            await w._detect_and_alert(pool, summary, spans)


class TestMetricsHealthSnapshot:
    """Tests for metrics counter behavior and snapshot."""

    def test_snapshot_contains_all_fields(self) -> None:
        m = AnalyticsMetrics()
        snap = m.snapshot()
        expected_keys = {
            "processed_run_count",
            "failed_run_count",
            "duplicate_skip_count",
            "replay_rebuild_count",
            "anomaly_detected_count",
            "anomaly_by_type",
            "read_model_freshness",
        }
        assert set(snap.keys()) == expected_keys

    def test_freshness_starts_none(self) -> None:
        m = AnalyticsMetrics()
        assert m.read_model_freshness is None

    def test_freshness_settable(self) -> None:
        m = AnalyticsMetrics()
        now = datetime.now(timezone.utc)
        m.read_model_freshness = now
        assert m.read_model_freshness == now

    def test_inc_anomaly_with_type(self) -> None:
        m = AnalyticsMetrics()
        m.inc_anomaly_detected(anomaly_type="loop")
        m.inc_anomaly_detected(anomaly_type="loop")
        m.inc_anomaly_detected(anomaly_type="retry_storm")
        assert m.anomaly_detected_count == 3
        assert m.anomaly_count_by_type("loop") == 2
        assert m.anomaly_count_by_type("retry_storm") == 1

    def test_snapshot_by_type_is_copy(self) -> None:
        m = AnalyticsMetrics()
        m.inc_anomaly_detected(anomaly_type="loop")
        snap = m.snapshot()
        snap["anomaly_by_type"]["loop"] = 999
        assert m.anomaly_count_by_type("loop") == 1

    def test_log_summary_does_not_raise(self) -> None:
        m = AnalyticsMetrics()
        m.inc_processed(5)
        m.inc_failed(1)
        m.inc_anomaly_detected(anomaly_type="loop")
        m.log_summary()


