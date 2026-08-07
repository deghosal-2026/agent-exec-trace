"""Pydantic models for the analytics service's domain objects.

Defines the data shapes used throughout the ingestion pipeline: run summaries,
anomalies, fleet rollups, version cohorts, span trees, and raw traces.  All
models inherit from ``pydantic.BaseModel`` for validation, serialization, and
OpenAPI schema generation.

**Design decisions:**

- **Auto-generated IDs**: ``Anomaly.id`` uses a hex UUID default factory so
  each anomaly is uniquely identifiable without needing a database sequence.
- **Datetime defaults**: ``detected_at`` defaults to UTC now at construction
  time, capturing when the anomaly was *created in code*, not when it was
  persisted to the database.
- **Nested spans**: ``SpanNode`` uses recursive ``child_spans`` lists
  (``ForwardRef`` handled by Pydantic with ``from __future__ import annotations``),
  allowing arbitrary tree depth without a separate edge table.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class AnomalyType(str, Enum):
    """Enumeration of all anomaly types produced by the 35 rule-based + 6 LLM detectors.

    Each value matches the ``anomaly_type`` class attribute on its corresponding
    detector.  Used by the API layer for validation and by the analytics worker
    for per-detector toggles (``settings.detector_disabled``) and metrics.

    The values are organized by detector category:
    - ``loop`` through ``redundant_tool_call``: Tool execution (8 types)
    - ``cost_spike`` through ``wasted_tool_calls``: Cost & resource (6 types)
    - ``run_duration`` through ``premature_completion``: Runtime (5 types)
    - ``retry_storm`` through ``recovery_path``: Retry & recovery (5 types)
    - ``intervention_frequency`` through ``intervention_rejection``: Interaction (4 types)
    - ``empty_response`` through ``output_drift``: Output quality (4 types)
    - ``anomaly_cluster`` through ``first_run_heuristic``: Cross-run patterns (3 types)
    - ``semantic_loop`` through ``confusion_pattern``: LLM-augmented (5 types)
    """

    loop = "loop"
    pattern_loop = "pattern_loop"
    argument_loop = "argument_loop"
    tool_error_rate = "tool_error_rate"
    specific_tool_error = "specific_tool_error"
    tool_latency = "tool_latency"
    tool_timeout = "tool_timeout"
    redundant_tool_call = "redundant_tool_call"
    cost_spike = "cost_spike"
    cost_vs_baseline = "cost_vs_baseline"
    cost_efficiency = "cost_efficiency"
    token_explosion = "token_explosion"
    per_tool_cost_spike = "per_tool_cost_spike"
    wasted_tool_calls = "wasted_tool_calls"
    run_duration = "run_duration"
    max_step_hit = "max_step_hit"
    step_efficiency = "step_efficiency"
    inactivity = "inactivity"
    premature_completion = "premature_completion"
    retry_storm = "retry_storm"
    systemic_retry = "systemic_retry"
    transient_retry = "transient_retry"
    cascading_retry = "cascading_retry"
    recovery_path = "recovery_path"
    intervention_frequency = "intervention_frequency"
    escalation_rate = "escalation_rate"
    approval_latency = "approval_latency"
    intervention_rejection = "intervention_rejection"
    empty_response = "empty_response"
    low_output = "low_output"
    indeterminate_status = "indeterminate_status"
    output_drift = "output_drift"
    anomaly_cluster = "anomaly_cluster"
    run_frequency_anomaly = "run_frequency_anomaly"
    first_run_heuristic = "first_run_heuristic"
    semantic_loop = "semantic_loop"
    hallucination = "hallucination"
    goal_drift = "goal_drift"
    quality_degradation = "quality_degradation"
    confusion_pattern = "confusion_pattern"


class RunSummary(BaseModel):
    """Aggregated summary of a single agent run.

    Extracted from the root span of a trace tree.  Carries version and workload
    metadata for fleet-level grouping, plus cost, retry, and loop counters for
    anomaly detection.

    Notes:
        - ``run_id`` is the primary key for deduplication.
        - ``agent_version`` and ``workload_type`` are optional because not all
          trace sources include them.
        - ``estimated_cost`` is optional because cost data depends on the
          trace instrumentation depth.
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

    ``id`` auto-generates as a hex UUID so each anomaly is uniquely
    identifiable regardless of the detector that produced it.
    ``detected_at`` defaults to the current UTC time at object creation.

    Notes:
        - ``explanation`` is a human-readable sentence.  It is used in webhook
          alerts, dashboards, and LLM triage classification.
        - ``evidence`` is a free-form dict of detector-specific data
          (thresholds crossed, raw values, ratios).  It is persisted as JSON
          in the database.
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

    Notes:
        - ``period_start`` / ``period_end`` define the rolling time window
          (typically 24 hours).
        - ``avg_duration_ms`` and ``avg_cost`` are simple arithmetic means.
        - ``anomaly_count`` is fetched from the ``anomalies`` table via a
          correlated subquery.
    """

    id: str = ""
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

    Used by the version comparison page to show side-by-side metrics and
    tool usage deltas between two versions.

    Notes:
        - ``top_tools`` is a ``dict[str, int]`` mapping tool name to call count.
        - Only rows with a non-null ``agent_version`` are included.
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

    Represents one behavior span (plan, tool execution, retrieval, memory)
    with timing, status, attributes, and nested child spans.  The tree
    structure is built by ``TraceParser`` and consumed by the run-timeline
    API and all anomaly detectors.

    Notes:
        - ``attributes`` is a free-form dict that carries OTel and agent-
          specific metadata (tool name, arguments, results, token counts, etc.).
        - ``child_spans`` is a recursive list — the tree depth is unlimited
          but in practice agent traces rarely exceed 3-4 levels.
        - ``duration_ms`` is pre-computed from ``start_time`` and ``end_time``
          where available, but may be ``None`` for timestampless spans.
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
    ``SpanNode`` trees.  ``spans`` is a flat list before tree resolution.
    """

    trace_id: str
    spans: list[SpanNode]
    service_name: str | None = None
