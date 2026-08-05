"""OpenAI-compatible LLM client for MLX-backed semantic anomaly detection.

The ``LLMClient`` wraps an OpenAI-compatible HTTP endpoint (served by an MLX
server such as ``omlx`` / ``mlx-lm``) exposing chat completions and
embeddings.  Every call degrades gracefully: if the model server is down,
returns ``None`` / ``False`` instead of raising, so the rule-based detectors
keep working without the LLM layer.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from typing import Any

from analytics.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Async OpenAI-compatible client with caching and graceful degradation.

    Attributes:
        base_url: OpenAI-compatible endpoint (defaults to the MLX server).
        api_key: auth token for the endpoint.
        chat_model: model id used for chat completions.
        embed_model: model id used for embeddings.
        timeout_seconds: per-request timeout.
        max_tokens: default completion token cap for chat calls.
    """

    def __init__(
        self,
        base_url: str = "",
        api_key: str = "",
        chat_model: str = "",
        embed_model: str = "",
        timeout_seconds: float = 0.0,
        max_tokens: int = 512,
        http_client: Any = None,
    ) -> None:
        self.base_url = base_url or settings.llm_base_url
        self.api_key = api_key or settings.llm_api_key
        self.chat_model = chat_model or settings.llm_chat_model
        self.embed_model = embed_model or settings.llm_embed_model
        self.timeout_seconds = timeout_seconds or settings.llm_timeout_seconds
        self.max_tokens = max_tokens

        self._client = None
        self._http_client = http_client
        self._cache: dict[Any, Any] = {}
        self._models_cache: list[str] | None = None
        self._stats = {
            "chat_calls": 0,
            "embed_calls": 0,
            "errors": 0,
            "total_latency_ms": 0.0,
        }
        self._responses: list[dict[str, Any]] = []

    def _client_instance(self) -> Any:
        """Lazily build the OpenAI client (imported on first use)."""
        if self._client is not None:
            return self._client
        try:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(  # type: ignore[assignment]
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=self.timeout_seconds,
                max_retries=0,
                http_client=self._http_client,
            )
        except Exception as exc:  # pragma: no cover - import guard
            logger.warning("openai client unavailable: %s", exc)
            self._client = None
        return self._client

    async def available(self) -> bool:
        """True if the model server responds to a model-list request."""
        client = self._client_instance()
        if client is None:
            return False
        start = time.monotonic()
        try:
            resp = await client.models.list()
            # Populate model cache so callers can inspect available models.
            self._models_cache = [m.id for m in resp.data] if resp.data else []
            self._record(start, "chat_calls")
            return True
        except Exception as exc:
            self._record_error(start)
            logger.warning("LLM availability check failed: %s", exc)
            return False

    async def chat(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> str | None:
        """Run a chat completion and return the assistant text.

        Returns ``None`` on any failure (server down, timeout, empty reply)
        rather than raising, to preserve graceful degradation.
        """
        client = self._client_instance()
        if client is None:
            return None

        key = ("chat", prompt, system or "", max_tokens or self.max_tokens)
        if key in self._cache:
            return self._cache[key]  # type: ignore[no-any-return]

        start = time.monotonic()
        try:
            messages: list[dict[str, str]] = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            resp = await client.chat.completions.create(
                model=self.chat_model,
                messages=messages,
                max_tokens=max_tokens or self.max_tokens,
            )
            content = resp.choices[0].message.content if resp.choices else None
            if not content:
                self._record(start, "chat_calls")
                return None
            self._record(start, "chat_calls")
            self._cache[key] = content
            self._responses.append({
                "system": system or "",
                "prompt": prompt[:500],
                "response": content[:500],
            })
            return content  # type: ignore[no-any-return]
        except Exception as exc:
            self._record(start, "chat_calls")
            self._record_error(start)
            logger.warning("LLM chat call failed: %s", exc)
            return None

    async def embed(self, text: str) -> list[float] | None:
        """Embed a single text and return its vector, or None on failure."""
        client = self._client_instance()
        if client is None:
            return None

        key = ("embed", text)
        if key in self._cache:
            return self._cache[key]  # type: ignore[no-any-return]

        start = time.monotonic()
        try:
            resp = await client.embeddings.create(
                model=self.embed_model,
                input=[text],
            )
            vector = list(resp.data[0].embedding)
            self._record(start, "embed_calls")
            self._cache[key] = vector
            return vector
        except Exception as exc:
            self._record(start, "embed_calls")
            self._record_error(start)
            logger.warning("LLM embed call failed: %s", exc)
            return None

    def _record(self, start: float, kind: str) -> None:
        self._stats[kind] += 1
        self._stats["total_latency_ms"] += (time.monotonic() - start) * 1000.0

    def _record_error(self, start: float) -> None:
        self._stats["errors"] += 1
        self._stats["total_latency_ms"] += (time.monotonic() - start) * 1000.0

    def stats(self) -> dict[str, float]:
        """Return a copy of call metrics for observability."""
        return dict(self._stats)

    def models(self) -> list[str] | None:
        """Return cached model list (populated after a successful availability check).

        Returns None if the endpoint has never been successfully reached.
        """
        return self._models_cache

    def responses(self) -> list[dict[str, Any]]:
        """Return all raw LLM chat responses recorded during this session."""
        return list(self._responses)


class PromptBuilder:
    """Pre-built prompt templates for LLM-augmented anomaly detectors.

    Each classmethod returns ``(system, user)`` ready for ``LLMClient.chat()``.
    """

    @classmethod
    def explain_quality(cls, anomaly_type: str, explanation: str) -> tuple[str, str]:
        system = (
            "You are an observability assistant. Rate the clarity and actionability "
            "of anomaly detector explanations on a 1-5 scale. 5 = immediately "
            "actionable and crystal clear. 1 = confusing or unhelpful."
        )
        user = (
            f"Anomaly type: {anomaly_type}\n"
            f"Explanation: {explanation}\n\n"
            "Return a JSON object: {\"score\": <int 1-5>, \"reasoning\": \"<one sentence>\"}"
        )
        return system, user

    @classmethod
    def triage_fp(cls, anomaly_type: str, severity: str, summary: str) -> tuple[str, str]:
        system = (
            "You are a triage classifier. Given an anomaly alert, classify it as "
            "\"tp\" (true positive), \"fp\" (false positive), or \"uncertain\". "
            "A false positive is a benign condition that happens to cross a numeric "
            "threshold without real problems."
        )
        user = (
            f"Anomaly type: {anomaly_type}\n"
            f"Severity: {severity}\n"
            f"Run summary: {summary}\n\n"
            "Return JSON: {\"verdict\": \"tp|fp|uncertain\", \"confidence\": <0.0-1.0>, "
            "\"reasoning\": \"<one sentence>\"}"
        )
        return system, user

    @classmethod
    def drift_check(cls, prior_output: str, current_output: str) -> tuple[str, str]:
        system = (
            "You compare agent outputs across versions. Determine whether a semantic "
            "drift has occurred: did the agent change WHAT it says, not just HOW?"
        )
        user = (
            f"Prior version output: {prior_output}\n"
            f"Current version output: {current_output}\n\n"
            "Return JSON: {\"drift\": true|false, \"magnitude\": \"none|minor|major\", "
            "\"note\": \"<one sentence>\"}"
        )
        return system, user

    @classmethod
    def semantic_loop(cls, prev: str, curr: str) -> tuple[str, str]:
        system = (
            "Check whether two consecutive agent outputs are semantically identical "
            "even if wording differs. Reply with a similarity score 0-1."
        )
        user = (
            f"Output A: {prev}\nOutput B: {curr}\n\n"
            "Return JSON: {\"identical\": true|false, \"similarity\": <0.0-1.0>}"
        )
        return system, user

    @classmethod
    def hallucination(cls, claim: str, context: str) -> tuple[str, str]:
        system = (
            "Verify whether a claim made by an agent is supported by the provided "
            "context (tool outputs, documents). Unsupported claims are hallucinations."
        )
        user = (
            f"Claim: {claim}\nContext: {context}\n\n"
            "Return JSON: {\"hallucination\": true|false, "
            "\"evidence\": \"<quote from context or 'none'>\"}"
        )
        return system, user

    @classmethod
    def goal_drift(cls, original_goal: str, current_action: str) -> tuple[str, str]:
        system = "Detect goal drift: is the agent pursuing a different objective than intended?"
        user = (
            f"Original goal: {original_goal}\n"
            f"Current action: {current_action}\n\n"
            "Return JSON: {\"diverged\": true|false, "
            "\"similarity\": <0.0-1.0>, \"note\": \"<one sentence>\"}"
        )
        return system, user

    @classmethod
    def quality_degradation(cls, baseline_output: str, current_output: str) -> tuple[str, str]:
        system = "Rate whether agent output quality has degraded relative to a baseline."
        user = (
            f"Baseline output: {baseline_output}\n"
            f"Current output: {current_output}\n\n"
            "Return JSON: {\"degraded\": true|false, \"severity\": \"none|minor|major\", "
            "\"note\": \"<one sentence>\"}"
        )
        return system, user

    @classmethod
    def confusion(cls, plan: str, execution: str) -> tuple[str, str]:
        system = "Detect contradictions between an agent's plan and its execution."
        user = (
            f"Plan: {plan}\nExecution: {execution}\n\n"
            "Return JSON: {\"contradiction\": true|false, "
            "\"explanation\": \"<one sentence if contradiction>\"}"
        )
        return system, user

    @classmethod
    def calibrate_thresholds(
        cls, detector_name: str, anomaly_rate: float,
        sample_count: int, current_threshold: str,
    ) -> tuple[str, str]:
        system = (
            "You calibrate anomaly detector thresholds. Given historical anomaly "
            "rates, suggest whether thresholds should be raised or lowered."
        )
        user = (
            f"Detector: {detector_name}\n"
            f"Anomaly rate: {anomaly_rate:.2%} ({sample_count} samples)\n"
            f"Current threshold: {current_threshold}\n\n"
            "Return JSON: {\"action\": \"raise|lower|keep\", "
            "\"suggested_value\": \"<new threshold or 'same'>\", "
            "\"rationale\": \"<one sentence>\"}"
        )
        return system, user


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity between two equal-length vectors."""
    if not a or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)  # type: ignore[no-any-return]
