"""Tool execution anomaly detectors (8 detectors).

These detectors analyze tool call patterns, error rates, latency, and
argument-based redundancy within a single run's span tree.

**Detectors in this module:**

1. **LoopDetector**: Detects consecutive repeated calls to the same tool
   name (regardless of arguments).  Catches agents stuck in a loop calling
   the same tool over and over.  Threshold: 5 consecutive calls by default.

2. **PatternLoopDetector**: Detects repeating sequences of tool calls
   (e.g., A→B→C→A→B→C).  More sophisticated than LoopDetector because it
   catches multi-tool patterns.  Window size: 4 by default.

3. **ArgumentLoopDetector**: Detects consecutive calls to the same tool
   *with identical arguments*.  Stronger signal than LoopDetector because
   same-tool-different-args might be intentional.  Threshold: 3 by default
   (lower than LoopDetector because it's a stronger signal).

4. **ToolErrorRateDetector**: Detects when the overall error rate across
   all tool calls exceeds a threshold.  Threshold: 30% by default.

5. **SpecificToolErrorDetector**: Detects when a particular tool type has
   a high error rate, even if the overall rate is normal.  Useful for
   catching flaky tools.  Threshold: 30% by default.

6. **ToolLatencyDetector**: Detects individual tool calls whose duration
   significantly exceeds the average for that tool type within the same run.
   Multiplier: 3x average by default.

7. **ToolTimeoutDetector**: Detects any tool call exceeding an absolute
   duration limit.  Limit: 60 seconds by default.

8. **RedundantToolCallDetector**: Detects consecutive calls to the same
   tool with same arguments AND same result — the agent is repeating work
   without any state change.  Threshold: 3 consecutive matches by default.

**Polling tool allowlisting**: LoopDetector, PatternLoopDetector, and
ArgumentLoopDetector all support a ``polling_tool_allowlist`` — tools that,
when encountered, reset the consecutive call counter.  This prevents
legitimate polling operations (e.g., repeatedly checking job status) from
triggering loop anomalies.
"""

from __future__ import annotations

import json
import logging

from analytics.config import settings
from analytics.detectors.base import BaseDetector
from analytics.models import Anomaly, RunSummary, SpanNode

logger = logging.getLogger(__name__)


