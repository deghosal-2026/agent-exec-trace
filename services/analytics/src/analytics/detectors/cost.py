"""Cost and resource anomaly detectors (6 detectors).

These detectors analyze cost metrics, token usage, and tool efficiency
across individual runs and relative to version cohort baselines.

**Detectors in this module:**

1. **CostSpikeDetector**: Detects runs whose cost exceeds both absolute
   ($5 default) and relative (2x baseline) thresholds.  Uses dual-mode
   detection (sync stub for compatibility, async for real work).

2. **CostVsBaselineDetector**: Pure relative detection — compares run cost
   to the version cohort baseline.  2x multiplier by default.

3. **CostEfficiencyDetector**: Detects bad cost efficiency — either high
   cost-per-tool (>$0.50) or too many tool calls (>20) for a successful run.

4. **TokenExplosionDetector**: Detects when token counts grow dramatically
   across the span tree (late half > 3x early half).  Catches models that
   become increasingly verbose or enter "rambling" states.

5. **PerToolCostSpikeDetector**: Identifies which specific tool type is
   driving cost by analyzing tool call share (>50%) and dominance ratio.

6. **WastedToolCallsDetector**: Detects tool calls producing the same output
   across different tools — the agent is calling different tools but getting
   identical results, suggesting the calls are wasted.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Awaitable
from typing import Any, NoReturn, overload

from analytics.config import settings
from analytics.detectors.base import BaseDetector, _has_valid_pool
from analytics.models import Anomaly, RunSummary, SpanNode

logger = logging.getLogger(__name__)


_SENTINEL = object()


class CostSpikeDetector(BaseDetector):
    """Detect runs whose cost exceeds thresholds (absolute and relative to baseline).

    **What it catches**: Runs where the estimated cost exceeds:
    - An absolute threshold ($5.00 by default).
    - A relative threshold (2x the version cohort baseline).

    **False-positive risks**:
    - Runs with legitimately high costs because the task was complex.
      The 2x baseline helps: if all runs cost $4, a $5 run is anomalous;
      if all runs cost $10, a $5 run is not flagged.
    - Missing baseline data: if no baseline exists for the version,
      only the absolute threshold is checked.

    **Dual-mode design**: This detector's ``detect()`` is overloaded:
    - When called without ``pool``: raises ``NotImplementedError`` so the
      caller falls back to ``detect_async``.
    - When called with ``pool``: returns an awaitable that performs the
      real async detection (baseline query + threshold check).

    This pattern exists for backward compatibility — the worker's Phase 1
    detection always uses the async path.

    **Threshold rationale**:
    - Absolute $5: most agent runs cost well under $1 (a few LLM calls).
      $5+ suggests an unusually expensive run.
    - Baseline 2x: a run costing twice the version average is worth
      investigation, regardless of the absolute value.
    - Critical at $15 (3x absolute): cost is high enough to warrant
      immediate attention.

    **Evidence produced**:
    - ``cost``: the run's estimated cost.
    - ``absolute_threshold``: the configured absolute threshold.
    - ``baseline_cost``: the version cohort baseline (if available).
    - ``baseline_multiplier``: the configured baseline multiplier.
    """

    anomaly_type = "cost_spike"

    def __init__(
        self,
        absolute_threshold: float | None = None,
        baseline_multiplier: float | None = None,
        min_baseline_run_count: int | None = None,
    ) -> None:
        self.absolute_threshold = absolute_threshold or settings.cost_threshold_usd
        self.baseline_multiplier = baseline_multiplier or settings.detector_cost_baseline_multiplier
        self.min_baseline_run_count = (
            min_baseline_run_count or settings.detector_cost_min_baseline_runs
        )

    @overload
    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> NoReturn: ...

    @overload
    def detect(
        self, summary: RunSummary, spans: list[SpanNode], *, pool: Any
    ) -> Awaitable[Anomaly | None]: ...

    def detect(self, summary: RunSummary, spans: list[SpanNode], pool: Any = _SENTINEL) -> Any:
        """Dual-mode detect.

        - When called without the optional 'pool' argument (e.g., factory
          smoke tests), raise NotImplementedError so callers fall back to
          ``detect_async`` or skip.
        - When called with 'pool' (even if None), return an awaitable and
          perform the real async detection logic.

        This design allows the detector to work in both the validator's
        batch loop (which calls ``detect_async`` directly) and the worker's
        Phase 1 detection (which passes ``pool`` to ``detect``).
        """
        if pool is _SENTINEL:
            raise NotImplementedError

        async def _run() -> Anomaly | None:
            return await self.detect_async(summary, spans, pool=pool)

        return _run()

    async def detect_async(
        self,
        summary: RunSummary,
        spans: list[SpanNode],
        pool: Any = None,
    ) -> Anomaly | None:
        cost = summary.estimated_cost
        if cost is None:
            return None

        reasons: list[str] = []

        # Check 1: Absolute threshold.
        if cost > self.absolute_threshold:
            reasons.append(f"absolute spike: ${cost:.2f} exceeds ${self.absolute_threshold:.2f}")

        # Check 2: Relative to version cohort baseline (requires database pool).
        baseline: float | None = None
        if pool is not None and summary.agent_name and summary.agent_version:
            from analytics.ingest import _get_version_cohort_baseline

            baseline = await _get_version_cohort_baseline(
                pool, summary.agent_name, summary.agent_version
            )
            if baseline is not None and baseline > 0 and cost > baseline * self.baseline_multiplier:
                reasons.append(
                    f"relative spike: ${cost:.2f} is {cost / baseline:.1f}x "
                    f"baseline ${baseline:.2f} (multiplier: {self.baseline_multiplier})"
                )

        if not reasons:
            return None

        # Severity: critical if cost > 3x absolute threshold ($15 by default).
        severity: str = "warning"
        if cost > self.absolute_threshold * 3:
            severity = "critical"

        evidence: dict[str, object] = {
            "cost": cost,
            "absolute_threshold": self.absolute_threshold,
        }
        if baseline is not None:
            evidence["baseline_cost"] = baseline
            evidence["baseline_multiplier"] = self.baseline_multiplier

        return self._build_anomaly(summary, severity, "; ".join(reasons), evidence)


class CostVsBaselineDetector(BaseDetector):
    """Detect cost vs version cohort baseline (2x multiplier default).

    **What it catches**: Purely relative cost comparison — this detector
    does NOT check an absolute threshold.  It only fires when the run's
    cost exceeds the version cohort baseline by the configured multiplier.

    **Why separate from CostSpikeDetector?**  This detector gives a
    cleaner signal when operators want pure relative detection without
    the noise of absolute thresholds.  The two can fire independently
    on the same run, providing complementary evidence.

    **False-positive risks**:
    - Small sample sizes: if the cohort has only a few runs, the baseline
      is sensitive to outliers.  Mitigated by requiring valid pool and
      agent name/version metadata.

    **Evidence produced**:
    - ``cost``, ``baseline``, ``ratio``, ``multiplier``.
    """

    anomaly_type = "cost_vs_baseline"

    def __init__(
        self,
        multiplier: float | None = None,
        min_baseline_run_count: int | None = None,
    ) -> None:
        self.multiplier = multiplier or settings.detector_cost_vs_baseline_multiplier
        self.min_baseline_run_count = (
            min_baseline_run_count or settings.detector_cost_min_baseline_runs
        )

    def detect(
        self, summary: RunSummary, spans: list[SpanNode], pool: Any = None
    ) -> Anomaly | None:
        # Sync path always returns None; real work in detect_async.
        return None

    async def detect_async(
        self,
        summary: RunSummary,
        spans: list[SpanNode],
        pool: Any = None,
    ) -> Anomaly | None:
        cost = summary.estimated_cost
        if cost is None or cost <= 0:
            return None
        if pool is None or not summary.agent_name or not summary.agent_version:
            return None
        if not _has_valid_pool(pool):
            return None

        from analytics.ingest import _get_version_cohort_baseline

        baseline = await _get_version_cohort_baseline(
            pool, summary.agent_name, summary.agent_version
        )

        # No baseline data yet — skip detection for this run.
        if baseline is None or baseline <= 0:
            return None

        ratio = cost / baseline
        if ratio >= self.multiplier:
            severity = self._severity(ratio, self.multiplier)
            return self._build_anomaly(
                summary,
                severity,
                f"Run cost ${cost:.2f} is {ratio:.1f}x version cohort baseline of ${baseline:.2f}",
                {
                    "cost": cost,
                    "baseline": baseline,
                    "ratio": round(ratio, 1),
                    "multiplier": self.multiplier,
                },
            )
        return None


class CostEfficiencyDetector(BaseDetector):
    """Detect low cost efficiency: high cost with few tools or low cost with many tools.

    Checks two cases:
    1. **High cost-per-tool**: cost / tool_calls > $0.50.  Each tool call is
       expensive, suggesting expensive model calls wrapped as tools.
    2. **Too many tool calls for success**: >20 tool calls in a successful
       run suggests inefficiency — the agent took many steps to achieve what
       could have been done in fewer.

    **Why only successful runs?**  Failed runs naturally have many tool calls
    (the agent kept trying).  Flagging them as inefficient is redundant with
    other detectors (retry storms, error rates).  Only successful runs are
    checked for efficiency.

    **False-positive risks**:
    - Complex tasks that legitimately need many tool calls (e.g., code
      generation with multiple file writes).  The threshold (20) is
      conservative but may need tuning per workload type.

    **Evidence produced**:
    - ``cost``, ``tool_calls``, ``cost_per_tool``, ``threshold``.
    - Or ``max_efficient`` with ``tool_calls`` for the too-many-calls path.
    """

    anomaly_type = "cost_efficiency"

    def __init__(
        self,
        high_cost_per_tool_threshold: float | None = None,
        max_efficient_tool_calls: int | None = None,
    ) -> None:
        self.high_cost_per_tool_threshold = (
            high_cost_per_tool_threshold or settings.detector_cost_per_tool_high
        )
        self.max_efficient_tool_calls = (
            max_efficient_tool_calls or settings.detector_cost_efficiency_max_calls
        )

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        cost = summary.estimated_cost
        if cost is None or cost <= 0:
            return None
        # Only check efficiency for successful runs.
        if summary.status != "success":
            return None

        tool_calls = summary.total_tool_calls
        if tool_calls == 0:
            return None  # No tool calls to evaluate efficiency for.

        cost_per_tool = cost / tool_calls

        # Case 1: Each individual tool call is too expensive.
        if cost_per_tool > self.high_cost_per_tool_threshold:
            severity = self._severity(cost_per_tool, self.high_cost_per_tool_threshold)
            return self._build_anomaly(
                summary,
                severity,
                f"High cost efficiency: ${cost_per_tool:.2f}/tool "
                f"({tool_calls} calls, ${cost:.2f} total)",
                {
                    "cost": cost,
                    "tool_calls": tool_calls,
                    "cost_per_tool": round(cost_per_tool, 4),
                    "threshold": self.high_cost_per_tool_threshold,
                },
            )

        # Case 2: Too many tool calls for a successful run.
        if tool_calls > self.max_efficient_tool_calls:
            severity = self._severity(float(tool_calls), float(self.max_efficient_tool_calls))
            return self._build_anomaly(
                summary,
                severity,
                f"Too many tool calls ({tool_calls}) for a successful run (cost: ${cost:.2f})",
                {
                    "tool_calls": tool_calls,
                    "max_efficient": self.max_efficient_tool_calls,
                    "cost": cost,
                },
            )
        return None


class TokenExplosionDetector(BaseDetector):
    """Detect token count growing dramatically over the span tree.

    **What it catches**: Models that become increasingly verbose as the run
    progresses.  This compares the average token count in the first half of
    spans vs. the second half.  A ratio >= 3x indicates token explosion.

    **Why compare halves?**  Token count naturally grows as the conversation
    lengthens (due to context).  Comparing first vs. second half captures
    whether the growth is disproportionate — a 3x increase from the early
    conversation to the late conversation suggests the model is rambling,
    repeating itself, or generating unnecessarily verbose responses.

    **Token extraction**: Pulls ``gen_ai.usage.prompt_tokens`` and
    ``gen_ai.usage.completion_tokens`` from span attributes and sums them.
    This covers both input tokens (which grow with conversation length) and
    output tokens (which indicate verbosity).

    **False-positive risks**:
    - Runs with very few spans (<4): not enough data for a meaningful split.
      Mitigated by the minimum span count check.
    - Runs where early spans happen to have no token data: the early average
      would be 0, creating an infinite ratio.  Mitigated by the
      ``early_avg == 0`` guard.

    **Evidence produced**:
    - ``early_avg_tokens``, ``late_avg_tokens``, ``ratio``, ``multiplier``.

    **Threshold rationale**: 3x growth from early to late conversation is a
    strong signal.  Normal conversation growth is typically 1.5-2x as context
    accumulates.
    """

    anomaly_type = "token_explosion"

    def __init__(self, growth_multiplier: float | None = None) -> None:
        self.growth_multiplier = growth_multiplier or settings.detector_token_explosion_multiplier

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        all_spans = self._walk_spans(spans)
        if len(all_spans) < 4:
            return None  # Need enough spans for a meaningful split.

        early_tokens: list[int] = []
        late_tokens: list[int] = []

        # Split spans approximately in half.  Integer division is fine here
        # — the halves don't need to be exactly equal.
        half = len(all_spans) // 2
        for i, span in enumerate(all_spans):
            tokens = self._extract_tokens(span)
            if tokens > 0:
                if i < half:
                    early_tokens.append(tokens)
                else:
                    late_tokens.append(tokens)

        # Both halves must have at least one span with tokens.
        if not early_tokens or not late_tokens:
            return None

        early_avg = sum(early_tokens) / len(early_tokens)
        late_avg = sum(late_tokens) / len(late_tokens)

        if early_avg == 0:
            return None  # Prevent division by zero.

        ratio = late_avg / early_avg
        if ratio >= self.growth_multiplier:
            severity = self._severity(ratio, self.growth_multiplier)
            return self._build_anomaly(
                summary,
                severity,
                f"Token explosion: late avg {late_avg:.0f} tokens "
                f"vs early avg {early_avg:.0f} ({ratio:.1f}x)",
                {
                    "early_avg_tokens": round(early_avg, 0),
                    "late_avg_tokens": round(late_avg, 0),
                    "ratio": round(ratio, 1),
                    "multiplier": self.growth_multiplier,
                },
            )
        return None

    @staticmethod
    def _extract_tokens(span: SpanNode) -> int:
        """Extract total token count (prompt + completion) from a span's attributes.

        Handles the case where token counts come as strings (from parquet
        conversion) or ints/floats (from direct OTel instrumentation).
        """
        attrs = span.attributes
        prompt_tokens = 0
        completion_tokens = 0
        _pts = attrs.get("gen_ai.usage.prompt_tokens", 0)
        if isinstance(_pts, int | float | str):
            with contextlib.suppress(TypeError, ValueError):
                prompt_tokens += int(_pts)
        _cts = attrs.get("gen_ai.usage.completion_tokens", 0)
        if isinstance(_cts, int | float | str):
            with contextlib.suppress(TypeError, ValueError):
                completion_tokens += int(_cts)
        return prompt_tokens + completion_tokens


class PerToolCostSpikeDetector(BaseDetector):
    """Detect which specific tool type is driving cost.

    **What it catches**: When a single tool type dominates the cost of a run
    (e.g., 80% of total cost comes from "search" tool calls).  This helps
    identify which tool is the cost bottleneck.

    **Algorithm**: For each tool type, computes:
    1. Its share of total tool calls (tool_count / total_spans).
    2. Its estimated cost (share * total_cost).
    3. Dominance ratio: share / (1 - share), i.e., how many times more
       common this tool is than all others combined.

    If share > 50% AND count >= 3 AND dominance ratio >= multiplier (2x):
    → fire anomaly.

    **False-positive risks**:
    - Runs dominated by a single tool type by design (e.g., a search-intensive
      task where "search_web" is the only tool used).  The 50% share and
      dominance ratio thresholds are intentionally conservative.

    **Evidence produced**:
    - ``tool_name``, ``tool_calls``, ``total_tool_calls``, ``tool_share_pct``,
      ``est_tool_cost``, ``total_cost``, ``dominance_ratio``, ``multiplier``.
    """

    anomaly_type = "per_tool_cost_spike"

    def __init__(self, multiplier: float | None = None) -> None:
        self.multiplier = multiplier or settings.detector_per_tool_cost_multiplier

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        cost = summary.estimated_cost
        if cost is None or cost <= 0:
            return None

        tool_spans = self._walk_tool_spans(spans)
        if not tool_spans:
            return None

        # Count calls per tool type.
        tool_counts: dict[str, int] = {}
        for span in tool_spans:
            tool_name = str(span.attributes.get("gen_ai.tool.name", "unknown"))
            tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

        total_spans = len(tool_spans)

        # Check each tool type for cost dominance.
        for tool_name, count in tool_counts.items():
            share = count / total_spans
            if share > 0.5 and count >= 3:
                est_cost_for_tool = share * cost
                other_share = 1.0 - share
                # Avoid division by zero: if share is 1.0 (only one tool),
                # other_share is 0.0.  Use a small epsilon.
                dominance_ratio = share / max(other_share, 0.0001)

                if dominance_ratio >= self.multiplier:
                    severity = self._severity(dominance_ratio, self.multiplier)
                    return self._build_anomaly(
                        summary,
                        severity,
                        f"Tool '{tool_name}' dominates cost: "
                        f"{count}/{total_spans} calls "
                        f"(${est_cost_for_tool:.2f} of ${cost:.2f})",
                        {
                            "tool_name": tool_name,
                            "tool_calls": count,
                            "total_tool_calls": total_spans,
                            "tool_share_pct": round(share * 100, 1),
                            "est_tool_cost": round(est_cost_for_tool, 2),
                            "total_cost": cost,
                            "dominance_ratio": round(dominance_ratio, 2),
                            "multiplier": self.multiplier,
                        },
                    )
        return None


class WastedToolCallsDetector(BaseDetector):
    """Detect tool calls producing no effect (identical output across different tools).

    **What it catches**: When the agent calls different tools but gets the
    same result back.  This means the tool calls had no effect — either the
    tools are all returning the same error/default response, or the agent
    is calling the wrong tools.

    **Algorithm**: Groups tool calls by their result (serialized as JSON).
    If a result appears N+ times (threshold: 3) across different tool types,
    flags those calls as wasted.

    **Why check different tools?**  If the same tool returns the same result,
    that's already caught by RedundantToolCallDetector.  This detector focuses
    on the case where *different* tools return *identical* results — a stronger
    signal that the tools are all failing the same way.

    **False-positive risks**:
    - Tools returning the same error message (e.g., all tools returning
      "unauthorized").  This is actually a true positive — the agent is
      wasting calls because it lacks authorization.
    - Small results like "OK" or "success" that happen to be identical.
      Mitigated by the threshold of 3+ occurrences.

    **Evidence produced**:
    - ``wasted_count``, ``threshold``, ``output_preview``.
    """

    anomaly_type = "wasted_tool_calls"

    def __init__(self, threshold: int | None = None) -> None:
        self.threshold = threshold or settings.detector_wasted_tool_threshold

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        tool_spans = self._walk_tool_spans(spans)
        if len(tool_spans) < self.threshold:
            return None

        import json

        # Map: serialized_result → set of tool names that produced it.
        output_tool_map: dict[str, set[str]] = {}

        for span in tool_spans:
            result_raw = span.attributes.get("gen_ai.tool.result")
            if result_raw is None:
                continue
            elif isinstance(result_raw, str):
                result_str = result_raw
            else:
                try:
                    # Sort keys for deterministic serialization.
                    result_str = json.dumps(result_raw, sort_keys=True)
                except (TypeError, ValueError):
                    result_str = str(result_raw)

            tool_name = str(span.attributes.get("gen_ai.tool.name", "unknown"))
            output_tool_map.setdefault(result_str, set()).add(tool_name)

        # Find the result that appears most across different tools.
        max_wasted = 0
        wasted_output = ""
        for output_str, tool_names in output_tool_map.items():
            count = sum(1 for _ in tool_spans if self._matches_output(_, output_str))
            # Must appear at least threshold times AND across at least 2 different tools.
            if count >= self.threshold and len(tool_names) >= 2 and count > max_wasted:
                max_wasted = count
                wasted_output = output_str

        if max_wasted > 0:
            severity = self._severity(float(max_wasted), float(self.threshold))
            # Truncate output preview to 200 chars for readability.
            output_preview = wasted_output[:200] if wasted_output else "(empty)"
            explain = f"Wasted tool calls: repeated {max_wasted}x across different tools"
            return self._build_anomaly(
                summary,
                severity,
                explain,
                {
                    "wasted_count": max_wasted,
                    "threshold": self.threshold,
                    "output_preview": output_preview,
                },
            )
        return None

    @staticmethod
    def _matches_output(span: SpanNode, target: str) -> bool:
        """Check if a span's tool result matches a serialized target string."""
        import json

        result_raw = span.attributes.get("gen_ai.tool.result")
        if result_raw is None:
            return False
        elif isinstance(result_raw, str):
            return result_raw == target
        else:
            try:
                return json.dumps(result_raw, sort_keys=True) == target
            except (TypeError, ValueError):
                return str(result_raw) == target
