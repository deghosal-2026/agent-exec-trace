"""Trace fetching, parsing, and persistence for the analytics pipeline.

The ingestion pipeline has three stages:

  1. **Fetch**: ``TraceFetcher`` retrieves raw traces from Jaeger's API.
  2. **Parse**: ``TraceParser`` converts Jaeger's JSON format into a tree of
     ``SpanNode`` objects with parent-child relationships resolved.
  3. **Summarize**: ``RunSummaryBuilder`` extracts a flat ``RunSummary`` from the
     span tree, aggregating metrics like cost, retries, and tool calls.

The module also provides persistence functions (``persist_run_summary``,
``persist_anomaly``, ``persist_fleet_rollup``, ``persist_version_cohort``) that
upsert data into the analytics database, plus helper functions for safe type
conversion from Jaeger's loosely-typed attribute values.

**Design decisions:**

- **Upsert everywhere**: All persistence functions use ``ON CONFLICT ... DO UPDATE``
  (or ``DO NOTHING`` for anomalies) so re-processing the same trace is idempotent.
  This enables the ``rebuild`` CLI command to safely re-ingest all traces.
- **Safe type conversion**: Jaeger attributes can be any JSON type.  The
  ``_to_float``, ``_to_int``, ``_to_bool`` helpers coerce values safely,
  returning defaults rather than raising on unexpected types.
- **In-order traversal**: ``RunSummaryBuilder`` uses a nonlocal closure
  (``count_spans``) to walk the tree and count tool calls in a single pass.
  This is more efficient than walking multiple times for different counters.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from analytics.config import settings
from analytics.models import Anomaly, FleetRollup, RunSummary, SpanNode, VersionCohortSummary


def _to_float(val: object) -> float | None:
    """Safely convert a Jaeger attribute value to float, or return None.

    Jaeger attributes arrive as ``int | float | str`` from JSON.  This
    function tries to parse strings and returns ``None`` for anything
    that cannot be coerced (lists, dicts, None, etc.).
    """
    if val is None:
        return None
    if isinstance(val, int | float | str):
        try:
            return float(val)
        except (ValueError, TypeError):
            return None
    return None


def _to_int(val: object, default: int = 0) -> int:
    """Safely convert a Jaeger attribute value to int, with a fallback default.

    Unlike ``_to_float``, this never returns ``None`` — it always returns an
    integer value, defaulting to ``0`` when conversion fails.  This is
    appropriate for counters (loop counts, retry counts) where "absent"
    should mean "zero".
    """
    if val is None:
        return default
    if isinstance(val, int | float | str):
        try:
            return int(val)
        except (ValueError, TypeError):
            return default
    return default


def _to_bool(val: object, default: bool = False) -> bool:
    """Safely convert a Jaeger attribute value to bool, with a fallback default.

    Handles string representations (``"true"``, ``"false"``, ``"1"``, ``"0"``,
    ``"yes"``, ``"no"``) in addition to native Python booleans and truthiness.
    """
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in ("true", "1", "yes")
    return bool(val)


logger = logging.getLogger(__name__)


class TraceFetcher:
    """Fetch traces from the Jaeger query API.

    Wraps the Jaeger HTTP API (``/api/traces`` and ``/api/traces/{id}``) to
    retrieve raw trace data.  The endpoint is configured via
    ``settings.jaeger_endpoint``.

    The Jaeger API returns JSON objects containing ``data`` arrays of trace
    dicts.  Each trace dict has a ``spans`` list and a ``traceID``.
    """

    def __init__(self, jaeger_endpoint: str = settings.jaeger_endpoint) -> None:
        # Strip trailing slash so URL construction is predictable.
        # Without this, f"{base}/api/traces" could produce double slashes.
        self.jaeger_endpoint = jaeger_endpoint.rstrip("/")

    async def fetch_traces_by_service(self, service: str, limit: int = 100) -> list[dict[str, Any]]:
        """Fetch the most recent traces for a given Jaeger service name.

        Uses Jaeger's ``/api/traces?service=...&limit=...`` endpoint.  This
        returns traces in reverse chronological order (most recent first).

        Args:
            service: the Jaeger service name to query (e.g., ``"demo-agent"``).
            limit: maximum number of traces to return.  Jaeger may return fewer
                   if fewer traces exist.

        Returns:
            A list of raw trace dicts as returned by the Jaeger API.  Empty
            list if the service has no traces or is unreachable.

        Raises:
            httpx.HTTPStatusError: if the Jaeger API returns a non-2xx status.
            httpx.ConnectError: if the Jaeger endpoint is unreachable.
        """
        import httpx

        url = f"{self.jaeger_endpoint}/api/traces"
        params: dict[str, int | str] = {"service": service, "limit": limit}
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data: Any = resp.json()
            return list(data.get("data", []))

    async def list_services(self) -> list[str]:
        """List all services known to Jaeger.

        Uses Jaeger's ``/api/services`` endpoint. Returns a list of service
        names, excluding internal services like ``jaeger-all-in-one``.

        Returns:
            List of service name strings, or empty list on failure.
        """
        import httpx

        url = f"{self.jaeger_endpoint}/api/services"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=10)
                resp.raise_for_status()
                data: Any = resp.json()
                return list(data.get("data", []))
        except Exception:
            return []

    async def fetch_trace_by_id(self, trace_id: str) -> dict[str, Any] | None:
        """Fetch a single trace by its Jaeger trace ID.

        Uses Jaeger's ``/api/traces/{trace_id}`` endpoint.  Returns ``None``
        on 404 (trace not found) rather than raising, because missing traces
        are expected during reprocessing of old or deleted traces.

        Args:
            trace_id: the Jaeger trace ID to fetch (hex string).

        Returns:
            The raw trace dict, or ``None`` if the trace is not found (404).

        Raises:
            httpx.HTTPStatusError: for non-404 HTTP errors.
            httpx.ConnectError: if the Jaeger endpoint is unreachable.
        """
        import httpx

        url = f"{self.jaeger_endpoint}/api/traces/{trace_id}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=30)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
            traces = data.get("data", [])
            return traces[0] if traces else None


class TraceParser:
    """Parse Jaeger JSON traces into a tree of ``SpanNode`` objects.

    The parser handles parent-child relationship resolution: Jaeger spans
    carry their parent's span ID in ``references``, and this parser builds
    a tree from the flat list, sorts children by start time, and returns
    root spans.

    **Algorithm:**
    1. Build a ``spans_map`` (span_id → SpanNode) and ``child_map``
       (parent_id → [child_ids]) from the flat spans list.
    2. Identify roots: spans whose parent_span_id is None or not in the map.
    3. Recursively build each root's subtree, sorting children by start_time.
    """

    @staticmethod
    def parse_jaeger_trace(raw: dict[str, Any]) -> list[SpanNode]:
        """Convert a raw Jaeger trace dict into a sorted tree of SpanNodes.

        Builds a span map from the flat spans list, resolves parent-child
        relationships, and returns root-level spans with their children
        attached recursively.

        Args:
            raw: a single trace dict from the Jaeger API, containing a
                ``spans`` list.

        Returns:
            A list of root ``SpanNode`` objects, each with populated
            ``child_spans``.  Returns an empty list if ``spans`` is empty.
        """
        spans_raw = raw.get("spans", [])
        spans_map: dict[str, SpanNode] = {}
        child_map: dict[str, list[str]] = {}

        # Pass 1: build SpanNode objects and collect parent-child IDs.
        for s in spans_raw:
            span_id = s.get("spanID", "")
            trace_id = s.get("traceID", "")
            # Jaeger references: the first reference is typically the parent
            # span.  Jaeger's reference model supports multiple types
            # (CHILD_OF, FOLLOWS_FROM), but for agent traces we only care
            # about CHILD_OF which is always index 0.
            parent_span_id = (
                s.get("references", [{}])[0].get("spanID") if s.get("references") else None
            )
            operation_name = s.get("operationName", "unknown")
            # Jaeger reports timestamps in microseconds since epoch.
            start_time_us = s.get("startTime", 0)
            duration_us = s.get("duration", 0)

            # Collect all tags into a flat attrs dict.  Jaeger tags are
            # key-value pairs where the value can be any JSON type.
            attrs: dict[str, object] = {}
            for tag in s.get("tags", []):
                key = tag.get("key", "")
                value = tag.get("value")
                if value is not None:
                    attrs[key] = value

            # Convert microseconds to Python datetime (UTC).
            start_time = (
                datetime.fromtimestamp(start_time_us / 1_000_000, tz=timezone.utc)
                if start_time_us
                else None
            )
            # Convert microseconds to milliseconds for the SpanNode model.
            duration_ms = int(duration_us / 1000) if duration_us else None

            node = SpanNode(
                span_id=span_id,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
                operation_name=operation_name,
                start_time=start_time,
                duration_ms=duration_ms,
                attributes=attrs,
                status=s.get("status"),
            )
            spans_map[span_id] = node
            parent = parent_span_id or ""
            child_map.setdefault(parent, []).append(span_id)

        # Roots are spans whose parent is either absent or not in the spans
        # map.  This handles both genuine roots and orphaned spans (where
        # the parent span was not included in the trace).
        root_spans: list[SpanNode] = []
        for _span_id, node in spans_map.items():
            if node.parent_span_id is None or node.parent_span_id not in spans_map:
                root_spans.append(node)

        def build_tree(parent_id: str) -> list[SpanNode]:
            """Recursively build child subtrees for a given parent span ID."""
            children: list[SpanNode] = []
            for child_id in child_map.get(parent_id, []):
                child = spans_map[child_id]
                child.child_spans = build_tree(child_id)
                children.append(child)
            # Sort children by start_time for chronological order.
            # Spans without start_time are sorted to the end using datetime.min.
            children.sort(key=lambda x: x.start_time or datetime.min.replace(tzinfo=timezone.utc))
            return children

        # Attach subtrees to each root.
        for root in root_spans:
            root.child_spans = build_tree(root.span_id)

        return root_spans


class RunSummaryBuilder:
    """Build a flat ``RunSummary`` from a parsed span tree.

    Extracts agent identity, cost, retry/loop counters, and status from the
    root span's attributes and walks the tree to count tool calls.

    **Edge cases handled:**
    - Missing/absent attributes return safe defaults (0, None, "unknown").
    - Status is inferred from child span statuses if no root-level status.
    - ``run_id`` falls back to ``trace_id`` if the ``gen_ai.agent.run.id``
      attribute is absent.
    """

    @staticmethod
    def build_from_span_tree(root_spans: list[SpanNode], trace_id: str) -> RunSummary | None:
        """Extract a run summary from the root span of a trace tree.

        Walks the tree once (using a nonlocal closure) to count tool calls
        and detect error statuses.

        Args:
            root_spans: root-level span nodes from
                ``TraceParser.parse_jaeger_trace``.
            trace_id: the Jaeger trace ID (used as fallback ``run_id``).

        Returns:
            A ``RunSummary`` with metrics aggregated from the span tree,
            or ``None`` if the tree is empty.
        """
        if not root_spans:
            return None

        root = root_spans[0]  # First root span carries agent-level metadata.
        attrs = root.attributes

        # Extract agent identity from OTel semantic convention attributes.
        agent_name = str(attrs.get("gen_ai.agent.name", "unknown"))
        agent_version = (
            str(attrs["gen_ai.agent.version"])
            if "gen_ai.agent.version" in attrs
            else None
        )
        workload_type = (
            str(attrs["gen_ai.agent.workload.type"])
            if "gen_ai.agent.workload.type" in attrs
            else None
        )
        # run_id from the trace instrumentation, falling back to trace_id.
        run_id = str(attrs.get("gen_ai.agent.run.id", ""))
        cost_raw = attrs.get("gen_ai.agent.run.cost.total")
        estimated_cost = _to_float(cost_raw)
        loop_count = _to_int(attrs.get("gen_ai.agent.loop.count", 0))
        loop_detected = _to_bool(attrs.get("gen_ai.agent.loop.detected", False))
        retry_count = _to_int(attrs.get("gen_ai.agent.retry.count", 0))
        intervention_count = _to_int(attrs.get("gen_ai.agent.intervention.count", 0))

        total_tool_calls = 0
        # Default status is "success" — we only downgrade if we find evidence.
        status: str | None = "success"

        # Set of status values that indicate an explicit error/failure.
        # Includes common variants (cancelled/canceled) and framework-specific
        # statuses (max_steps_exceeded, max_steps_hit).
        explicit_error_statuses = {
            "error",
            "failed",
            "failure",
            "timeout",
            "timed_out",
            "cancelled",
            "canceled",
            "interrupted",
            "incomplete",
            "max_steps_exceeded",
            "max_steps_hit",
        }

        def count_spans(nodes: list[SpanNode]) -> None:
            """Recursively traverse the tree, counting tool calls and checking status."""
            nonlocal total_tool_calls, status
            for node in nodes:
                if node.operation_name == "execute_tool":
                    total_tool_calls += 1
                # Check if any span has an explicit error status.
                node_status = (node.status or "").strip().lower()
                if node_status in explicit_error_statuses:
                    status = "error"
                count_spans(node.child_spans)

        count_spans(root_spans)

        started_at = root.start_time
        completed_at = None
        duration_ms = root.duration_ms

        # Compute completed_at from start_time + duration if both are available.
        # This is more reliable than expecting an explicit end_time attribute.
        if started_at and duration_ms:
            completed_at = datetime.fromtimestamp(
                started_at.timestamp() + duration_ms / 1000, tz=timezone.utc
            )

        return RunSummary(
            run_id=run_id or trace_id,
            agent_name=agent_name,
            agent_version=agent_version,
            workload_type=workload_type,
            duration_ms=duration_ms,
            total_tool_calls=total_tool_calls,
            total_retries=retry_count,
            total_interventions=intervention_count,
            estimated_cost=estimated_cost,
            loop_count=loop_count,
            loop_detected=loop_detected,
            status=status,
            root_span_id=root.span_id,
            trace_id=trace_id,
            started_at=started_at,
            completed_at=completed_at,
        )


class SpanTreeBuilder:
    """Build a parent-child tree from a flat list of SpanNodes.

    Used when spans are already parsed but need tree reconstruction (e.g.,
    from a non-Jaeger source or from cached span data).  The Jaeger path
    uses ``TraceParser.parse_jaeger_trace`` instead; this class handles
    SpanNode objects that already exist but are flattened.
    """

    @staticmethod
    def build_tree(spans: list[SpanNode]) -> list[SpanNode]:
        """Build a tree from a flat list of SpanNodes.

        Nodes are assigned to their parent's ``child_spans`` list.  Roots
        are sorted by start time.  This is an O(n) single-pass algorithm.

        Args:
            spans: a flat list of ``SpanNode`` objects.

        Returns:
            Root-level spans with children populated recursively.
        """
        spans_map = {s.span_id: s for s in spans}
        roots: list[SpanNode] = []
        for s in spans:
            # A span is a root if its parent is missing or not in the map.
            if s.parent_span_id is None or s.parent_span_id not in spans_map:
                roots.append(s)
            else:
                parent = spans_map[s.parent_span_id]
                parent.child_spans.append(s)

        # Sort roots by start time for consistent ordering.
        roots.sort(key=lambda x: x.start_time or datetime.min.replace(tzinfo=timezone.utc))
        return roots


async def persist_run_summary(pool: Any, summary: RunSummary) -> None:
    """Upsert a run summary into the ``run_summaries`` table.

    Uses ``ON CONFLICT (run_id) DO UPDATE`` so re-processing a trace updates
    the existing row rather than failing.  This makes the entire pipeline
    idempotent: you can re-process traces without data loss or duplicates.

    All non-nullable columns are updated.  ``updated_at`` is set to ``NOW()``
    on both insert and update to track freshness.

    Args:
        pool: asyncpg connection pool.
        summary: the ``RunSummary`` to persist.

    Raises:
        asyncpg.exceptions.PostgresError: on database errors (connection
            lost, constraint violation, etc.).
    """
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO run_summaries (
                run_id, agent_name, agent_version, workload_type,
                duration_ms, total_tool_calls, total_retries, total_interventions,
                estimated_cost, loop_count, loop_detected, status,
                root_span_id, trace_id, started_at, completed_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, NOW())
            ON CONFLICT (run_id) DO UPDATE SET
                agent_name = EXCLUDED.agent_name,
                agent_version = EXCLUDED.agent_version,
                workload_type = EXCLUDED.workload_type,
                duration_ms = EXCLUDED.duration_ms,
                total_tool_calls = EXCLUDED.total_tool_calls,
                total_retries = EXCLUDED.total_retries,
                total_interventions = EXCLUDED.total_interventions,
                estimated_cost = EXCLUDED.estimated_cost,
                loop_count = EXCLUDED.loop_count,
                loop_detected = EXCLUDED.loop_detected,
                status = EXCLUDED.status,
                root_span_id = EXCLUDED.root_span_id,
                trace_id = EXCLUDED.trace_id,
                started_at = EXCLUDED.started_at,
                completed_at = EXCLUDED.completed_at,
                updated_at = NOW()
            """,
            summary.run_id,
            summary.agent_name,
            summary.agent_version,
            summary.workload_type,
            summary.duration_ms,
            summary.total_tool_calls,
            summary.total_retries,
            summary.total_interventions,
            summary.estimated_cost,
            summary.loop_count,
            summary.loop_detected,
            summary.status,
            summary.root_span_id,
            summary.trace_id,
            summary.started_at,
            summary.completed_at,
        )


