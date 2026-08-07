"""Attribute contract integration tests.

Validates that detectors fire correctly on spans with the canonical gen_ai.*
attribute keys written by the SDK.  Each test builds SpanNode trees with
realistic attribute payloads and asserts the expected detectors fire.

These tests prevent the class of bug found in M13.2 where SDK attribute naming
(_et.tool vs gen_ai.tool.name) was never caught because synthetic traces used
a different code path.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from analytics.detectors import create_all_detectors
from analytics.detectors.base import BaseDetector
from analytics.detectors.llm import (
    ConfusionPatternDetector,
    GoalDriftDetector,
    HallucinationDetector,
    QualityDegradationDetector,
    SemanticLoopDetector,
)
from analytics.models import Anomaly, RunSummary, SpanNode


def _detectors(exclude_llm: bool = True) -> list[BaseDetector]:
    all_dets = create_all_detectors()
    if exclude_llm:
        return [
            d
            for d in all_dets
            if not isinstance(
                d,
                (
                    SemanticLoopDetector,
                    HallucinationDetector,
                    GoalDriftDetector,
                    QualityDegradationDetector,
                    ConfusionPatternDetector,
                ),
            )
        ]
    return list(all_dets)


def _run_detectors(
    detectors: list[BaseDetector],
    summary: RunSummary,
    spans: list[SpanNode],
) -> dict[str, Anomaly]:
    results: dict[str, Anomaly] = {}
    for det in detectors:
        anomaly: object | None = None
        try:
            anomaly = det.detect(summary, spans)
        except NotImplementedError:
            anomaly = asyncio.run(det.detect_async(summary, spans))
        if anomaly is not None and isinstance(anomaly, Anomaly):
            results[det.anomaly_type] = anomaly
    return results


def _sp(span_id: str, parent: str | None, op: str, **attrs: object) -> SpanNode:
    child_spans_value: list[SpanNode] = attrs.pop("child_spans", [])  # type: ignore[assignment]
    status_value: str | None = attrs.pop("status", None)  # type: ignore[assignment]
    start_time_value: object = attrs.pop("start_time", None)
    end_time_value: object = attrs.pop("end_time", None)
    return SpanNode(
        span_id=span_id,
        trace_id="trace-1",
        parent_span_id=parent,
        operation_name=op,
        start_time=start_time_value,  # type: ignore[arg-type]
        end_time=end_time_value,  # type: ignore[arg-type]
        attributes={k: v for k, v in attrs.items()},
        status=status_value,
        child_spans=child_spans_value,
    )


def _summary(
    agent_name: str = "test-agent",
    agent_version: str = "1.0.0",
    duration_ms: int = 5000,
    total_tool_calls: int = 0,
    total_retries: int = 0,
    estimated_cost: float | None = None,
    status: str | None = "completed",
) -> RunSummary:
    return RunSummary(
        run_id="run-1",
        agent_name=agent_name,
        agent_version=agent_version,
        duration_ms=duration_ms,
        total_tool_calls=total_tool_calls,
        total_retries=total_retries,
        estimated_cost=estimated_cost,
        status=status,
    )


# ---------------------------------------------------------------------------
# Tool execution detectors — depend on gen_ai.tool.name, gen_ai.operation.name
# ---------------------------------------------------------------------------


def test_loop_detector_fires_on_repeated_tool() -> None:
    op = "execute_tool"
    spans = [
        _sp(
            "1",
            None,
            "invoke_agent",
            child_spans=[
                _sp("2", "1", op, **{"gen_ai.tool.name": "search_kb", "gen_ai.operation.name": op}),
                _sp("3", "1", op, **{"gen_ai.tool.name": "search_kb", "gen_ai.operation.name": op}),
                _sp("4", "1", op, **{"gen_ai.tool.name": "search_kb", "gen_ai.operation.name": op}),
                _sp("5", "1", op, **{"gen_ai.tool.name": "search_kb", "gen_ai.operation.name": op}),
                _sp("6", "1", op, **{"gen_ai.tool.name": "search_kb", "gen_ai.operation.name": op}),
                _sp("7", "1", op, **{"gen_ai.tool.name": "search_kb", "gen_ai.operation.name": op}),
            ],
        )
    ]
    s = _summary(total_tool_calls=6)
    results = _run_detectors(_detectors(), s, spans)
    assert "loop" in results
    explanation = results["loop"].explanation or ""
    assert "search_kb" in explanation


def test_pattern_loop_detector_fires_on_repeating_pattern() -> None:
    op = "execute_tool"
    spans = [
        _sp(
            "1",
            None,
            "invoke_agent",
            child_spans=[
                _sp("2", "1", op, **{"gen_ai.tool.name": "read", "gen_ai.operation.name": op}),
                _sp("3", "1", op, **{"gen_ai.tool.name": "search", "gen_ai.operation.name": op}),
                _sp("4", "1", op, **{"gen_ai.tool.name": "read", "gen_ai.operation.name": op}),
                _sp("5", "1", op, **{"gen_ai.tool.name": "search", "gen_ai.operation.name": op}),
                _sp("6", "1", op, **{"gen_ai.tool.name": "read", "gen_ai.operation.name": op}),
                _sp("7", "1", op, **{"gen_ai.tool.name": "search", "gen_ai.operation.name": op}),
                _sp("8", "1", op, **{"gen_ai.tool.name": "read", "gen_ai.operation.name": op}),
                _sp("9", "1", op, **{"gen_ai.tool.name": "search", "gen_ai.operation.name": op}),
            ],
        )
    ]
    s = _summary(total_tool_calls=8)
    results = _run_detectors(_detectors(), s, spans)
    assert "pattern_loop" in results


def test_tool_error_rate_detector_fires_on_errors() -> None:
    op = "execute_tool"
    spans = [
        _sp(
            "1",
            None,
            "invoke_agent",
            child_spans=[
                _sp(
                    "2",
                    "1",
                    op,
                    status="error",
                    **{"gen_ai.tool.name": "api_call", "gen_ai.operation.name": op},
                ),
                _sp(
                    "3",
                    "1",
                    op,
                    status="error",
                    **{"gen_ai.tool.name": "api_call", "gen_ai.operation.name": op},
                ),
                _sp(
                    "4",
                    "1",
                    op,
                    status="error",
                    **{"gen_ai.tool.name": "db_query", "gen_ai.operation.name": op},
                ),
                _sp(
                    "5",
                    "1",
                    op,
                    status="error",
                    **{"gen_ai.tool.name": "db_query", "gen_ai.operation.name": op},
                ),
                _sp(
                    "6",
                    "1",
                    op,
                    status="ok",
                    **{"gen_ai.tool.name": "http_get", "gen_ai.operation.name": op},
                ),
            ],
        )
    ]
    s = _summary(total_tool_calls=5)
    results = _run_detectors(_detectors(), s, spans)
    assert "tool_error_rate" in results


def test_specific_tool_error_detector_fires() -> None:
    op = "execute_tool"
    spans = [
        _sp(
            "1",
            None,
            "invoke_agent",
            child_spans=[
                _sp(
                    "2",
                    "1",
                    op,
                    status="error",
                    **{"gen_ai.tool.name": "flaky_api", "gen_ai.operation.name": op},
                ),
                _sp(
                    "3",
                    "1",
                    op,
                    status="error",
                    **{"gen_ai.tool.name": "flaky_api", "gen_ai.operation.name": op},
                ),
                _sp(
                    "4",
                    "1",
                    op,
                    status="error",
                    **{"gen_ai.tool.name": "flaky_api", "gen_ai.operation.name": op},
                ),
                _sp(
                    "5",
                    "1",
                    op,
                    status="error",
                    **{"gen_ai.tool.name": "flaky_api", "gen_ai.operation.name": op},
                ),
                _sp(
                    "6",
                    "1",
                    op,
                    status="ok",
                    **{"gen_ai.tool.name": "stable", "gen_ai.operation.name": op},
                ),
            ],
        )
    ]
    s = _summary(total_tool_calls=5)
    results = _run_detectors(_detectors(), s, spans)
    assert "specific_tool_error" in results


# ---------------------------------------------------------------------------
# Output detectors — depend on gen_ai.response.content
# ---------------------------------------------------------------------------


def test_low_output_detector_fires_on_short_response() -> None:
    spans = [
        _sp(
            "1",
            None,
            "invoke_agent",
            child_spans=[
                _sp("2", "1", "plan", **{"gen_ai.response.content": "OK"}),
            ],
        )
    ]
    results = _run_detectors(_detectors(), _summary(), spans)
    assert "low_output" in results


def test_empty_response_detector_fires() -> None:
    spans = [
        _sp(
            "1",
            None,
            "invoke_agent",
            child_spans=[
                _sp("2", "1", "plan", **{"gen_ai.response.content": ""}),
            ],
        )
    ]
    results = _run_detectors(_detectors(), _summary(), spans)
    assert "empty_response" in results


# ---------------------------------------------------------------------------
# Retry / recovery detectors — depend on error status and gen_ai.tool.name
# ---------------------------------------------------------------------------


def test_retry_storm_detector_fires_on_repeated_errors() -> None:
    op = "execute_tool"
    spans = [
        _sp(
            "1",
            None,
            "invoke_agent",
            child_spans=[
                _sp(
                    "2",
                    "1",
                    op,
                    status="error",
                    **{"gen_ai.tool.name": "retry_me", "gen_ai.operation.name": op},
                ),
                _sp(
                    "3",
                    "1",
                    op,
                    status="error",
                    **{"gen_ai.tool.name": "retry_me", "gen_ai.operation.name": op},
                ),
                _sp(
                    "4",
                    "1",
                    op,
                    status="error",
                    **{"gen_ai.tool.name": "retry_me", "gen_ai.operation.name": op},
                ),
                _sp(
                    "5",
                    "1",
                    op,
                    status="error",
                    **{"gen_ai.tool.name": "retry_me", "gen_ai.operation.name": op},
                ),
                _sp(
                    "6",
                    "1",
                    op,
                    status="error",
                    **{"gen_ai.tool.name": "retry_me", "gen_ai.operation.name": op},
                ),
                _sp(
                    "7",
                    "1",
                    op,
                    status="error",
                    **{"gen_ai.tool.name": "retry_me", "gen_ai.operation.name": op},
                ),
            ],
        )
    ]
    s = _summary(total_tool_calls=6, total_retries=6)
    results = _run_detectors(_detectors(), s, spans)
    assert "retry_storm" in results


def test_recovery_path_detector_fires_after_error_recovery() -> None:
    op = "execute_tool"
    spans = [
        _sp(
            "1",
            None,
            "invoke_agent",
            child_spans=[
                _sp(
                    "2",
                    "1",
                    op,
                    status="error",
                    **{"gen_ai.tool.name": "unstable", "gen_ai.operation.name": op},
                ),
                _sp(
                    "3",
                    "1",
                    op,
                    status="ok",
                    **{"gen_ai.tool.name": "fix_1", "gen_ai.operation.name": op},
                ),
                _sp(
                    "4",
                    "1",
                    op,
                    status="ok",
                    **{"gen_ai.tool.name": "fix_2", "gen_ai.operation.name": op},
                ),
                _sp(
                    "5",
                    "1",
                    op,
                    status="ok",
                    **{"gen_ai.tool.name": "fix_3", "gen_ai.operation.name": op},
                ),
                _sp(
                    "6",
                    "1",
                    op,
                    status="ok",
                    **{"gen_ai.tool.name": "fix_4", "gen_ai.operation.name": op},
                ),
                _sp(
                    "7",
                    "1",
                    op,
                    status="ok",
                    **{"gen_ai.tool.name": "fix_5", "gen_ai.operation.name": op},
                ),
                _sp(
                    "8",
                    "1",
                    op,
                    status="ok",
                    **{"gen_ai.tool.name": "fix_6", "gen_ai.operation.name": op},
                ),
            ],
        )
    ]
    s = _summary(total_tool_calls=7)
    results = _run_detectors(_detectors(), s, spans)
    assert "recovery_path" in results


# ---------------------------------------------------------------------------
# Cost detectors
# ---------------------------------------------------------------------------


def test_cost_spike_detector_fires_on_high_cost() -> None:
    op = "execute_tool"
    now = datetime.now(timezone.utc)
    spans = [
        _sp(
            "1",
            None,
            "invoke_agent",
            **{
                "gen_ai.agent.run_cost_total": 15.0,
            },
            child_spans=[
                _sp(
                    "2",
                    "1",
                    op,
                    start_time=now,
                    end_time=now + timedelta(seconds=5),
                    **{"gen_ai.tool.name": "expensive_op", "gen_ai.operation.name": op},
                ),
            ],
        ),
    ]
    s = _summary(duration_ms=5000, total_tool_calls=1, estimated_cost=15.0)
    results = _run_detectors(_detectors(), s, spans)
    assert "cost_spike" in results


# ---------------------------------------------------------------------------
# Runtime detectors
# ---------------------------------------------------------------------------


def test_max_step_hit_detector_fires() -> None:
    op = "execute_tool"
    spans: list[SpanNode] = [_sp("1", None, "invoke_agent", child_spans=[])]
    for i in range(51):
        sid = str(i + 2)
        spans[0].child_spans.append(
            _sp(sid, "1", op, **{"gen_ai.tool.name": f"step_{i}", "gen_ai.operation.name": op})
        )
    s = _summary(total_tool_calls=51, status="incomplete")
    results = _run_detectors(_detectors(), s, spans)
    assert "max_step_hit" in results


def test_step_efficiency_detector_fires_on_many_tool_calls() -> None:
    op = "execute_tool"
    spans: list[SpanNode] = [_sp("1", None, "invoke_agent", child_spans=[])]
    for i in range(25):
        sid = str(i + 2)
        spans[0].child_spans.append(
            _sp(sid, "1", op, **{"gen_ai.tool.name": f"tool_{i}", "gen_ai.operation.name": op})
        )
    s = _summary(total_tool_calls=25, status="success")
    results = _run_detectors(_detectors(), s, spans)
    assert "step_efficiency" in results


# ---------------------------------------------------------------------------
# Transient / cascading / systemic retry detectors
# ---------------------------------------------------------------------------


def test_transient_retry_detector_fires() -> None:
    op = "execute_tool"
    spans = [
        _sp(
            "1",
            None,
            "invoke_agent",
            child_spans=[
                _sp(
                    "2",
                    "1",
                    op,
                    status="error",
                    **{
                        "gen_ai.tool.name": "flake",
                        "gen_ai.operation.name": op,
                        "gen_ai.retry.successful": True,
                    },
                ),
                _sp(
                    "3",
                    "1",
                    op,
                    status="ok",
                    **{"gen_ai.tool.name": "flake", "gen_ai.operation.name": op},
                ),
                _sp(
                    "4",
                    "1",
                    op,
                    status="error",
                    **{
                        "gen_ai.tool.name": "flake",
                        "gen_ai.operation.name": op,
                        "gen_ai.retry.successful": True,
                    },
                ),
                _sp(
                    "5",
                    "1",
                    op,
                    status="ok",
                    **{"gen_ai.tool.name": "flake", "gen_ai.operation.name": op},
                ),
                _sp(
                    "6",
                    "1",
                    op,
                    status="error",
                    **{
                        "gen_ai.tool.name": "flake",
                        "gen_ai.operation.name": op,
                        "gen_ai.retry.successful": True,
                    },
                ),
                _sp(
                    "7",
                    "1",
                    op,
                    status="ok",
                    **{"gen_ai.tool.name": "flake", "gen_ai.operation.name": op},
                ),
            ],
        )
    ]
    s = _summary(total_tool_calls=6, total_retries=3)
    results = _run_detectors(_detectors(), s, spans)
    assert "transient_retry" in results


def test_cascading_retry_detector_fires() -> None:
    op = "execute_tool"
    spans = [
        _sp(
            "1",
            None,
            "invoke_agent",
            child_spans=[
                _sp(
                    "2",
                    "1",
                    op,
                    status="error",
                    **{
                        "gen_ai.tool.name": "step_a",
                        "gen_ai.operation.name": op,
                        "gen_ai.retry.count": 1,
                    },
                ),
                _sp(
                    "3",
                    "1",
                    op,
                    status="ok",
                    **{"gen_ai.tool.name": "step_a_retry", "gen_ai.operation.name": op},
                ),
                _sp(
                    "4",
                    "1",
                    op,
                    status="error",
                    **{
                        "gen_ai.tool.name": "step_b",
                        "gen_ai.operation.name": op,
                        "gen_ai.retry.count": 1,
                    },
                ),
                _sp(
                    "5",
                    "1",
                    op,
                    status="ok",
                    **{"gen_ai.tool.name": "step_b_retry", "gen_ai.operation.name": op},
                ),
                _sp(
                    "6",
                    "1",
                    op,
                    status="error",
                    **{
                        "gen_ai.tool.name": "step_c",
                        "gen_ai.operation.name": op,
                        "gen_ai.retry.count": 1,
                    },
                ),
                _sp(
                    "7",
                    "1",
                    op,
                    status="ok",
                    **{"gen_ai.tool.name": "step_c_retry", "gen_ai.operation.name": op},
                ),
            ],
        )
    ]
    s = _summary(total_tool_calls=6, total_retries=3)
    results = _run_detectors(_detectors(), s, spans)
    assert "cascading_retry" in results


def test_systemic_retry_detector_fires() -> None:
    op = "execute_tool"
    spans = [
        _sp(
            "1",
            None,
            "invoke_agent",
            child_spans=[
                _sp(
                    "2",
                    "1",
                    op,
                    status="error",
                    **{
                        "gen_ai.tool.name": "a",
                        "gen_ai.operation.name": op,
                        "gen_ai.retry.successful": False,
                    },
                ),
                _sp(
                    "3",
                    "1",
                    op,
                    status="error",
                    **{
                        "gen_ai.tool.name": "b",
                        "gen_ai.operation.name": op,
                        "gen_ai.retry.successful": False,
                    },
                ),
                _sp(
                    "4",
                    "1",
                    op,
                    status="error",
                    **{
                        "gen_ai.tool.name": "c",
                        "gen_ai.operation.name": op,
                        "gen_ai.retry.successful": False,
                    },
                ),
                _sp(
                    "5",
                    "1",
                    op,
                    status="error",
                    **{
                        "gen_ai.tool.name": "d",
                        "gen_ai.operation.name": op,
                        "gen_ai.retry.successful": False,
                    },
                ),
                _sp(
                    "6",
                    "1",
                    op,
                    status="error",
                    **{
                        "gen_ai.tool.name": "e",
                        "gen_ai.operation.name": op,
                        "gen_ai.retry.successful": False,
                    },
                ),
                _sp(
                    "7",
                    "1",
                    op,
                    status="error",
                    **{
                        "gen_ai.tool.name": "f",
                        "gen_ai.operation.name": op,
                        "gen_ai.retry.successful": False,
                    },
                ),
            ],
        )
    ]
    s = _summary(total_tool_calls=6, total_retries=6)
    results = _run_detectors(_detectors(), s, spans)
    assert "systemic_retry" in results


# ---------------------------------------------------------------------------
# Indeterminate / premature completion
# ---------------------------------------------------------------------------


def test_indeterminate_detector_fires_on_empty_output() -> None:
    spans = [
        _sp(
            "1",
            None,
            "invoke_agent",
            child_spans=[
                _sp(
                    "2",
                    "1",
                    "plan",
                    **{"gen_ai.response.content": "Request could not be completed properly"},
                ),
            ],
        )
    ]
    s = _summary(status=None)
    results = _run_detectors(_detectors(), s, spans)
    assert "indeterminate_status" in results


def test_premature_completion_detector_fires_on_short_run() -> None:
    spans = [
        _sp(
            "1",
            None,
            "invoke_agent",
            child_spans=[
                _sp("2", "1", "plan", **{"gen_ai.response.content": "done"}),
            ],
        )
    ]
    s = _summary(duration_ms=500, total_tool_calls=1, status="error")
    results = _run_detectors(_detectors(), s, spans)
    assert "premature_completion" in results


# ---------------------------------------------------------------------------
# Contract: detectors must NOT fire critical anomalies on clean runs
# ---------------------------------------------------------------------------


def test_clean_run_produces_no_critical_anomalies() -> None:
    op = "execute_tool"
    now = datetime.now(timezone.utc)
    spans = [
        _sp(
            "1",
            None,
            "invoke_agent",
            start_time=now,
            end_time=now + timedelta(seconds=30),
            **{"gen_ai.response.content": "Task completed successfully with all steps verified."},
            child_spans=[
                _sp(
                    "2",
                    "1",
                    "plan",
                    start_time=now,
                    end_time=now + timedelta(seconds=5),
                    **{"gen_ai.plan.content": "Plan: step 1 lookup, step 2 verify"},
                ),
                _sp(
                    "3",
                    "1",
                    op,
                    start_time=now,
                    end_time=now + timedelta(seconds=5),
                    status="ok",
                    **{"gen_ai.tool.name": "lookup", "gen_ai.operation.name": op},
                ),
                _sp(
                    "4",
                    "1",
                    op,
                    start_time=now,
                    end_time=now + timedelta(seconds=5),
                    status="ok",
                    **{"gen_ai.tool.name": "verify", "gen_ai.operation.name": op},
                ),
                _sp(
                    "5",
                    "1",
                    op,
                    start_time=now,
                    end_time=now + timedelta(seconds=5),
                    status="ok",
                    **{"gen_ai.tool.name": "report", "gen_ai.operation.name": op},
                ),
            ],
        ),
    ]
    s = _summary(duration_ms=30000, total_tool_calls=3)
    results = _run_detectors(_detectors(), s, spans)
    critical_anomalies = {k: v for k, v in results.items() if v.severity == "critical"}
    assert not critical_anomalies, (
        f"Clean run should not produce critical anomalies, got: {list(critical_anomalies.keys())}"
    )
