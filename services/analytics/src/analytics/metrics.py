"""Thread-safe in-process metrics counter for the analytics worker.

Tracks processing counts (processed, failed, skipped, rebuilt, anomalies detected)
and read-model freshness.  All counters are thread-safe via a ``threading.Lock`` so
they can be updated from the worker loop and read from a metrics endpoint
concurrently.

Design decision: Uses in-process counters rather than an external metrics sink
for simplicity and zero-dependency operation.  For production deployment with
multiple workers, an external metrics aggregator (Prometheus, Datadog) would
be more appropriate.
"""

from __future__ import annotations

import logging
from datetime import datetime
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)


class AnalyticsMetrics:
    """In-process counters for the analytics ingestion pipeline.

    Each counter has a thread-safe increment method and a ``snapshot()`` method
    that returns all current values atomically.  Designed for health-check
    endpoints and periodic log summaries.

    Usage::

        metrics = AnalyticsMetrics()
        metrics.inc_processed()
        metrics.inc_anomaly_detected(anomaly_type="loop")
        snap = metrics.snapshot()
    """

    def __init__(self) -> None:
        # Lock serializes all read/write access to counters.
        self._lock = Lock()
        self._processed_run_count: int = 0
        self._failed_run_count: int = 0
        self._duplicate_skip_count: int = 0
        self._replay_rebuild_count: int = 0
        self._anomaly_detected_count: int = 0
        self._anomaly_by_type: dict[str, int] = {}
        self._read_model_freshness: datetime | None = None

    @property
    def processed_run_count(self) -> int:
        return self._processed_run_count

    @property
    def failed_run_count(self) -> int:
        return self._failed_run_count

    @property
    def duplicate_skip_count(self) -> int:
        return self._duplicate_skip_count

    @property
    def anomaly_detected_count(self) -> int:
        return self._anomaly_detected_count

    @property
    def replay_rebuild_count(self) -> int:
        return self._replay_rebuild_count

    @property
    def read_model_freshness(self) -> datetime | None:
        return self._read_model_freshness

    @read_model_freshness.setter
    def read_model_freshness(self, value: datetime) -> None:
        # Thread-safe write: freshness is always the latest processing timestamp.
        with self._lock:
            self._read_model_freshness = value

    def inc_processed(self, n: int = 1) -> None:
        """Increment the processed runs counter by ``n``."""
        with self._lock:
            self._processed_run_count += n

    def inc_failed(self, n: int = 1) -> None:
        """Increment the failed runs counter by ``n``."""
        with self._lock:
            self._failed_run_count += n

    def inc_duplicate_skip(self, n: int = 1) -> None:
        """Increment the duplicate-skip counter by ``n``."""
        with self._lock:
            self._duplicate_skip_count += n

    def inc_replay_rebuild(self, n: int = 1) -> None:
        """Increment the rebuild/replay counter by ``n``."""
        with self._lock:
            self._replay_rebuild_count += n

    def inc_anomaly_detected(self, n: int = 1, anomaly_type: str | None = None) -> None:
        """Increment the anomaly counter and optionally track by type.

        Args:
            n: number of anomalies to add (default 1).
            anomaly_type: if provided, also increments the per-type counter.
        """
        with self._lock:
            self._anomaly_detected_count += n
            if anomaly_type:
                self._anomaly_by_type[anomaly_type] = self._anomaly_by_type.get(anomaly_type, 0) + n

    def anomaly_count_by_type(self, anomaly_type: str) -> int:
        """Return the count of anomalies for a specific type.

        Args:
            anomaly_type: the anomaly type string (e.g., ``"loop"``).

        Returns:
            The count of anomalies of this type, or 0 if none have been recorded.
        """
        with self._lock:
            return self._anomaly_by_type.get(anomaly_type, 0)

    def snapshot(self) -> dict[str, Any]:
        """Atomically capture all counter values.

        Returns:
            A dict with all counter names and values, plus the freshness timestamp
            in ISO format (or None if no processing has occurred yet).
        """
        with self._lock:
            return {
                "processed_run_count": self._processed_run_count,
                "failed_run_count": self._failed_run_count,
                "duplicate_skip_count": self._duplicate_skip_count,
                "replay_rebuild_count": self._replay_rebuild_count,
                "anomaly_detected_count": self._anomaly_detected_count,
                "anomaly_by_type": dict(self._anomaly_by_type),
                "read_model_freshness": (
                    self._read_model_freshness.isoformat() if self._read_model_freshness else None
                ),
            }

    def log_summary(self) -> None:
        """Log the current metrics snapshot at INFO level for human inspection."""
        snap = self.snapshot()
        by_type = snap.get("anomaly_by_type", {})
        # Build a compact string like "loop=5, retry_storm=2, cost_spike=1"
        type_summary = (
            ", ".join(f"{k}={v}" for k, v in sorted(by_type.items())) if by_type else "none"
        )
        logger.info(
            "Metrics snapshot: processed=%d failed=%d skipped=%d rebuild=%d "
            "anomalies=%d freshness=%s by_type=[%s]",
            snap["processed_run_count"],
            snap["failed_run_count"],
            snap["duplicate_skip_count"],
            snap["replay_rebuild_count"],
            snap["anomaly_detected_count"],
            snap["read_model_freshness"] or "never",
            type_summary,
        )
