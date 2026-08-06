"""Comprehensive tests for all async LLM detector paths."""

from __future__ import annotations

import json

import httpx
import pytest

from analytics.detectors.llm import (
    ConfusionPatternDetector,
    EmbeddingDriftDetector,
    ExplanationScorer,
    GoalDriftDetector,
    HallucinationDetector,
    LLMTriageClassifier,
    QualityDegradationDetector,
    SemanticLoopDetector,
    ThresholdCalibrator,
)
from analytics.llm_client import LLMClient
from analytics.models import Anomaly, RunSummary, SpanNode


def _make_summary(**overrides: object) -> RunSummary:
    defaults: dict[str, object] = {
        "run_id": "run-1",
        "agent_name": "test-agent",
    }
    defaults.update(overrides)
    return RunSummary(**defaults)  # type: ignore[arg-type]


def _make_span(
    span_id: str,
    operation_name: str = "llm",
    attributes: dict[str, object] | None = None,
    child_spans: list[SpanNode] | None = None,
) -> SpanNode:
    return SpanNode(
        span_id=span_id,
        trace_id="trace-1",
        parent_span_id=None,
        operation_name=operation_name,
        attributes=attributes or {},
        child_spans=child_spans or [],
    )


def _make_llm_client(responses: list[str]) -> LLMClient:
    response_iter = iter(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "/embeddings" in path:
            return httpx.Response(
                200,
                json={"data": [{"embedding": [0.1, 0.2, 0.3]}]},
            )
        try:
            content = next(response_iter)
        except StopIteration:
            return httpx.Response(500, json={"error": "no more mock responses"})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": content}}]},
        )

    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    return LLMClient(
        base_url="http://test/v1",
        api_key="test",
        chat_model="test-model",
        embed_model="test-embed",
        http_client=httpx.AsyncClient(transport=transport),
    )


def _make_failing_llm_client() -> LLMClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "server down"})

    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    return LLMClient(
        base_url="http://test/v1",
        api_key="test",
        chat_model="test-model",
        embed_model="test-embed",
        http_client=httpx.AsyncClient(transport=transport),
    )


