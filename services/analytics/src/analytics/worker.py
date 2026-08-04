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
from analytics.detectors import CostSpikeDetector, LoopDetector, RetryStormDetector
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
from analytics.models import RunSummary, SpanNode

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

        Three detectors run in sequence (loop, retry, cost).  Each anomaly found
        is persisted to the database and dispatched via the webhook alerter.
        """
        pool_any = pool
        spans_list = spans

        loop_anomaly = self.loop_detector.detect(summary, spans_list)
        if loop_anomaly:
            await persist_anomaly(pool_any, loop_anomaly)
            await self.alerter.send_alert(loop_anomaly)
            self.metrics.inc_anomaly_detected()

        retry_anomaly = self.retry_detector.detect(summary, spans_list)
        if retry_anomaly:
            await persist_anomaly(pool_any, retry_anomaly)
            await self.alerter.send_alert(retry_anomaly)
            self.metrics.inc_anomaly_detected()

        cost_anomaly = await self.cost_detector.detect(summary, spans_list, pool=pool_any)
        if cost_anomaly:
            await persist_anomaly(pool_any, cost_anomaly)
            await self.alerter.send_alert(cost_anomaly)
            self.metrics.inc_anomaly_detected()

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