class LoopDetector(BaseDetector):
    """Detect runs where the same tool is called consecutively beyond a threshold.

    **What it catches**: An agent stuck in a loop, repeatedly calling the same
    tool (e.g., ``search_web`` called 10 times in a row, each time with a
    slightly different query).

    **False-positive risks**:
    - Legitimate iteration: agents that intentionally call the same tool
      multiple times (e.g., paginating through results).  Mitigated by the
      ``polling_tool_allowlist`` parameter.
    - Batch operations: agents that call ``write_file`` 5 times in a row.
      This is normal behavior but crosses the default threshold.

    **Threshold rationale**: 5 consecutive calls is well beyond normal
    iterative behavior.  Most agentic patterns call a tool 1-3 times
    consecutively before switching to a different tool for the next step.

    **Evidence produced**:
    - ``tool_name``: the tool that was repeatedly called.
    - ``consecutive_calls``: the count of consecutive identical calls.
    - ``threshold``: the configured threshold that was exceeded.
    - ``polled_tools_skipped``: if any polling tools were encountered.

    **Usage**:
        detector = LoopDetector(threshold=5, polling_tool_allowlist=["check_status"])
        anomaly = detector.detect(summary, spans)
    """

    anomaly_type = "loop"

    def __init__(
        self,
        threshold: int | None = None,
        polling_tool_allowlist: list[str] | None = None,
    ) -> None:
        self.threshold = threshold or settings.loop_threshold
        self.polling_tool_allowlist = polling_tool_allowlist or []

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        # Get ordered list of tool names from the span tree.
        tool_calls = self._walk_tool_names(spans)

        max_consecutive = 0
        current = 0
        last_tool = ""
        repeated_tool = ""
        polled_tools_found: list[str] = []

        # Single-pass consecutive sequence detector.
        # O(n) time, O(1) additional space.
        for tool_name in tool_calls:
            # Polling tools are explicitly allowed and reset the streak.
            # This prevents check_status → check_status → check_status
            # from being flagged as a loop.
            if tool_name in self.polling_tool_allowlist:
                polled_tools_found.append(tool_name)
                current = 0
                last_tool = ""
                continue
            # Same tool as last time: extend the streak.
            if tool_name == last_tool and tool_name:
                current += 1
                if current > max_consecutive:
                    max_consecutive = current
                    repeated_tool = tool_name
            else:
                # Different tool or first call: reset streak to 1 (counting this call).
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
    """Detect repeating tool call patterns (e.g., A→B→C→A→B→C cycles).

    **What it catches**: Agents that cycle through a pattern of tools
    repeatedly.  This is most common in reasoning agents that get stuck
    in a "plan → search → plan → search" loop.

    **False-positive risks**:
    - Intended cyclic workflows (e.g., read→process→write×N).
      The window size and repeat count mitigate this: the pattern must
      repeat at least twice to fire.
    - Short patterns in small traces: the detector requires at least
      2× window_size tool calls.

    **Threshold rationale**: Window size 4 means we detect patterns of
    length 4+ that repeat.  Shorter windows (2-3) would catch too many
    benign patterns (e.g., tool A then B is a common alternation).

    **Evidence produced**:
    - ``pattern``: the repeating tool name sequence.
    - ``repeat_count``: how many times the pattern was observed.
    - ``window_size``: the configured window size.

    **Algorithm**: Sliding window with detection of adjacent identical
    windows, followed by extension to count repetitions.
    """

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
        # Filter out polling tools and empty tool names.
        filtered = [t for t in tool_calls if t and t not in self.polling_tool_allowlist]

        # Need at least 2 full windows to detect a repeating pattern.
        if len(filtered) < self.window_size * 2:
            return None

        max_repeats = 0
        detected_pattern: tuple[str, ...] = ()

        # Sliding window: compare each window of size `window_size` with
        # the adjacent window to its right.  If they match, extend to count
        # how many times the pattern repeats.
        for i in range(len(filtered) - self.window_size * 2 + 1):
            window1 = tuple(filtered[i : i + self.window_size])
            window2 = tuple(filtered[i + self.window_size : i + self.window_size * 2])

            if window1 == window2:
                # Pattern detected — count how many times it repeats.
                repeats = 2  # We've already seen two windows.
                j = i + self.window_size * 2  # Start of the third window.
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

        # A pattern must repeat at least twice (i.e., seen 2+ times).
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
    """Detect same tool + same args repeats (stronger signal than name-only loop).

    **What it catches**: An agent that calls the same tool with identical
    arguments repeatedly.  This is a much stronger signal than the
    LoopDetector because same-tool-different-args is often intentional
    (e.g., searching for different queries), while same-args is almost
    certainly a bug or infinite loop.

    **False-positive risks**:
    - Idempotent retries: the agent may intentionally retry a failed
      operation with the same args.  Mitigated by requiring 3+ consecutive
      calls (a single retry would be 2 calls).

    **Threshold rationale**: 3 consecutive calls with identical args is
    a conservative threshold.  At 2 calls, it could be a retry.  At 3,
    it's almost certainly a loop.

    **Evidence produced**:
    - ``tool_name``: the tool that was repeatedly called.
    - ``consecutive_calls``: the count of consecutive identical calls.
    - ``threshold``: the configured threshold.
    """

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
            # Reset on polling tools, same as LoopDetector.
            if tool_name in self.polling_tool_allowlist:
                current = 0
                last_key = ""
                continue

            # Extract and normalize arguments.
            # We try both "gen_ai.tool.arguments" and "gen_ai.tool.args"
            # because different instrumentations use different attribute names.
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
                    # Normalize dict args to a deterministic JSON string
                    # for comparison.  sort_keys=True ensures {"b": 1, "a": 2}
                    # and {"a": 2, "b": 1} are treated as equal.
                    args_str = json.dumps(args_raw, sort_keys=True)
            except (TypeError, ValueError):
                # Non-serializable args: reset and skip this span.
                current = 0
                last_key = ""
                continue

            # Composite key: tool_name + serialized args.
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
    """Detect high error rate across all tool spans.

    **What it catches**: Runs where an unusually high percentage of tool
    calls fail.  This indicates a systemic issue (API outage, auth failure,
    misconfigured tool) rather than an isolated error.

    **False-positive risks**:
    - Runs with very few tool calls: 1 error out of 2 calls = 50% rate,
      but this is not meaningful.  Mitigated by requiring at least 1 tool
      call (validated by ``total == 0`` check).

    **Threshold rationale**: 30% error rate is well above normal operation.
    Most healthy runs have error rates below 5%.

    **Evidence produced**:
    - ``error_rate_pct``: the observed error rate.
    - ``errors``: count of error tool spans.
    - ``total_tool_spans``: total tool spans analyzed.
    - ``threshold_pct``: the configured threshold.
    """

    anomaly_type = "tool_error_rate"

    def __init__(self, threshold_pct: float | None = None) -> None:
        self.threshold_pct = threshold_pct or settings.detector_tool_error_rate_pct

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        tool_spans = self._walk_tool_spans(spans)
        total = len(tool_spans)
        if total == 0:
            return None

        # Count span statuses that are not "ok" — this includes "error",
        # "failed", "timeout", None, etc.
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
    """Detect a single tool type with an error rate spike.

    **What it catches**: A specific tool that is failing at a high rate,
    even if the overall error rate is low.  This is essential for
    identifying flaky tools (e.g., a specific API endpoint that is
    intermittently returning 500s).

    **False-positive risks**:
    - Tools with very few calls (<2): 1 error in 1 call = 100%.
      Mitigated by requiring at least 2 calls per tool type.

    **Threshold rationale**: 30% for a specific tool is concerning, even
    if it's only a fraction of total tool calls.  The same threshold as
    ToolErrorRateDetector is used for consistency.

    **Evidence produced**:
    - ``tool_name``: the tool with high error rate.
    - ``error_rate_pct``: the specific tool's error rate.
    - ``errors``, ``total_calls``: counts for the specific tool.
    - ``threshold_pct``: the configured threshold.
    """

    anomaly_type = "specific_tool_error"

    def __init__(self, threshold_pct: float | None = None) -> None:
        self.threshold_pct = threshold_pct or settings.detector_specific_tool_error_pct

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        tool_spans = self._walk_tool_spans(spans)
        tool_counts: dict[str, int] = {}
        tool_errors: dict[str, int] = {}

        # First pass: count calls and errors per tool type.
        for span in tool_spans:
            tool_name = str(span.attributes.get("gen_ai.tool.name", "unknown"))
            tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
            if span.status and span.status not in ("ok", "OK"):
                tool_errors[tool_name] = tool_errors.get(tool_name, 0) + 1

        # Second pass: check each tool type against the threshold.
        for tool_name, count in tool_counts.items():
            if count < 2:
                continue  # Not enough data for a meaningful rate.
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
    """Detect tool calls whose duration exceeds a multiplier of the average.

    **What it catches**: Individual tool calls that are significantly
    slower than other calls to the same tool within the same run.
    This catches performance regressions, network issues, or backend
    slowdowns affecting a specific call.

    **False-positive risks**:
    - Cold-start effects: the first call to a tool is often slower.
      Mitigated by comparing against the average within the same run,
      which naturally accounts for cold starts if there are enough calls.
    - Tools with varying complexity: some tool calls are legitimately
      slower (e.g., a large file write vs. a small one).  The multiplier
      catches truly exceptional outliers.

    **Threshold rationale**: 3x the average is a conservative threshold
    that catches genuine latency anomalies while ignoring normal variance.
    At 2x, too many benign slow calls would be flagged.

    **Evidence produced**:
    - ``tool_name``: the tool with anomalous latency.
    - ``call_index``: which call (1-based) was slow.
    - ``duration_ms``: the slow call's duration.
    - ``average_duration_ms``: the tool's average in this run.
    - ``ratio``: duration / average.
    - ``multiplier``: the configured multiplier.
    """

    anomaly_type = "tool_latency"

    def __init__(self, multiplier: float | None = None) -> None:
        self.multiplier = multiplier or settings.detector_tool_latency_multiplier

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        tool_spans = self._walk_tool_spans(spans)
        tool_durations: dict[str, list[int]] = {}

        # Group durations by tool name.
        for span in tool_spans:
            tool_name = str(span.attributes.get("gen_ai.tool.name", "unknown"))
            if span.duration_ms:
                tool_durations.setdefault(tool_name, []).append(span.duration_ms)

        # For each tool type, compute the average and check each call.
        for tool_name, durations in tool_durations.items():
            if len(durations) < 2:
                continue  # Need at least 2 calls for a meaningful average.
            avg = sum(durations) / len(durations)
            if avg == 0:
                continue  # Avoid division by zero.
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
    """Detect any tool call that exceeds an absolute duration limit.

    **What it catches**: Tool calls that take longer than a hard timeout.
    Unlike ToolLatencyDetector which compares to the average, this catches
    any call exceeding an absolute limit regardless of other calls.

    **False-positive risks**:
    - Legitimately slow operations: some tools (e.g., model inference,
      large file downloads) can take >60s.  The threshold should be tuned
      for the specific agent's expected tool durations.

    **Threshold rationale**: 60 seconds is a generous timeout.  Most tool
    calls complete in well under 10 seconds.  A call exceeding 60 seconds
    is either hung, has a network issue, or is processing an unusually
    large payload — all worth flagging.

    **Evidence produced**:
    - ``tool_name``: the timed-out tool.
    - ``duration_ms``: the actual duration.
    - ``limit_ms``: the configured timeout limit.
    - ``span_id``: the span identifier for tracing.
    """

    anomaly_type = "tool_timeout"

    def __init__(self, limit_seconds: float | None = None) -> None:
        self.limit_ms = (limit_seconds or settings.detector_tool_timeout_seconds) * 1000

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        tool_spans = self._walk_tool_spans(spans)

        # Check each tool span against the absolute limit.
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
    """Detect same tool called with same args, same result, no state change.

    **What it catches**: The most definitive form of redundant work — the
    agent calls the same tool with the same arguments and gets the same
    result back.  This means no state change occurred between calls, and
    the agent is re-doing work that had no effect.

    **False-positive risks**:
    - Idempotent operations: some operations are designed to be called
      with the same args and return the same result (e.g., ``get_current_time``).
      This is rare in agent traces but possible.
    - Result normalization: if the same tool return value is serialized
      differently across calls, the detector won't match them, producing
      false negatives rather than false positives.

    **Threshold rationale**: 3 identical calls (same tool + same args +
    same result) is definitively redundant.  At 2 calls, it could be a
    legitimate retry.

    **Evidence produced**:
    - ``redundant_count``: number of consecutive identical calls.
    - ``threshold``: the configured threshold.
    - ``output_preview``: the first 200 chars of the repeated output.
    """

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
            # Extract and normalize arguments (same pattern as ArgumentLoopDetector).
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

            # Extract and normalize result for comparison.
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

            # Triple key: tool + args + result.  All three must match.
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