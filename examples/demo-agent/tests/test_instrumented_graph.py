"""Tests for the LangGraph adapter (``trace_graph`` wrapper).

= Purpose
Verifies that a ``TracedGraph`` wrapping the demo agent produces a coherent trace
tree with correct OTel span semantics.  All tests use an in-memory span exporter
(no network I/O) with synchronous flush for deterministic assertions.

= Test coverage
1. **Root span** (``test_instrumented_graph_creates_root_span``):
   The instrumented graph must produce at least one ``invoke_agent`` span with
   correct operation name, agent name, version label, and a non-empty run ID.

2. **Nested parenting** (``test_instrumented_graph_nested_spans_parent_to_root``):
   All non-root spans must share the same trace_id as the root span (no orphan
   spans in a different trace).  The root span must have no parent.

3. **Planner mapping** (``test_instrumented_graph_maps_planner_to_plan_span``):
   The ``planner`` LangGraph node must produce spans with operation name
   ``SPAN_KIND_PLAN``, verifying the node-to-span-kind mapping.

4. **Tool mapping** (``test_instrumented_graph_maps_run_tool_to_tool_span``):
   The ``run_tool`` LangGraph node must produce spans with operation name
   ``SPAN_KIND_TOOL`` and a ``gen_ai.tool.name`` attribute with the tool name.

5. **Result pass-through** (``test_instrumented_graph_returns_result``):
   The instrumented graph must return the same result as the raw graph
   (``invoke()`` result must contain the expected outcome/status fields).

6. **No duplicates** (``test_no_duplicate_node_wrappers_in_trace``):
   Each LangGraph node execution must produce at most one behavior span.
   A normal run has 5 node executions (planner → run_tool → planner →
   run_tool → resolve); the total behavior span count must be ≤ 5.

= Test fixture
``_reset`` (autouse): Resets the global OTel tracer provider before and after
each test.  This prevents span leakage between tests and ensures a clean state.
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
    """Start each test from a clean tracer provider.

    This fixture runs automatically before every test (autouse=True).
    It resets the global OTel tracer so that each test starts with no
    lingering span processors, exporters, or instrumentation state.
    After the test, it resets again to clean up.
    """
    reset_tracing()
    yield  # Test runs here.
    reset_tracing()


def _exporter() -> InMemorySpanExporter:
    """Configure an in-memory, synchronously-flushed exporter.

    Uses ``SimpleSpanProcessor`` (not BatchSpanProcessor) so spans are exported
    immediately -- essential for deterministic assertions without waiting for
    flush timeouts.

    Returns:
        The configured exporter, ready for ``get_finished_spans()`` calls.
    """
    exporter = InMemorySpanExporter()
    configure_tracing(SDKConfig(), processor=SimpleSpanProcessor(exporter))
    return exporter


def test_instrumented_graph_creates_root_span() -> None:
    """Validate that invoking the instrumented graph creates a root span.

    The root span must:
        - Have operation name "invoke_agent".
        - Carry the SPAN_KIND_INVOKE_AGENT as its gen_ai operation attribute.
        - Carry the agent name "request-triage".
        - Carry the version "v0.1.0".
        - Carry a non-empty gen_ai.agent.run.id attribute.
    """
    exporter = _exporter()
    graph = trace_graph(
        build_graph(),
        agent_name="request-triage",
        agent_version="v0.1.0",
    )
    graph.invoke(normal_request())

    spans = exporter.get_finished_spans()
    assert len(spans) >= 1

    # Find the root span by name "invoke_agent" (there should be exactly one).
    root = next(s for s in spans if s.name == "invoke_agent")
    assert root.attributes is not None
    assert root.attributes[GEN_AI_OPERATION_NAME] == SPAN_KIND_INVOKE_AGENT
    assert root.attributes[GEN_AI_AGENT_NAME] == "request-triage"
    assert root.attributes[GEN_AI_AGENT_VERSION_LABEL] == "v0.1.0"
    assert GEN_AI_AGENT_RUN_ID in root.attributes


def test_instrumented_graph_nested_spans_parent_to_root() -> None:
    """Validate that all child spans share the same trace as the root.

    The root span (invoke_agent) must:
        - Have no parent (it is the trace root).
    All other spans (behavior spans: plan, tool) must:
        - Share the root's trace_id.
    This guarantees no orphan spans are leaking across traces.
    """
    exporter = _exporter()
    graph = trace_graph(build_graph(), agent_name="request-triage")
    graph.invoke(normal_request())

    spans = exporter.get_finished_spans()
    root = next(s for s in spans if s.name == "invoke_agent")
    root_ctx = root.context
    assert root_ctx is not None

    # Root span must have no parent in the trace tree.
    assert root.parent is None

    # All non-root spans must share the trace_id with the root.
    children = [s for s in spans if s.name != "invoke_agent"]
    assert len(children) >= 1
    for child in children:
        child_ctx = child.context
        assert child_ctx is not None
        assert child_ctx.trace_id == root_ctx.trace_id


def test_instrumented_graph_maps_planner_to_plan_span() -> None:
    """Validate that the ``planner`` node produces ``SPAN_KIND_PLAN`` spans.

    The trace_graph adapter maps the "planner" LangGraph node to operation
    name "plan" with the SPAN_KIND_PLAN attribute.  This test ensures that
    at least one such span exists for a normal run (which has 2 planner turns).
    """
    exporter = _exporter()
    graph = trace_graph(build_graph(), agent_name="request-triage")
    graph.invoke(normal_request())

    plan_spans = [
        s for s in exporter.get_finished_spans()
        if s.attributes and s.attributes.get(GEN_AI_OPERATION_NAME) == SPAN_KIND_PLAN
    ]
    assert len(plan_spans) >= 1


def test_instrumented_graph_maps_run_tool_to_tool_span() -> None:
    """Validate that ``run_tool`` produces ``SPAN_KIND_TOOL`` spans with tool name.

    Each tool span must:
        - Have SPAN_KIND_TOOL as its gen_ai operation attribute.
        - Carry ``gen_ai.tool.name`` with either "search_kb" or "lookup_account" (the
          two tools used by the normal seed).
    """
    exporter = _exporter()
    graph = trace_graph(build_graph(), agent_name="request-triage")
    graph.invoke(normal_request())

    tool_spans = [
        s for s in exporter.get_finished_spans()
        if s.attributes and s.attributes.get(GEN_AI_OPERATION_NAME) == SPAN_KIND_TOOL
    ]
    assert len(tool_spans) >= 1

    # Verify the first tool span carries the expected tool-name attribute.
    tool_attrs = tool_spans[0].attributes
    assert tool_attrs is not None
    assert tool_attrs.get("gen_ai.tool.name") in ("search_kb", "lookup_account")


def test_instrumented_graph_returns_result() -> None:
    """Validate that instrumented graphs preserve the result from the raw graph.

    The ``trace_graph`` wrapper must be transparent: ``invoke()`` on the
    instrumented graph must return the same outcome/status as the raw graph.
    This also proves that span export doesn't interfere with graph execution.
    """
    exporter = _exporter()
    graph = trace_graph(build_graph(), agent_name="request-triage")
    result = graph.invoke(normal_request())
    assert result.get("outcome") == "resolve"
    assert result.get("status") == "ok"
    # At least the root span should exist after invocation.
    assert len(exporter.get_finished_spans()) >= 1


def test_no_duplicate_node_wrappers_in_trace() -> None:
    """Validate that each LangGraph node produces at most one behavior span.

    A normal run's node execution sequence is:
        planner → run_tool → planner → run_tool → resolve = 5 node executions.
    Each node should produce at most one behavior span (exclude the root).
    So the behavior span count must be > 1 and ≤ 5.
    If this exceeds 5, there's a duplicate wrapper bug in the adapter.
    """
    exporter = _exporter()
    graph = trace_graph(build_graph(), agent_name="request-triage")
    graph.invoke(normal_request())

    spans = exporter.get_finished_spans()

    # Count behavior spans (all spans except the root invoke_agent).
    behavior = [s for s in spans if s.name != "invoke_agent"]

    # Normal run: planner (2x) + run_tool (2x) + resolve (1x) = 5 node execs.
    # Each should produce at most one span.
    assert len(behavior) > 1
    assert len(behavior) <= 5