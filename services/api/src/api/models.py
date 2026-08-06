"""Pydantic models for the REST API's request/response shapes.

Defines the data shapes returned by the API endpoints.  These models are separate
from the analytics service's domain models (``analytics.models``) because the API
layer may need different serialization, aliasing, or aggregation -- e.g. the
``RunTimelineResponse`` combines summary data, span info, and anomalies into a
single response shape.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AnomalyType(str, Enum):
    """Enumeration of all anomaly types produced by the 35 rule-based + 6 LLM detectors.

    IMPORTANT: This enum mirrors ``analytics.models.AnomalyType`` exactly.  It is
    duplicated here (rather than imported) so that the API Docker image can be built
    independently without pulling in the full analytics package.  If a new anomaly
    type is added to the analytics service, this enum must be updated to match
    (source of truth: ``services/analytics/src/analytics/models.py``).

    Drift risk: if the analytics service introduces a new anomaly type and the API
    is not updated, ``AnomalyType(str(db_value))`` will raise ``ValueError`` at
    runtime.  This trade-off is accepted for v0.1.0; a shared ``types`` package
    should replace this duplication in a future release.
    """

    # ── Flow / structure anomalies ──
    loop = "loop"
    pattern_loop = "pattern_loop"
    argument_loop = "argument_loop"

    # ── Tool behaviour anomalies ──
    tool_error_rate = "tool_error_rate"
    specific_tool_error = "specific_tool_error"
    tool_latency = "tool_latency"
    tool_timeout = "tool_timeout"
    redundant_tool_call = "redundant_tool_call"

    # ── Cost anomalies ──
    cost_spike = "cost_spike"
    cost_vs_baseline = "cost_vs_baseline"
    cost_efficiency = "cost_efficiency"
    token_explosion = "token_explosion"
    per_tool_cost_spike = "per_tool_cost_spike"
    wasted_tool_calls = "wasted_tool_calls"

    # ── Performance anomalies ──
    run_duration = "run_duration"
    max_step_hit = "max_step_hit"
    step_efficiency = "step_efficiency"
    inactivity = "inactivity"
    premature_completion = "premature_completion"

    # ── Retry & recovery anomalies ──
    retry_storm = "retry_storm"
    systemic_retry = "systemic_retry"
    transient_retry = "transient_retry"
    cascading_retry = "cascading_retry"
    recovery_path = "recovery_path"

    # ── Human-in-the-loop anomalies ──
    intervention_frequency = "intervention_frequency"
    escalation_rate = "escalation_rate"
    approval_latency = "approval_latency"
    intervention_rejection = "intervention_rejection"

    # ── Output quality anomalies ──
    empty_response = "empty_response"
    low_output = "low_output"
    indeterminate_status = "indeterminate_status"
    output_drift = "output_drift"

    # ── Systematic / cross-run anomalies ──
    anomaly_cluster = "anomaly_cluster"
    run_frequency_anomaly = "run_frequency_anomaly"
    first_run_heuristic = "first_run_heuristic"

    # ── LLM-based semantic anomalies ──
    semantic_loop = "semantic_loop"
    hallucination = "hallucination"
    goal_drift = "goal_drift"
    quality_degradation = "quality_degradation"
    confusion_pattern = "confusion_pattern"


class RunSummaryInfo(BaseModel):
    """High-level summary metadata for a single run.

    Serialized with aliases for the frontend's expected field names.

    Note:
        ``estimated_cost_usd`` is aliased from ``estimated_cost`` so the
        frontend field name includes the currency unit.  Similarly,
        ``retry_count`` and ``intervention_count`` use the frontend's
        preferred key names.
    """

    run_id: str
    agent_name: str
    agent_version: str | None = None
    status: str | None = None

    # Aliased fields: the frontend expects snake_case suffixes with semantic
    # names.  ``serialization_alias`` renames only in the JSON output; the
    # Python attribute remains ``estimated_cost`` for internal use.
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
    ``parent_span_id``.  This keeps payload size small and avoids recursive
    JSON nesting that degrades serialization performance.

    Attributes:
        span_id: Unique span identifier within the trace.
        parent_span_id: The parent span's ID, or None for root spans.
        operation_name: Semantic operation name (e.g. ``"execute_tool"``, ``"plan"``).
        start_time: ISO-8601 formatted start timestamp.
        duration_ms: Span duration in milliseconds.
        status: Span status code (``"ok"``, ``"error"``, ``"unset"``).
        attributes: OTel key-value attributes attached to this span.  Items
            may include ``gen_ai.tool.name``, ``gen_ai.tool.result``,
            ``error.code``, etc.
    """

    span_id: str
    parent_span_id: str | None = None
    operation_name: str
    start_time: datetime | None = None
    duration_ms: int | None = None
    status: str | None = None
    # ``default_factory=dict`` ensures each model instance gets its own empty
    # dict rather than sharing a mutable class-level default.
    attributes: dict[str, Any] = Field(default_factory=dict)


