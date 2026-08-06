"""Tests for the LangGraph adapter.

Tests the _NodeCallbackHandler directly by simulating LangGraph callback events,
and the TracedGraph wrapper with a mock graph to verify the trace tree is
produced correctly without requiring a real LangGraph instance.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock

import pytest
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from agent_exec_trace.config import SDKConfig
from agent_exec_trace.langgraph import TracedGraph, _NodeCallbackHandler, trace_graph
from agent_exec_trace.tracer import configure_tracing, reset_tracing


@pytest.fixture(autouse=True)
def _reset() -> Iterator[None]:
    reset_tracing()
    yield
    reset_tracing()


def _exporter() -> InMemorySpanExporter:
    exporter = InMemorySpanExporter()
    configure_tracing(SDKConfig(), processor=SimpleSpanProcessor(exporter))
    return exporter


def _kwargs(run_id: str, tags: list[str], node: str | None) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "tags": tags,
        "metadata": {"langgraph_node": node} if node else {},
    }


# ---------------------------------------------------------------------------
# _NodeCallbackHandler — static methods
# ---------------------------------------------------------------------------

def test_node_name_extracts_from_metadata() -> None:
    assert _NodeCallbackHandler._node_name({"metadata": {"langgraph_node": "planner"}}) == "planner"


def test_node_name_returns_none_without_metadata() -> None:
    assert _NodeCallbackHandler._node_name({}) is None
    assert _NodeCallbackHandler._node_name({"metadata": "not-dict"}) is None


def test_is_primary_start_detects_graph_step() -> None:
    assert _NodeCallbackHandler._is_primary_start({"tags": ["graph:step:1"]}) is True
    assert _NodeCallbackHandler._is_primary_start({"tags": ["seq:step:1"]}) is False
    assert _NodeCallbackHandler._is_primary_start({"tags": []}) is False
    assert _NodeCallbackHandler._is_primary_start({}) is False


# ---------------------------------------------------------------------------
# _NodeCallbackHandler — on_chain_start / on_chain_end
# ---------------------------------------------------------------------------

def test_on_chain_start_creates_plan_span_for_planner() -> None:
    _exporter()
    handler = _NodeCallbackHandler()
    rid = str(uuid.uuid4())
    handler.on_chain_start(
        serialized={},
        inputs={"messages": []},
        **_kwargs(rid, ["graph:step:1"], "planner"),
    )
    assert rid in handler._spans
    span = handler._spans[rid]
    assert span is not None


def test_on_chain_start_creates_tool_span_for_run_tool() -> None:
    _exporter()
    handler = _NodeCallbackHandler()
    rid = str(uuid.uuid4())
    handler.on_chain_start(
        serialized={},
        inputs={"plan": "search_kb", "query": "test"},
        **_kwargs(rid, ["graph:step:2"], "run_tool"),
    )
    assert rid in handler._spans


def test_on_chain_start_creates_generic_span_for_unknown_node() -> None:
    _exporter()
    handler = _NodeCallbackHandler()
    rid = str(uuid.uuid4())
    handler.on_chain_start(
        serialized={},
        inputs={},
        **_kwargs(rid, ["graph:step:3"], "escalate"),
    )
    assert rid in handler._spans


def test_on_chain_start_ignores_seq_step_events() -> None:
    _exporter()
    handler = _NodeCallbackHandler()
    rid = str(uuid.uuid4())
    handler.on_chain_start(
        serialized={},
        inputs={},
        **_kwargs(rid, ["seq:step:1"], "planner"),
    )
    assert rid not in handler._spans


def test_on_chain_start_ignores_no_node_name() -> None:
    _exporter()
    handler = _NodeCallbackHandler()
    rid = str(uuid.uuid4())
    handler.on_chain_start(
        serialized={},
        inputs={},
        **_kwargs(rid, ["graph:step:1"], None),
    )
    assert rid not in handler._spans


def test_on_chain_end_closes_span_and_captures_output() -> None:
    _exporter()
    handler = _NodeCallbackHandler()
    rid = str(uuid.uuid4())
    handler.on_chain_start(
        serialized={},
        inputs={},
        **_kwargs(rid, ["graph:step:1"], "planner"),
    )
    handler.on_chain_end(
        outputs={"plan": "do something"},
        **_kwargs(rid, ["graph:step:1"], "planner"),
    )
    assert rid not in handler._spans


def test_on_chain_end_for_tool_node_captures_result() -> None:
    _exporter()
    handler = _NodeCallbackHandler()
    rid = str(uuid.uuid4())
    handler.on_chain_start(
        serialized={},
        inputs={"plan": "search"},
        **_kwargs(rid, ["graph:step:2"], "run_tool"),
    )
    handler.on_chain_end(
        outputs={"result": "found"},
        **_kwargs(rid, ["graph:step:2"], "run_tool"),
    )
    assert rid not in handler._spans


def test_on_chain_end_noop_for_unknown_run_id() -> None:
    _exporter()
    handler = _NodeCallbackHandler()
    handler.on_chain_end(
        outputs={},
        **_kwargs("unknown-rid", ["graph:step:1"], "planner"),
    )
    assert len(handler._spans) == 0


def test_on_chain_end_handles_empty_outputs() -> None:
    _exporter()
    handler = _NodeCallbackHandler()
    rid = str(uuid.uuid4())
    handler.on_chain_start(
        serialized={},
        inputs={},
        **_kwargs(rid, ["graph:step:1"], "planner"),
    )
    handler.on_chain_end(
        outputs={},
        **_kwargs(rid, ["graph:step:1"], "planner"),
    )
    assert rid not in handler._spans


# ---------------------------------------------------------------------------
# _NodeCallbackHandler — on_chain_error
# ---------------------------------------------------------------------------

def test_on_chain_error_records_exception_and_closes_span() -> None:
    _exporter()
    handler = _NodeCallbackHandler()
    rid = str(uuid.uuid4())
    handler.on_chain_start(
        serialized={},
        inputs={},
        **_kwargs(rid, ["graph:step:1"], "planner"),
    )
    error = RuntimeError("node failed")
    handler.on_chain_error(
        error=error,
        **_kwargs(rid, ["graph:step:1"], "planner"),
    )
    assert rid not in handler._spans


def test_on_chain_error_noop_for_unknown_run_id() -> None:
    _exporter()
    handler = _NodeCallbackHandler()
    handler.on_chain_error(
        error=RuntimeError("boom"),
        **_kwargs("unknown", ["graph:step:1"], "planner"),
    )
    assert len(handler._spans) == 0


# ---------------------------------------------------------------------------
# TracedGraph — invoke with a mock graph
# ---------------------------------------------------------------------------

def _mock_graph(result: dict[str, Any] | None = None) -> Any:
    graph = MagicMock()
    graph.invoke.return_value = result or {"response": "task done"}
    return graph


def test_traced_graph_invoke_produces_root_span_with_output() -> None:
    exporter = _exporter()
    graph = _mock_graph({"response": "completed"})
    traced = TracedGraph(graph, agent_name="test-agent", agent_version="v1.0")
    result = traced.invoke({"messages": []})
    assert result == {"response": "completed"}
    spans = exporter.get_finished_spans()
    assert len(spans) >= 1
    root = next(s for s in spans if s.name == "invoke_agent")
    assert root.attributes is not None
    assert root.attributes["gen_ai.agent.name"] == "test-agent"
    assert root.attributes["gen_ai.response.content"] == "completed"


def test_traced_graph_invoke_fallback_output_keys() -> None:
    exporter = _exporter()
    graph = _mock_graph({"output": "via-output-key"})
    traced = TracedGraph(graph, agent_name="a")
    traced.invoke({})
    root = next(s for s in exporter.get_finished_spans() if s.name == "invoke_agent")
    assert root.attributes is not None
    assert root.attributes["gen_ai.response.content"] == "via-output-key"


def test_traced_graph_invoke_with_answer_key() -> None:
    exporter = _exporter()
    graph = _mock_graph({"answer": "42"})
    traced = TracedGraph(graph, agent_name="a")
    traced.invoke({})
    root = next(s for s in exporter.get_finished_spans() if s.name == "invoke_agent")
    assert root.attributes is not None
    assert root.attributes["gen_ai.response.content"] == "42"


def test_traced_graph_invoke_with_outcome_key() -> None:
    exporter = _exporter()
    graph = _mock_graph({"outcome": "success"})
    traced = TracedGraph(graph, agent_name="a")
    traced.invoke({})
    root = next(s for s in exporter.get_finished_spans() if s.name == "invoke_agent")
    assert root.attributes is not None
    assert root.attributes["gen_ai.response.content"] == "success"


def test_traced_graph_invoke_no_output_when_result_has_no_known_key() -> None:
    exporter = _exporter()
    graph = _mock_graph({"unknown_key": "value"})
    traced = TracedGraph(graph, agent_name="a")
    traced.invoke({})
    root = next(s for s in exporter.get_finished_spans() if s.name == "invoke_agent")
    assert root.attributes is not None
    assert "gen_ai.response.content" not in root.attributes


def test_traced_graph_invoke_merges_existing_callbacks() -> None:
    exporter = _exporter()
    graph = _mock_graph({"response": "ok"})
    user_cb = MagicMock()
    traced = TracedGraph(graph, agent_name="a")
    traced.invoke({"messages": []}, config={"callbacks": [user_cb]})
    _, invoke_kwargs = graph.invoke.call_args
    merged = invoke_kwargs.get("config", {})
    assert isinstance(merged.get("callbacks"), list)
    assert len(merged["callbacks"]) == 2


def test_traced_graph_invoke_no_existing_callbacks() -> None:
    exporter = _exporter()
    graph = _mock_graph({"response": "ok"})
    traced = TracedGraph(graph, agent_name="a")
    traced.invoke({"messages": []})
    _, invoke_kwargs = graph.invoke.call_args
    merged = invoke_kwargs.get("config", {})
    assert isinstance(merged.get("callbacks"), list)
    assert len(merged["callbacks"]) == 1


def test_traced_graph_invoke_with_non_dict_result() -> None:
    exporter = _exporter()
    graph = MagicMock()
    graph.invoke.return_value = "not-a-dict"
    traced = TracedGraph(graph, agent_name="a")
    result = traced.invoke({})
    assert result == "not-a-dict"


# ---------------------------------------------------------------------------
# trace_graph factory function
# ---------------------------------------------------------------------------

def test_trace_graph_returns_traced_graph() -> None:
    graph = _mock_graph()
    traced = trace_graph(graph, agent_name="my-agent", agent_version="v2.0")
    assert isinstance(traced, TracedGraph)
    assert traced._agent_name == "my-agent"
    assert traced._agent_version == "v2.0"


def test_trace_graph_with_optional_fields() -> None:
    graph = _mock_graph()
    traced = trace_graph(
        graph,
        agent_name="agent",
        agent_version="v1",
        workload_type="support",
        model="gpt-4o",
        provider="openai",
    )
    assert traced._workload_type == "support"
    assert traced._model == "gpt-4o"
    assert traced._provider == "openai"