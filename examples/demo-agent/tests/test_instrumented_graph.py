"""Tests for the LangGraph adapter (``trace_graph`` wrapper).

Verifies that a ``TracedGraph`` wrapping the demo agent produces a coherent trace
tree: one root ``invoke_agent`` span with run metadata, plus nested ``plan`` and
``execute_tool`` behavior spans parented to it -- no orphan spans, no duplicate
node wrappers leaking into the trace.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from agent_exec_trace.attrs import (
    GEN_AI_AGENT_NAME,
    GEN_AI_AGENT_RUN_ID,
    GEN_AI_AGENT_VERSION_LABEL,
    GEN_AI_OPERATION_NAME,
    SPAN_KIND_INVOKE_AGENT,
    SPAN_KIND_PLAN,
    SPAN_KIND_TOOL,
)
from agent_exec_trace.config import SDKConfig
from agent_exec_trace.langgraph import trace_graph
from agent_exec_trace.tracer import configure_tracing, reset_tracing
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from request_triage.graph import build_graph
from request_triage.seeds import normal_request


@pytest.fixture(autouse=True)
def _reset() -> Iterator[None]:
    """Start each test from a clean tracer provider."""
    reset_tracing()
    yield
    reset_tracing()


def _exporter() -> InMemorySpanExporter:
    """Configure an in-memory, synchronously-flushed exporter."""
    exporter = InMemorySpanExporter()
    configure_tracing(SDKConfig(), processor=SimpleSpanProcessor(exporter))
    return exporter


def test_instrumented_graph_creates_root_span() -> None:
    exporter = _exporter()
    graph = trace_graph(
        build_graph(),
        agent_name="request-triage",
        agent_version="v0.1.0",
    )
    graph.invoke(normal_request())

    spans = exporter.get_finished_spans()
    assert len(spans) >= 1
    root = next(s for s in spans if s.name == "invoke_agent")
    assert root.attributes is not None
    assert root.attributes[GEN_AI_OPERATION_NAME] == SPAN_KIND_INVOKE_AGENT
    assert root.attributes[GEN_AI_AGENT_NAME] == "request-triage"
    assert root.attributes[GEN_AI_AGENT_VERSION_LABEL] == "v0.1.0"
    assert GEN_AI_AGENT_RUN_ID in root.attributes


def test_instrumented_graph_nested_spans_parent_to_root() -> None:
    exporter = _exporter()
    graph = trace_graph(build_graph(), agent_name="request-triage")
    graph.invoke(normal_request())

    spans = exporter.get_finished_spans()
    root = next(s for s in spans if s.name == "invoke_agent")
    root_ctx = root.context
    assert root_ctx is not None
    assert root.parent is None
    children = [s for s in spans if s.name != "invoke_agent"]
    assert len(children) >= 1
    for child in children:
        child_ctx = child.context
        assert child_ctx is not None
        assert child_ctx.trace_id == root_ctx.trace_id


def test_instrumented_graph_maps_planner_to_plan_span() -> None:
    exporter = _exporter()
    graph = trace_graph(build_graph(), agent_name="request-triage")
    graph.invoke(normal_request())

    plan_spans = [
        s for s in exporter.get_finished_spans()
        if s.attributes and s.attributes.get(GEN_AI_OPERATION_NAME) == SPAN_KIND_PLAN
    ]
    assert len(plan_spans) >= 1


def test_instrumented_graph_maps_run_tool_to_tool_span() -> None:
    exporter = _exporter()
    graph = trace_graph(build_graph(), agent_name="request-triage")
    graph.invoke(normal_request())

    tool_spans = [
        s for s in exporter.get_finished_spans()
        if s.attributes and s.attributes.get(GEN_AI_OPERATION_NAME) == SPAN_KIND_TOOL
    ]
    assert len(tool_spans) >= 1
    # The tool span should carry the _et.tool attribute with the tool name.
    tool_attrs = tool_spans[0].attributes
    assert tool_attrs is not None
    assert tool_attrs.get("_et.tool") in ("search_kb", "lookup_account")


def test_instrumented_graph_returns_result() -> None:
    exporter = _exporter()
    graph = trace_graph(build_graph(), agent_name="request-triage")
    result = graph.invoke(normal_request())
    assert result.get("outcome") == "resolve"
    assert result.get("status") == "ok"
    assert len(exporter.get_finished_spans()) >= 1


def test_no_duplicate_node_wrappers_in_trace() -> None:
    """Each LangGraph node should produce at most one behavior span."""
    exporter = _exporter()
    graph = trace_graph(build_graph(), agent_name="request-triage")
    graph.invoke(normal_request())

    spans = exporter.get_finished_spans()
    # Count behavior spans (exclude the root).
    behavior = [s for s in spans if s.name != "invoke_agent"]
    # A normal run should have: planner + run_tool + planner + run_tool + resolve = 5
    # node executions; each produces at most one span.
    assert len(behavior) > 1
    assert len(behavior) <= 5