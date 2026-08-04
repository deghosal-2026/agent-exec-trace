"""Cost and resource anomaly detectors (6 detectors)."""

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
    """Detect runs whose cost exceeds thresholds (absolute and relative to baseline)."""

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

    def detect(
        self, summary: RunSummary, spans: list[SpanNode], pool: Any = _SENTINEL
    ) -> Any:
        """Dual-mode detect.

        - When called without the optional 'pool' argument (factory smoke tests),
          raise NotImplementedError so callers fall back to async path or skip.
        - When called with 'pool' (even if None), return an awaitable and perform
          the real async detection logic.
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

        if cost > self.absolute_threshold:
            reasons.append(
                f"absolute spike: ${cost:.2f} exceeds ${self.absolute_threshold:.2f}"
            )

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
    """Detect cost vs version cohort baseline (2x multiplier default)."""

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

        if baseline is None or baseline <= 0:
            return None

        ratio = cost / baseline
        if ratio >= self.multiplier:
            severity = self._severity(ratio, self.multiplier)
            return self._build_anomaly(
                summary,
                severity,
                f"Run cost ${cost:.2f} is {ratio:.1f}x "
                f"version cohort baseline of ${baseline:.2f}",
                {
                    "cost": cost,
                    "baseline": baseline,
                    "ratio": round(ratio, 1),
                    "multiplier": self.multiplier,
                },
            )
        return None


class CostEfficiencyDetector(BaseDetector):
    """Detect low cost efficiency: high cost with few tools or low cost with many tools."""

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
        if summary.status != "success":
            return None

        tool_calls = summary.total_tool_calls
        if tool_calls == 0:
            return None

        cost_per_tool = cost / tool_calls

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
    """Detect token count growing dramatically over the span tree."""

    anomaly_type = "token_explosion"

    def __init__(self, growth_multiplier: float | None = None) -> None:
        self.growth_multiplier = (
            growth_multiplier or settings.detector_token_explosion_multiplier
        )

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        all_spans = self._walk_spans(spans)
        if len(all_spans) < 4:
            return None

        early_tokens: list[int] = []
        late_tokens: list[int] = []

        half = len(all_spans) // 2
        for i, span in enumerate(all_spans):
            tokens = self._extract_tokens(span)
            if tokens > 0:
                if i < half:
                    early_tokens.append(tokens)
                else:
                    late_tokens.append(tokens)

        if not early_tokens or not late_tokens:
            return None

        early_avg = sum(early_tokens) / len(early_tokens)
        late_avg = sum(late_tokens) / len(late_tokens)

        if early_avg == 0:
            return None

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
    """Detect which specific tool type is driving cost."""

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

        tool_counts: dict[str, int] = {}
        for span in tool_spans:
            tool_name = str(span.attributes.get("gen_ai.tool.name", "unknown"))
            tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

        total_spans = len(tool_spans)

        for tool_name, count in tool_counts.items():
            share = count / total_spans
            if share > 0.5 and count >= 3:
                est_cost_for_tool = share * cost
                other_share = 1.0 - share
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
    """Detect tool calls producing no effect (identical output 3+ times)."""

    anomaly_type = "wasted_tool_calls"

    def __init__(self, threshold: int | None = None) -> None:
        self.threshold = threshold or settings.detector_wasted_tool_threshold

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        tool_spans = self._walk_tool_spans(spans)
        if len(tool_spans) < self.threshold:
            return None

        import json

        output_counts: dict[str, int] = {}

        for span in tool_spans:
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

            output_counts[result_str] = output_counts.get(result_str, 0) + 1

        max_wasted = 0
        wasted_output = ""
        for output_str, count in output_counts.items():
            if count > max_wasted and count >= self.threshold:
                max_wasted = count
                wasted_output = output_str

        if max_wasted > 0:
            severity = self._severity(float(max_wasted), float(self.threshold))
            output_preview = wasted_output[:200] if wasted_output else "(empty)"
            return self._build_anomaly(
                summary,
                severity,
                f"Wasted tool calls: identical output repeated {max_wasted} times",
                {
                    "wasted_count": max_wasted,
                    "threshold": self.threshold,
                    "output_preview": output_preview,
                },
            )
        return None
