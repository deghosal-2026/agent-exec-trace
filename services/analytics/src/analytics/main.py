"""CLI entry point for the analytics service.

Provides a ``click``-based CLI with commands for:

  * ``run-worker``: continuous polling loop that fetches traces and detects anomalies.
  * ``reprocess``: re-process a specific trace or time range.
  * ``rebuild``: re-process all known traces.
  * ``health``: database connectivity check.
  * ``materialize``: run fleet rollup and version cohort materialization.
  * ``download-traces``: download and convert agent traces from Hugging Face.
  * ``validate``: run all detectors against processed parquet traces and produce reports.

Usage: ``python -m analytics.main run-worker``
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import click

from analytics.config import settings
from analytics.db import close_pool, ensure_schema, get_pool, health_check
from analytics.logging import setup_logging

logger = logging.getLogger(__name__)


@click.group()
def cli() -> None:
    setup_logging()


@cli.command()
@click.option("--interval", default=None, type=int, help="Polling interval in seconds")
def run_worker(interval: int | None) -> None:
    if interval is not None:
        settings.polling_interval_seconds = interval

    _run_async(_run_worker_async)


@cli.command()
@click.option("--start", required=True, help="Start time (ISO format)")
@click.option("--end", required=True, help="End time (ISO format)")
@click.option("--trace-id", default=None, help="Specific trace ID to reprocess")
def reprocess(start: str, end: str, trace_id: str | None) -> None:
    _run_async(_reprocess_async(start, end, trace_id))


@cli.command()
def rebuild() -> None:
    _run_async(_rebuild_async())


@cli.command()
def health() -> None:
    result = _run_async(_health_async())
    if result:
        click.echo("Health: OK")
    else:
        click.echo("Health: FAILED")


@cli.command()
@click.option(
    "--input",
    "input_dir",
    default="data/traces/processed",
    help="Directory of processed parquet traces",
)
@click.option(
    "--output",
    "output_dir",
    default="data/traces/validations",
    help="Output directory for reports",
)
@click.option(
    "--llm-sample",
    default=None,
    type=int,
    help="Sample N traces and include LLM detectors",
)
@click.option(
    "--resume",
    is_flag=True,
    default=False,
    help="Skip previously completed traces (uses progress.json)",
)
@click.option(
    "--diagnose",
    is_flag=True,
    default=False,
    help="Run compatibility diagnostic: map trace fields, produce detector eligibility report",
)
@click.option(
    "--db",
    is_flag=True,
    default=False,
    help="Connect to Postgres for baseline-dependent detectors",
)
def validate(
    input_dir: str,
    output_dir: str,
    llm_sample: int | None,
    resume: bool,
    diagnose: bool,
    db: bool,
) -> None:
    """Run all detectors against processed traces and produce validation reports."""

    async def _run() -> None:
        from typing import Any

        from analytics.trace_pipeline.validator import Validator

        pool = None
        if db:
            from analytics.db import ensure_schema, get_pool

            pool = await get_pool()
            await ensure_schema(pool)

        v = Validator(
            input_dir=input_dir, output_dir=output_dir,
            llm_sample=llm_sample, resume=resume, diagnose=diagnose,
            pool=pool,
        )
        if diagnose:
            diag_report: dict[str, Any] = v.run_diagnose()
            click.echo("\n=== TRACE COMPATIBILITY DIAGNOSTIC ===")
            click.echo(f"Traces analyzed:     {diag_report.get('total_traces', 0)}")
            click.echo(f"Datasets:            {diag_report.get('total_datasets', 0)}")
            click.echo(f"Detectors:           {diag_report.get('total_detectors', 0)}")
            score = diag_report.get("global_compatibility_score_pct", 0)
            click.echo(f"Compatibility score: {score}%")
            click.echo("\nCorpus field coverage:")
            for field, data in (diag_report.get("corpus_field_coverage", {}) or {}).items():
                if isinstance(data, dict):
                    click.echo(f"  {field}: {data.get('pct', 0)}% ({data.get('count', 0)} traces)")
            mode = "without-llm"
            report_dir = (Path(output_dir) / mode).resolve()
            click.echo(f"\nReport: {report_dir / 'compatibility_matrix.json'}")
            return
        report: dict[str, Any] = await v.run()
        total = int(report["traces_processed"])
        anomaly_count = int(report["anomaly_count"])
        label = f"LLM sample {llm_sample}" if llm_sample else "rule-based"
        click.echo(f"\n=== TRACE VALIDATION ({label}) ===")
        click.echo(f"Traces processed:     {total}")
        click.echo(f"Traces with anomalies: {report['traces_with_anomalies']}")
        click.echo(f"Anomalies found:      {anomaly_count}")

        by_type: dict[str, int] = report.get("anomaly_by_type", {})
        if by_type:
            click.echo("\nTop detectors:")
            for dt, cnt in list(by_type.items())[:10]:
                click.echo(f"  {dt}: {cnt}")

        suspicious: dict[str, float] = report.get("suspicious_patterns", {})
        if suspicious:
            click.echo("\nSuspicious (>50% fire rate):")
            for dt, pct in suspicious.items():
                click.echo(f"  {dt}: {pct}%")

        corr: dict[str, Any] = report.get("cross_detector_correlation", {})
        top_pairs_raw = corr.get("top_co_fires", [])
        top_pairs: list[dict[str, Any]] = (
            list(top_pairs_raw) if isinstance(top_pairs_raw, list) else []
        )
        top5 = top_pairs[:5]
        if top5:
            click.echo("\nCross-detector hotspots:")
            for entry in top5:
                pair = " + ".join(entry["pair"])
                click.echo(f"  {pair}: {entry['count']} traces ({entry['pct']}%)")

        mode = "with-llm" if llm_sample else "without-llm"
        report_dir = (Path(output_dir) / mode).resolve()
        click.echo(f"\nReports: {report_dir}/")
        click.echo(f"Summary: {report_dir / 'summary.json'}")

    _run_async(_run())


@cli.command()
@click.option("--agent-name", default=None, help="Filter by agent name")
@click.option("--workload-type", default=None, help="Filter by workload type")
@click.option("--period-hours", default=24, type=int, help="Rollup period in hours")
def materialize(
    agent_name: str | None,
    workload_type: str | None,
    period_hours: int,
) -> None:
    _run_async(_materialize_async(agent_name, workload_type, period_hours))


@cli.command()
@click.option("--target", default=150000, type=int, help="Target trace count")
@click.option("--ingest", is_flag=True, default=False, help="Feed traces into analytics pipeline")
@click.option("--output-dir", default="data/traces/processed", help="Output directory for parquet")
@click.option("--batch-size", default=5, type=int, help="Rows streamed per dataset per cycle")
@click.option(
    "--dataset",
    multiple=True,
    help="Dataset ID. Repeat to provide multiple datasets.",
)
@click.option(
    "--datasets-file",
    default=None,
    type=str,
    help="Path to a text file with one dataset ID per line (comments starting with # ignored)",
)
def download_traces(
    target: int,
    ingest: bool,
    output_dir: str,
    batch_size: int,
    dataset: tuple[str, ...],
    datasets_file: str | None,
) -> None:
    """Download and convert agent traces from Hugging Face datasets."""
    _run_async(
        _download_traces_async(
            target,
            ingest,
            output_dir,
            batch_size,
            dataset,
            datasets_file,
        )
    )


async def _download_traces_async(
    target: int,
    ingest: bool,
    output_dir: str,
    batch_size: int,
    dataset: tuple[str, ...] = (),
    datasets_file: str | None = None,
) -> None:
    from analytics.trace_pipeline.pipeline import TracePipeline

    pipeline = TracePipeline(output_dir=output_dir)
    # Build dataset list if provided
    dataset_ids: list[str] | None = None
    ids: list[str] = list(dataset)
    if datasets_file:
        try:
            from pathlib import Path
            lines = Path(datasets_file).read_text().splitlines()
            ids.extend(
                [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]
            )
        except Exception as exc:
            click.echo(f"Warning: cannot read datasets file: {exc}", err=True)
    if ids:
        # De-duplicate, preserve order
        seen: set[str] = set()
        ordered: list[str] = []
        for ds in ids:
            if ds not in seen:
                seen.add(ds)
                ordered.append(ds)
        dataset_ids = ordered

    summary = await pipeline.run(
        target_count=target, ingest=ingest, batch_size=batch_size, datasets=dataset_ids,
    )
    click.echo("Download complete:")
    click.echo(f"  Datasets attempted: {summary.get('datasets_downloaded', 0)}")
    click.echo(f"  Total rows downloaded: {summary.get('total_rows_downloaded', 0)}")
    click.echo(f"  Total valid traces: {summary.get('total_traces_valid', 0)}")
    click.echo("  Manifest: data/traces/manifest.json")


def _run_async(coro: object) -> object:
    """Run an async coroutine in a synchronous CLI context.

    Uses ``asyncio.run()`` under the hood.  The type ignore is required because
    click's type system does not know about coroutines.
    """
    import asyncio as _asyncio

    return _asyncio.run(coro)  # type: ignore[arg-type]


async def _run_worker_async() -> None:
    from analytics.worker import AnalyticsWorker

    pool = await get_pool()
    await ensure_schema(pool)

    worker = AnalyticsWorker()
    try:
        await worker.run()
    except KeyboardInterrupt:
        logger.info("Worker interrupted, shutting down")
    finally:
        await worker.shutdown()
        await close_pool()


async def _reprocess_async(start: str, end: str, trace_id: str | None) -> None:
    from analytics.worker import AnalyticsWorker

    pool = await get_pool()
    await ensure_schema(pool)

    worker = AnalyticsWorker()

    try:
        if trace_id:
            logger.info("Reprocessing single trace: %s", trace_id)
            success = await worker.process_trace(trace_id)
            if success:
                click.echo(f"Reprocessed trace {trace_id}")
            else:
                click.echo(f"Trace {trace_id} not found or failed", err=True)
        else:
            start_dt = datetime.fromisoformat(start)
            end_dt = datetime.fromisoformat(end)
            count = await worker.process_traces_in_range(start_dt, end_dt)
            click.echo(f"Reprocessed {count} traces from {start} to {end}")
    finally:
        await close_pool()


async def _rebuild_async() -> None:
    from analytics.worker import AnalyticsWorker

    pool = await get_pool()
    await ensure_schema(pool)

    worker = AnalyticsWorker()
    try:
        count = await worker.rebuild_all()
        click.echo(f"Rebuild complete: {count} traces reprocessed")
    finally:
        await close_pool()


async def _health_async() -> bool:
    pool = await get_pool()
    return await health_check(pool)


async def _materialize_async(
    agent_name: str | None,
    workload_type: str | None,
    period_hours: int,
) -> None:
    from analytics.materializer import FleetRollupMaterializer, VersionCohortMaterializer

    pool = await get_pool()

    fleet_mat = FleetRollupMaterializer()
    cohort_mat = VersionCohortMaterializer()

    fleet_count = await fleet_mat.materialize_fleet_rollups(
        pool,
        agent_name=agent_name,
        workload_type=workload_type,
        period_hours=period_hours,
    )
    cohort_count = await cohort_mat.materialize_version_cohorts(
        pool,
        agent_name=agent_name,
    )

    click.echo(f"Materialized {fleet_count} fleet rollups, {cohort_count} version cohorts")

if __name__ == "__main__":
    cli()
