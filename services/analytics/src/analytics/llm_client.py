"""OpenAI-compatible LLM client for MLX-backed semantic anomaly detection.

The ``LLMClient`` wraps an OpenAI-compatible HTTP endpoint (served by an MLX
server such as ``omlx`` / ``mlx-lm``) exposing chat completions and
embeddings.  Every call degrades gracefully: if the model server is down,
returns ``None`` / ``False`` instead of raising, so the rule-based detectors
keep working without the LLM layer.

**Design decisions:**

- **Graceful degradation**: All methods return ``None`` on failure rather
  than raising exceptions.  This means the LLM is strictly additive — it
  can only add signals, never remove or break the rule-based pipeline.
- **In-memory cache**: Responses are cached in a ``dict`` keyed by
  ``(method, prompt, system, max_tokens)`` to avoid redundant LLM calls
  within a session.  This is particularly valuable during validation where
  the same prompts may be reused across traces.
- **Lazy client construction**: The OpenAI client is built on first use,
  deferring import errors and enabling the module to be imported without
  the ``openai`` package installed.
- **Response logging**: Optional file-based logging of all LLM interactions
  for debugging, audit, and quality assessment.
- **Stats tracking**: Per-instance counters for chat_calls, embed_calls,
  errors, and total_latency_ms enable observability into LLM usage and cost.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Sequence
from typing import Any

from analytics.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Async OpenAI-compatible client with caching and graceful degradation.

    Wraps the ``openai.AsyncOpenAI`` client.  Every method that talks to
    the model catches ``Exception`` and returns ``None`` so the rule-based
    pipeline is never blocked by LLM unavailability.

    Attributes:
        base_url: OpenAI-compatible endpoint (defaults to the MLX server).
        api_key: auth token for the endpoint.
        chat_model: model id used for chat completions.
        embed_model: model id used for embeddings.
        timeout_seconds: per-request timeout in seconds.
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
        # Fall back to settings defaults for any empty parameter.
        self.base_url = base_url or settings.llm_base_url
        self.api_key = api_key or settings.llm_api_key
        self.chat_model = chat_model or settings.llm_chat_model
        self.embed_model = embed_model or settings.llm_embed_model
        self.timeout_seconds = timeout_seconds or settings.llm_timeout_seconds
        self.max_tokens = max_tokens

        # Lazy-initialized OpenAI client.  None until first use.
        self._client = None
        # Optional pre-built httpx client (for testing/injection).
        self._http_client = http_client
        # In-memory cache: (method, prompt, system, max_tokens) → response.
        # Prevents redundant LLM calls within a session.
        self._cache: dict[Any, Any] = {}
        # Cached model list from a successful availability check.
        self._models_cache: list[str] | None = None
        # Per-instance observability counters.
        self._stats = {
            "chat_calls": 0,
            "embed_calls": 0,
            "errors": 0,
            "total_latency_ms": 0.0,
        }
        # Recorded chat responses for audit/debugging.
        self._responses: list[dict[str, Any]] = []
        # Optional file path for JSONL response logging.
        self._response_log: str | None = None
        # Trace context for associating LLM calls with traces and detectors.
        self._trace_context: dict[str, str] = {}

    def set_response_log(self, path: str) -> None:
        """Enable JSONL logging of all chat responses to the given file path.

        Args:
            path: filesystem path to append JSONL lines to.
        """
        self._response_log = path

    def set_trace_context(self, trace_id: str, detector: str) -> None:
        """Associate subsequent LLM calls with a specific trace and detector.

        This context is included in response log entries and the responses
        list, enabling correlation of LLM decisions to traces.

        Args:
            trace_id: the trace being analyzed.
            detector: the detector invoking the LLM.
        """
        self._trace_context = {"trace_id": trace_id, "detector": detector}

    def _client_instance(self) -> Any:
        """Lazily build the OpenAI client (imported on first use).

        Returns the client if construction succeeds, ``None`` if the
        ``openai`` package is not installed or construction fails.

        This lazy pattern avoids forcing an ``openai`` import at module
        load time, which matters because the service may run without
        the LLM layer (e.g., rule-based-only mode).
        """
        if self._client is not None:
            return self._client
        try:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(  # type: ignore[assignment]
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=self.timeout_seconds,
                max_retries=0,  # No retries: we handle failures ourselves.
                http_client=self._http_client,
            )
        except Exception as exc:  # pragma: no cover - import guard
            logger.warning("openai client unavailable: %s", exc)
            self._client = None
        return self._client

    async def available(self) -> bool:
        """Check if the model server responds to a model-list request.

        Sends a ``GET /v1/models`` request and populates the internal model
        cache on success.  This is the recommended way to check LLM
        availability before invoking detectors.

        Returns:
            ``True`` if the server responds with a model list, ``False``
            otherwise (server down, timeout, auth error, etc.).
        """
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

        Uses the configured ``chat_model``.  Responses are cached in-memory
        so identical prompts within a session hit the cache instead of the
        model.

        Args:
            prompt: the user message content.
            system: optional system message (sets behavior/instructions).
            max_tokens: override the default token cap for this call.

        Returns:
            The assistant's text response as a string, or ``None`` on any
            failure (server down, timeout, empty reply, model error).
        """
        client = self._client_instance()
        if client is None:
            return None

        # Cache key includes all inputs that could change the response.
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
            # Record for audit/debugging (truncated to 500 chars).
            self._responses.append({
                **self._trace_context,
                "system": system or "",
                "prompt": prompt[:500],
                "response": content[:500],
            })
            # Optionally write to JSONL log file.
            if self._response_log:
                import json as _json
                with open(self._response_log, "a") as _f:
                    _f.write(_json.dumps({
                        **self._trace_context,
                        "system": system or "",
                        "prompt": prompt[:500],
                        "response": content[:500],
                    }) + "\n")
            return content  # type: ignore[no-any-return]
        except Exception as exc:
            self._record(start, "chat_calls")
            self._record_error(start)
            logger.warning("LLM chat call failed: %s", exc)
            return None

    async def embed(self, text: str) -> list[float] | None:
        """Embed a single text and return its vector, or None on failure.

        Uses the configured ``embed_model``.  Results are cached in-memory.

        Args:
            text: the text to embed.

        Returns:
            A list of floats representing the embedding vector, or ``None``
            if the embedding call fails.
        """
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
        """Record a successful call's timing and increment the type counter.

        Args:
            start: ``time.monotonic()`` timestamp from call initiation.
            kind: one of ``"chat_calls"`` or ``"embed_calls"``.
        """
        self._stats[kind] += 1
        self._stats["total_latency_ms"] += (time.monotonic() - start) * 1000.0

    def _record_error(self, start: float) -> None:
        """Record a failed call's timing and increment the error counter.

        Args:
            start: ``time.monotonic()`` timestamp from call initiation.
        """
        self._stats["errors"] += 1
        self._stats["total_latency_ms"] += (time.monotonic() - start) * 1000.0

    def stats(self) -> dict[str, float]:
        """Return a copy of call metrics for observability.

        Returns:
            Dict with keys: ``chat_calls``, ``embed_calls``, ``errors``,
            ``total_latency_ms`` (all as floats).
        """
        return dict(self._stats)

    def models(self) -> list[str] | None:
        """Return cached model list (populated after a successful availability check).

        Returns:
            List of model IDs, or ``None`` if the endpoint has never been
            successfully reached.
        """
        return self._models_cache

    def responses(self) -> list[dict[str, Any]]:
        """Return all raw LLM chat responses recorded during this session.

        Returns:
            A list of dicts with keys: trace_id, detector, system, prompt,
            response (each truncated to 500 chars).
        """
        return list(self._responses)


