"""Trace pipeline orchestrator.

Downloads agent traces from Hugging Face, converts them to OTel-compatible
SpanNode format, validates results, stores them as parquet files, and optionally
feeds them through the analytics ingestion pipeline for anomaly detection.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from analytics.models import SpanNode
from analytics.trace_pipeline.converter import TraceConverter
from analytics.trace_pipeline.downloader import DEFAULT_DATASETS, HFTraceDownloader

logger = logging.getLogger(__name__)


def _dataset_id_to_path(dataset_id: str) -> str:
    """Convert a HF dataset ID to a safe filesystem path component."""
    return dataset_id.replace("/", "__").replace("\\", "__")


def _infer_framework(dataset_id: str, rows: list[dict[str, object]]) -> str:
    """Heuristically infer the agent framework from dataset name and data."""
    lower = dataset_id.lower()
    if "langchain" in lower or "langsmith" in lower:
        return "langchain"
    if "crewai" in lower:
        return "crewai"
    if "autogen" in lower:
        return "autogen"
    if "llamaindex" in lower or "llama_index" in lower:
        return "llamaindex"
    if "claude" in lower:
        return "claude_code"
    if "swe" in lower:
        return "swe_agent"
    if "code" in lower:
        return "coding_agent"
    if "hermes" in lower:
        return "hermes"

    if rows:
        sample = rows[0]
        keys = set(sample.keys())
        if "run_type" in keys:
            return "langchain"
        if "messages" in keys:
            return "chat"

    return "unknown"


def _infer_task_domain(dataset_id: str) -> str:
    """Heuristically infer the task domain from dataset name."""
    lower = dataset_id.lower()
    if "chem" in lower or "chemistry" in lower:
        return "chemistry"
    if "medical" in lower or "clinical" in lower or "clingen" in lower:
        return "clinical"
    if "legal" in lower:
        return "legal_document_analysis"
    if "customer" in lower:
        return "customer_support"
    if "job" in lower or "jobseek" in lower:
        return "job_seeking"
    if "sandbag" in lower:
        return "security"
    if "market" in lower:
        return "market_research"
    if "debug" in lower:
        return "debugging"
    if "code" in lower or "swe" in lower:
        return "software_engineering"
    if "hal" in lower:
        return "general_reasoning"
    if "pi_coding" in lower or "pi-coding" in lower:
        return "software_engineering"
    return "general"


class TracePipeline:
    """Orchestrates the full trace pipeline: download → convert → validate → store.

    Usage::

        pipeline = TracePipeline()
        summary = await pipeline.run(target_count=150_000)
        print(summary)
    """

    def __init__(self, output_dir: str = "data/traces/processed") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.downloader = HFTraceDownloader()
        self.converter = TraceConverter()

    async def run(
        self,
        target_count: int = 150_000,
        datasets: list[str] | None = None,
        ingest: bool = False,
    ) -> dict[str, object]:
        """Download, convert, validate, and store traces.

        Args:
            target_count: target number of traces to collect.
            datasets: specific dataset IDs (uses defaults if None).
            ingest: if True, feed converted traces through analytics pipeline.

        Returns:
            Summary dict with counts, conversion rates, and quality info.
        """
        dataset_ids = datasets if datasets is not None else DEFAULT_DATASETS

        logger.info(
            "Starting trace pipeline: %d datasets, target=%d traces, ingest=%s",
            len(dataset_ids), target_count, ingest,
        )

        all_rows = await self.downloader.download_all(datasets=dataset_ids)

        total_downloaded = sum(len(rows) for rows in all_rows.values())
        logger.info("Downloaded %d total rows", total_downloaded)

        dataset_manifests: list[dict[str, object]] = []
        all_traces: list[list[SpanNode]] = []

        for ds_id in dataset_ids:
            rows = all_rows.get(ds_id, [])
            if not rows:
                logger.warning("No rows for dataset %s, skipping conversion", ds_id)
                continue

            spans_batch = self.converter.convert_batch(ds_id, rows)

            total_in_batch = len(spans_batch)
            converted = sum(1 for s in spans_batch if s)
            conversion_rate = converted / total_in_batch if total_in_batch else 0.0

            validation_errors: list[str] = []
            valid_count = 0
            for spans in spans_batch:
                if not spans:
                    continue
                errors = self.converter.validate_spans(spans)
                if errors:
                    validation_errors.extend(errors)
                else:
                    valid_count += 1

            framework = _infer_framework(ds_id, rows)
            task_domain = _infer_task_domain(ds_id)

            if valid_count > 0:
                valid_traces = [s for s in spans_batch if s]
                self.save_traces(ds_id, valid_traces)
                all_traces.extend(valid_traces)

            manifest_entry: dict[str, object] = {
                "dataset_id": ds_id,
                "trace_count_rows": len(rows),
                "trace_count_converted": converted,
                "trace_count_valid": valid_count,
                "framework": framework,
                "task_domain": task_domain,
                "conversion_success_rate": round(conversion_rate, 4),
                "validation_errors": len(validation_errors),
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }
            dataset_manifests.append(manifest_entry)

            logger.info(
                "Dataset %s: %d rows -> %d converted -> %d valid (%.1f%%)",
                ds_id, len(rows), converted, valid_count, conversion_rate * 100,
            )

        total_valid = sum(
            int(cast(int, m["trace_count_valid"]))
            for m in dataset_manifests
        )
        logger.info("Pipeline complete: %d valid traces collected", total_valid)

        if ingest and all_traces:
            await self._ingest_traces(all_traces)

        await self.generate_manifest(dataset_manifests, total_valid)

        return {
            "datasets_downloaded": len(
                [d for d in dataset_manifests if d.get("trace_count_rows")]
            ),
            "total_rows_downloaded": total_downloaded,
            "total_traces_valid": total_valid,
            "datasets": dataset_manifests,
        }

    def save_traces(self, source_id: str, traces: list[list[SpanNode]]) -> Path:
        """Save converted traces to parquet files.

        Each span is stored as a row in a parquet file with columns:
        trace_id, span_id, parent_span_id, operation_name, start_time, end_time,
        duration_ms, attributes_json, status.

        Args:
            source_id: source dataset identifier.
            traces: list of SpanNode trees.

        Returns:
            Path to the saved parquet file.
        """
        import pyarrow as pa
        import pyarrow.parquet as pq

        dataset_dir = self.output_dir / _dataset_id_to_path(source_id)
        dataset_dir.mkdir(parents=True, exist_ok=True)

        rows: list[dict[str, object]] = []

        def flatten(node: SpanNode, row_idx: int) -> None:
            attrs_json = json.dumps(node.attributes, default=str)
            rows.append({
                "trace_id": node.trace_id,
                "span_id": node.span_id,
                "parent_span_id": node.parent_span_id,
                "operation_name": node.operation_name,
                "start_time": node.start_time.isoformat() if node.start_time else None,
                "end_time": node.end_time.isoformat() if node.end_time else None,
                "duration_ms": node.duration_ms,
                "attributes_json": attrs_json,
                "status": node.status,
                "source_dataset": source_id,
                "source_row_idx": row_idx,
            })
            for child in node.child_spans:
                flatten(child, row_idx)

        for idx, trace_trees in enumerate(traces):
            for root in trace_trees:
                flatten(root, idx)

        if not rows:
            logger.warning("No spans to save for dataset %s", source_id)
            return dataset_dir

        table = pa.Table.from_pylist(rows)
        output_path = dataset_dir / "traces.parquet"
        pq.write_table(table, str(output_path))  # type: ignore[no-untyped-call]
        logger.info("Saved %d spans to %s", len(rows), output_path)

        return output_path

    async def generate_manifest(
        self,
        dataset_entries: list[dict[str, object]],
        total_valid: int,
    ) -> dict[str, object]:
        """Generate manifest.json cataloging all stored traces.

        Args:
            dataset_entries: list of per-dataset manifest entries.
            total_valid: total number of valid traces across all datasets.

        Returns:
            The manifest dict.
        """
        manifest: dict[str, object] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "version": "1.0",
            "total_traces": total_valid,
            "dataset_count": len(dataset_entries),
            "datasets": dataset_entries,
        }

        manifest_path = self.output_dir.parent / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, default=str))
        logger.info("Manifest written to %s", manifest_path)

        return manifest

    async def _ingest_traces(self, all_traces: list[list[SpanNode]]) -> None:
        """Feed converted traces through the analytics ingestion pipeline.

        Builds run summaries from span trees, persists them, and runs anomaly
        detection.  Requires a database connection.
        """
        try:
            from analytics.alerts import WebhookAlerter
            from analytics.config import settings
            from analytics.db import ensure_schema, get_pool
            from analytics.detectors import CostSpikeDetector, LoopDetector, RetryStormDetector
            from analytics.ingest import (
                RunSummaryBuilder,
                is_run_processed,
                persist_anomaly,
                persist_run_summary,
            )
            from analytics.materializer import FleetRollupMaterializer, VersionCohortMaterializer
            from analytics.metrics import AnalyticsMetrics
        except ImportError as exc:
            logger.warning("Cannot ingest traces: missing analytics modules (%s)", exc)
            return

        pool = await get_pool()
        await ensure_schema(pool)

        builder = RunSummaryBuilder()
        loop_detector = LoopDetector()
        retry_detector = RetryStormDetector()
        cost_detector = CostSpikeDetector()
        fleet_mat = FleetRollupMaterializer()
        cohort_mat = VersionCohortMaterializer()
        alerter = WebhookAlerter(webhook_url=settings.webhook_url)
        metrics = AnalyticsMetrics()

        ingested = 0
        skipped = 0
        anomalies_found = 0

        for trace_trees in all_traces:
            for root in trace_trees:
                trace_id = root.trace_id
                summary = builder.build_from_span_tree([root], trace_id)
                if summary is None:
                    continue

                run_id = summary.run_id
                if await is_run_processed(pool, run_id):
                    skipped += 1
                    continue

                await persist_run_summary(pool, summary)
                metrics.inc_processed()
                ingested += 1

                loop_anomaly = loop_detector.detect(summary, [root])
                if loop_anomaly:
                    await persist_anomaly(pool, loop_anomaly)
                    await alerter.send_alert(loop_anomaly)
                    metrics.inc_anomaly_detected()
                    anomalies_found += 1

                retry_anomaly = retry_detector.detect(summary, [root])
                if retry_anomaly:
                    await persist_anomaly(pool, retry_anomaly)
                    await alerter.send_alert(retry_anomaly)
                    metrics.inc_anomaly_detected()
                    anomalies_found += 1

                cost_anomaly = await cost_detector.detect(summary, [root], pool=pool)
                if cost_anomaly:
                    await persist_anomaly(pool, cost_anomaly)
                    await alerter.send_alert(cost_anomaly)
                    metrics.inc_anomaly_detected()
                    anomalies_found += 1

        await fleet_mat.materialize_fleet_rollups(pool)
        await cohort_mat.materialize_version_cohorts(pool)

        logger.info(
            "Ingestion complete: %d ingested, %d skipped, %d anomalies found",
            ingested, skipped, anomalies_found,
        )
