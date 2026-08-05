"""Tool execution anomaly detectors (8 detectors)."""

from __future__ import annotations

import json
import logging

from analytics.config import settings
from analytics.detectors.base import BaseDetector
from analytics.models import Anomaly, RunSummary, SpanNode

logger = logging.getLogger(__name__)


class LoopDetector(BaseDetector):
    """Detect runs where the same tool is called consecutively beyond a threshold."""

    anomaly_type = "loop"

    def __init__(
        self,
        threshold: int | None = None,
        polling_tool_allowlist: list[str] | None = None,
    ) -> None:
        self.threshold = threshold or settings.loop_threshold
        self.polling_tool_allowlist = polling_tool_allowlist or []

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        tool_calls = self._walk_tool_names(spans)

        max_consecutive = 0
        current = 0
        last_tool = ""
        repeated_tool = ""
        polled_tools_found: list[str] = []

        for tool_name in tool_calls:
            if tool_name in self.polling_tool_allowlist:
                polled_tools_found.append(tool_name)
                current = 0
                last_tool = ""
                continue
            if tool_name == last_tool and tool_name:
                current += 1
                if current > max_consecutive:
                    max_consecutive = current
                    repeated_tool = tool_name
            else:
                current = 1
                last_tool = tool_name

        if max_consecutive >= self.threshold:
            severity = self._severity(float(max_consecutive), float(self.threshold))
            evidence: dict[str, object] = {
                "tool_name": repeated_tool,
                "consecutive_calls": max_consecutive,
                "threshold": self.threshold,
            }
            if polled_tools_found:
                evidence["polled_tools_skipped"] = list(set(polled_tools_found))
            return self._build_anomaly(
                summary,
                severity,
                f"Tool '{repeated_tool}' called {max_consecutive} times consecutively",
                evidence,
            )
        return None


class PatternLoopDetector(BaseDetector):
    """Detect repeating tool call patterns (A->B->A->B cycles)."""

    anomaly_type = "pattern_loop"

    def __init__(
        self,
        window_size: int | None = None,
        polling_tool_allowlist: list[str] | None = None,
    ) -> None:
        self.window_size = window_size or settings.detector_pattern_loop_window
        self.polling_tool_allowlist = polling_tool_allowlist or []

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        tool_calls = self._walk_tool_names(spans)
        filtered = [t for t in tool_calls if t and t not in self.polling_tool_allowlist]

        if len(filtered) < self.window_size * 2:
            return None

        max_repeats = 0
        detected_pattern: tuple[str, ...] = ()

        for i in range(len(filtered) - self.window_size * 2 + 1):
            window1 = tuple(filtered[i : i + self.window_size])
            window2 = tuple(filtered[i + self.window_size : i + self.window_size * 2])

            if window1 == window2:
                repeats = 2
                j = i + self.window_size * 2
                while j + self.window_size <= len(filtered):
                    next_window = tuple(filtered[j : j + self.window_size])
                    if next_window == window1:
                        repeats += 1
                        j += self.window_size
                    else:
                        break
                if repeats > max_repeats:
                    max_repeats = repeats
                    detected_pattern = window1

        if max_repeats >= 2:
            severity = self._severity(float(max_repeats), 2.0)
            return self._build_anomaly(
                summary,
                severity,
                f"Repeating tool pattern {detected_pattern} detected {max_repeats} times",
                {
                    "pattern": list(detected_pattern),
                    "repeat_count": max_repeats,
                    "window_size": self.window_size,
                },
            )
        return None