class PromptBuilder:
    """Pre-built prompt templates for LLM-augmented anomaly detectors.

    Each classmethod returns ``(system_prompt, user_prompt)`` ready for
    ``LLMClient.chat()``.  All prompts instruct the model to return
    ``ONLY VALID JSON. NO PROSE.`` to ensure machine-readable output.

    **Edge cases:** Text inputs are cleaned and truncated before being
    inserted into prompts.  This prevents:
    1. Exceeding model context windows.
    2. Leaking thinking/reasoning content from agent traces.
    3. Including raw tool_call XML that would confuse the model.
    """

    @staticmethod
    def _clean_text(text: str, limit: int = 500) -> str:
        """Clean and truncate raw agent output for prompt insertion.

        Removes thinking blocks (`` thinking... response``), tool_call XML
        tags, and collapses whitespace, then truncates to ``limit`` chars.

        Args:
            text: raw text from agent output.
            limit: maximum characters to return.

        Returns:
            Cleaned and truncated text.
        """
        # Strip thinking/reasoning blocks that some agent frameworks emit.
        text = re.sub(r" thinking.*? response", " ", text, flags=re.DOTALL)
        # Strip <tool_call>...</tool_call> XML that is noise for LLM tasks.
        text = re.sub(r"<tool_call>.*?</tool_call>", " ", text, flags=re.DOTALL)
        # Collapse multiple whitespace characters into single spaces.
        text = re.sub(r"\s+", " ", text).strip()
        return text[:limit]

    @classmethod
    def explain_quality(cls, anomaly_type: str, explanation: str) -> tuple[str, str]:
        """Build prompt to rate anomaly explanation quality on a 1-5 scale.

        Used by ``ExplanationScorer`` to assess whether detector explanations
        are clear and actionable.  Scores below 3 indicate the detector's
        explanation template needs improvement.

        Args:
            anomaly_type: the type of anomaly (e.g., "loop").
            explanation: the detector's generated explanation text.

        Returns:
            (system_prompt, user_prompt) tuple.
        """
        system = (
            "You are an observability assistant. Rate the clarity and actionability "
            "of anomaly detector explanations on a 1-5 scale. 5 = immediately "
            "actionable and crystal clear. 1 = confusing or unhelpful. "
            "RETURN ONLY VALID JSON. NO PROSE."
        )
        user = (
            f"Anomaly type: {anomaly_type}\n"
            f"Explanation: {cls._clean_text(explanation, 300)}\n\n"
            "Return a JSON object: {\"score\": <int 1-5>, \"reasoning\": \"<one sentence>\"}"
        )
        return system, user

    @classmethod
    def triage_fp(cls, anomaly_type: str, severity: str, summary: str) -> tuple[str, str]:
        """Build prompt to classify an anomaly as true positive, false positive, or uncertain.

        Used by ``LLMTriageClassifier`` for second-pass review of rule-based
        alerts.  The LLM considers the anomaly type, severity, and run summary
        context.

        Args:
            anomaly_type: the type of anomaly detected.
            severity: the severity level (warning/critical).
            summary: a text summary of the run.

        Returns:
            (system_prompt, user_prompt) tuple.
        """
        system = (
            "You are a triage classifier. Given an anomaly alert, classify it as "
            "\"tp\" (true positive), \"fp\" (false positive), or \"uncertain\". "
            "A false positive is a benign condition that happens to cross a numeric "
            "threshold without real problems. RETURN ONLY VALID JSON. NO PROSE."
        )
        user = (
            f"Anomaly type: {anomaly_type}\n"
            f"Severity: {severity}\n"
            f"Run summary: {cls._clean_text(summary, 400)}\n\n"
            "Return JSON: {\"verdict\": \"tp|fp|uncertain\", \"confidence\": <0.0-1.0>, "
            "\"reasoning\": \"<one sentence>\"}"
        )
        return system, user

    @classmethod
    def drift_check(cls, prior_output: str, current_output: str) -> tuple[str, str]:
        """Build prompt to detect semantic drift between two agent outputs.

        Compares outputs across versions to determine if the agent changed
        *what* it says (semantic drift), not just *how* (wording changes).

        Args:
            prior_output: output from the baseline/prior version.
            current_output: output from the current version.

        Returns:
            (system_prompt, user_prompt) tuple.
        """
        system = (
            "You compare agent outputs across versions. Determine whether a semantic "
            "drift has occurred: did the agent change WHAT it says, not just HOW? "
            "RETURN ONLY VALID JSON. NO PROSE."
        )
        user = (
            f"Prior version output: {cls._clean_text(prior_output)}\n"
            f"Current version output: {cls._clean_text(current_output)}\n\n"
            "Return JSON: {\"drift\": true|false, \"magnitude\": \"none|minor|major\", "
            "\"note\": \"<one sentence>\"}"
        )
        return system, user

    @classmethod
    def semantic_loop(cls, prev: str, curr: str) -> tuple[str, str]:
        """Build prompt to check if two consecutive outputs are semantically identical.

        Used by ``SemanticLoopDetector`` to detect when an agent repeats
        itself with different wording.  This catches subtler loops than
        exact-match detection.

        Args:
            prev: the earlier output text.
            curr: the later output text.

        Returns:
            (system_prompt, user_prompt) tuple.
        """
        system = (
            "Check whether two consecutive agent outputs are semantically identical "
            "even if wording differs. RETURN ONLY VALID JSON. NO PROSE."
        )
        user = (
            f"Output A: {cls._clean_text(prev)}\nOutput B: {cls._clean_text(curr)}\n\n"
            "Return JSON: {\"identical\": true|false, \"similarity\": <0.0-1.0>}"
        )
        return system, user

    @classmethod
    def hallucination(cls, claim: str, context: str) -> tuple[str, str]:
        """Build prompt to verify a claim against its supporting context.

        Used by ``HallucinationDetector``.  The LLM checks if the claim is
        supported by any evidence in the context (tool outputs, documents).

        Args:
            claim: the specific claim made by the agent.
            context: tool results, documents, or other evidence context.

        Returns:
            (system_prompt, user_prompt) tuple.
        """
        system = (
            "Verify whether a claim made by an agent is supported by the provided "
            "context (tool outputs, documents). Unsupported claims are hallucinations. "
            "RETURN ONLY VALID JSON. NO PROSE."
        )
        user = (
            f"Claim: {cls._clean_text(claim, 300)}\nContext: {cls._clean_text(context, 500)}\n\n"
            "Return JSON: {\"hallucination\": true|false, "
            "\"evidence\": \"<quote from context or 'none'>\"}"
        )
        return system, user

    @classmethod
    def goal_drift(cls, original_goal: str, current_action: str) -> tuple[str, str]:
        """Build prompt to detect if the agent is pursuing a different objective.

        Used by ``GoalDriftDetector``.  Compares the agent's stated goal/plan
        against its actual actions to detect divergence.

        Args:
            original_goal: the agent's stated goal or plan.
            current_action: the agent's actual tool call or action.

        Returns:
            (system_prompt, user_prompt) tuple.
        """
        system = (
            "Detect goal drift: is the agent pursuing a different objective than intended? "
            "RETURN ONLY VALID JSON. NO PROSE."
        )
        user = (
            f"Original goal: {cls._clean_text(original_goal, 300)}\n"
            f"Current action: {cls._clean_text(current_action, 200)}\n\n"
            "Return JSON: {\"diverged\": true|false, "
            "\"similarity\": <0.0-1.0>, \"note\": \"<one sentence>\"}"
        )
        return system, user

    @classmethod
    def quality_degradation(cls, baseline_output: str, current_output: str) -> tuple[str, str]:
        """Build prompt to rate whether output quality degraded vs baseline.

        Used by ``QualityDegradationDetector``.

        Args:
            baseline_output: the reference output from an earlier/baseline version.
            current_output: the output to evaluate.

        Returns:
            (system_prompt, user_prompt) tuple.
        """
        system = (
            "Rate whether agent output quality has degraded relative to a baseline. "
            "RETURN ONLY VALID JSON. NO PROSE."
        )
        user = (
            f"Baseline output: {cls._clean_text(baseline_output)}\n"
            f"Current output: {cls._clean_text(current_output)}\n\n"
            "Return JSON: {\"degraded\": true|false, \"severity\": \"none|minor|major\", "
            "\"note\": \"<one sentence>\"}"
        )
        return system, user

    @classmethod
    def confusion(cls, plan: str, execution: str) -> tuple[str, str]:
        """Build prompt to detect contradictions between plan and execution.

        Used by ``ConfusionPatternDetector``.

        Args:
            plan: the agent's plan text.
            execution: a summary of the agent's actual execution.

        Returns:
            (system_prompt, user_prompt) tuple.
        """
        system = (
            "Detect contradictions between an agent's plan and its execution. "
            "RETURN ONLY VALID JSON. NO PROSE."
        )
        user = (
            f"Plan: {cls._clean_text(plan, 300)}\nExecution: {cls._clean_text(execution, 200)}\n\n"
            "Return JSON: {\"contradiction\": true|false, "
            "\"explanation\": \"<one sentence if contradiction>\"}"
        )
        return system, user

    @classmethod
    def calibrate_thresholds(
        cls, detector_name: str, anomaly_rate: float,
        sample_count: int, current_threshold: str,
    ) -> tuple[str, str]:
        """Build prompt to suggest threshold adjustments based on anomaly rates.

        Used by ``ThresholdCalibrator``.

        Args:
            detector_name: name of the detector being calibrated.
            anomaly_rate: current anomaly fire rate (0.0 - 1.0).
            sample_count: number of traces sampled.
            current_threshold: the current threshold value as a string.

        Returns:
            (system_prompt, user_prompt) tuple.
        """
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
    """Compute cosine similarity between two equal-length vectors.

    Cosine similarity ranges from -1.0 (opposite) to 1.0 (identical).
    Returns 0.0 for zero-length or mismatched vectors.

    Args:
        a: first vector.
        b: second vector.

    Returns:
        Cosine similarity score between -1.0 and 1.0, or 0.0 on error.
    """
    # Guard against empty or mismatched vectors.
    if not a or len(a) != len(b):
        return 0.0
    # Dot product: sum of element-wise products.
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    # L2 norms (Euclidean).
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    # Guard against division by zero (zero vectors).
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)  # type: ignore[no-any-return]