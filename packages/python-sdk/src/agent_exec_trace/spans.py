"""Nested behavior span helpers.

========================================================
Purpose
========================================================
A bare root span is generic tracing. The product's value is a **behavioral story**:
what the agent planned, which tools it called, what it retrieved, and what it wrote
to memory. Each helper in this module turns one of those behaviors into a first-class,
navigable child span under the run's root ``invoke_agent`` span.

Design rules shared by every helper:
  * Each span is stamped with ``gen_ai.operation.name`` so the analytics service and
    the run-timeline UI can recognize its behavior class without name-parsing.
  * Spans parent to the current active span, so nesting is automatic when used inside
    ``invoke_agent`` or another helper.
  * Sensitive payloads (tool args, memory content) are ONLY written through
    ``RedactionConfig.apply(..., allowed=<field flag>)``. This is the privacy
    enforcement point -- see :mod:`agent_exec_trace.redact`.

========================================================
Span portability guarantees
========================================================
Every span produced through a helper in this module carries:

  1. ``gen_ai.operation.name`` set to the behavior class (``"plan"``,
     ``"execute_tool"``, ``"retrieval"``, ``"memory"``).
  2. A span kind matching the semantics (INTERNAL for agent-internal steps,
     CLIENT for external calls like tools and retrieval).
  3. Automatic parentage to the current active span -- no explicit parent plumbing
     required.  Each helper uses ``trace.use_span(span, end_on_exit=True)`` to make
     the span active for the duration of the ``with`` block and auto-close it on exit.

========================================================
Usage
========================================================

::

    from agent_exec_trace.spans import (
        plan_span,
        execute_tool_span,
        retrieval_span,
        memory_span,
        record_event,
    )
    from agent_exec_trace.instrument import invoke_agent
    from agent_exec_trace.context import RunContext
    from agent_exec_trace.redact import RedactionConfig, PrivacyMode

    redact = RedactionConfig(mode=PrivacyMode.TRUNCATED, capture_tool_args=True)

    with invoke_agent(RunContext(agent_name="my-agent")):
        with plan_span("decide next action"):
            with retrieve_span("find relevant docs"):
                ...
            with execute_tool_span("search", redaction=redact, tool_args="query"):
                ...
            with memory_span("set", redaction=redact, content="remembered fact"):
                ...
            record_event(span, "loop_hint", {"count": 3})
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.trace import Span, SpanKind

from agent_exec_trace.attrs import (
    GEN_AI_OPERATION_NAME,
    GEN_AI_TOOL_NAME,
    GEN_AI_TOOL_ARGS,
    GEN_AI_TOOL_RESULT,
    GEN_AI_RESPONSE_CONTENT,
    GEN_AI_AGENT_OUTPUT,
    SPAN_KIND_MEMORY,
    SPAN_KIND_PLAN,
    SPAN_KIND_RETRIEVAL,
    SPAN_KIND_TOOL,
)
from agent_exec_trace.redact import RedactionConfig
from agent_exec_trace.tracer import get_tracer

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

# Values OTel allows as span attribute values. Kept as a single alias so every helper
# declares attribute dicts consistently and the type cannot drift per-call.
_Value = str | bool | int | float

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _start_span(
    name: str,
    *,
    kind: SpanKind,
    kind_name: str,
    attributes: dict[str, _Value] | None,
    tracer: trace.Tracer | None,
) -> Span:
    """Start a child span, stamping the operation name and merging caller attributes.

    Centralizing span construction here means every behavior helper gets the same
    operation-name behavior and attribute-merging semantics, and any future change
    (e.g. adding a common span attribute) is a one-line change.

    The operation name (``gen_ai.operation.name``) is always set first so it cannot
    be clobbered by a caller-supplied key with the same name; then caller attributes
    are layered on top.

    Args:
        name: the span name (shows as the span name in Jaeger / Tempo).
        kind: the OTel span kind (INTERNAL for agent steps, CLIENT for tool/retrieval).
        kind_name: the value for ``gen_ai.operation.name`` (e.g. ``"plan"``).
        attributes: optional caller-supplied attributes merged on top of the operation
            name.  Caller keys never overwrite ``gen_ai.operation.name``.
        tracer: optional explicit tracer; falls back to ``get_tracer()``.

    Returns:
        A started (but not yet active or ended) :class:`~opentelemetry.trace.Span`.
        The caller is responsible for making it active (via ``trace.use_span``) and
        ending it.
    """
    t = tracer or get_tracer()
    # Operation name first so it cannot be clobbered by a caller-supplied key with
    # the same name; then caller attributes are layered on top.
    attrs: dict[str, _Value] = {GEN_AI_OPERATION_NAME: kind_name}
    if attributes:
        attrs.update(attributes)
    return t.start_span(name, kind=kind, attributes=attrs)


# ---------------------------------------------------------------------------
# Public span helpers
# ---------------------------------------------------------------------------


@contextmanager
def plan_span(
    description: str,
    *,
    attributes: dict[str, _Value] | None = None,
    tracer: trace.Tracer | None = None,
) -> Iterator[Span]:
    """Create a ``plan`` child span.

    Represents a planning step: the agent deciding what to do next. ``description``
    should be a short human label (e.g. "decide next action") that shows in the
    timeline.

    Args:
        description: human label for the planning step (used as the span name).
        attributes: optional extra span attributes.
        tracer: optional explicit tracer (tests).

    Yields:
        The ``plan`` :class:`~opentelemetry.trace.Span`.

    Example::

        with plan_span("decide next action"):
            # Any nested spans started here parent to this plan span
            ...

        with plan_span("classify intent", attributes={"intent": "escalation"}):
            ...
    """
    span = _start_span(
        description,
        kind=SpanKind.INTERNAL,
        kind_name=SPAN_KIND_PLAN,
        attributes=attributes,
        tracer=tracer,
    )
    # ``use_span`` makes the span active for the block so anything started inside
    # parents to it, and ends it when the block exits.  ``end_on_exit=True``
    # guarantees the span is closed even if the block raises an exception.
    with trace.use_span(span, end_on_exit=True):
        yield span


@contextmanager
def execute_tool_span(
    tool_name: str,
    *,
    attributes: dict[str, _Value] | None = None,
    redaction: RedactionConfig | None = None,
    tool_args: str | None = None,
    tool_result: str | None = None,
    tracer: trace.Tracer | None = None,
) -> Iterator[Span]:
    """Create an ``execute_tool`` child span.

    Represents one tool call. The span carries ``gen_ai.tool.name`` (the tool identity)
    which the loop/retry detectors and tool-usage rollups aggregate on, plus optional
    ``gen_ai.tool.args`` and ``gen_ai.tool.result`` for the LLM hallucination detector.

    Privacy note: ``tool_args`` and ``tool_result`` are only written when the caller
    supplies a ``redaction`` config AND that config opts tool args in
    (``capture_tool_args``). Otherwise the content never reaches the span.

    Args:
        tool_name: the tool being called (used as the span name).
        attributes: optional extra span attributes.
        redaction: privacy config used to decide whether/how ``tool_args``/``tool_result`` is stored.
        tool_args: raw tool arguments; captured only when redaction allows it.
        tool_result: tool return value; captured only when redaction allows it.
        tracer: optional explicit tracer (tests).

    Yields:
        The ``execute_tool`` :class:`~opentelemetry.trace.Span`.

    Example::

        from agent_exec_trace.redact import RedactionConfig, PrivacyMode

        redact = RedactionConfig(mode=PrivacyMode.TRUNCATED, capture_tool_args=True)

        with execute_tool_span("search_kb", redaction=redact, tool_args='{"q": "password"}') as span:
            result = search("password")
            span.set_attribute(GEN_AI_TOOL_RESULT, str(result))
    """
    # Use gen_ai.tool.name (standard OTel semantic convention) instead of _et.tool.
    merged = {**(attributes or {}), GEN_AI_TOOL_NAME: tool_name}
    span = _start_span(
        tool_name, kind=SpanKind.CLIENT, kind_name=SPAN_KIND_TOOL, attributes=merged, tracer=tracer
    )

    # Capture tool args and result under standard gen_ai.* keys when redaction allows.
    if redaction is not None and tool_args is not None:
        redacted = redaction.apply(tool_args, allowed=redaction.capture_tool_args)
        if redacted is not None:
            span.set_attribute(GEN_AI_TOOL_ARGS, redacted)

    if redaction is not None and tool_result is not None:
        redacted = redaction.apply(tool_result, allowed=redaction.capture_tool_args)
        if redacted is not None:
            span.set_attribute(GEN_AI_TOOL_RESULT, redacted)

    with trace.use_span(span, end_on_exit=True):
        yield span


@contextmanager
def retrieval_span(
    query: str,
    *,
    attributes: dict[str, _Value] | None = None,
    tracer: trace.Tracer | None = None,
) -> Iterator[Span]:
    """Create a ``retrieval`` child span.

    Represents a retrieval/data-source lookup (RAG, vector search, KB lookup). The
    span name is the query so the timeline reads as "what was looked up".

    Args:
        query: the retrieval query (used as the span name).
        attributes: optional extra span attributes.
        tracer: optional explicit tracer (tests).

    Yields:
        The ``retrieval`` :class:`~opentelemetry.trace.Span`.

    Example::

        with retrieval_span("find relevant docs for escalation policy"):
            docs = vector_store.search(query)
            ...
    """
    span = _start_span(
        query,
        kind=SpanKind.CLIENT,
        kind_name=SPAN_KIND_RETRIEVAL,
        attributes=attributes,
        tracer=tracer,
    )
    with trace.use_span(span, end_on_exit=True):
        yield span


@contextmanager
def memory_span(
    operation: str,
    *,
    attributes: dict[str, _Value] | None = None,
    redaction: RedactionConfig | None = None,
    content: str | None = None,
    tracer: trace.Tracer | None = None,
) -> Iterator[Span]:
    """Create a ``memory`` operation child span.

    Represents a memory read/write (set, get, delete). The ``_et.operation`` attribute
    records which memory operation happened. Like ``execute_tool_span``, ``content`` is
    gated by ``capture_memory``.

    Args:
        operation: the memory operation (e.g. ``"set"``, ``"get"``, ``"delete"``).
        attributes: optional extra span attributes.
        redaction: privacy config used to decide whether/how ``content`` is stored.
        content: memory content; captured only when redaction allows it.
        tracer: optional explicit tracer (tests).

    Yields:
        The ``memory`` :class:`~opentelemetry.trace.Span`.

    Example::

        from agent_exec_trace.redact import RedactionConfig, PrivacyMode

        redact = RedactionConfig(mode=PrivacyMode.HASHED, capture_memory=True)

        with memory_span("set", redaction=redact, content="user prefers short answers"):
            memory_store.set("user_pref", "short answers")
            ...
    """
    merged = {**(attributes or {}), "_et.operation": operation}
    span = _start_span(
        operation,
        kind=SpanKind.INTERNAL,
        kind_name=SPAN_KIND_MEMORY,
        attributes=merged,
        tracer=tracer,
    )

    # Same double-gate as execute_tool_span: redaction config must be present,
    # AND the per-field flag must be opted in, AND the mode must not be
    # metadata-only.  Only then does content reach the span.
    if redaction is not None and content is not None:
        redacted = redaction.apply(content, allowed=redaction.capture_memory)
        if redacted is not None:
            span.set_attribute("gen_ai.memory.content", redacted)

    with trace.use_span(span, end_on_exit=True):
        yield span


# ---------------------------------------------------------------------------
# Span events
# ---------------------------------------------------------------------------


def record_event(span: Span, name: str, attributes: dict[str, _Value] | None = None) -> None:
    """Attach a structured event to a span.

    Events are lightweight, timestamped annotations on a span -- ideal for anomaly
    hints, warnings, and notable state changes that are not themselves spans (e.g.
    "loop_hint", "human_approval_requested"). The run-timeline UI can overlay these
    as markers.

    Args:
        span: the span to annotate.
        name: the event name (shown as the marker label).
        attributes: optional key/value event attributes.

    Example::

        with execute_tool_span("search") as span:
            result = search(query)
            if result.truncated:
                record_event(span, "result_truncated", {"count": result.count})
    """
    # OTel's ``add_event`` accepts either positional attributes dict or none.
    # Split into two branches to avoid passing an empty dict (cleaner trace output).
    if attributes:
        span.add_event(name, attributes)
    else:
        span.add_event(name)