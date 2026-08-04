"""Anomaly detection package — exports all 35 detectors and a factory function.

Usage::

    from analytics.detectors import create_all_detectors
    detectors = create_all_detectors()
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

    Returns:
        A list of detector instances ready to use.
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