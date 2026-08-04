"""Background worker that polls Jaeger, ingests traces, and detects anomalies.

The ``AnalyticsWorker`` is the core loop of the analytics service.  On each cycle it:

  1. Fetches recent traces from Jaeger via ``TraceFetcher``.
  2. Parses each trace into a span tree (``TraceParser``).
  3. Builds a run summary (``RunSummaryBuilder``).
  4. Skips already-processed runs (deduplication).
  5. Persists the summary and runs anomaly detection.
  6. Materializes fleet rollups and version cohorts after each cycle.

The worker also supports ad-hoc operations: ``process_trace`` for reprocessing a
single trace, ``rebuild_all`` for full re-ingestion, and ``process_traces_in_range``
for time-window reprocessing.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from analytics.alerts import WebhookAlerter
from analytics.config import settings
from analytics.db import get_pool
from analytics.detectors import create_all_detectors
from analytics.detectors.base import BaseDetector
from analytics.detectors.cost import CostSpikeDetector
from analytics.detectors.retry import RetryStormDetector
from analytics.detectors.tool import LoopDetector
from analytics.ingest import (
    RunSummaryBuilder,
    TraceFetcher,
    TraceParser,
    is_run_processed,
    persist_anomaly,
    persist_run_summary,
)
from analytics.materializer import FleetRollupMaterializer, VersionCohortMaterializer
from analytics.metrics import AnalyticsMetrics
from analytics.models import Anomaly, RunSummary, SpanNode

logger = logging.getLogger(__name__)


class AnalyticsWorker:
    """Continuous worker that polls Jaeger and processes traces.

    Usage::

        worker = AnalyticsWorker()
        await worker.run()      # forever loop
        # or
        await worker.process_trace("trace_id_here")
    """

    def __init__(self) -> None:
        self.fetcher = TraceFetcher()
        self.parser = TraceParser()
        self.builder = RunSummaryBuilder()
        self.metrics = AnalyticsMetrics()
        self.loop_detector = LoopDetector()
        self.retry_detector = RetryStormDetector()
        self.cost_detector = CostSpikeDetector()
        self.detectors: list[BaseDetector] = create_all_detectors()
        self.fleet_materializer = FleetRollupMaterializer()
        self.cohort_materializer = VersionCohortMaterializer()
        self.alerter = WebhookAlerter(webhook_url=settings.webhook_url)
        self._running = False

    async def run(self) -> None:
        """Main polling loop.  Runs until cancelled or interrupted.

        Polls Jaeger at ``settings.polling_interval_seconds`` intervals, processes
        new traces, detects anomalies, and materializes rollups.
        """
        self._running = True
        logger.info("Worker started (interval=%ds)", settings.polling_interval_seconds)

        while self._running:
            try:
                await self._process_cycle()
            except asyncio.CancelledError:
                logger.info("Worker cancelled, shutting down")
                break
            except Exception:
                logger.exception("Unhandled error in processing cycle")
                self.metrics.inc_failed()

            await asyncio.sleep(settings.polling_interval_seconds)

    async def _process_cycle(self) -> None:
        """Single processing cycle: fetch, parse, persist, detect, materialize."""
        pool = await get_pool()
        traces = await self.fetcher.fetch_traces_by_service(
            service=settings.trace_query_service, limit=50
        )

        for trace_data in traces:
            trace_id = trace_data.get("traceID", "")
            if not trace_id:
                continue

            root_spans = self.parser.parse_jaeger_trace(trace_data)
            if not root_spans:
                continue

            summary = self.builder.build_from_span_tree(root_spans, trace_id)
            if summary is None:
                continue

            run_id = summary.run_id

            if await is_run_processed(pool, run_id):
                self.metrics.inc_duplicate_skip()
                continue

            await persist_run_summary(pool, summary)
            self.metrics.inc_processed()
            self.metrics.read_model_freshness = datetime.now(timezone.utc)
            logger.info(
                "Processed run %s (agent=%s, status=%s)",
                run_id,
                summary.agent_name,
                summary.status,
            )

            await self._detect_and_alert(pool, summary, root_spans)

        await self.fleet_materializer.materialize_fleet_rollups(pool)
        await self.cohort_materializer.materialize_version_cohorts(pool)

    async def _detect_and_alert(
        self,
        pool: object,
        summary: RunSummary,
        spans: list[SpanNode],
    ) -> None:
        """Run all anomaly detectors against a summary and persist/alert on hits.

        Runs the original three detectors (loop, retry, cost) first for backward
        compatibility, then runs the full set of 35 detectors.  Anomalies found
        are persisted to the database and dispatched via the webhook alerter.
        """
        anomalies: list[Anomaly] = []

        # Original three detectors (backward compatible)
        try:
            loop_anomaly = self.loop_detector.detect(summary, spans)
            if loop_anomaly:
                anomalies.append(loop_anomaly)
        except Exception:
            logger.exception("LoopDetector failed for run %s", summary.run_id)

        try:
            retry_anomaly = self.retry_detector.detect(summary, spans)
            if retry_anomaly:
                anomalies.append(retry_anomaly)
        except Exception:
            logger.exception("RetryStormDetector failed for run %s", summary.run_id)

        try:
            cost_anomaly = await self.cost_detector.detect(summary, spans, pool=pool)
            if cost_anomaly:
                anomalies.append(cost_anomaly)
        except Exception:
            logger.exception("CostSpikeDetector failed for run %s", summary.run_id)

        # All 35 detectors (deduplicating the original three by type)
        async_tasks = []
        for detector in self.detectors:
            if isinstance(detector, (LoopDetector, RetryStormDetector, CostSpikeDetector)):
                continue
            if (
                hasattr(type(detector), "detect_async")
                and type(detector).detect_async is not BaseDetector.detect_async
            ):
                async_tasks.append(
                    self._run_async_detector(detector, summary, spans, pool, anomalies)
                )
            else:
                try:
                    result = detector.detect(summary, spans)
                    if result is not None:
                        anomalies.append(result)
                except Exception:
                    logger.exception(
                        "Detector %s failed for run %s",
                        detector.anomaly_type or type(detector).__name__,
                        summary.run_id,
                    )

        if async_tasks:
            await asyncio.gather(*async_tasks)

        for anomaly in anomalies:
            try:
                await persist_anomaly(pool, anomaly)
                await self.alerter.send_alert(anomaly)
                self.metrics.inc_anomaly_detected()
            except Exception:
                logger.exception(
                    "Failed to persist/alert anomaly %s for run %s",
                    anomaly.anomaly_type,
                    summary.run_id,
                )

    async def _run_async_detector(
        self,
        detector: BaseDetector,
        summary: RunSummary,
        spans: list[SpanNode],
        pool: object,
        anomalies: list[Anomaly],
    ) -> None:
        """Run a single async detector and collect results."""
        try:
            result = await detector.detect_async(summary, spans, pool=pool)
            if result is not None:
                anomalies.append(result)
        except Exception:
            logger.exception(
                "Async detector %s failed for run %s",
                detector.anomaly_type or type(detector).__name__,
                summary.run_id,
            )

    async def process_trace(self, trace_id: str) -> bool:
        """Reprocess a single trace by ID: fetch, parse, persist, detect.

        Args:
            trace_id: the Jaeger trace ID to process.

        Returns:
            True if the trace was found and processed, False otherwise.
        """
        raw = await self.fetcher.fetch_trace_by_id(trace_id)
        if raw is None:
            logger.warning("Trace %s not found", trace_id)
            return False

        pool = await get_pool()
        root_spans = self.parser.parse_jaeger_trace(raw)
        if not root_spans:
            logger.warning("No root spans for trace %s", trace_id)
            return False

        summary = self.builder.build_from_span_tree(root_spans, trace_id)
        if summary is None:
            return False

        await persist_run_summary(pool, summary)
        await self._detect_and_alert(pool, summary, root_spans)
        self.metrics.inc_processed()
        self.metrics.inc_replay_rebuild()
        self.metrics.read_model_freshness = datetime.now(timezone.utc)
        logger.info("Reprocessed trace %s (run=%s)", trace_id, summary.run_id)
        return True

    async def rebuild_all(self) -> int:
        """Reprocess every trace that has a stored run summary.

        Iterates all distinct trace IDs in the ``run_summaries`` table and
        re-fetches + re-processes each one.

        Returns:
            The number of traces successfully reprocessed.
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT DISTINCT trace_id FROM run_summaries WHERE trace_id IS NOT NULL"
            )

        count = 0
        for row in rows:
            trace_id = row["trace_id"]
            try:
                success = await self.process_trace(trace_id)
                if success:
                    count += 1
            except Exception:
                logger.exception("Failed to rebuild trace %s", trace_id)
                self.metrics.inc_failed()

        logger.info("Rebuild complete: %d traces reprocessed", count)
        return count

    async def shutdown(self) -> None:
        """Signal the worker loop to stop after the current cycle."""
        self._running = False

    async def process_traces_in_range(
        self, start: datetime, end: datetime
    ) -> int:
        """Reprocess all traces from Jaeger within a time range.

        Fetches traces from Jaeger (up to 200) and processes each one.  Note
        this does NOT filter by time on the Jaeger side -- it fetches recent
        traces and relies on the caller to have set an appropriate time window.

        Args:
            start: start of the time window (unused at the API level).
            end: end of the time window (unused at the API level).

        Returns:
            The number of traces successfully processed.
        """
        traces = await self.fetcher.fetch_traces_by_service(
            service=settings.trace_query_service, limit=200
        )
        count = 0
        for trace_data in traces:
            trace_id = trace_data.get("traceID", "")
            if not trace_id:
                continue
            success = await self.process_trace(trace_id)
            if success:
                count += 1
        return count