def _make_embedding_llm_client(embed_vector: list[float] | None = None) -> LLMClient:
    """Client that supports embed() calls and returns no chat responses."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "/embeddings" in path:
            if embed_vector is None:
                return httpx.Response(500, json={"error": "embed down"})
            return httpx.Response(
                200,
                json={"data": [{"embedding": embed_vector}]},
            )
        return httpx.Response(500, json={"error": "chat not expected"})

    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    return LLMClient(
        base_url="http://test/v1",
        api_key="test",
        chat_model="test-model",
        embed_model="test-embed",
        http_client=httpx.AsyncClient(transport=transport),
    )


# ============================================================================
# ExplanationScorer
# ============================================================================


class TestExplanationScorer:
    @pytest.mark.asyncio
    async def test_happy_path_returns_score(self) -> None:
        client = _make_llm_client(['{"score": 4, "reasoning": "clear explanation"}'])
        scorer = ExplanationScorer(client)
        result = await scorer.score("loop", "The agent called the same tool 10 times")
        assert result is not None
        assert result["score"] == 4
        assert result["reasoning"] == "clear explanation"

    @pytest.mark.asyncio
    async def test_llm_unavailable_returns_none(self) -> None:
        client = _make_failing_llm_client()
        scorer = ExplanationScorer(client)
        result = await scorer.score("loop", "explanation text")
        assert result is None

    @pytest.mark.asyncio
    async def test_no_score_field_returns_none(self) -> None:
        client = _make_llm_client(['{"reasoning": "no score here"}'])
        scorer = ExplanationScorer(client)
        result = await scorer.score("loop", "explanation text")
        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_json_returns_none(self) -> None:
        client = _make_llm_client(["not json at all"])
        scorer = ExplanationScorer(client)
        result = await scorer.score("loop", "explanation text")
        assert result is None

    @pytest.mark.asyncio
    async def test_json_in_markdown_code_block(self) -> None:
        client = _make_llm_client(['```json\n{"score": 5, "reasoning": "perfect"}\n```'])
        scorer = ExplanationScorer(client)
        result = await scorer.score("loop", "explanation text")
        assert result is not None
        assert result["score"] == 5

    @pytest.mark.asyncio
    async def test_score_zero_edge_case(self) -> None:
        client = _make_llm_client(['{"score": 0, "reasoning": "empty explanation"}'])
        scorer = ExplanationScorer(client)
        result = await scorer.score("loop", "")
        assert result is not None
        assert result["score"] == 0

    @pytest.mark.asyncio
    async def test_extra_fields_in_response_preserved(self) -> None:
        client = _make_llm_client(['{"score": 3, "reasoning": "ok", "extra": "ignored"}'])
        scorer = ExplanationScorer(client)
        result = await scorer.score("loop", "test")
        assert result is not None
        assert result["score"] == 3


# ============================================================================
# LLMTriageClassifier
# ============================================================================


class TestLLMTriageClassifier:
    @pytest.mark.asyncio
    async def test_verdict_true_positive(self) -> None:
        client = _make_llm_client(
            ['{"verdict": "tp", "confidence": 0.9, "reasoning": "real anomaly"}']
        )
        classifier = LLMTriageClassifier(client)
        result = await classifier.classify("cost_spike", "critical", "run summary text")
        assert result is not None
        assert result["verdict"] == "tp"
        assert result["confidence"] == 0.9

    @pytest.mark.asyncio
    async def test_verdict_false_positive(self) -> None:
        client = _make_llm_client(
            ['{"verdict": "fp", "confidence": 0.85, "reasoning": "benign spike"}']
        )
        classifier = LLMTriageClassifier(client)
        result = await classifier.classify("cost_spike", "warning", "summary")
        assert result is not None
        assert result["verdict"] == "fp"

    @pytest.mark.asyncio
    async def test_verdict_uncertain(self) -> None:
        client = _make_llm_client(
            ['{"verdict": "uncertain", "confidence": 0.5, "reasoning": "not sure"}']
        )
        classifier = LLMTriageClassifier(client)
        result = await classifier.classify("loop", "warning", "summary")
        assert result is not None
        assert result["verdict"] == "uncertain"

    @pytest.mark.asyncio
    async def test_llm_unavailable_returns_none(self) -> None:
        client = _make_failing_llm_client()
        classifier = LLMTriageClassifier(client)
        result = await classifier.classify("cost_spike", "critical", "summary")
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_verdict_field_returns_none(self) -> None:
        client = _make_llm_client(['{"confidence": 0.9, "reasoning": "no verdict"}'])
        classifier = LLMTriageClassifier(client)
        result = await classifier.classify("cost_spike", "critical", "summary")
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_confidence_field_defaults(self) -> None:
        client = _make_llm_client(
            ['{"verdict": "tp", "reasoning": "no confidence field"}']
        )
        classifier = LLMTriageClassifier(client)
        result = await classifier.classify("loop", "warning", "summary")
        assert result is not None
        assert result["verdict"] == "tp"
        assert result["confidence"] == 0.5

    @pytest.mark.asyncio
    async def test_json_parse_failure_returns_none(self) -> None:
        client = _make_llm_client(["garbage response"])
        classifier = LLMTriageClassifier(client)
        result = await classifier.classify("loop", "warning", "summary")
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_response_returns_none(self) -> None:
        client = _make_llm_client([""])
        classifier = LLMTriageClassifier(client)
        result = await classifier.classify("loop", "warning", "summary")
        assert result is None

    @pytest.mark.asyncio
    async def test_json_with_surrounding_text(self) -> None:
        client = _make_llm_client(
            ['Sure! {"verdict": "fp", "confidence": 0.7, "reasoning": "likely benign"} thanks']
        )
        classifier = LLMTriageClassifier(client)
        result = await classifier.classify("cost_spike", "warning", "summary")
        assert result is not None
        assert result["verdict"] == "fp"


# ============================================================================
# EmbeddingDriftDetector
# ============================================================================


class TestEmbeddingDriftDetector:
    @pytest.mark.asyncio
    async def test_detects_drift_when_distance_exceeds_threshold(self) -> None:
        client = _make_embedding_llm_client([1.0, 0.0, 0.0])
        detector = EmbeddingDriftDetector(client, threshold=0.3)
        detector._baselines["test-agent"] = [0.0, 1.0, 0.0]
        summary = _make_summary()
        span = _make_span("sp1", attributes={"gen_ai.response.content": "drifted output"})
        result = await detector.detect_async(summary, [span])
        assert result is not None
        assert result.anomaly_type == "output_drift"

    @pytest.mark.asyncio
    async def test_no_drift_when_distance_below_threshold(self) -> None:
        client = _make_embedding_llm_client([0.9, 0.8, 0.7])
        detector = EmbeddingDriftDetector(client, threshold=0.3)
        detector._baselines["test-agent"] = [0.9, 0.8, 0.7]
        summary = _make_summary()
        span = _make_span("sp1", attributes={"gen_ai.response.content": "similar output"})
        result = await detector.detect_async(summary, [span])
        assert result is None

    @pytest.mark.asyncio
    async def test_embed_unavailable_returns_none(self) -> None:
        client = _make_embedding_llm_client(None)
        detector = EmbeddingDriftDetector(client)
        detector._baselines["test-agent"] = [0.9, 0.8, 0.7]
        summary = _make_summary()
        span = _make_span("sp1", attributes={"gen_ai.response.content": "output"})
        result = await detector.detect_async(summary, [span])
        assert result is None

    @pytest.mark.asyncio
    async def test_first_run_establishes_baseline_no_anomaly(self) -> None:
        client = _make_embedding_llm_client([0.1, 0.2, 0.3])
        detector = EmbeddingDriftDetector(client)
        summary = _make_summary()
        span = _make_span("sp1", attributes={"gen_ai.response.content": "first output"})
        result = await detector.detect_async(summary, [span])
        assert result is None
        assert "test-agent" in detector._baselines

    @pytest.mark.asyncio
    async def test_no_output_spans_uses_placeholder(self) -> None:
        client = _make_embedding_llm_client([1.0, 0.0, 0.0])
        detector = EmbeddingDriftDetector(client, threshold=0.3)
        detector._baselines["test-agent"] = [0.0, 0.0, 1.0]
        summary = _make_summary()
        span = _make_span("sp1", attributes={})
        result = await detector.detect_async(summary, [span])
        assert result is not None

    @pytest.mark.asyncio
    async def test_detect_method_returns_none(self) -> None:
        client = _make_embedding_llm_client([0.1, 0.2, 0.3])
        detector = EmbeddingDriftDetector(client)
        summary = _make_summary()
        assert detector.detect(summary, []) is None

    @pytest.mark.asyncio
    async def test_critical_severity_when_distance_above_0_5(self) -> None:
        client = _make_embedding_llm_client([0.1, 0.2, 0.3])
        detector = EmbeddingDriftDetector(client, threshold=0.3)
        detector._baselines["test-agent"] = [-0.8, -0.7, -0.6]
        summary = _make_summary()
        span = _make_span("sp1", attributes={"gen_ai.response.content": "very different"})
        result = await detector.detect_async(summary, [span])
        assert result is not None
        assert result.severity == "critical"

    @pytest.mark.asyncio
    async def test_drift_with_different_baseline_key(self) -> None:
        client = _make_embedding_llm_client([1.0, 0.0, 0.0])
        detector = EmbeddingDriftDetector(client, threshold=0.3)
        detector._baselines["agent-alpha"] = [0.0, 0.0, 1.0]
        summary = _make_summary(agent_name="agent-alpha")
        span = _make_span("sp1", attributes={"gen_ai.response.content": "alpha output"})
        result = await detector.detect_async(summary, [span])
        assert result is not None
        assert result.evidence["baseline_key"] == "agent-alpha"  # type: ignore[index]


# ============================================================================
# ThresholdCalibrator
# ============================================================================


class TestThresholdCalibrator:
    @pytest.mark.asyncio
    async def test_suggests_raise(self) -> None:
        client = _make_llm_client(
            ['{"action": "raise", "suggested_value": "0.5", "rationale": "too noisy"}']
        )
        calibrator = ThresholdCalibrator(client)
        result = await calibrator.suggest("LoopDetector", 0.42, 1000, "0.3")
        assert result is not None
        assert result["action"] == "raise"
        assert result["suggested_value"] == "0.5"

    @pytest.mark.asyncio
    async def test_suggests_lower(self) -> None:
        client = _make_llm_client(
            ['{"action": "lower", "suggested_value": "0.1", "rationale": "misses anomalies"}']
        )
        calibrator = ThresholdCalibrator(client)
        result = await calibrator.suggest("CostSpike", 0.01, 500, "0.3")
        assert result is not None
        assert result["action"] == "lower"

    @pytest.mark.asyncio
    async def test_suggests_keep(self) -> None:
        client = _make_llm_client(
            ['{"action": "keep", "suggested_value": "same", "rationale": "optimal rate"}']
        )
        calibrator = ThresholdCalibrator(client)
        result = await calibrator.suggest("LoopDetector", 0.05, 1000, "0.2")
        assert result is not None
        assert result["action"] == "keep"

    @pytest.mark.asyncio
    async def test_llm_unavailable_returns_none(self) -> None:
        client = _make_failing_llm_client()
        calibrator = ThresholdCalibrator(client)
        result = await calibrator.suggest("LoopDetector", 0.1, 100, "0.3")
        assert result is None

    @pytest.mark.asyncio
    async def test_json_parse_failure_returns_none(self) -> None:
        client = _make_llm_client(["not json"])
        calibrator = ThresholdCalibrator(client)
        result = await calibrator.suggest("LoopDetector", 0.1, 100, "0.3")
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_fields_default(self) -> None:
        client = _make_llm_client(["{}"])
        calibrator = ThresholdCalibrator(client)
        result = await calibrator.suggest("LoopDetector", 0.1, 100, "0.3")
        assert result is not None
        assert result["action"] == "keep"
        assert result["suggested_value"] == "same"

    @pytest.mark.asyncio
    async def test_zero_anomaly_rate(self) -> None:
        client = _make_llm_client(
            ['{"action": "lower", "suggested_value": "0.05", "rationale": "too strict"}']
        )
        calibrator = ThresholdCalibrator(client)
        result = await calibrator.suggest("LoopDetector", 0.0, 1000, "0.3")
        assert result is not None
        assert result["action"] == "lower"


# ============================================================================
# SemanticLoopDetector
# ============================================================================


class TestSemanticLoopDetector:
    @pytest.mark.asyncio
    async def test_detects_semantic_loop(self) -> None:
        client = _make_llm_client(['{"identical": true, "similarity": 0.98}'])
        detector = SemanticLoopDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1", attributes={"gen_ai.response.content": "Hello world"}),
            _make_span("sp2", attributes={"gen_ai.response.content": "Hi world"}),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is not None
        assert result.anomaly_type == "semantic_loop"

    @pytest.mark.asyncio
    async def test_no_loop_when_not_identical(self) -> None:
        client = _make_llm_client(['{"identical": false, "similarity": 0.2}'])
        detector = SemanticLoopDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1", attributes={"gen_ai.response.content": "A"}),
            _make_span("sp2", attributes={"gen_ai.response.content": "B"}),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is None

    @pytest.mark.asyncio
    async def test_identical_but_below_threshold_returns_none(self) -> None:
        client = _make_llm_client(['{"identical": true, "similarity": 0.90}'])
        detector = SemanticLoopDetector(client, threshold=0.95)
        summary = _make_summary()
        spans = [
            _make_span("sp1", attributes={"gen_ai.response.content": "A"}),
            _make_span("sp2", attributes={"gen_ai.response.content": "A"}),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is None

    @pytest.mark.asyncio
    async def test_llm_unavailable_returns_none(self) -> None:
        client = _make_failing_llm_client()
        detector = SemanticLoopDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1", attributes={"gen_ai.response.content": "A"}),
            _make_span("sp2", attributes={"gen_ai.response.content": "B"}),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is None

    @pytest.mark.asyncio
    async def test_single_output_uses_fallback(self) -> None:
        client = _make_llm_client(['{"identical": true, "similarity": 1.0}'])
        detector = SemanticLoopDetector(client, threshold=0.95)
        summary = _make_summary()
        spans = [_make_span("sp1", attributes={"gen_ai.response.content": "Only output"})]
        result = await detector.detect_async(summary, spans)
        assert result is not None

    @pytest.mark.asyncio
    async def test_no_spans_with_outputs(self) -> None:
        client = _make_llm_client(["unused"])
        detector = SemanticLoopDetector(client, threshold=0.95)
        summary = _make_summary()
        spans: list[SpanNode] = []
        result = await detector.detect_async(summary, spans)
        assert result is None

    @pytest.mark.asyncio
    async def test_json_parse_failure_returns_none(self) -> None:
        client = _make_llm_client(["not json"])
        detector = SemanticLoopDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1", attributes={"gen_ai.response.content": "A"}),
            _make_span("sp2", attributes={"gen_ai.response.content": "B"}),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is None

    @pytest.mark.asyncio
    async def test_detect_method_returns_none(self) -> None:
        client = _make_llm_client(["unused"])
        detector = SemanticLoopDetector(client)
        summary = _make_summary()
        assert detector.detect(summary, []) is None

    @pytest.mark.asyncio
    async def test_extracts_output_from_gen_ai_node_output(self) -> None:
        client = _make_llm_client(['{"identical": true, "similarity": 0.99}'])
        detector = SemanticLoopDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1", attributes={"gen_ai.node.output": "node output A"}),
            _make_span("sp2", attributes={"gen_ai.node.output": "node output A"}),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is not None

    @pytest.mark.asyncio
    async def test_extracts_output_from_plan_content(self) -> None:
        client = _make_llm_client(['{"identical": true, "similarity": 0.97}'])
        detector = SemanticLoopDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1", attributes={"gen_ai.plan.content": "plan A"}),
            _make_span("sp2", attributes={"gen_ai.plan.content": "plan B"}),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is not None


# ============================================================================
# HallucinationDetector
# ============================================================================


class TestHallucinationDetector:
    @pytest.mark.asyncio
    async def test_detects_hallucination(self) -> None:
        client = _make_llm_client(
            ['{"hallucination": true, "evidence": "none"}']
        )
        detector = HallucinationDetector(client)
        summary = _make_summary()
        spans = [
            _make_span(
                "sp1",
                attributes={"gen_ai.response.content": "The sky is green"},
            ),
            _make_span(
                "sp2",
                attributes={"gen_ai.tool.result": "The sky is blue"},
            ),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is not None
        assert result.anomaly_type == "hallucination"
        assert result.severity == "critical"

    @pytest.mark.asyncio
    async def test_no_hallucination(self) -> None:
        client = _make_llm_client(
            ['{"hallucination": false, "evidence": "cited from context"}']
        )
        detector = HallucinationDetector(client)
        summary = _make_summary()
        spans = [
            _make_span(
                "sp1",
                attributes={"gen_ai.response.content": "The sky is blue"},
            ),
            _make_span(
                "sp2",
                attributes={"gen_ai.tool.result": "The sky is blue"},
            ),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is None

    @pytest.mark.asyncio
    async def test_llm_unavailable_returns_none(self) -> None:
        client = _make_failing_llm_client()
        detector = HallucinationDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1", attributes={"gen_ai.response.content": "claim"}),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_claims_uses_fallback(self) -> None:
        client = _make_llm_client(
            ['{"hallucination": true, "evidence": "none"}']
        )
        detector = HallucinationDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1", attributes={"gen_ai.agent.output": "fallback claim"}),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is not None

    @pytest.mark.asyncio
    async def test_no_spans_uses_placeholder(self) -> None:
        client = _make_llm_client(
            ['{"hallucination": true, "evidence": "none"}']
        )
        detector = HallucinationDetector(client)
        summary = _make_summary()
        spans: list[SpanNode] = []
        result = await detector.detect_async(summary, spans)
        assert result is not None

    @pytest.mark.asyncio
    async def test_json_parse_failure_returns_none(self) -> None:
        client = _make_llm_client(["invalid json"])
        detector = HallucinationDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1", attributes={"gen_ai.response.content": "claim"}),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is None

    @pytest.mark.asyncio
    async def test_detect_method_returns_none(self) -> None:
        client = _make_llm_client(["unused"])
        detector = HallucinationDetector(client)
        summary = _make_summary()
        assert detector.detect(summary, []) is None

    @pytest.mark.asyncio
    async def test_multiple_claims_checks_up_to_three(self) -> None:
        client = _make_llm_client([
            '{"hallucination": false, "evidence": "supported"}',
            '{"hallucination": false, "evidence": "supported"}',
            '{"hallucination": true, "evidence": "unsupported claim 3"}',
        ])
        detector = HallucinationDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1", attributes={"gen_ai.response.content": "claim1"}),
            _make_span("sp2", attributes={"gen_ai.response.content": "claim2"}),
            _make_span("sp3", attributes={"gen_ai.response.content": "claim3"}),
            _make_span("sp4", attributes={"gen_ai.response.content": "claim4"}),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is not None

    @pytest.mark.asyncio
    async def test_context_built_from_tool_results(self) -> None:
        client = _make_llm_client(
            ['{"hallucination": true, "evidence": "none"}']
        )
        detector = HallucinationDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1", attributes={"gen_ai.response.content": "unsupported"}),
            _make_span(
                "sp2",
                attributes={
                    "gen_ai.tool.result": "result data",
                    "gen_ai.tool.output": "more data",
                },
            ),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is not None


# ============================================================================
# GoalDriftDetector
# ============================================================================


class TestGoalDriftDetector:
    @pytest.mark.asyncio
    async def test_detects_goal_drift(self) -> None:
        client = _make_llm_client(
            ['{"diverged": true, "similarity": 0.2, "note": "agent is off track"}']
        )
        detector = GoalDriftDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1",
                operation_name="plan",
                attributes={"gen_ai.response.content": "Build a web app"}),
            _make_span("sp2",
                operation_name="execute_tool",
                attributes={"tool.name": "debug_logging"}),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is not None
        assert result.anomaly_type == "goal_drift"

    @pytest.mark.asyncio
    async def test_no_drift(self) -> None:
        client = _make_llm_client(
            ['{"diverged": false, "similarity": 0.9, "note": "on track"}']
        )
        detector = GoalDriftDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1",
                operation_name="plan",
                attributes={"gen_ai.response.content": "Build a web app"}),
            _make_span("sp2",
                operation_name="execute_tool",
                attributes={"tool.name": "create_react_app"}),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is None

    @pytest.mark.asyncio
    async def test_llm_unavailable_returns_none(self) -> None:
        client = _make_failing_llm_client()
        detector = GoalDriftDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1",
                operation_name="plan",
                attributes={"gen_ai.response.content": "goal"}),
            _make_span("sp2",
                operation_name="execute_tool",
                attributes={"tool.name": "action"}),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_goal_spans_returns_none(self) -> None:
        client = _make_llm_client(['{"diverged": true}'])
        detector = GoalDriftDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1",
                operation_name="execute_tool",
                attributes={"tool.name": "some_action"}),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_action_spans_returns_none(self) -> None:
        client = _make_llm_client(['{"diverged": true}'])
        detector = GoalDriftDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1",
                operation_name="plan",
                attributes={"gen_ai.response.content": "some goal"}),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_spans_returns_none(self) -> None:
        client = _make_llm_client(["unused"])
        detector = GoalDriftDetector(client)
        summary = _make_summary()
        result = await detector.detect_async(summary, [])
        assert result is None

    @pytest.mark.asyncio
    async def test_json_parse_failure_returns_none(self) -> None:
        client = _make_llm_client(["garbage"])
        detector = GoalDriftDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1",
                operation_name="plan",
                attributes={"gen_ai.response.content": "goal"}),
            _make_span("sp2",
                operation_name="execute_tool",
                attributes={"tool.name": "action"}),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is None

    @pytest.mark.asyncio
    async def test_detect_method_returns_none(self) -> None:
        client = _make_llm_client(["unused"])
        detector = GoalDriftDetector(client)
        summary = _make_summary()
        assert detector.detect(summary, []) is None

    @pytest.mark.asyncio
    async def test_finds_goal_from_planning_operation(self) -> None:
        client = _make_llm_client(
            ['{"diverged": true, "similarity": 0.1, "note": "drifted"}']
        )
        detector = GoalDriftDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1",
                operation_name="planning",
                attributes={"gen_ai.response.content": "build feature X"}),
            _make_span("sp2",
                operation_name="execute_tool",
                attributes={"tool.name": "unrelated_action"}),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is not None

    @pytest.mark.asyncio
    async def test_finds_goal_from_think_operation(self) -> None:
        client = _make_llm_client(
            ['{"diverged": true, "similarity": 0.3, "note": "diverged"}']
        )
        detector = GoalDriftDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1",
                operation_name="think",
                attributes={"content": "I need to fix the bug"}),
            _make_span("sp2",
                operation_name="tool_call",
                attributes={"tool.name": "unrelated_task"}),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is not None

    @pytest.mark.asyncio
    async def test_finds_action_from_tool_call_operation(self) -> None:
        client = _make_llm_client(
            ['{"diverged": true, "similarity": 0.1, "note": "drifted"}']
        )
        detector = GoalDriftDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1",
                operation_name="plan",
                attributes={"gen_ai.response.content": "goal"}),
            _make_span("sp2",
                operation_name="tool_call",
                attributes={"tool.name": "action_name"}),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is not None


# ============================================================================
# QualityDegradationDetector
# ============================================================================


class TestQualityDegradationDetector:
    @pytest.mark.asyncio
    async def test_detects_quality_degradation(self) -> None:
        client = _make_llm_client(
            ['{"degraded": true, "severity": "major", "note": "output is much worse"}']
        )
        detector = QualityDegradationDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1",
                attributes={
                    "gen_ai.response.content": "Detailed, thorough analysis of the data",
                    "gen_ai.baseline_output": "Baseline gold-standard analysis",
                }),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is not None
        assert result.anomaly_type == "quality_degradation"

    @pytest.mark.asyncio
    async def test_no_degradation(self) -> None:
        client = _make_llm_client(
            ['{"degraded": false, "severity": "none", "note": "quality maintained"}']
        )
        detector = QualityDegradationDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1",
                attributes={
                    "gen_ai.response.content": "good output",
                    "gen_ai.baseline_output": "good baseline",
                }),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is None

    @pytest.mark.asyncio
    async def test_llm_unavailable_returns_none(self) -> None:
        client = _make_failing_llm_client()
        detector = QualityDegradationDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1",
                attributes={
                    "gen_ai.response.content": "output",
                    "gen_ai.baseline_output": "baseline",
                }),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_output_content_returns_none(self) -> None:
        client = _make_llm_client(["unused"])
        detector = QualityDegradationDetector(client)
        summary = _make_summary()
        spans = [_make_span("sp1", attributes={})]
        result = await detector.detect_async(summary, spans)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_baseline_falls_back_to_first_output(self) -> None:
        client = _make_llm_client(
            ['{"degraded": true, "severity": "minor", "note": "slight degradation"}']
        )
        detector = QualityDegradationDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1",
                attributes={"gen_ai.response.content": "earlier output"}),
            _make_span("sp2",
                attributes={"gen_ai.response.content": "later degraded output"}),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is not None

    @pytest.mark.asyncio
    async def test_empty_spans_returns_none(self) -> None:
        client = _make_llm_client(["unused"])
        detector = QualityDegradationDetector(client)
        summary = _make_summary()
        result = await detector.detect_async(summary, [])
        assert result is None

    @pytest.mark.asyncio
    async def test_json_parse_failure_returns_none(self) -> None:
        client = _make_llm_client(["not json"])
        detector = QualityDegradationDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1",
                attributes={
                    "gen_ai.response.content": "output",
                    "gen_ai.baseline_output": "baseline",
                }),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is None

    @pytest.mark.asyncio
    async def test_detect_method_returns_none(self) -> None:
        client = _make_llm_client(["unused"])
        detector = QualityDegradationDetector(client)
        summary = _make_summary()
        assert detector.detect(summary, []) is None

    @pytest.mark.asyncio
    async def test_baseline_from_two_or_more_outputs(self) -> None:
        client = _make_llm_client(
            ['{"degraded": true, "severity": "minor", "note": "slight drop"}']
        )
        detector = QualityDegradationDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1",
                attributes={"gen_ai.response.content": "first baseline output"}),
            _make_span("sp2",
                attributes={"gen_ai.response.content": "second output"}),
            _make_span("sp3",
                attributes={"gen_ai.response.content": "third output degraded"}),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is not None


# ============================================================================
# ConfusionPatternDetector
# ============================================================================


class TestConfusionPatternDetector:
    @pytest.mark.asyncio
    async def test_detects_confusion(self) -> None:
        client = _make_llm_client(
            ['{"contradiction": true, "explanation": "plan says build API, but agent ran tests"}']
        )
        detector = ConfusionPatternDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1",
                operation_name="plan",
                attributes={"gen_ai.response.content": "Build a REST API"}),
            _make_span("sp2",
                operation_name="execute_tool",
                attributes={"gen_ai.tool.name": "run_tests"}),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is not None
        assert result.anomaly_type == "confusion_pattern"

    @pytest.mark.asyncio
    async def test_no_confusion(self) -> None:
        client = _make_llm_client(
            ['{"contradiction": false, "explanation": ""}']
        )
        detector = ConfusionPatternDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1",
                operation_name="plan",
                attributes={"gen_ai.response.content": "Build a REST API"}),
            _make_span("sp2",
                operation_name="execute_tool",
                attributes={"gen_ai.tool.name": "scaffold_api"}),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is None

    @pytest.mark.asyncio
    async def test_llm_unavailable_returns_none(self) -> None:
        client = _make_failing_llm_client()
        detector = ConfusionPatternDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1",
                operation_name="plan",
                attributes={"gen_ai.response.content": "plan text"}),
            _make_span("sp2",
                operation_name="execute_tool",
                attributes={"gen_ai.tool.name": "some_tool"}),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_plan_spans_returns_none(self) -> None:
        client = _make_failing_llm_client()
        detector = ConfusionPatternDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1",
                operation_name="execute_tool",
                attributes={"gen_ai.tool.name": "some_tool"}),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_execution_spans_returns_none(self) -> None:
        client = _make_llm_client(["unused"])
        detector = ConfusionPatternDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1",
                operation_name="plan",
                attributes={"gen_ai.response.content": "plan text"}),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_spans_returns_none(self) -> None:
        client = _make_llm_client(["unused"])
        detector = ConfusionPatternDetector(client)
        summary = _make_summary()
        result = await detector.detect_async(summary, [])
        assert result is None

    @pytest.mark.asyncio
    async def test_json_parse_failure_returns_none(self) -> None:
        client = _make_llm_client(["garbage"])
        detector = ConfusionPatternDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1",
                operation_name="plan",
                attributes={"gen_ai.response.content": "plan text"}),
            _make_span("sp2",
                operation_name="execute_tool",
                attributes={"gen_ai.tool.name": "some_tool"}),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is None

    @pytest.mark.asyncio
    async def test_detect_method_returns_none(self) -> None:
        client = _make_llm_client(["unused"])
        detector = ConfusionPatternDetector(client)
        summary = _make_summary()
        assert detector.detect(summary, []) is None

    @pytest.mark.asyncio
    async def test_finds_plan_from_planning_operation(self) -> None:
        client = _make_llm_client(
            ['{"contradiction": true, "explanation": "mismatch"}']
        )
        detector = ConfusionPatternDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1",
                operation_name="planning",
                attributes={"gen_ai.response.content": "plan from planning"}),
            _make_span("sp2",
                operation_name="execute_tool",
                attributes={"gen_ai.tool.name": "wrong_tool"}),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is not None

    @pytest.mark.asyncio
    async def test_finds_plan_from_think_operation(self) -> None:
        client = _make_llm_client(
            ['{"contradiction": true, "explanation": "mismatch"}']
        )
        detector = ConfusionPatternDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1",
                operation_name="think",
                attributes={"gen_ai.response.content": "thinking plan"}),
            _make_span("sp2",
                operation_name="tool_call",
                attributes={"gen_ai.tool.name": "contradictory_tool"}),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is not None

    @pytest.mark.asyncio
    async def test_summarises_tool_call_execution(self) -> None:
        client = _make_llm_client(
            ['{"contradiction": true, "explanation": "plan contradicts execution"}']
        )
        detector = ConfusionPatternDetector(client)
        summary = _make_summary()
        spans = [
            _make_span("sp1",
                operation_name="plan",
                attributes={"gen_ai.response.content": "test plan"}),
            _make_span("sp2",
                operation_name="tool_call",
                attributes={"gen_ai.tool.name": "tool_alpha"}),
            _make_span("sp3",
                operation_name="tool_call",
                attributes={"gen_ai.tool.name": "tool_beta"}),
        ]
        result = await detector.detect_async(summary, spans)
        assert result is not None