class AnomalyInfo(BaseModel):
    """An anomaly associated with a run, as returned by the API.

    Fields are aliased so the frontend receives ``anomaly_id`` instead of ``id``
    and ``created_at`` instead of ``detected_at`` (though ``detected_at`` is
    the source field from the database).
    """

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
    detected on the run.  This is the primary response shape for the
    ``GET /runs/{run_id}`` endpoint.
    """

    run: RunSummaryInfo
    summary: RunSummaryStats
    # Defaults to empty lists so the frontend always receives arrays, never None.
    spans: list[SpanInfo] = Field(default_factory=list)
    anomalies: list[AnomalyInfo] = Field(default_factory=list)


class FleetRow(BaseModel):
    """A single row in the fleet health table.

    Represents one agent/version/workload group with aggregated metrics.
    ``success_rate`` is computed client-side by the query builder, not stored
    in the database.
    """

    agent_name: str
    agent_version: str | None = None
    workload_type: str | None = None
    run_count: int = 0
    success_rate: float = 0.0
    avg_cost_usd: float | None = None
    anomaly_count: int = 0


class VersionCohort(BaseModel):
    """A version cohort in the version comparison view.

    Represents the aggregate statistics for all runs of a specific agent version.
    """

    version: str
    run_count: int = 0


class VersionDeltas(BaseModel):
    """Deltas between two version cohorts.

    Each delta is computed as ``right - left``, so a positive value means the
    right (candidate) version performed better (or worse, depending on the metric).
    """

    avg_cost_usd: float | None = None
    retry_rate: float | None = None
    success_rate: float | None = None


class ToolDelta(BaseModel):
    """Per-tool usage delta between two versions.

    ``left_count`` and ``right_count`` are raw invocation counts.  ``delta`` is
    the difference in per-run rates (``right_rate - left_rate``), typically a
    small float.
    """

    tool_name: str
    left_count: int = 0
    right_count: int = 0
    delta: float = 0.0


class VersionCompareResponse(BaseModel):
    """Complete response for the version comparison endpoint.

    Includes cohort metadata, computed deltas, per-tool usage comparison, and
    optional warnings when cohort sizes are too small for reliable analysis.
    """

    left: VersionCohort
    right: VersionCohort
    deltas: VersionDeltas
    tool_deltas: list[ToolDelta] = Field(default_factory=list)
    warning: str | None = None
    note: str | None = None


class AnomalyInboxItem(BaseModel):
    """A single anomaly as shown in the anomaly inbox list.

    Shape is intentionally identical to ``AnomalyInfo`` to keep frontend
    consumption uniform.  The two models may diverge in the future if the
    inbox view requires additional metadata (e.g. agent cohort counts, trend
    indicators).
    """

    id: str = Field(serialization_alias="anomaly_id")
    anomaly_type: AnomalyType = Field(serialization_alias="type")
    severity: str = "warning"
    agent_name: str
    run_id: str
    summary: str = ""
    explanation: str | None = None
    detected_at: datetime | None = Field(default=None, serialization_alias="created_at")


class PaginationMeta(BaseModel):
    """Pagination metadata for list endpoints.

    Attached to every paginated response as the ``meta`` key so the frontend
    can render page controls without counting items manually.
    """

    total: int = 0
    page: int = 1
    page_size: int = 20


class ListResponse(BaseModel):
    """Generic paginated list response.

    ``data`` is typed as ``Any`` because different endpoints return different
    inner shapes (e.g. ``{"rows": [...]}`` vs ``{"items": [...]}``).  Concrete
    typing would require a generic type parameter, which FastAPI's OpenAPI
    schema generation does not handle well out of the box.
    """

    data: Any
    meta: PaginationMeta


class ErrorResponse(BaseModel):
    """Standard error response shape.

    Used for structured error payloads on 404 and other error responses.
    ``code`` is a machine-readable error code (e.g. ``"run_not_found"``)
    that the frontend can switch on.
    """

    detail: str
    code: str
