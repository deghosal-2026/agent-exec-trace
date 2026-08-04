"""Pydantic models for the analytics service's domain objects.

Defines the data shapes used throughout the ingestion pipeline: run summaries,
anomalies, fleet rollups, version cohorts, span trees, and raw traces.  All models
inherit from ``pydantic.BaseModel`` for validation, serialization, and OpenAPI
schema generation.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class RunSummary(BaseModel):
    """Aggregated summary of a single agent run.

    Extracted from the root span of a trace tree.  Carries version and workload
    metadata for fleet-level grouping, plus cost, retry, and loop counters for
    anomaly detection.
    """

    run_id: str
    agent_name: str
    agent_version: str | None = None
    workload_type: str | None = None
    duration_ms: int | None = None
    total_tool_calls: int = 0
    total_retries: int = 0
    total_interventions: int = 0
    estimated_cost: float | None = None
    loop_count: int = 0
    loop_detected: bool = False
    status: str | None = None
    root_span_id: str | None = None
    trace_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class Anomaly(BaseModel):
    """A detected anomaly on a single agent run.

    ``id`` auto-generates as a hex UUID so each anomaly is uniquely identifiable
    regardless of the detector that produced it.  ``detected_at`` defaults to
    the current UTC time.
    """

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    run_id: str
    agent_name: str
    anomaly_type: str
    severity: str = "warning"
    explanation: str | None = None
    evidence: dict[str, object] | None = None
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FleetRollup(BaseModel):
    """Pre-computed aggregate over a group of runs sharing agent/version/workload.

    Materialized periodically by ``FleetRollupMaterializer`` to serve the fleet
    health dashboard without re-aggregating raw runs on every request.
    """

    agent_name: str
    agent_version: str | None = None
    workload_type: str | None = None
    period_start: datetime
    period_end: datetime
    total_runs: int = 0
    success_count: int = 0
    error_count: int = 0
    loop_count: int = 0
    anomaly_count: int = 0
    avg_duration_ms: int | None = None
    avg_cost: float | None = None


class VersionCohortSummary(BaseModel):
    """Pre-computed aggregate for a specific agent version cohort.

    Used by the version comparison page to show side-by-side metrics and tool
    usage deltas between two versions.
    """

    agent_name: str
    agent_version: str
    total_runs: int = 0
    success_count: int = 0
    error_count: int = 0
    loop_count: int = 0
    anomaly_count: int = 0
    avg_duration_ms: int | None = None
    avg_cost: float | None = None
    total_tool_calls: int = 0
    total_retries: int = 0
    top_tools: dict[str, int] | None = None


class SpanNode(BaseModel):
    """A single span in a trace tree, with parent-child relationships.

    Represents one behavior span (plan, tool execution, retrieval, memory) with
    timing, status, attributes, and nested child spans.  The tree structure is
    built by ``TraceParser`` and consumed by the run-timeline API.
    """

    span_id: str
    trace_id: str
    parent_span_id: str | None = None
    operation_name: str
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration_ms: int | None = None
    attributes: dict[str, object] = Field(default_factory=dict)
    status: str | None = None
    child_spans: list[SpanNode] = Field(default_factory=list)


class RawTrace(BaseModel):
    """A raw trace as received from Jaeger, before parsing into span trees.

    Kept for reference / debugging; the pipeline primarily works with parsed
    ``SpanNode`` trees.
    """

    trace_id: str
    spans: list[SpanNode]
    service_name: str | None = None