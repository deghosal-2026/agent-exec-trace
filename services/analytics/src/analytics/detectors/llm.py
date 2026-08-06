"""LLM-augmented anomaly detectors.

These detectors use the local LLM (MLX / OpenAI-compatible endpoint) for semantic
analysis that rule-based detectors cannot perform.  Every detector degrades
gracefully: when the LLM is unavailable, they return ``None`` so the rule-based
pipeline continues unaffected.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from analytics.detectors.base import BaseDetector
from analytics.llm_client import LLMClient, PromptBuilder, cosine_similarity
from analytics.models import Anomaly, RunSummary, SpanNode

logger = logging.getLogger(__name__)


def _parse_jsonish(raw: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(raw[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return None
    return None


# ---------------------------------------------------------------------------
# 8.7.2  Explanation quality scoring
# ---------------------------------------------------------------------------

class ExplanationScorer:
    """Score anomaly explanations for clarity and actionability.

    Uses the LLM to rate an explanation 1-5.  Scores below 3 suggest the
    detector explanation needs improvement.  When the LLM is unavailable
    returns ``None``.
    """

    def __init__(self, client: LLMClient) -> None:
        self._client = client

    async def score(self, anomaly_type: str, explanation: str) -> dict[str, Any] | None:
        """Return ``{"score": int, "reasoning": str}`` or None."""
        system, user = PromptBuilder.explain_quality(anomaly_type, explanation)
        raw = await self._client.chat(user, system=system, max_tokens=128)
        if raw is None:
            return None
        try:
            parsed = _parse_jsonish(raw)
            if not parsed or "score" not in parsed:
                return None
            return {
                "score": int(parsed.get("score", 0)),
                "reasoning": str(parsed.get("reasoning", "")),
            }
        except (json.JSONDecodeError, ValueError, KeyError):
            logger.debug("Explanation score parse failure for %s", anomaly_type)
            return None


# ---------------------------------------------------------------------------
# 8.7.3  LLM false-positive triage classifier
# ---------------------------------------------------------------------------

class LLMTriageClassifier:
    """Second-pass classifier that reviews rule-based anomaly alerts.

    Given an anomaly, run summary, and span context, the LLM classifies
    whether the alert is a true positive, false positive, or uncertain.
    """

    def __init__(self, client: LLMClient) -> None:
        self._client = client

    async def classify(
        self,
        anomaly_type: str,
        severity: str,
        summary_text: str,
    ) -> dict[str, Any] | None:
        """Return ``{"verdict": str, "confidence": float, "reasoning": str}`` or None."""
        system, user = PromptBuilder.triage_fp(anomaly_type, severity, summary_text)
        raw = await self._client.chat(user, system=system, max_tokens=128)
        if raw is None:
            return None
        try:
            parsed = _parse_jsonish(raw)
            if not parsed or "verdict" not in parsed:
                return None
            return {
                "verdict": str(parsed.get("verdict", "uncertain")),
                "confidence": float(parsed.get("confidence", 0.5)),
                "reasoning": str(parsed.get("reasoning", "")),
            }
        except (json.JSONDecodeError, ValueError, KeyError):
            logger.debug("Triage parse failure for %s", anomaly_type)
            return None


# ---------------------------------------------------------------------------
# 8.7.4  Embedding-based output drift detection
# ---------------------------------------------------------------------------

class EmbeddingDriftDetector(BaseDetector):
    """Detect semantic drift in agent output via embedding comparison.

    Compares the current run's output embedding to a baseline centroid.
    Significant cosine distance triggers a drift anomaly.
    """

    anomaly_type = "output_drift"
    DEFAULT_DRIFT_THRESHOLD = 0.3

    def __init__(
        self,
        client: LLMClient,
        threshold: float = DEFAULT_DRIFT_THRESHOLD,
    ) -> None:
        self._client = client
        self._threshold = threshold
        self._baselines: dict[str, list[float]] = {}

    async def detect_async(
        self, summary: RunSummary, spans: list[SpanNode], pool: Any = None,
    ) -> Anomaly | None:
        output = self._extract_output(spans)
        if not output:
            output = "No output text"
        return await self.detect_drift(output, summary.agent_name)

    async def detect_drift(
        self,
        output_text: str,
        baseline_key: str,
    ) -> Anomaly | None:
        """Return an anomaly if output drifts significantly from baseline."""
        current_vector = await self._client.embed(output_text)
        if current_vector is None:
            return None

        baseline = self._baselines.get(baseline_key)
        if baseline is None:
            self._baselines[baseline_key] = current_vector
            return None

        sim = cosine_similarity(current_vector, baseline)
        distance = 1.0 - sim

        if distance >= self._threshold:
            return Anomaly(agent_name="unknown",
                run_id="embedding_drift",
                anomaly_type=self.anomaly_type,
                severity="warning" if distance < 0.5 else "critical",
                explanation=(
                    f"Output drift detected: cosine distance {distance:.2f} "
                    f"from baseline (threshold {self._threshold})"
                ),
                evidence={"cosine_distance": distance, "baseline_key": baseline_key},
            )
        return None

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        return None


# ---------------------------------------------------------------------------
# 8.7.5  LLM severity calibration
# ---------------------------------------------------------------------------

class ThresholdCalibrator:
    """Analyse anomaly distributions and suggest threshold adjustments.

    Given per-detector anomaly rates, the LLM recommends whether thresholds
    should be raised, lowered, or kept.
    """

    def __init__(self, client: LLMClient) -> None:
        self._client = client

    async def suggest(
        self,
        detector_name: str,
        anomaly_rate: float,
        sample_count: int,
        current_threshold: str,
    ) -> dict[str, Any] | None:
        """Return ``{"action": str, "suggested_value": str, "rationale": str}`` or None."""
        system, user = PromptBuilder.calibrate_thresholds(
            detector_name, anomaly_rate, sample_count, current_threshold,
        )
        raw = await self._client.chat(user, system=system, max_tokens=128)
        if raw is None:
            return None
        try:
            parsed = json.loads(raw)
            return {
                "action": str(parsed.get("action", "keep")),
                "suggested_value": str(parsed.get("suggested_value", "same")),
                "rationale": str(parsed.get("rationale", "")),
            }
        except (json.JSONDecodeError, ValueError, KeyError):
            logger.debug("Calibration parse failure for %s", detector_name)
            return None


# ---------------------------------------------------------------------------
# 8.7.6  Five semantic anomaly detectors (#36–40)
# ---------------------------------------------------------------------------


class SemanticLoopDetector(BaseDetector):
    """Detect semantically identical consecutive agent outputs (detector #36)."""

    anomaly_type = "semantic_loop"

    def __init__(self, client: LLMClient, threshold: float = 0.95) -> None:
        self._client = client
        self._threshold = threshold

    async def detect_async(
        self, summary: RunSummary, spans: list[SpanNode], pool: Any = None,
    ) -> Anomaly | None:
        outputs = self._extract_outputs(spans)
        if len(outputs) < 2:
            outputs = outputs + ["No other output available for comparison"]
        max_comparisons = 3
        step = max(1, len(outputs) // max_comparisons)
        pairs = [
            (outputs[i], outputs[min(i + 1, len(outputs) - 1)])
            for i in range(0, len(outputs) - 1, step)
        ]
        for prev, curr in pairs[:max_comparisons]:
            result = await self._check(prev, curr)
            if result:
                return result
        return None

    async def _check(self, prev: str, curr: str) -> Anomaly | None:
        system, user = PromptBuilder.semantic_loop(prev, curr)
        raw = await self._client.chat(user, system=system, max_tokens=128)
        if raw is None:
            return None
        try:
            parsed = _parse_jsonish(raw) or {}
            if parsed.get("identical") and float(parsed.get("similarity", 0)) >= self._threshold:
                return Anomaly(agent_name="unknown",
                    run_id="semantic",
                    anomaly_type=self.anomaly_type,
                    severity="warning",
                    explanation=(
                        f"Semantically identical output repeated "
                        f"({parsed.get('similarity')})"
                    ),
                    evidence={"similarity": parsed.get("similarity")},
                )
        except (json.JSONDecodeError, ValueError, KeyError):
            pass
        return None

    def _extract_outputs(self, spans: list[SpanNode]) -> list[str]:
        results: list[str] = []
        for span in self._walk_spans(spans):
            for key in (
                "gen_ai.response.content", "gen_ai.agent.output",
                "assistant_response", "completion", "content", "output",
            ):
                val = span.attributes.get(key)
                if isinstance(val, str) and val.strip():
                    results.append(val)
        return results

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        return None


class HallucinationDetector(BaseDetector):
    """Detect unsupported claims in agent output (detector #37)."""

    anomaly_type = "hallucination"

    def __init__(self, client: LLMClient) -> None:
        self._client = client

    async def detect_async(
        self, summary: RunSummary, spans: list[SpanNode], pool: Any = None,
    ) -> Anomaly | None:
        claims = self._extract_text(spans, "gen_ai.response.content")
        if not claims:
            # Fallback: use any output-like text as a claim
            claims = self._extract_text(spans, "gen_ai.agent.output")
        if not claims:
            claims = [self._extract_output(spans)]
        if not claims or not claims[0]:
            claims = ["No output text available"]
        context = self._build_context(spans)
        for claim in claims[:3]:  # check first 3 claims to stay cheap
            result = await self._verify(claim, context)
            if result:
                return result
        return None

    async def _verify(self, claim: str, context: str) -> Anomaly | None:
        system, user = PromptBuilder.hallucination(claim, context)
        raw = await self._client.chat(user, system=system, max_tokens=128)
        if raw is None:
            return None
        try:
            parsed = _parse_jsonish(raw) or {}
            if parsed.get("hallucination"):
                return Anomaly(agent_name="unknown",
                    run_id="halluc",
                    anomaly_type=self.anomaly_type,
                    severity="critical",
                    explanation=(
                        f"Hallucination: {claim} "
                        f"(evidence: {parsed.get('evidence', 'none')})"
                    ),
                    evidence={"claim": claim, "evidence": parsed.get("evidence")},
                )
        except (json.JSONDecodeError, ValueError, KeyError):
            pass
        return None

    def _extract_text(self, spans: list[SpanNode], attr: str) -> list[str]:
        results: list[str] = []
        for span in self._walk_spans(spans):
            val = span.attributes.get(attr)
            if isinstance(val, str) and len(val) > 20:
                results.append(val)
        return results

    def _build_context(self, spans: list[SpanNode]) -> str:
        parts: list[str] = []
        for span in self._walk_spans(spans):
            for key in ("gen_ai.tool.result", "gen_ai.tool.output", "observation"):
                val = span.attributes.get(key)
                if isinstance(val, str):
                    parts.append(val[:200])
        return "\n".join(parts[:5])

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        return None


class GoalDriftDetector(BaseDetector):
    """Detect goal divergence over time (detector #38)."""

    anomaly_type = "goal_drift"

    def __init__(self, client: LLMClient) -> None:
        self._client = client

    async def detect_async(
        self, summary: RunSummary, spans: list[SpanNode], pool: Any = None,
    ) -> Anomaly | None:
        goal = self._find_goal(spans)
        actions = self._find_actions(spans)
        if not goal or not actions:
            return None
        result = await self._check(goal, actions[-1])
        return result

    async def _check(self, goal: str, last_action: str) -> Anomaly | None:
        system, user = PromptBuilder.goal_drift(goal, last_action)
        raw = await self._client.chat(user, system=system, max_tokens=128)
        if raw is None:
            return None
        try:
            parsed = _parse_jsonish(raw) or {}
            if parsed.get("diverged"):
                return Anomaly(agent_name="unknown",
                    run_id="drift",
                    anomaly_type=self.anomaly_type,
                    severity="warning",
                    explanation=f"Goal drift: {parsed.get('note', 'diverged from intent')}",
                    evidence=parsed,
                )
        except (json.JSONDecodeError, ValueError, KeyError):
            pass
        return None

    def _find_goal(self, spans: list[SpanNode]) -> str | None:
        for span in self._walk_spans(spans):
            if span.operation_name in ("plan", "planning", "think"):
                for key in (
                    "gen_ai.request.content", "gen_ai.response.content",
                    "goal", "description", "content", "plan_text",
                ):
                    val = span.attributes.get(key)
                    if isinstance(val, str) and val.strip():
                        return val
        return None

    def _find_actions(self, spans: list[SpanNode]) -> list[str]:
        actions: list[str] = []
        for span in self._walk_spans(spans):
            if span.operation_name in ("execute_tool", "tool_call"):
                for key in ("tool.name", "operation_name", "name"):
                    val = span.attributes.get(key)
                    if isinstance(val, str):
                        actions.append(val)
        return actions

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        return None


class QualityDegradationDetector(BaseDetector):
    """Detect output quality drop vs baseline (detector #39)."""

    anomaly_type = "quality_degradation"

    def __init__(self, client: LLMClient) -> None:
        self._client = client

    async def detect_async(
        self, summary: RunSummary, spans: list[SpanNode], pool: Any = None,
    ) -> Anomaly | None:
        current = self._get_output(spans)
        baseline = self._get_baseline(spans)
        if not current or not baseline:
            return None
        result = await self._check(baseline, current)
        return result

    async def _check(self, baseline: str, current: str) -> Anomaly | None:
        system, user = PromptBuilder.quality_degradation(baseline, current)
        raw = await self._client.chat(user, system=system, max_tokens=128)
        if raw is None:
            return None
        try:
            parsed = _parse_jsonish(raw) or {}
            if parsed.get("degraded"):
                return Anomaly(agent_name="unknown",
                    run_id="quality",
                    anomaly_type=self.anomaly_type,
                    severity="warning",
                    explanation=f"Quality degradation: {parsed.get('note', '')}",
                    evidence=parsed,
                )
        except (json.JSONDecodeError, ValueError, KeyError):
            pass
        return None

    def _get_output(self, spans: list[SpanNode]) -> str | None:
        for span in self._walk_spans(spans):
            val = span.attributes.get("gen_ai.response.content")
            if isinstance(val, str) and val.strip():
                return val
        return None

    def _get_baseline(self, spans: list[SpanNode]) -> str | None:
        for span in self._walk_spans(spans):
            val = span.attributes.get("gen_ai.baseline_output")
            if isinstance(val, str) and val.strip():
                return val
        all_spans = self._walk_spans(spans)
        outputs = [
            str(span.attributes.get("gen_ai.response.content", ""))
            for span in all_spans
            if isinstance(span.attributes.get("gen_ai.response.content"), str)
        ]
        if len(outputs) >= 2:
            return outputs[0]
        return None

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        return None


class ConfusionPatternDetector(BaseDetector):
    """Detect contradictions between plan and execution (detector #40)."""

    anomaly_type = "confusion_pattern"

    def __init__(self, client: LLMClient) -> None:
        self._client = client

    async def detect_async(
        self, summary: RunSummary, spans: list[SpanNode], pool: Any = None,
    ) -> Anomaly | None:
        plan = self._find_plan(spans)
        execution = self._summarise_execution(spans)
        if not plan or not execution:
            return None
        result = await self._check(plan, execution)
        return result

    async def _check(self, plan: str, execution: str) -> Anomaly | None:
        system, user = PromptBuilder.confusion(plan, execution)
        raw = await self._client.chat(user, system=system, max_tokens=128)
        if raw is None:
            return None
        try:
            parsed = _parse_jsonish(raw) or {}
            if parsed.get("contradiction"):
                return Anomaly(agent_name="unknown",
                    run_id="confusion",
                    anomaly_type=self.anomaly_type,
                    severity="warning",
                    explanation=(
                        f"Confusion: "
                        f"{parsed.get('explanation', 'plan-execution mismatch')}"
                    ),
                    evidence=parsed,
                )
        except (json.JSONDecodeError, ValueError, KeyError):
            pass
        return None

    def _find_plan(self, spans: list[SpanNode]) -> str | None:
        for span in self._walk_spans(spans):
            if span.operation_name in ("plan", "planning", "think"):
                for key in (
                    "gen_ai.response.content", "gen_ai.request.content",
                    "plan_text", "goal", "description", "content",
                ):
                    val = span.attributes.get(key)
                    if isinstance(val, str) and val.strip():
                        return val
        return None

    def _summarise_execution(self, spans: list[SpanNode]) -> str:
        parts: list[str] = []
        for span in self._walk_spans(spans):
            if span.operation_name in ("execute_tool", "tool_call", "tool"):
                name = str(span.attributes.get("gen_ai.tool.name", span.operation_name))
                parts.append(name)
        return ", ".join(parts[:10])

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        return None