async def persist_anomaly(pool: Any, anomaly: Anomaly) -> None:
    """Insert an anomaly record, skipping duplicates on conflict.

    Uses ``ON CONFLICT (id) DO NOTHING`` so the same anomaly (identified by
    its hex UUID) is never stored twice.  The ``evidence`` field is
    serialized to JSON for storage.

    Why ``DO NOTHING`` instead of ``DO UPDATE``?  Anomalies are immutable
    snapshots.  Once detected, an anomaly's explanation and evidence should
    not change on re-processing.  If the same UUID is generated again
    (extremely unlikely with UUID4), we silently skip.

    Args:
        pool: asyncpg connection pool.
        anomaly: the ``Anomaly`` to persist.

    Raises:
        asyncpg.exceptions.PostgresError: on database errors.
    """
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO anomalies (
                id, run_id, agent_name, anomaly_type, severity, explanation, evidence
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (id) DO NOTHING
            """,
            anomaly.id,
            anomaly.run_id,
            anomaly.agent_name,
            anomaly.anomaly_type,
            anomaly.severity,
            anomaly.explanation,
            json.dumps(anomaly.evidence) if anomaly.evidence else None,
        )


async def persist_fleet_rollup(pool: Any, rollup: FleetRollup) -> None:
    """Upsert a fleet rollup row, keyed by agent/version/workload/time window.

    The natural key is the 5-tuple (agent_name, agent_version, workload_type,
    period_start, period_end).  Re-materializing the same window updates the
    existing row rather than inserting a duplicate.

    Args:
        pool: asyncpg connection pool.
        rollup: the ``FleetRollup`` to persist.

    Raises:
        asyncpg.exceptions.PostgresError: on database errors.
    """
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO fleet_rollups (
                id, agent_name, agent_version, workload_type,
                period_start, period_end, total_runs, success_count,
                error_count, loop_count, anomaly_count, avg_duration_ms, avg_cost
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            ON CONFLICT (agent_name, agent_version, workload_type, period_start, period_end)
            DO UPDATE SET
                total_runs = EXCLUDED.total_runs,
                success_count = EXCLUDED.success_count,
                error_count = EXCLUDED.error_count,
                loop_count = EXCLUDED.loop_count,
                anomaly_count = EXCLUDED.anomaly_count,
                avg_duration_ms = EXCLUDED.avg_duration_ms,
                avg_cost = EXCLUDED.avg_cost
            """,
            rollup.id,
            rollup.agent_name,
            rollup.agent_version,
            rollup.workload_type,
            rollup.period_start,
            rollup.period_end,
            rollup.total_runs,
            rollup.success_count,
            rollup.error_count,
            rollup.loop_count,
            rollup.anomaly_count,
            rollup.avg_duration_ms,
            rollup.avg_cost,
        )


