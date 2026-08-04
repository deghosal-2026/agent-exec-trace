"""Tests for the LLMClient OpenAI-compatible wrapper (MLX backend)."""

from __future__ import annotations

import json

import httpx
import pytest

from analytics.llm_client import LLMClient, PromptBuilder

CHAT_MODEL = "Qwen3.5-4B-4bit"
EMBED_MODEL = "all-MiniLM-L6-v2"


def _make_client(handler: object, chat_model: str = CHAT_MODEL) -> LLMClient:
    """Build a client routed through a mock transport handler."""
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    client = LLMClient(
        base_url="http://test/v1",
        api_key="mlx",
        chat_model=chat_model,
        embed_model=EMBED_MODEL,
        http_client=httpx.AsyncClient(transport=transport),
    )
    return client


class TestAvailable:
    @pytest.mark.asyncio
    async def test_true_when_models_listable(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/v1/models"
            return httpx.Response(200, json={"object": "list", "data": []})

        client = _make_client(handler)
        assert await client.available() is True

    @pytest.mark.asyncio
    async def test_false_when_server_down(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"error": "boom"})

        client = _make_client(handler)
        assert await client.available() is False

    @pytest.mark.asyncio
    async def test_false_on_timeout(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectTimeout("unreachable")

        client = _make_client(handler)
        assert await client.available() is False


class TestChat:
    @pytest.mark.asyncio
    async def test_returns_completion_text(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            assert body["model"] == CHAT_MODEL
            assert body["messages"][-1]["content"] == "hi"
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {"role": "assistant", "content": "hello back"},
                            "finish_reason": "stop",
                        }
                    ]
                },
            )

        client = _make_client(handler)
        assert await client.chat("hi") == "hello back"

    @pytest.mark.asyncio
    async def test_includes_system_prompt(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            assert body["messages"][0]["role"] == "system"
            assert body["messages"][0]["content"] == "be strict"
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"role": "assistant", "content": "x"}}]
                },
            )

        client = _make_client(handler)
        await client.chat("q", system="be strict")

    @pytest.mark.asyncio
    async def test_returns_none_on_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"error": "rate limited"})

        client = _make_client(handler)
        assert await client.chat("hi") is None

    @pytest.mark.asyncio
    async def test_empty_content_returns_none(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"choices": [{"message": {"role": "assistant", "content": ""}}]},
            )

        client = _make_client(handler)
        assert await client.chat("hi") is None


class TestEmbed:
    @pytest.mark.asyncio
    async def test_returns_embedding_vector(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            assert body["model"] == EMBED_MODEL
            assert body["input"] == ["text to embed"]
            return httpx.Response(
                200,
                json={
                    "data": [{"embedding": [0.1, 0.2, 0.3]}],
                    "model": EMBED_MODEL,
                },
            )

        client = _make_client(handler)
        assert await client.embed("text to embed") == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_returns_none_on_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, json={"error": "down"})

        client = _make_client(handler)
        assert await client.embed("x") is None


class TestCaching:
    @pytest.mark.asyncio
    async def test_chat_returns_cached_result_without_second_call(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"role": "assistant", "content": "same"}}]
                },
            )

        client = _make_client(handler)
        first = await client.chat("repeat")
        second = await client.chat("repeat")
        assert first == "same"
        assert second == "same"
        assert calls["n"] == 1

    @pytest.mark.asyncio
    async def test_cache_key_includes_system_prompt(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"role": "assistant", "content": "r"}}]
                },
            )

        client = _make_client(handler)
        await client.chat("q", system="a")
        await client.chat("q", system="b")
        assert calls["n"] == 2


class TestLatencyTracking:
    @pytest.mark.asyncio
    async def test_records_call_metrics(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if "/embeddings" in request.url.path:
                return httpx.Response(
                    200,
                    json={"data": [{"embedding": [0.1, 0.2, 0.3]}]},
                )
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"role": "assistant", "content": "ok"}}]
                },
            )

        client = _make_client(handler)
        await client.chat("ping")
        await client.embed("vec")

        stats = client.stats()
        assert stats["chat_calls"] == 1
        assert stats["embed_calls"] == 1
        assert stats["errors"] == 0
        assert stats["total_latency_ms"] >= 0


class TestModelConfig:
    @pytest.mark.asyncio
    async def test_uses_configured_chat_model(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            assert body["model"] == "Custom-7B-4bit"
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"role": "assistant", "content": "y"}}]
                },
            )

        client = _make_client(handler, chat_model="Custom-7B-4bit")
        assert await client.chat("hi") == "y"


class TestModelCache:
    @pytest.mark.asyncio
    async def test_models_returns_cached_list(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/v1/models"
            return httpx.Response(
                200,
                json={
                    "object": "list",
                    "data": [
                        {"id": "Chat-4bit", "object": "model"},
                        {"id": "Embed-v2", "object": "model"},
                    ],
                },
            )

        client = _make_client(handler)
        assert await client.available() is True
        assert client.models() == ["Chat-4bit", "Embed-v2"]

    @pytest.mark.asyncio
    async def test_models_none_before_available(self) -> None:
        client = LLMClient(base_url="http://test")
        assert client.models() is None

    @pytest.mark.asyncio
    async def test_models_empty_on_empty_server(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"object": "list", "data": []})

        client = _make_client(handler)
        assert await client.available() is True
        assert client.models() == []


class TestPromptBuilder:
    def test_explain_quality_returns_system_and_user(self) -> None:
        system, user = PromptBuilder.explain_quality("Loop", "Too many calls")
        assert "1-5 scale" in system
        assert "Loop" in user
        assert "Too many calls" in user

    def test_triage_fp_returns_system_and_user(self) -> None:
        system, user = PromptBuilder.triage_fp("CostSpike", "critical", "run: 123")
        assert "triage classifier" in system.lower()
        assert "CostSpike" in user

    def test_semantic_loop(self) -> None:
        system, user = PromptBuilder.semantic_loop("hello", "hi there")
        assert "hello" in user and "hi there" in user

    def test_hallucination(self) -> None:
        system, user = PromptBuilder.hallucination("X is Y", "doc: X is Z")
        assert "hallucination" in system.lower()
        assert "X is Y" in user

    def test_drift_check(self) -> None:
        system, user = PromptBuilder.drift_check("v1 out", "v2 out")
        assert "v1 out" in user

    def test_goal_drift(self) -> None:
        system, user = PromptBuilder.goal_drift("build app", "debug logs")
        assert "build app" in user

    def test_quality_degradation(self) -> None:
        system, user = PromptBuilder.quality_degradation("gold", "silver")
        assert "gold" in user

    def test_confusion(self) -> None:
        system, user = PromptBuilder.confusion("plan X", "did Y")
        assert "plan X" in user

    def test_calibrate_thresholds(self) -> None:
        system, user = PromptBuilder.calibrate_thresholds(
            "LoopDetector", 0.42, 1000, "5"
        )
        assert "42" in user