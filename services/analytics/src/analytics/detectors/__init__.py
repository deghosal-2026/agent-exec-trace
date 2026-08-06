"""Anomaly detection package — exports all 35 detectors and a factory function.

The detectors are organized by domain:

- **Tool execution** (``tool.py``): 8 detectors for tool call patterns, errors,
  latency, timeouts, and redundancy.
- **Cost & resource** (``cost.py``): 6 detectors for cost spikes, efficiency,
  token explosions, and wasted calls.
- **Runtime & completion** (``runtime.py``): 5 detectors for run duration,
  step budgets, inactivity, and premature completion.
- **Retry & recovery** (``retry.py``): 5 detectors for retry storms, systemic
  failures, transient storms, cascading retries, and recovery paths.
- **Interaction & control** (``interaction.py``): 4 detectors for human
  interventions, escalations, approval latency, and rejections.
- **Output quality** (``output.py``): 4 detectors for empty/low output,
  indeterminate status, and output drift.
- **Cross-run patterns** (``cross_run.py``): 3 detectors for anomaly
  clustering, run frequency anomalies, and first-run heuristics.

**Factory usage**::

    from analytics.detectors import create_all_detectors
    detectors = create_all_detectors()

All detectors inherit from ``BaseDetector`` and expose a ``detect(summary, spans)``
method (optionally async via ``detect_async``).
"""

from __future__ import annotations

from analytics.detectors.base import BaseDetector
from analytics.detectors.cost import (
    CostEfficiencyDetector,
    CostSpikeDetector,
    CostVsBaselineDetector,
    PerToolCostSpikeDetector,
    TokenExplosionDetector,
    WastedToolCallsDetector,
)
from analytics.detectors.cross_run import (
    AnomalyClusterDetector,
    FirstRunHeuristicDetector,
    RunFrequencyAnomalyDetector,
)
from analytics.detectors.interaction import (
    ApprovalLatencyDetector,
    EscalationRateDetector,
    InterventionFrequencyDetector,
    InterventionRejectionDetector,
)
from analytics.detectors.output import (
    EmptyResponseDetector,
    IndeterminateDetector,
    LowOutputDetector,
    OutputDriftDetector,
)
from analytics.detectors.retry import (
    CascadingRetryDetector,
    RecoveryPathDetector,
    RetryStormDetector,
    SystemicRetryDetector,
    TransientRetryDetector,
)
from analytics.detectors.runtime import (
    InactivityDetector,
    MaxStepHitDetector,
    PrematureCompletionDetector,
    RunDurationDetector,
    StepEfficiencyDetector,
)
from analytics.detectors.tool import (
    ArgumentLoopDetector,
    LoopDetector,
    PatternLoopDetector,
    RedundantToolCallDetector,
    SpecificToolErrorDetector,
    ToolErrorRateDetector,
    ToolLatencyDetector,
    ToolTimeoutDetector,
)


def create_all_detectors() -> list[BaseDetector]:
    """Factory: instantiate all 35 detectors with default thresholds from settings.

    Each detector reads its thresholds from ``settings.*`` environment
    variables.  Detectors are instantiated without arguments so they pick
    up the current configuration.

    Returns:
        A list of 35 detector instances, ordered by category.
    """
    return [
        # Tool execution (8)
        LoopDetector(),
        PatternLoopDetector(),
        ArgumentLoopDetector(),
        ToolErrorRateDetector(),
        SpecificToolErrorDetector(),
        ToolLatencyDetector(),
        ToolTimeoutDetector(),
        RedundantToolCallDetector(),
        # Cost & resource (6)
        CostSpikeDetector(),
        CostVsBaselineDetector(),
        CostEfficiencyDetector(),
        TokenExplosionDetector(),
        PerToolCostSpikeDetector(),
        WastedToolCallsDetector(),
        # Runtime & completion (5)
        RunDurationDetector(),
        MaxStepHitDetector(),
        StepEfficiencyDetector(),
        InactivityDetector(),
        PrematureCompletionDetector(),
        # Retry & recovery (5)
        RetryStormDetector(),
        SystemicRetryDetector(),
        TransientRetryDetector(),
        CascadingRetryDetector(),
        RecoveryPathDetector(),
        # Interaction & control (4)
        InterventionFrequencyDetector(),
        EscalationRateDetector(),
        ApprovalLatencyDetector(),
        InterventionRejectionDetector(),
        # Output quality (4)
        EmptyResponseDetector(),
        LowOutputDetector(),
        IndeterminateDetector(),
        OutputDriftDetector(),
        # Cross-run patterns (3)
        AnomalyClusterDetector(),
        RunFrequencyAnomalyDetector(),
        FirstRunHeuristicDetector(),
    ]


__all__ = [
    "BaseDetector",
    "LoopDetector",
    "PatternLoopDetector",
    "ArgumentLoopDetector",
    "ToolErrorRateDetector",
    "SpecificToolErrorDetector",
    "ToolLatencyDetector",
    "ToolTimeoutDetector",
    "RedundantToolCallDetector",
    "CostSpikeDetector",
    "CostVsBaselineDetector",
    "CostEfficiencyDetector",
    "TokenExplosionDetector",
    "PerToolCostSpikeDetector",
    "WastedToolCallsDetector",
    "RunDurationDetector",
    "MaxStepHitDetector",
    "StepEfficiencyDetector",
    "InactivityDetector",
    "PrematureCompletionDetector",
    "RetryStormDetector",
    "SystemicRetryDetector",
    "TransientRetryDetector",
    "CascadingRetryDetector",
    "RecoveryPathDetector",
    "InterventionFrequencyDetector",
    "EscalationRateDetector",
    "ApprovalLatencyDetector",
    "InterventionRejectionDetector",
    "EmptyResponseDetector",
    "LowOutputDetector",
    "IndeterminateDetector",
    "OutputDriftDetector",
    "AnomalyClusterDetector",
    "RunFrequencyAnomalyDetector",
    "FirstRunHeuristicDetector",
    "create_all_detectors",
]