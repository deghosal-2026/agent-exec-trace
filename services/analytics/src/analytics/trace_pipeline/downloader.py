"""HF dataset downloader for agent traces.

Downloads agent trace datasets from Hugging Face using the ``datasets`` library
in streaming mode.  Only the rows actually read are pulled over the wire, so we
never materialize a full dataset in memory.

Each dataset is opened once as a forward-only streaming iterator.  Callers pull
small batches (e.g. 5 rows), process them, then pull the next batch.  Errors are
never retried: the iterator is dropped and the caller moves on to the next
dataset, which is the right behavior when Hugging Face rate-limits us (HTTP 429).
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATASET_SPLITS: dict[str, str] = {
    "juliensimon/open-agent-traces": "customer-support-triage",
}

DEFAULT_DATASETS: list[str] = [
    "agent-data/misc-merged-claude-code-traces-v1",
    "juliensimon/open-agent-traces",
    "lambda/hermes-agent-reasoning-traces",
    "DCAgent/neulab-nebius-swe-agent-trajectories-sandboxes-traces-terminus-2",
    "DCAgent/neulab-nebius-swe-agent-trajectories-sandboxes_glm_4.7_traces_jupiter",
    "agent-data/code-contests-sandboxes-traces-terminus-2",
    "rshn-krn/clingen-agent-traces",
    "YunjueTech/Yunjue-Agent-Traces",
    "viktor-shcherb/jobseek-agent-traces",
    "DJLougen/hermes-agent-traces-filtered",
    "vincentoh/sandbagging-agent-traces",
    "vincentoh/sandbagging-agent-traces-v2",
    "juliensimon/agent-traces-data-pipeline-debugging",
    "juliensimon/agent-traces-code-review-pipeline",
    "juliensimon/agent-traces-market-research",
    "juliensimon/agent-traces-legal-document-analysis",
    "juliensimon/agent-traces-customer-support-triage",
    "compsciencelab/traces_claude_chem_agent",
    "agent-evals/hal_traces",
    "MaxDevv/real-pi-coding-agent-traces-sessions",
]


class HFTraceDownloader:
    """Stream agent trace datasets from Hugging Face.

    Each dataset is opened as a forward-only streaming iterator, cached on the
    instance.  ``download_dataset`` pulls the next ``max_rows`` rows, advancing
    the iterator.  Errors are not retried — the stream is closed and the error
    propagates so the caller can skip to the next dataset.
    """

    def __init__(self, cache_dir: str = "data/traces/raw") -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.hf_token: str | None = os.environ.get("HF_TOKEN")
        self._streams: dict[str, Any] = {}

    def _download_config(self) -> Any:
        """Return a config that disables automatic retries."""
        try:
            from datasets import DownloadConfig  # type: ignore[import-untyped]
        except ImportError:
            return None
        return DownloadConfig(max_retries=0)

    async def open_dataset(
        self,
        dataset_id: str,
        split: str | None = None,
        timeout: float = 20.0,
    ) -> bool:
        """Open a streaming iterator for a dataset.

        Tries common split names in order.  Returns True if a split opened,
        False otherwise (e.g. dataset does not exist or is rate-limited).

        Opening runs in a worker thread with a timeout so a hung or enormous
        dataset never blocks the pipeline; on timeout it returns False and the
        caller moves on.
        """
        if dataset_id in self._streams:
            return True

        try:
            from datasets import load_dataset
        except ImportError:
            raise ImportError(
                "The 'datasets' library is required to download traces. "
                "Install it with: pip install datasets pyarrow"
            ) from None

        resolved_split = split or DATASET_SPLITS.get(dataset_id)
        splits_to_try = [resolved_split] if resolved_split else ["train", "full", "default", "all"]

        def _open_sync() -> Any | None:
            for candidate_split in splits_to_try:
                try:
                    it = load_dataset(
                        dataset_id,
                        split=candidate_split,
                        streaming=True,
                        cache_dir=str(self.cache_dir / "hf_cache"),
                        token=self.hf_token,
                        download_config=self._download_config(),
                    )
                    return candidate_split, it
                except Exception as exc:
                    logger.debug(
                        "Cannot open %s with split '%s': %s", dataset_id, candidate_split, exc
                    )
            return None

        loop = asyncio.get_running_loop()
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(None, _open_sync), timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning("Timed out opening dataset %s, skipping", dataset_id)
            return False

        if result is None:
            logger.warning("Could not open any split for dataset %s", dataset_id)
            return False

        candidate_split, it = result
        self._streams[dataset_id] = iter(it)
        logger.info("Opened stream %s [%s]", dataset_id, candidate_split)
        return True

    async def download_dataset(
        self,
        dataset_id: str,
        split: str | None = None,
        max_rows: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, object]]:
        """Pull the next rows from a dataset's streaming iterator.

        Args:
            dataset_id: Hugging Face dataset identifier.
            split: ignored for streaming (split resolved at open time).
            max_rows: number of rows to pull (defaults to 5).
            offset: ignored; streams are forward-only.

        Returns:
            Up to ``max_rows`` row dicts.  Empty when the dataset is exhausted.

        Raises:
            RuntimeError: if the dataset was not opened first.
            Exception: propagates streaming errors so the caller skips this
                dataset without retrying.
        """
        stream = self._streams.get(dataset_id)
        if stream is None:
            raise RuntimeError(
                f"Dataset {dataset_id} is not open; call open_dataset() first"
            )

        batch = max_rows if max_rows is not None else 5
        rows: list[dict[str, object]] = []
        try:
            for _ in range(batch):
                rows.append(dict(next(stream)))
        except StopIteration:
            # Stream exhausted — drop it so callers stop scheduling it.
            self._streams.pop(dataset_id, None)
        except Exception:
            # Streaming error (e.g. HTTP 429). Drop the stream, no retries.
            self._streams.pop(dataset_id, None)
            raise

        return rows

    def is_open(self, dataset_id: str) -> bool:
        """Return True if the dataset still has an active stream."""
        return dataset_id in self._streams

    def close(self, dataset_id: str) -> None:
        """Close a dataset stream."""
        self._streams.pop(dataset_id, None)

    async def download_all(
        self,
        datasets: list[str] | None = None,
        max_rows_per_dataset: int | None = None,
    ) -> dict[str, list[dict[str, object]]]:
        """Download a capped batch from all configured datasets.

        Uses streaming: each dataset contributes at most ``max_rows_per_dataset``
        rows (default 5).  Datasets that fail to open are skipped.
        """
        dataset_ids = datasets if datasets is not None else DEFAULT_DATASETS
        results: dict[str, list[dict[str, object]]] = {}

        for ds_id in dataset_ids:
            logger.info("Downloading dataset: %s", ds_id)
            if not await self.open_dataset(ds_id):
                results[ds_id] = []
                continue
            try:
                rows = await self.download_dataset(
                    ds_id, max_rows=max_rows_per_dataset
                )
                results[ds_id] = rows
                logger.info("  -> %d rows downloaded", len(rows))
            except Exception:
                logger.exception("Skipping dataset %s due to download failure", ds_id)
                results[ds_id] = []

        return results

    async def download_with_progress(self) -> tuple[int, dict[str, int]]:
        """Download a capped batch from all datasets with progress reporting.

        Returns:
            Tuple of ``(total_traces, {dataset_id: count})``.
        """
        results = await self.download_all()
        per_dataset = {ds_id: len(rows) for ds_id, rows in results.items()}
        total = sum(per_dataset.values())
        logger.info("Download complete: %d total rows across %d datasets", total, len(per_dataset))
        return total, per_dataset
