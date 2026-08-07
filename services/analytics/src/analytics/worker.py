"""Background worker that polls Jaeger, ingests traces, and detects anomalies.

The ``AnalyticsWorker`` is the core loop of the analytics service.  On each
cycle it:

  1. Fetches recent traces from Jaeger via ``TraceFetcher``.
  2. Parses each trace into a span tree (``TraceParser``).
  3. Builds a run summary (``RunSummaryBuilder``).
  4. Skips already-processed runs (deduplication via ``is_run_processed``).
  5. Persists the summary and runs anomaly detection (all 35 detectors).
  6. Materializes fleet rollups and version cohorts after each cycle.
  7. Dispatches anomalies via the webhook alerter.

The worker also supports ad-hoc operations: ``process_trace`` for reprocessing
a single trace, ``rebuild_all`` for full re-ingestion, and
``process_traces_in_range`` for time-window reprocessing.

**Design decisions:**

- **Two-pass detection**: The original three detectors (loop, retry, cost) run
  first for backward compatibility, then the full set of 35 detectors runs
  (skipping the three that already ran).  This ensures existing integrations
  continue to work while the new detectors add signal.
- **Async gather for async detectors**: Detectors that override ``detect_async``
  run concurrently via ``asyncio.gather``, reducing total detection latency.
  Sync detectors run sequentially in the main task.
- **Per-detector error isolation**: Each detector is wrapped in try/except so
  a single buggy detector cannot crash the entire detection pass.
- **Disabled detector toggling**: Detectors whose ``anomaly_type`` is in
  ``settings.detector_disabled`` are skipped entirely, both for the original
  three and the full set.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import cast

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

    The worker runs an infinite polling loop (controlled by an internal
    ``_running`` flag) that fetches recent traces, processes them through
    the full analytics pipeline (parse → summarize → detect → alert →
    materialize), and sleeps between cycles.

    Usage::

        worker = AnalyticsWorker()
        await worker.run()      # forever loop (until shutdown() or interrupt)
        # or:
        await worker.process_trace("trace_id_here")
    """

    def __init__(self) -> None:
        # Core pipeline components.
        self.fetcher = TraceFetcher()
        self.parser = TraceParser()
        self.builder = RunSummaryBuilder()
        self.metrics = AnalyticsMetrics()
        # Original three detectors (backward compat).
        self.loop_detector = LoopDetector()
        self.retry_detector = RetryStormDetector()
        self.cost_detector = CostSpikeDetector()
        # Full set of 35 detectors (created from the factory).
        self.detectors: list[BaseDetector] = create_all_detectors()
        # Frozen set for O(1) membership testing in disabled detector lookup.
        self.disabled_set: frozenset[str] = frozenset(settings.detector_disabled)
        # Materializers for post-cycle aggregation.
        self.fleet_materializer = FleetRollupMaterializer()
        self.cohort_materializer = VersionCohortMaterializer()
        # Alerter for webhook notifications.
        self.alerter = WebhookAlerter(webhook_url=settings.webhook_url)
        # Internal running flag, set by run() and cleared by shutdown().
        self._running = False

    async def run(self) -> None:
        """Main polling loop.  Runs until cancelled or interrupted.

        Polls Jaeger at ``settings.polling_interval_seconds`` intervals,
        processes new traces, detects anomalies, and materializes rollups.
        Each cycle is isolated: an exception in one cycle does not stop
        the loop.

        Raises:
            KeyboardInterrupt: if the process receives SIGINT (handled by
                the caller, not raised here — CancelledError is caught).
        """
        self._running = True
        logger.info("Worker started (interval=%ds)", settings.polling_interval_seconds)

        while self._running:
            try:
                await self._process_cycle()
            except asyncio.CancelledError:
                # Graceful shutdown: log and break out of the loop.
                logger.info("Worker cancelled, shutting down")
                break
            except Exception:
                # Any other exception is logged but the loop continues.
                # This prevents a transient error (e.g., Jaeger timeout)
                # from killing the worker permanently.
                logger.exception("Unhandled error in processing cycle")
                self.metrics.inc_failed()

            await asyncio.sleep(settings.polling_interval_seconds)

    async def _process_cycle(self) -> None:
        """Single processing cycle: fetch, parse, persist, detect, materialize.

        Fetches up to 50 traces per configured service from Jaeger, processing
        each one through the pipeline. When ``trace_query_services`` contains
        ``"*"``, it queries the Jaeger API for all available services and
        processes traces from every one.
        """
        pool = await get_pool()
        services = list(settings.trace_query_services)

        # If "*" is configured, discover all services from Jaeger.
        if "*" in services:
            try:
                all_services = await self.fetcher.list_services()
                services = [s for s in all_services if s not in ("jaeger-all-in-one",)]
                logger.info("Auto-discovered %d services: %s", len(services), services)
            except Exception:
                logger.warning("Failed to list services, falling back to demo-agent")
                services = ["demo-agent"]

        for service in services:
            traces = await self.fetcher.fetch_traces_by_service(
                service=service, limit=settings.trace_fetch_limit
            )

            for trace_data in traces:
                trace_id = trace_data.get("traceID", "")
                if not trace_id:
                    continue

                # Parse the raw trace into a tree of SpanNode objects.
                root_spans = self.parser.parse_jaeger_trace(trace_data)
                if not root_spans:
                    continue

                # Build a run summary from the span tree.
                summary = self.builder.build_from_span_tree(root_spans, trace_id)
                if summary is None:
                    continue

                run_id = summary.run_id

                # Deduplication: skip if this run was already processed.
                # This handles the case where Jaeger returns the same trace
                # across multiple polling cycles.
                if await is_run_processed(pool, run_id):
                    self.metrics.inc_duplicate_skip()
                    continue

                # Persist the summary to the database.
                await persist_run_summary(pool, summary)
                self.metrics.inc_processed()
                self.metrics.read_model_freshness = datetime.now(timezone.utc)
                logger.info(
                    "Processed run %s (agent=%s, status=%s)",
                    run_id,
                    summary.agent_name,
                    summary.status,
                )

                # Run anomaly detection and dispatch alerts.
                await self._detect_and_alert(pool, summary, root_spans)

        # After processing all traces in this cycle, materialize rollups.
        # This is deferred to after detection so anomaly counts are included
        # in the rollup.
        await self.fleet_materializer.materialize_fleet_rollups(pool)
        await self.cohort_materializer.materialize_version_cohorts(pool)

    async def _detect_and_alert(
        self,
        pool: object,
        summary: RunSummary,
        spans: list[SpanNode],
    ) -> None:
        """Run all anomaly detectors against a summary and persist/alert on hits.

        Detection runs in two phases:

        1. **Backward-compatible phase**: The original three detectors (loop,
           retry, cost) run first.  These are the detectors that existing
           integrations depend on.

        2. **Full detector set**: All 35 detectors run (skipping the three
           that already ran in phase 1, and any detectors whose anomaly_type
           is in ``settings.detector_disabled``).

        Async detectors (those overriding ``detect_async``) are gathered and
        run concurrently.  Sync detectors run sequentially.  Per-detector
        errors are caught and logged individually.

        Args:
            pool: asyncpg connection pool for database-dependent detectors.
            summary: the run summary to analyze.
            spans: the span tree for the run.
        """
        anomalies: list[Anomaly] = []

        # ---- Phase 1: Original three detectors (backward compatible) ----
        # Each wrapped in its own try/except so a failure in one doesn't
        # prevent the others from running.

        if "loop" not in self.disabled_set:
            try:
                loop_anomaly = self.loop_detector.detect(summary, spans)
                if loop_anomaly:
                    anomalies.append(loop_anomaly)
            except Exception:
                logger.exception("LoopDetector failed for run %s", summary.run_id)

        if "retry_storm" not in self.disabled_set:
            try:
                retry_anomaly = self.retry_detector.detect(summary, spans)
                if retry_anomaly:
                    anomalies.append(retry_anomaly)
            except Exception:
                logger.exception("RetryStormDetector failed for run %s", summary.run_id)

        if "cost_spike" not in self.disabled_set:
            try:
                # CostSpikeDetector requires a database pool for baselines.
                cost_anomaly = await self.cost_detector.detect(summary, spans, pool=pool)
                if cost_anomaly:
                    anomalies.append(cost_anomaly)
            except Exception:
                logger.exception("CostSpikeDetector failed for run %s", summary.run_id)

        # ---- Phase 2: All 35 detectors (deduplicating the original three) ----
        async_tasks = []
        for detector in self.detectors:
            # Skip detectors that already ran in Phase 1.
            if isinstance(detector, (LoopDetector, RetryStormDetector, CostSpikeDetector)):
                continue
            # Skip detectors disabled via settings.
            if detector.anomaly_type in self.disabled_set:
                continue
            # Detect async detectors: those that override detect_async from
            # BaseDetector (i.e., their detect_async is NOT BaseDetector.detect_async).
            if (
                hasattr(type(detector), "detect_async")
                and type(detector).detect_async is not BaseDetector.detect_async
            ):
                async_tasks.append(
                    self._run_async_detector(detector, summary, spans, pool, anomalies)
                )
            else:
                try:
                    # This branch only runs for detectors that do not override
                    # BaseDetector.detect_async (i.e., purely sync detectors).
                    result = detector.detect(summary, spans)
                    if result is not None:
                        anomalies.append(cast(Anomaly, result))
                except Exception:
                    logger.exception(
                        "Detector %s failed for run %s",
                        detector.anomaly_type or type(detector).__name__,
                        summary.run_id,
                    )

        # Run all async detectors concurrently for lower total latency.
        if async_tasks:
            await asyncio.gather(*async_tasks)

        # Persist each anomaly and send alerts.  Each is individually
        # wrapped in try/except so a persistence failure for one anomaly
        # doesn't prevent the others from being saved.
        for anomaly in anomalies:
            try:
                await persist_anomaly(pool, anomaly)
                await self.alerter.send_alert(anomaly)
                self.metrics.inc_anomaly_detected(anomaly_type=anomaly.anomaly_type)
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
        """Run a single async detector and append results to the anomalies list.

        Wrapped in try/except so a failure in one async detector doesn't
        crash the gather for all other async detectors.

        Args:
            detector: the detector instance to run.
            summary: the run summary.
            spans: the span tree.
            pool: database connection pool.
            anomalies: shared list to append results to (thread-safe because
                async code is single-threaded cooperative multitasking).
        """
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

        This is the ad-hoc path used by the ``reprocess --trace-id`` CLI
        command.  Unlike the polling loop, this fetches a specific trace
        by its Jaeger trace ID.

        Args:
            trace_id: the Jaeger trace ID to process (hex string).

        Returns:
            ``True`` if the trace was found and processed, ``False`` if
            the trace was not found (404) or had no root spans.
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

        # Note: process_trace does NOT check is_run_processed — it always
        # re-processes, overwriting any previous summary.  This is intentional
        # for reprocessing scenarios.
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
        re-fetches + re-processes each one via ``process_trace``.  This is
        used for bulk re-ingestion after a code change or schema migration.

        Returns:
            The number of traces successfully reprocessed.

        Raises:
            asyncpg.exceptions.PostgresError: on database errors.
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
        """Signal the worker loop to stop after the current cycle.

        Sets ``_running`` to ``False``.  The loop checks this flag at the
        top of each iteration and breaks on False.  Any in-progress cycle
        completes before the coroutine exits.

        This is a graceful shutdown: no in-progress work is interrupted.
        """
        self._running = False

    async def process_traces_in_range(self, start: datetime, end: datetime) -> int:
        """Reprocess all traces from Jaeger within a time range.

        Fetches traces from Jaeger (up to 200) and processes each one.
        Note this does NOT filter by time on the Jaeger side — it fetches
        recent traces and relies on Jaeger's default time window behavior.
        The ``start`` and ``end`` parameters are accepted for API
        compatibility but not currently used for filtering.

        Args:
            start: start of the time window (currently unused).
            end: end of the time window (currently unused).

        Returns:
            The number of traces successfully processed.
        """
        services = list(settings.trace_query_services)
        count = 0
        for service in services:
            traces = await self.fetcher.fetch_traces_by_service(service=service, limit=10000)
            for trace_data in traces:
                trace_id = trace_data.get("traceID", "")
                if not trace_id:
                    continue
                success = await self.process_trace(trace_id)
                if success:
                    count += 1
        return count
