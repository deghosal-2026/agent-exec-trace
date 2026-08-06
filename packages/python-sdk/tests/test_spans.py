"""Tests for nested behavior span helpers.

These exercise the behavioral span contract: child spans parent correctly under the
root, carry the right ``gen_ai.operation.name`` for their behavior class, and --
critically -- only ever store sensitive payloads (tool args, memory content) when
both the privacy mode and the per-field capture flag allow it.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from agent_exec_trace.attrs import (
    GEN_AI_OPERATION_NAME,
    SPAN_KIND_MEMORY,
    SPAN_KIND_PLAN,
    SPAN_KIND_RETRIEVAL,
    SPAN_KIND_TOOL,
)
from agent_exec_trace.config import SDKConfig
from agent_exec_trace.context import RunContext
from agent_exec_trace.instrument import invoke_agent
from agent_exec_trace.redact import PrivacyMode, RedactionConfig
from agent_exec_trace.spans import (
    execute_tool_span,
    memory_span,
    plan_span,
    plan_span_simple,
    record_event,
    retrieval_span,
    tool_span,
)
from agent_exec_trace.tracer import configure_tracing, reset_tracing


@pytest.fixture(autouse=True)
def _reset() -> Iterator[None]:
    """Start each test from a clean tracer provider (see test_instrument.py)."""
    reset_tracing()
    yield
    reset_tracing()


def _exporter() -> InMemorySpanExporter:
    """Configure an in-memory, synchronously-flushed exporter (see test_instrument.py)."""
    exporter = InMemorySpanExporter()
    configure_tracing(SDKConfig(), processor=SimpleSpanProcessor(exporter))
    return exporter


def test_nested_spans_parent_to_root() -> None:
    # All behavior spans created inside the run share the root's trace id, forming
    # one coherent trace tree (no orphaned spans).
    exporter = _exporter()
    ctx = RunContext(run_id="run-1", agent_name="triage")
    with invoke_agent(ctx):
        with plan_span("plan the work"), execute_tool_span("search_kb"):
            pass
        with retrieval_span("find docs"):
            pass
        with memory_span("set"):
            pass

    spans = exporter.get_finished_spans()
    root = next(s for s in spans if s.name == "invoke_agent")
    children = [s for s in spans if s.name != "invoke_agent"]
    assert len(children) == 4
    root_ctx = root.context
    assert root_ctx is not None
    assert root.parent is None
    for child in children:
        child_ctx = child.context
        assert child_ctx is not None
        assert child_ctx.trace_id == root_ctx.trace_id


def test_nested_tool_parents_to_plan_span() -> None:
    # Nested helpers parent to the innermost active span: the tool is a child of the
    # plan, not a sibling -- this is what makes the timeline hierarchy navigable.
    exporter = _exporter()
    ctx = RunContext(run_id="run-1", agent_name="triage")
    with invoke_agent(ctx), plan_span("plan the work"), execute_tool_span("search_kb"):
        pass

    spans = exporter.get_finished_spans()
    plan = next(s for s in spans if s.name == "plan the work")
    tool = next(s for s in spans if s.name == "search_kb")
    plan_ctx = plan.context
    tool_parent = tool.parent
    assert plan_ctx is not None
    assert tool_parent is not None
    assert tool_parent.span_id == plan_ctx.span_id


def test_behavior_span_operation_names() -> None:
    # Each behavior class stamps its own gen_ai.operation.name so the analytics
    # service and UI can classify spans without parsing span names.
    exporter = _exporter()
    ctx = RunContext(run_id="run-1", agent_name="triage")
    with invoke_agent(ctx):
        with plan_span("plan"):
            pass
        with execute_tool_span("tool"):
            pass
        with retrieval_span("q"):
            pass
        with memory_span("op"):
            pass

    def _op(span: object) -> str | None:
        # Read attributes defensively via getattr so the test doesn't depend on the
        # concrete span type's attribute accessor.
        attributes = getattr(span, "attributes", None)
        if attributes is None:
            return None
        return str(attributes[GEN_AI_OPERATION_NAME])

    attrs = {s.name: _op(s) for s in exporter.get_finished_spans()}
    assert attrs["plan"] == SPAN_KIND_PLAN
    assert attrs["tool"] == SPAN_KIND_TOOL
    assert attrs["q"] == SPAN_KIND_RETRIEVAL
    assert attrs["op"] == SPAN_KIND_MEMORY


def test_tool_args_dropped_in_metadata_only_mode() -> None:
    # Privacy default: METADATA_ONLY drops payloads outright, even when the field is
    # "allowed". This is the core privacy guarantee.
    exporter = _exporter()
    ctx = RunContext(run_id="run-1", agent_name="triage")
    redaction = RedactionConfig(mode=PrivacyMode.METADATA_ONLY)
    with (
        invoke_agent(ctx),
        execute_tool_span("search_kb", redaction=redaction, tool_args="secret query"),
    ):
        pass
    span = next(s for s in exporter.get_finished_spans() if s.name == "search_kb")
    assert span.attributes is not None
    assert "gen_ai.tool.args" not in span.attributes


def test_tool_args_dropped_when_field_not_opted_in() -> None:
    # Double gate: even in a capture-enabled mode, a field the caller did NOT opt in
    # must not be stored. Opting into prompts does NOT opt into tool args.
    exporter = _exporter()
    ctx = RunContext(run_id="run-1", agent_name="triage")
    redaction = RedactionConfig(mode=PrivacyMode.TRUNCATED, capture_prompts=True, capture_tool_args=False)
    with (
        invoke_agent(ctx),
        execute_tool_span("search_kb", redaction=redaction, tool_args="secret query"),
    ):
        pass
    span = next(s for s in exporter.get_finished_spans() if s.name == "search_kb")
    assert span.attributes is not None
    assert "gen_ai.tool.args" not in span.attributes


def test_tool_args_captured_when_enabled() -> None:
    # When the field IS opted in under a capture mode, args flow through redaction
    # (truncation) and onto the span.
    exporter = _exporter()
    ctx = RunContext(run_id="run-1", agent_name="triage")
    redaction = RedactionConfig(mode=PrivacyMode.TRUNCATED, capture_tool_args=True)
    with (
        invoke_agent(ctx),
        execute_tool_span("search_kb", redaction=redaction, tool_args="secret query"),
    ):
        pass
    span = next(s for s in exporter.get_finished_spans() if s.name == "search_kb")
    assert span.attributes is not None
    assert span.attributes["gen_ai.tool.args"] == "secret query"


def test_memory_content_gated_by_capture_memory_flag() -> None:
    # Memory content is gated by capture_memory specifically; opting into tool args
    # does not leak memory content.
    exporter = _exporter()
    ctx = RunContext(run_id="run-1", agent_name="triage")
    redaction = RedactionConfig(mode=PrivacyMode.TRUNCATED, capture_tool_args=True)
    with (
        invoke_agent(ctx),
        memory_span("set", redaction=redaction, content="memory with secrets"),
    ):
        pass
    span = next(s for s in exporter.get_finished_spans() if s.name == "set")
    assert span.attributes is not None
    assert "gen_ai.memory.content" not in span.attributes


def test_memory_content_captured_when_enabled() -> None:
    # With capture_memory enabled, memory content passes through redaction onto the
    # span.
    exporter = _exporter()
    ctx = RunContext(run_id="run-1", agent_name="triage")
    redaction = RedactionConfig(mode=PrivacyMode.TRUNCATED, capture_memory=True)
    with (
        invoke_agent(ctx),
        memory_span("set", redaction=redaction, content="plain memory"),
    ):
        pass
    span = next(s for s in exporter.get_finished_spans() if s.name == "set")
    assert span.attributes is not None
    assert span.attributes["gen_ai.memory.content"] == "plain memory"


def test_record_event_attaches_event() -> None:
    # Events are lightweight, timestamped markers (e.g. anomaly hints) attached to a
    # span, distinct from child spans.
    exporter = _exporter()
    ctx = RunContext(run_id="run-1", agent_name="triage")
    with invoke_agent(ctx) as span:
        record_event(span, "anomaly_hint", {"code": "loop"})
    root = exporter.get_finished_spans()[0]
    assert len(root.events) == 1
    assert root.events[0].name == "anomaly_hint"
    assert root.events[0].attributes is not None
    assert root.events[0].attributes["code"] == "loop"


def test_tool_span_creates_tool_span_with_default_redaction() -> None:
    exporter = _exporter()
    ctx = RunContext(run_id="run-1", agent_name="triage")
    with invoke_agent(ctx), tool_span("search_kb", tool_input='{"q": "test"}'):
        pass
    span = next(s for s in exporter.get_finished_spans() if s.name == "search_kb")
    assert span.attributes is not None
    assert span.attributes["gen_ai.tool.name"] == "search_kb"
    assert span.attributes["gen_ai.operation.name"] == "execute_tool"
    assert span.attributes["gen_ai.tool.args"] is not None


def test_tool_span_parents_to_root() -> None:
    exporter = _exporter()
    ctx = RunContext(run_id="run-1", agent_name="triage")
    with invoke_agent(ctx) as root, tool_span("lookup"):
        pass
    span = next(s for s in exporter.get_finished_spans() if s.name == "lookup")
    assert span.parent is not None
    assert span.parent.span_id == root.context.span_id


def test_tool_span_with_result_captures_output() -> None:
    exporter = _exporter()
    ctx = RunContext(run_id="run-1", agent_name="triage")
    redaction = RedactionConfig(mode=PrivacyMode.TRUNCATED, capture_tool_args=True)
    with (
        invoke_agent(ctx),
        execute_tool_span("search", redaction=redaction, tool_args="query", tool_result="found"),
    ):
        pass
    span = next(s for s in exporter.get_finished_spans() if s.name == "search")
    assert span.attributes is not None
    assert span.attributes["gen_ai.tool.args"] == "query"
    assert span.attributes["gen_ai.tool.result"] == "found"


def test_plan_span_simple_creates_plan_span() -> None:
    exporter = _exporter()
    ctx = RunContext(run_id="run-1", agent_name="triage")
    with invoke_agent(ctx), plan_span_simple("decide"):
        pass
    span = next(s for s in exporter.get_finished_spans() if s.name == "decide")
    assert span.attributes is not None
    assert span.attributes["gen_ai.operation.name"] == "plan"