async def persist_version_cohort(pool: Any, cohort: VersionCohortSummary) -> None:
    """Upsert a version cohort summary, keyed by agent name + version.

    The natural key is (agent_name, agent_version).  Re-materializing the
    same cohort updates the aggregate values.

    The ``top_tools`` dict is serialized to JSON for storage.

    Args:
        pool: asyncpg connection pool.
        cohort: the ``VersionCohortSummary`` to persist.

    Raises:
        asyncpg.exceptions.PostgresError: on database errors.
    """
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO version_cohort_summaries (
                agent_name, agent_version, total_runs, success_count,
                error_count, loop_count, anomaly_count, avg_duration_ms,
                avg_cost, total_tool_calls, total_retries, top_tools
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            ON CONFLICT (agent_name, agent_version)
            DO UPDATE SET
                total_runs = EXCLUDED.total_runs,
                success_count = EXCLUDED.success_count,
                error_count = EXCLUDED.error_count,
                loop_count = EXCLUDED.loop_count,
                anomaly_count = EXCLUDED.anomaly_count,
                avg_duration_ms = EXCLUDED.avg_duration_ms,
                avg_cost = EXCLUDED.avg_cost,
                total_tool_calls = EXCLUDED.total_tool_calls,
                total_retries = EXCLUDED.total_retries,
                top_tools = EXCLUDED.top_tools
            """,
            cohort.agent_name,
            cohort.agent_version,
            cohort.total_runs,
            cohort.success_count,
            cohort.error_count,
            cohort.loop_count,
            cohort.anomaly_count,
            cohort.avg_duration_ms,
            cohort.avg_cost,
            cohort.total_tool_calls,
            cohort.total_retries,
            json.dumps(cohort.top_tools) if cohort.top_tools else None,
        )


async def is_run_processed(pool: Any, run_id: str) -> bool:
    """Check if a run ID has already been ingested into ``run_summaries``.

    Used to skip duplicate processing in the worker's polling loop.  This is
    the deduplication guard: if a trace was already processed (e.g., in a
    previous polling cycle), we skip it entirely rather than re-parsing and
    re-detecting.

    Args:
        pool: asyncpg connection pool.
        run_id: the run ID to check.

    Returns:
        ``True`` if the run exists in ``run_summaries``, ``False`` otherwise.

    Raises:
        asyncpg.exceptions.PostgresError: on database errors.
    """
    async with pool.acquire() as conn:
        row: object = await conn.fetchval("SELECT 1 FROM run_summaries WHERE run_id = $1", run_id)
        return bool(row == 1)


async def _get_version_cohort_baseline(
    pool: Any,
    agent_name: str,
    agent_version: str,
) -> float | None:
    """Compute the average cost for a given agent version cohort.

    Used by ``CostSpikeDetector`` to determine whether a run's cost is
    anomalous relative to its version peers.  The baseline is a simple
    arithmetic mean of ``estimated_cost`` across all runs for the same
    agent name + version pair.

    Args:
        pool: asyncpg connection pool.
        agent_name: the agent name to filter by.
        agent_version: the agent version to filter by.

    Returns:
        The average cost as a float, or ``None`` if no runs exist for
        the cohort or all costs are NULL.

    Raises:
        asyncpg.exceptions.PostgresError: on database errors.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT AVG(estimated_cost) AS avg_cost
            FROM run_summaries
            WHERE agent_name = $1 AND agent_version = $2
              AND estimated_cost IS NOT NULL
            """,
            agent_name,
            agent_version,
        )
        if row is None:
            return None
        val = row["avg_cost"]
        if val is None:
            return None
        return float(val)