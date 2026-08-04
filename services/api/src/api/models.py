"""Pydantic models for the REST API's request/response shapes.

Defines the data shapes returned by the API endpoints.  These models are separate
from the analytics service's domain models (``analytics.models``) because the API
layer may need different serialization, aliasing, or aggregation -- e.g. the
``RunTimelineResponse`` combines summary data, span info, and anomalies into a
single response shape.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from analytics.models import AnomalyType
from pydantic import BaseModel, Field


class RunSummaryInfo(BaseModel):
    """High-level summary metadata for a single run.

    Serialized with aliases for the frontend's expected field names.
    """

    run_id: str
    agent_name: str
    agent_version: str | None = None
    status: str | None = None
    estimated_cost: float | None = Field(default=None, serialization_alias="estimated_cost_usd")
    total_retries: int = Field(default=0, serialization_alias="retry_count")
    total_interventions: int = Field(default=0, serialization_alias="intervention_count")


class RunSummaryStats(BaseModel):
    """Aggregated statistics for a single run.

    Serialized with aliases for the frontend's expected field names.
    """

    total_tool_calls: int = Field(default=0, serialization_alias="tool_call_count")
    loop_detected: bool = False
    duration_ms: int | None = None


class SpanInfo(BaseModel):
    """A single span in a run's trace tree, as returned by the API.

    Unlike ``SpanNode`` in the analytics models, this is a flat representation
    (no ``child_spans``) because the frontend reconstructs the tree from
    ``parent_span_id``.
    """

    span_id: str
    parent_span_id: str | None = None
    operation_name: str
    start_time: datetime | None = None
    duration_ms: int | None = None
    status: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class AnomalyInfo(BaseModel):
    """An anomaly associated with a run, as returned by the API."""

    id: str = Field(serialization_alias="anomaly_id")
    anomaly_type: AnomalyType = Field(serialization_alias="type")
    severity: str = "warning"
    agent_name: str
    run_id: str
    summary: str = ""
    explanation: str | None = None
    detected_at: datetime | None = Field(default=None, serialization_alias="created_at")


class RunTimelineResponse(BaseModel):
    """Complete response for a single run timeline view.

    Combines the run's summary metadata, statistics, span tree, and any anomalies
    detected on the run.
    """

    run: RunSummaryInfo
    summary: RunSummaryStats
    spans: list[SpanInfo] = Field(default_factory=list)
    anomalies: list[AnomalyInfo] = Field(default_factory=list)


class FleetRow(BaseModel):
    """A single row in the fleet health table.

    Represents one agent/version/workload group with aggregated metrics.
    """

    agent_name: str
    agent_version: str | None = None
    workload_type: str | None = None
    run_count: int = 0
    success_rate: float = 0.0
    avg_cost_usd: float | None = None
    anomaly_count: int = 0


class VersionCohort(BaseModel):
    """A version cohort in the version comparison view."""

    version: str
    run_count: int = 0


class VersionDeltas(BaseModel):
    """Deltas between two version cohorts."""

    avg_cost_usd: float | None = None
    retry_rate: float | None = None
    success_rate: float | None = None


class ToolDelta(BaseModel):
    """Per-tool usage delta between two versions."""

    tool_name: str
    left_count: int = 0
    right_count: int = 0
    delta: float = 0.0


class VersionCompareResponse(BaseModel):
    """Complete response for the version comparison endpoint."""

    left: VersionCohort
    right: VersionCohort
    deltas: VersionDeltas
    tool_deltas: list[ToolDelta] = Field(default_factory=list)
    warning: str | None = None
    note: str | None = None


class AnomalyInboxItem(BaseModel):
    """A single anomaly as shown in the anomaly inbox list."""

    id: str = Field(serialization_alias="anomaly_id")
    anomaly_type: AnomalyType = Field(serialization_alias="type")
    severity: str = "warning"
    agent_name: str
    run_id: str
    summary: str = ""
    explanation: str | None = None
    detected_at: datetime | None = Field(default=None, serialization_alias="created_at")


class PaginationMeta(BaseModel):
    """Pagination metadata for list endpoints."""

    total: int = 0
    page: int = 1
    page_size: int = 20


class ListResponse(BaseModel):
    """Generic paginated list response."""

    data: Any
    meta: PaginationMeta


class ErrorResponse(BaseModel):
    """Standard error response shape."""

    detail: str
    code: str