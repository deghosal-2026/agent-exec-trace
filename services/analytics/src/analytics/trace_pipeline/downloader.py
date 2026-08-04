"""HF dataset downloader for agent traces.

Downloads agent trace datasets from Hugging Face using the ``datasets`` library.
Handles failures gracefully, caching downloads to avoid re-downloading.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

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
    """Download agent trace datasets from Hugging Face.

    Uses the ``datasets`` library to load datasets, caching locally to avoid
    redundant downloads.  Each dataset is downloaded independently so a single
    failure does not block the remaining datasets.
    """

    def __init__(self, cache_dir: str = "data/traces/raw") -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def download_dataset(
        self,
        dataset_id: str,
        split: str | None = None,
        max_rows: int | None = None,
    ) -> list[dict[str, object]]:
        """Download a single HF dataset and return rows as dicts.

        Args:
            dataset_id: Hugging Face dataset identifier (e.g. ``"juliensimon/open-agent-traces"``).
            split: dataset split name (defaults to ``"train"``; auto-detected if absent).
            max_rows: optional cap on number of rows (useful for testing).

        Returns:
            List of row dicts from the dataset.
        """
        try:
            from datasets import load_dataset  # type: ignore[import-untyped]
            from datasets.exceptions import DatasetNotFoundError  # type: ignore[import-untyped]
        except ImportError:
            raise ImportError(
                "The 'datasets' library is required to download traces. "
                "Install it with: pip install datasets pyarrow"
            ) from None

        splits_to_try = [split] if split else ["train", "full", "default", "all"]

        ds = None
        last_error: Exception | None = None

        for candidate_split in splits_to_try:
            try:
                ds = load_dataset(
                    dataset_id,
                    split=candidate_split,
                    cache_dir=str(self.cache_dir / "hf_cache"),
                    trust_remote_code=True,
                )
                logger.info("Loaded %s [%s]: %d rows", dataset_id, candidate_split, len(ds))
                break
            except (ValueError, DatasetNotFoundError, KeyError) as exc:
                last_error = exc
                logger.debug(
                    "Split '%s' not found for %s, trying next", candidate_split, dataset_id
                )
                continue
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Failed to load %s with split '%s': %s",
                    dataset_id, candidate_split, exc,
                )
                continue

        if ds is None:
            try:
                ds = load_dataset(
                    dataset_id,
                    cache_dir=str(self.cache_dir / "hf_cache"),
                    trust_remote_code=True,
                )
            except Exception as exc:
                logger.error("Cannot load dataset %s: %s", dataset_id, exc)
                raise exc from last_error

            if hasattr(ds, "items"):
                first_split = next(iter(ds.items()))
                if isinstance(first_split, tuple):
                    split_name, ds = first_split
                    logger.info("Loaded %s [%s]: %d rows", dataset_id, split_name, len(ds))
                else:
                    raise RuntimeError(f"Cannot resolve dataset keys for {dataset_id}")

        rows: list[dict[str, object]] = []
        for idx, row in enumerate(ds):
            rows.append(dict(row))
            if max_rows is not None and idx + 1 >= max_rows:
                break

        return rows

    async def download_all(
        self,
        datasets: list[str] | None = None,
        max_rows_per_dataset: int | None = None,
    ) -> dict[str, list[dict[str, object]]]:
        """Download all configured datasets.

        Args:
            datasets: list of dataset IDs.  Uses ``DEFAULT_DATASETS`` if None.
            max_rows_per_dataset: optional cap on rows per dataset.

        Returns:
            Dict mapping ``dataset_id`` → list of row dicts.
        """
        dataset_ids = datasets if datasets is not None else DEFAULT_DATASETS
        results: dict[str, list[dict[str, object]]] = {}

        for ds_id in dataset_ids:
            logger.info("Downloading dataset: %s", ds_id)
            try:
                rows = await self.download_dataset(ds_id, max_rows=max_rows_per_dataset)
                results[ds_id] = rows
                logger.info("  -> %d rows downloaded", len(rows))
            except Exception:
                logger.exception("Skipping dataset %s due to download failure", ds_id)
                results[ds_id] = []

        return results

    async def download_with_progress(self) -> tuple[int, dict[str, int]]:
        """Download all datasets with progress reporting.

        Returns:
            Tuple of ``(total_traces, {dataset_id: count})``.
        """
        results = await self.download_all()
        per_dataset = {ds_id: len(rows) for ds_id, rows in results.items()}
        total = sum(per_dataset.values())
        logger.info("Download complete: %d total rows across %d datasets", total, len(per_dataset))
        return total, per_dataset
