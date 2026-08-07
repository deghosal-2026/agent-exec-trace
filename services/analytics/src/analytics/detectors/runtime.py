"""Runtime and completion anomaly detectors (5 detectors)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from analytics.config import settings
from analytics.detectors.base import BaseDetector, _has_valid_pool
from analytics.models import Anomaly, RunSummary, SpanNode

logger = logging.getLogger(__name__)


class RunDurationDetector(BaseDetector):
    """Detect total run duration vs baseline (default 5x average)."""

    anomaly_type = "run_duration"

    def __init__(
        self,
        multiplier: float | None = None,
    ) -> None:
        self.multiplier = multiplier or settings.detector_run_duration_multiplier

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        return None

    async def detect_async(
        self,
        summary: RunSummary,
        spans: list[SpanNode],
        pool: Any = None,
    ) -> Anomaly | None:
        if summary.duration_ms is None or summary.duration_ms <= 0:
            return None
        if pool is None or not summary.agent_name:
            return None
        if not _has_valid_pool(pool):
            return None

        baseline = await self._get_duration_baseline(
            pool, summary.agent_name, summary.agent_version
        )
        if baseline is None or baseline <= 0:
            return None

        ratio = summary.duration_ms / baseline
        if ratio >= self.multiplier:
            severity = self._severity(ratio, self.multiplier)
            return self._build_anomaly(
                summary,
                severity,
                f"Run duration {summary.duration_ms}ms is {ratio:.1f}x baseline {baseline:.0f}ms",
                {
                    "duration_ms": summary.duration_ms,
                    "baseline_ms": round(baseline, 0),
                    "ratio": round(ratio, 1),
                    "multiplier": self.multiplier,
                },
            )
        return None

    @staticmethod
    async def _get_duration_baseline(
        pool: Any, agent_name: str, agent_version: str | None
    ) -> float | None:
        try:
            async with pool.acquire() as conn:
                if agent_version:
                    row = await conn.fetchrow(
                        "SELECT AVG(duration_ms) AS avg_dur FROM run_summaries "
                        "WHERE agent_name = $1 AND agent_version = $2 AND duration_ms IS NOT NULL",
                        agent_name,
                        agent_version,
                    )
                else:
                    row = await conn.fetchrow(
                        "SELECT AVG(duration_ms) AS avg_dur FROM run_summaries "
                        "WHERE agent_name = $1 AND duration_ms IS NOT NULL",
                        agent_name,
                    )
                if row is None:
                    return None
                val = row["avg_dur"]
                if val is None:
                    return None
                return float(val)
        except Exception:
            logger.debug("Failed to fetch duration baseline", exc_info=True)
            return None


class MaxStepHitDetector(BaseDetector):
    """Detect when the agent exhausted its step budget."""

    anomaly_type = "max_step_hit"

    def __init__(self) -> None:
        pass

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        min_spans_for_budget_exhausted = 20
        tool_spans = self._walk_tool_spans(spans)
        if len(tool_spans) < min_spans_for_budget_exhausted:
            return None

        status = (summary.status or "").lower()
        is_incomplete = status in ("incomplete", "max_steps_exceeded", "max_steps_hit")

        if not is_incomplete:
            all_spans = self._walk_spans(spans)
            plan_span_count = sum(1 for s in all_spans if s.operation_name in ("plan", "think"))
            if plan_span_count > 0 and len(tool_spans) > 50:
                is_incomplete = True

        if is_incomplete:
            return self._build_anomaly(
                summary,
                "warning",
                f"Agent exhausted step budget: "
                f"{len(tool_spans)} tool calls, status={summary.status}",
                {
                    "tool_calls": len(tool_spans),
                    "status": summary.status,
                },
            )
        return None


class StepEfficiencyDetector(BaseDetector):
    """Detect too many steps for a simple task."""

    anomaly_type = "step_efficiency"

    def __init__(self, max_tool_calls: int | None = None) -> None:
        self.max_tool_calls = max_tool_calls or settings.detector_step_efficiency_max_calls

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        tool_calls = summary.total_tool_calls
        if tool_calls > self.max_tool_calls and summary.status == "success":
            severity = self._severity(float(tool_calls), float(self.max_tool_calls))
            return self._build_anomaly(
                summary,
                severity,
                f"Inefficient: {tool_calls} tool calls for "
                f"a successful run (threshold: {self.max_tool_calls})",
                {
                    "tool_calls": tool_calls,
                    "threshold": self.max_tool_calls,
                    "status": summary.status,
                },
            )
        return None


class InactivityDetector(BaseDetector):
    """Detect long idle gaps between consecutive spans."""

    anomaly_type = "inactivity"

    def __init__(self, max_gap_seconds: float | None = None) -> None:
        self.max_gap_ms = (max_gap_seconds or settings.detector_inactivity_gap_seconds) * 1000

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        all_spans = self._walk_spans(spans)
        if len(all_spans) < 2:
            return None

        all_spans.sort(
            key=lambda s: (
                s.start_time
                if s.start_time is not None
                else datetime.min.replace(tzinfo=timezone.utc)
            )
        )

        max_gap_ms = 0
        gap_pair: tuple[str, str] = ("", "")

        for i in range(len(all_spans) - 1):
            curr = all_spans[i]
            nxt = all_spans[i + 1]

            if curr.start_time is None or nxt.start_time is None:
                continue

            gap = (nxt.start_time - curr.start_time).total_seconds() * 1000
            if gap > float(max_gap_ms):
                max_gap_ms = int(gap)
                gap_pair = (curr.span_id, nxt.span_id)

        if max_gap_ms > self.max_gap_ms:
            severity = self._severity(max_gap_ms, self.max_gap_ms)
            return self._build_anomaly(
                summary,
                severity,
                f"Long inactivity gap: {max_gap_ms:.0f}ms "
                f"between spans {gap_pair[0]} and {gap_pair[1]}",
                {
                    "max_gap_ms": round(max_gap_ms, 0),
                    "threshold_ms": self.max_gap_ms,
                    "from_span_id": gap_pair[0],
                    "to_span_id": gap_pair[1],
                },
            )
        return None


class PrematureCompletionDetector(BaseDetector):
    """Detect agent stopped before resolving (error status but no error spans)."""

    anomaly_type = "premature_completion"

    def __init__(self) -> None:
        pass

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        status = (summary.status or "").lower()

        all_spans = self._walk_spans(spans)
        output_content = self._extract_output(all_spans)
        error_spans = [
            s
            for s in all_spans
            if (s.status or "").strip().lower()
            in {
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
        ]

        if status == "error" and len(error_spans) == 0:
            return self._build_anomaly(
                summary,
                "warning",
                "Run marked as error but no error spans found — premature completion suspected",
                {
                    "status": summary.status,
                    "total_spans": len(all_spans),
                    "error_spans": 0,
                },
            )

        final_is_plan = bool(all_spans) and all_spans[-1].operation_name in ("plan", "think")
        successful_terminal_tool = any(
            s.operation_name == "execute_tool"
            and (s.status or "").strip().lower() in {"ok", "success", "completed"}
            for s in all_spans[-3:]
        )
        status_indicates_incomplete = status in {
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

        if (
            final_is_plan
            and status_indicates_incomplete
            and not output_content
            and not successful_terminal_tool
        ):
            return self._build_anomaly(
                summary,
                "warning",
                "Agent ended with a plan/think span — may not have completed the task",
                {
                    "final_span_operation": all_spans[-1].operation_name if all_spans else None,
                    "status": summary.status,
                    "total_spans": len(all_spans),
                    "has_output": bool(output_content),
                    "successful_terminal_tool": successful_terminal_tool,
                },
            )
        return None
