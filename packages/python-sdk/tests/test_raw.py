"""Tests for the raw Python adapter (``@trace_agent`` decorator).

The decorator is the "no-framework" onboarding path: it wraps any plain Python agent
function in an ``invoke_agent`` root span, so traces produced by a raw agent are
structurally consistent with the LangGraph adapter's output (same root shape, same
metadata keys, nested behavior spans parent to the root).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace.status import StatusCode

from agent_exec_trace.attrs import (
    GEN_AI_AGENT_NAME,
    GEN_AI_AGENT_RUN_ID,
    GEN_AI_AGENT_VERSION_LABEL,
    GEN_AI_OPERATION_NAME,
    SPAN_KIND_INVOKE_AGENT,
)
from agent_exec_trace.config import SDKConfig
from agent_exec_trace.raw import trace_agent
from agent_exec_trace.spans import execute_tool_span, plan_span
from agent_exec_trace.tracer import configure_tracing, reset_tracing


@pytest.fixture(autouse=True)
def _reset() -> Iterator[None]:
    """Start each test from a clean tracer provider (see test_instrument.py)."""
    reset_tracing()
    yield
    reset_tracing()


def _exporter() -> InMemorySpanExporter:
    """Configure an in-memory, synchronously-flushed exporter."""
    exporter = InMemorySpanExporter()
    configure_tracing(SDKConfig(), processor=SimpleSpanProcessor(exporter))
    return exporter


def test_trace_agent_creates_root_span() -> None:
    exporter = _exporter()

    @trace_agent("triage", agent_version="v0.1.0")
    def run() -> None:
        pass

    run()

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.name == "invoke_agent"
    assert span.attributes is not None
    assert span.attributes[GEN_AI_OPERATION_NAME] == SPAN_KIND_INVOKE_AGENT
    assert span.attributes[GEN_AI_AGENT_NAME] == "triage"
    assert span.attributes[GEN_AI_AGENT_VERSION_LABEL] == "v0.1.0"
    assert span.attributes[GEN_AI_AGENT_RUN_ID]


def test_trace_agent_nested_spans_parent_to_root() -> None:
    exporter = _exporter()

    @trace_agent("triage")
    def run() -> None:
        with plan_span("decide"), execute_tool_span("search_kb"):
            pass

    run()

    spans = exporter.get_finished_spans()
    root = next(s for s in spans if s.name == "invoke_agent")
    root_ctx = root.context
    assert root_ctx is not None
    children = [s for s in spans if s.name != "invoke_agent"]
    assert len(children) == 2
    for child in children:
        child_ctx = child.context
        assert child_ctx is not None
        assert child_ctx.trace_id == root_ctx.trace_id


def test_trace_agent_returns_function_result() -> None:
    exporter = _exporter()

    @trace_agent("triage")
    def run(a: int, b: int) -> int:
        return a + b

    assert run(2, 3) == 5
    assert len(exporter.get_finished_spans()) == 1


def test_trace_agent_preserves_function_metadata() -> None:
    exporter = _exporter()

    @trace_agent("triage")
    def my_agent_function() -> None:
        pass

    # functools.wraps must preserve the wrapped function's name and signature.
    assert my_agent_function.__name__ == "my_agent_function"
    my_agent_function()
    assert len(exporter.get_finished_spans()) == 1


def test_trace_agent_propagates_exception() -> None:
    exporter = _exporter()

    @trace_agent("triage")
    def run() -> None:
        raise ValueError("boom")

    with pytest.raises(ValueError):
        run()

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    # start_as_current_span records exceptions on the span, so the root carries the
    # error status even though the exception propagated to the caller.
    assert spans[0].status.status_code == StatusCode.ERROR
