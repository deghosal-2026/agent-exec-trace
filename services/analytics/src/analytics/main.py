"""CLI entry point for the analytics service.

Provides a ``click``-based CLI with commands for:

  * ``run-worker``: continuous polling loop that fetches traces and detects anomalies.
  * ``reprocess``: re-process a specific trace or time range.
  * ``rebuild``: re-process all known traces.
  * ``health``: database connectivity check.
  * ``materialize``: run fleet rollup and version cohort materialization.
  * ``download-traces``: download and convert agent traces from Hugging Face.

Usage: ``python -m analytics.main run-worker``
"""

from __future__ import annotations

import logging
from datetime import datetime

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
        click.echo("Health: FAIL", err=True)
        raise SystemExit(1)


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
def download_traces(target: int, ingest: bool, output_dir: str) -> None:
    """Download and convert agent traces from Hugging Face datasets."""
    _run_async(_download_traces_async(target, ingest, output_dir))


async def _download_traces_async(target: int, ingest: bool, output_dir: str) -> None:
    from analytics.trace_pipeline.pipeline import TracePipeline

    pipeline = TracePipeline(output_dir=output_dir)
    summary = await pipeline.run(target_count=target, ingest=ingest)
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