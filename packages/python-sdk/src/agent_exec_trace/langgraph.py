"""LangGraph adapter.

========================================================
Purpose
========================================================
The LangGraph adapter turns a compiled ``CompiledStateGraph`` into a traced version
whose ``invoke()`` produces a coherent OTel trace tree: one root ``invoke_agent``
span with run metadata, plus nested behavior spans mapped from node names.

Node mapping:
  * ``planner`` -> ``plan`` span (``gen_ai.operation.name = plan``)
  * ``run_tool`` -> ``execute_tool`` span (tool name from state ``plan`` field)
  * ``resolve`` / ``escalate`` -> generic child span

This keeps LangGraph output structurally consistent with the raw Python adapter
(same root shape, same metadata keys, sibling behavior spans), satisfying the
Release Blocker in the WBS.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from opentelemetry import trace
from opentelemetry.trace import Span, SpanKind

from agent_exec_trace.attrs import (
    GEN_AI_OPERATION_NAME,
    SPAN_KIND_PLAN,
    SPAN_KIND_TOOL,
)
from agent_exec_trace.context import RunContext
from agent_exec_trace.instrument import invoke_agent
from agent_exec_trace.tracer import get_tracer


class _NodeCallbackHandler(BaseCallbackHandler):
    """LangGraph callback that opens a behavior span per instrumented node.

    Relies on ``run_id`` for pairing: ``on_chain_start`` stores a span keyed by the
    event's run id; ``on_chain_end`` looks up and ends the span.  Only events whose
    ``tags`` include a ``graph:step:N`` entry produce spans -- the ``seq:step:N``
    wrapper events are silently ignored (their run ids are never stored, so
    ``on_chain_end`` becomes a no-op).
    """

    def __init__(
        self,
        *,
        tracer: trace.Tracer | None = None,
    ) -> None:
        self._tracer = tracer or get_tracer()
        # ``_spans`` maps event run_id -> Span for the primary (graph:step) events.
        self._spans: dict[str, Span] = {}

    @staticmethod
    def _node_name(kwargs: dict[str, Any]) -> str | None:
        """Extract the LangGraph node name from callback kwargs.

        The node name lives in ``kwargs["metadata"]["langgraph_node"]`` when LangGraph
        dispatches a callback event for a specific node.
        """
        md = kwargs.get("metadata")
        if not isinstance(md, dict):
            return None
        return md.get("langgraph_node")

    @staticmethod
    def _is_primary_start(kwargs: dict[str, Any]) -> bool:
        """Return True if the callback event is a primary graph step (not a wrapper).

        LangGraph emits both ``graph:step:N`` and ``seq:step:N`` events. Only the
        ``graph:step:*`` events represent real node boundaries that should produce spans.
        """
        tags = kwargs.get("tags")
        if not isinstance(tags, list | tuple):
            return False
        return any(isinstance(t, str) and t.startswith("graph:step:") for t in tags)

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        node = self._node_name(kwargs)
        if node is None or not self._is_primary_start(kwargs):
            return

        # Determine the span kind and name based on the node.
        if node == "planner":
            span = self._tracer.start_span(
                node,
                kind=SpanKind.INTERNAL,
                attributes={GEN_AI_OPERATION_NAME: SPAN_KIND_PLAN},
            )
        elif node == "run_tool":
            # The tool name is carried in the state's ``plan`` field.
            tool_name = (inputs or {}).get("plan", "run_tool")
            span = self._tracer.start_span(
                tool_name,
                kind=SpanKind.CLIENT,
                attributes={
                    GEN_AI_OPERATION_NAME: SPAN_KIND_TOOL,
                    "_et.tool": tool_name,
                },
            )
        else:
            # resolve / escalate -- generic child spans.
            span = self._tracer.start_span(
                node,
                kind=SpanKind.INTERNAL,
            )

        rid = str(kwargs.get("run_id", ""))
        if rid:
            self._spans[rid] = span

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        rid = str(kwargs.get("run_id", ""))
        span = self._spans.pop(rid, None)
        if span is not None:
            span.end()

    def on_chain_error(
        self,
        error: BaseException,
        **kwargs: Any,
    ) -> None:
        rid = str(kwargs.get("run_id", ""))
        span = self._spans.pop(rid, None)
        if span is not None:
            span.record_exception(error)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(error)))
            span.end()


class TracedGraph:
    """A wrapped ``CompiledStateGraph`` whose ``invoke()`` produces traced runs.

    Each call to ``invoke()`` starts one root ``invoke_agent`` span with the agent
    metadata supplied at construction, attaches a callback handler that creates
    nested behavior spans for instrumented nodes, and returns the original graph's
    result.
    """

    def __init__(
        self,
        graph: CompiledStateGraph[Any, Any, Any, Any],
        *,
        agent_name: str,
        agent_version: str | None = None,
        workload_type: str | None = None,
        model: str | None = None,
        provider: str | None = None,
    ) -> None:
        self._graph = graph
        self._agent_name = agent_name
        self._agent_version = agent_version
        self._workload_type = workload_type
        self._model = model
        self._provider = provider

    def invoke(
        self,
        input_state: dict[str, Any] | Mapping[str, Any],
        config: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Run the graph inside a root invoke_agent span.

        Args:
            input_state: initial state passed to the LangGraph (can be a ``TypedDict``
                or a plain dict).
            config: optional LangGraph runtime config.  The adapter will merge its own
                callback handler into ``config["callbacks"]``.
            **kwargs: forwarded to the underlying ``graph.invoke()``.

        Returns:
            The graph's final state (same type as ``graph.invoke()``).
        """
        ctx = RunContext(
            agent_name=self._agent_name,
            agent_version=self._agent_version,
            workload_type=self._workload_type,
            model=self._model,
            provider=self._provider,
        )
        handler = _NodeCallbackHandler()

        # Merge the adapter's callback handler with any user-supplied callbacks.
        cfg: dict[str, Any] = dict(config or {})
        existing = cfg.get("callbacks")
        if existing:
            cfg["callbacks"] = [handler, *existing]
        else:
            cfg["callbacks"] = [handler]

        with invoke_agent(ctx):
            result = self._graph.invoke(input_state, config=cast(RunnableConfig, cfg), **kwargs)
            return cast(dict[str, Any], result)


def trace_graph(
    graph: CompiledStateGraph[Any, Any, Any, Any],
    agent_name: str,
    *,
    agent_version: str | None = None,
    workload_type: str | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> TracedGraph:
    """Wrap a compiled LangGraph so each ``invoke()`` produces a traced run.

    This is the main entry point for the LangGraph adapter::

        graph = build_graph()
        traced = trace_graph(graph, agent_name="request-triage", agent_version="v0.1.0")
        result = traced.invoke(seed)

    Args:
        graph: a compiled LangGraph (``CompiledStateGraph``).
        agent_name: agent identity attached to the root span.
        agent_version: optional version label.
        workload_type: optional workload classification.
        model: optional model name used by the run.
        provider: optional provider name used by the run.

    Returns:
        A ``TracedGraph`` wrapping the original graph.
    """
    return TracedGraph(
        graph,
        agent_name=agent_name,
        agent_version=agent_version,
        workload_type=workload_type,
        model=model,
        provider=provider,
    )