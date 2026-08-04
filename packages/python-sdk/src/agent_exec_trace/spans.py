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
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.trace import Span, SpanKind

from agent_exec_trace.attrs import (
    GEN_AI_OPERATION_NAME,
    SPAN_KIND_MEMORY,
    SPAN_KIND_PLAN,
    SPAN_KIND_RETRIEVAL,
    SPAN_KIND_TOOL,
)
from agent_exec_trace.redact import RedactionConfig
from agent_exec_trace.tracer import get_tracer

# Values OTel allows as span attribute values. Kept as a single alias so every helper
# declares attribute dicts consistently and the type cannot drift per-call.
_Value = str | bool | int | float


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
    """
    t = tracer or get_tracer()
    # Operation name first so it cannot be clobbered by a caller-supplied key with
    # the same name; then caller attributes are layered on top.
    attrs: dict[str, _Value] = {GEN_AI_OPERATION_NAME: kind_name}
    if attributes:
        attrs.update(attributes)
    return t.start_span(name, kind=kind, attributes=attrs)


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
        description: human label for the planning step.
        attributes: optional extra span attributes.
        tracer: optional explicit tracer (tests).

    Yields:
        The ``plan`` :class:`~opentelemetry.trace.Span`.
    """
    span = _start_span(
        description,
        kind=SpanKind.INTERNAL,
        kind_name=SPAN_KIND_PLAN,
        attributes=attributes,
        tracer=tracer,
    )
    # ``use_span`` makes the span active for the block so anything started inside
    # parents to it, and ends it when the block exits.
    with trace.use_span(span, end_on_exit=True):
        yield span


@contextmanager
def execute_tool_span(
    tool_name: str,
    *,
    attributes: dict[str, _Value] | None = None,
    redaction: RedactionConfig | None = None,
    tool_args: str | None = None,
    tracer: trace.Tracer | None = None,
) -> Iterator[Span]:
    """Create an ``execute_tool`` child span.

    Represents one tool call. The span carries ``_et.tool`` (the tool identity) which
    the loop/retry detectors and tool-usage rollups aggregate on.

    Privacy note: ``tool_args`` is only written when the caller supplies a
    ``redaction`` config AND that config opts tool args in (``capture_tool_args``).
    Otherwise the args never reach the span, even in a "capture enabled" config -- the
    per-field flag is what gates it (see :meth:`RedactionConfig.apply`).

    Args:
        tool_name: the tool being called.
        attributes: optional extra span attributes.
        redaction: privacy config used to decide whether/how ``tool_args`` is stored.
        tool_args: raw tool arguments; captured only when redaction allows it.
        tracer: optional explicit tracer (tests).

    Yields:
        The ``execute_tool`` :class:`~opentelemetry.trace.Span`.
    """
    merged = {**(attributes or {}), "_et.tool": tool_name}
    span = _start_span(
        tool_name, kind=SpanKind.CLIENT, kind_name=SPAN_KIND_TOOL, attributes=merged, tracer=tracer
    )

    # Guard: only attempt the write when both a redaction config and args are present.
    # ``apply`` decides drop/truncate/hash based on mode + the capture_tool_args flag.
    if redaction is not None and tool_args is not None:
        redacted = redaction.apply(tool_args, allowed=redaction.capture_tool_args)
        if redacted is not None:
            span.set_attribute("_et.tool_args", redacted)

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
        operation: the memory operation (e.g. ``"set"``, ``"get"``).
        attributes: optional extra span attributes.
        redaction: privacy config used to decide whether/how ``content`` is stored.
        content: memory content; captured only when redaction allows it.
        tracer: optional explicit tracer (tests).

    Yields:
        The ``memory`` :class:`~opentelemetry.trace.Span`.
    """
    merged = {**(attributes or {}), "_et.operation": operation}
    span = _start_span(
        operation,
        kind=SpanKind.INTERNAL,
        kind_name=SPAN_KIND_MEMORY,
        attributes=merged,
        tracer=tracer,
    )

    if redaction is not None and content is not None:
        redacted = redaction.apply(content, allowed=redaction.capture_memory)
        if redacted is not None:
            span.set_attribute("_et.content", redacted)

    with trace.use_span(span, end_on_exit=True):
        yield span


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
    """
    if attributes:
        span.add_event(name, attributes)
    else:
        span.add_event(name)