class ArgumentLoopDetector(BaseDetector):
    """Detect same tool + same args repeats (stronger signal than name-only loop)."""

    anomaly_type = "argument_loop"

    def __init__(
        self,
        threshold: int | None = None,
        polling_tool_allowlist: list[str] | None = None,
    ) -> None:
        self.threshold = threshold or settings.detector_argument_loop_threshold
        self.polling_tool_allowlist = polling_tool_allowlist or []

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        tool_spans = self._walk_tool_spans(spans)

        max_consecutive = 0
        current = 0
        last_key = ""
        repeated_tool = ""

        for span in tool_spans:
            tool_name = str(span.attributes.get("gen_ai.tool.name", ""))
            if tool_name in self.polling_tool_allowlist:
                current = 0
                last_key = ""
                continue

            try:
                args_raw = span.attributes.get("gen_ai.tool.arguments")
                if args_raw is None:
                    args_raw = span.attributes.get("gen_ai.tool.args")
                if args_raw is None:
                    current = 0
                    last_key = ""
                    continue
                elif isinstance(args_raw, str):
                    args_str = args_raw
                else:
                    args_str = json.dumps(args_raw, sort_keys=True)
            except (TypeError, ValueError):
                current = 0
                last_key = ""
                continue

            key = f"{tool_name}:{args_str}"

            if key == last_key and key:
                current += 1
                if current > max_consecutive:
                    max_consecutive = current
                    repeated_tool = tool_name
            else:
                current = 1
                last_key = key

        if max_consecutive >= self.threshold:
            severity = self._severity(float(max_consecutive), float(self.threshold))
            return self._build_anomaly(
                summary,
                severity,
                f"Tool '{repeated_tool}' called with same "
                f"arguments {max_consecutive} times consecutively",
                {
                    "tool_name": repeated_tool,
                    "consecutive_calls": max_consecutive,
                    "threshold": self.threshold,
                },
            )
        return None


class ToolErrorRateDetector(BaseDetector):
    """Detect high error rate across all tool spans."""

    anomaly_type = "tool_error_rate"

    def __init__(self, threshold_pct: float | None = None) -> None:
        self.threshold_pct = threshold_pct or settings.detector_tool_error_rate_pct

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        tool_spans = self._walk_tool_spans(spans)
        total = len(tool_spans)
        if total == 0:
            return None

        errors = sum(1 for s in tool_spans if s.status and s.status not in ("ok", "OK"))
        error_rate = (errors / total) * 100

        if error_rate >= self.threshold_pct:
            severity = self._severity(error_rate, self.threshold_pct)
            return self._build_anomaly(
                summary,
                severity,
                f"Tool error rate {error_rate:.1f}% exceeds "
                f"threshold {self.threshold_pct}% ({errors}/{total})",
                {
                    "error_rate_pct": round(error_rate, 1),
                    "errors": errors,
                    "total_tool_spans": total,
                    "threshold_pct": self.threshold_pct,
                },
            )
        return None


class SpecificToolErrorDetector(BaseDetector):
    """Detect a single tool type with an error rate spike."""

    anomaly_type = "specific_tool_error"

    def __init__(self, threshold_pct: float | None = None) -> None:
        self.threshold_pct = threshold_pct or settings.detector_specific_tool_error_pct

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        tool_spans = self._walk_tool_spans(spans)
        tool_counts: dict[str, int] = {}
        tool_errors: dict[str, int] = {}

        for span in tool_spans:
            tool_name = str(span.attributes.get("gen_ai.tool.name", "unknown"))
            tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
            if span.status and span.status not in ("ok", "OK"):
                tool_errors[tool_name] = tool_errors.get(tool_name, 0) + 1

        for tool_name, count in tool_counts.items():
            if count < 2:
                continue
            errors = tool_errors.get(tool_name, 0)
            error_rate = (errors / count) * 100
            if error_rate >= self.threshold_pct:
                severity = self._severity(error_rate, self.threshold_pct)
                return self._build_anomaly(
                    summary,
                    severity,
                    f"Tool '{tool_name}' has error rate {error_rate:.1f}% ({errors}/{count})",
                    {
                        "tool_name": tool_name,
                        "error_rate_pct": round(error_rate, 1),
                        "errors": errors,
                        "total_calls": count,
                        "threshold_pct": self.threshold_pct,
                    },
                )
        return None


class ToolLatencyDetector(BaseDetector):
    """Detect tool calls whose duration exceeds a multiplier of the average."""

    anomaly_type = "tool_latency"

    def __init__(self, multiplier: float | None = None) -> None:
        self.multiplier = multiplier or settings.detector_tool_latency_multiplier

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        tool_spans = self._walk_tool_spans(spans)
        tool_durations: dict[str, list[int]] = {}

        for span in tool_spans:
            tool_name = str(span.attributes.get("gen_ai.tool.name", "unknown"))
            if span.duration_ms:
                tool_durations.setdefault(tool_name, []).append(span.duration_ms)

        for tool_name, durations in tool_durations.items():
            if len(durations) < 2:
                continue
            avg = sum(durations) / len(durations)
            if avg == 0:
                continue
            for i, dur in enumerate(durations):
                if dur > avg * self.multiplier:
                    severity = self._severity(float(dur) / max(avg, 1), float(self.multiplier))
                    return self._build_anomaly(
                        summary,
                        severity,
                        f"Tool '{tool_name}' call #{i + 1} "
                        f"duration {dur}ms is {dur / avg:.1f}x "
                        f"average ({avg:.0f}ms)",
                        {
                            "tool_name": tool_name,
                            "call_index": i,
                            "duration_ms": dur,
                            "average_duration_ms": round(avg, 0),
                            "multiplier": self.multiplier,
                            "ratio": round(dur / avg, 1),
                        },
                    )
        return None


class ToolTimeoutDetector(BaseDetector):
    """Detect any tool call that exceeds an absolute duration limit."""

    anomaly_type = "tool_timeout"

    def __init__(self, limit_seconds: float | None = None) -> None:
        self.limit_ms = (limit_seconds or settings.detector_tool_timeout_seconds) * 1000

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        tool_spans = self._walk_tool_spans(spans)

        for span in tool_spans:
            if span.duration_ms and span.duration_ms > self.limit_ms:
                tool_name = str(span.attributes.get("gen_ai.tool.name", "unknown"))
                severity = self._severity(float(span.duration_ms), float(self.limit_ms))
                return self._build_anomaly(
                    summary,
                    severity,
                    f"Tool '{tool_name}' call exceeded timeout: "
                    f"{span.duration_ms}ms > {self.limit_ms}ms",
                    {
                        "tool_name": tool_name,
                        "duration_ms": span.duration_ms,
                        "limit_ms": self.limit_ms,
                        "span_id": span.span_id,
                    },
                )
        return None


class RedundantToolCallDetector(BaseDetector):
    """Detect same tool called with same args, same result, no state change."""

    anomaly_type = "redundant_tool_call"

    def __init__(self, threshold: int | None = None) -> None:
        self.threshold = threshold or settings.detector_redundant_tool_threshold

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        tool_spans = self._walk_tool_spans(spans)
        if len(tool_spans) < 2:
            return None

        current_streak = 1
        max_streak = 1
        prev_key = ""

        for span in tool_spans:
            tool_name = str(span.attributes.get("gen_ai.tool.name", ""))
            try:
                args_raw = span.attributes.get("gen_ai.tool.arguments")
                if args_raw is None:
                    args_raw = span.attributes.get("gen_ai.tool.args")
                if args_raw is None:
                    current_streak = 1
                    prev_key = ""
                    continue
                elif isinstance(args_raw, str):
                    args_str = args_raw
                else:
                    args_str = json.dumps(args_raw, sort_keys=True)
            except (TypeError, ValueError):
                current_streak = 1
                prev_key = ""
                continue

            result_raw = span.attributes.get("gen_ai.tool.result")
            if result_raw is None:
                result_str = ""
            elif isinstance(result_raw, str):
                result_str = result_raw
            else:
                try:
                    result_str = json.dumps(result_raw, sort_keys=True)
                except (TypeError, ValueError):
                    result_str = str(result_raw)

            key = f"{tool_name}:{args_str}:{result_str}"

            if key == prev_key and key:
                current_streak += 1
                if current_streak > max_streak:
                    max_streak = current_streak
            else:
                current_streak = 1
                prev_key = key

        if max_streak >= self.threshold:
            severity = self._severity(float(max_streak), float(self.threshold))
            return self._build_anomaly(
                summary,
                severity,
                f"Redundant tool call pattern: same call-result repeated {max_streak} times",
                {
                    "redundant_count": max_streak,
                    "threshold": self.threshold,
                },
            )
        return None
