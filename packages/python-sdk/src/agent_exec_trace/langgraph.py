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
  * ``resolve`` / ``escalate`` -> generic child span (no special operation name)

This keeps LangGraph output structurally consistent with the raw Python adapter
(same root shape, same metadata keys, sibling behavior spans), satisfying the
Release Blocker in the WBS.

========================================================
How the adapter works
========================================================
1. ``trace_graph()`` wraps a ``CompiledStateGraph`` in a ``TracedGraph`` that stores
   agent metadata (name, version, workload, model, provider).

2. On each ``TracedGraph.invoke()`` call, the adapter:
   a. Creates a fresh ``RunContext`` from the stored metadata.
   b. Opens a root ``invoke_agent`` span via ``invoke_agent()``.
   c. Registers a ``_NodeCallbackHandler`` as a LangChain callback that listens
      for ``on_chain_start`` / ``on_chain_end`` / ``on_chain_error`` events.
   d. For each event tagged ``graph:step:N`` with a known LangGraph node name,
      opens a child behavior span under the root.

3. The ``seq:step:N`` wrapper events (emitted by LangGraph's internal sequencing)
   are silently ignored -- only ``graph:step:*`` events produce spans.

========================================================
Usage
========================================================

::

    from agent_exec_trace.langgraph import trace_graph
    from agent_exec_trace.tracer import configure_tracing, default_config

    configure_tracing(default_config())

    graph = build_graph()  # returns CompiledStateGraph
    traced = trace_graph(graph, agent_name="request-triage", agent_version="v0.1.0")
    result = traced.invoke({"messages": [{"role": "user", "content": "help"}]})
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
    GEN_AI_TOOL_NAME,
    GEN_AI_TOOL_ARGS,
    GEN_AI_TOOL_RESULT,
    GEN_AI_RESPONSE_CONTENT,
    GEN_AI_AGENT_OUTPUT,
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

    Design notes:
      * The handler is created per-``invoke()`` call (not per-graph) so spans from
        different concurrent runs do not share state.
      * Errors are recorded on the span UNTIL ``on_chain_error`` fires; the error
        span is still popped from the map (ended after recording), so a subsequent
        ``on_chain_end`` callback is harmless (map lookup returns None).
    """

    def __init__(
        self,
        *,
        tracer: trace.Tracer | None = None,
    ) -> None:
        """Initialize the callback handler with an optional tracer.

        Args:
            tracer: optional explicit tracer.  If ``None``, the handler calls
                ``get_tracer()`` to obtain the active tracer at construction time.
                Tests can inject a tracer bound to an in-memory provider.
        """
        self._tracer = tracer or get_tracer()
        # ``_spans`` maps event run_id -> Span for the primary (graph:step) events.
        # The dict is cleared entry-by-entry as spans end (via ``pop``) so a given
        # run_id is never double-ended.
        self._spans: dict[str, Span] = {}
        self._node_names: dict[str, str] = {}

    @staticmethod
    def _node_name(kwargs: dict[str, Any]) -> str | None:
        """Extract the LangGraph node name from callback kwargs.

        The node name lives in ``kwargs["metadata"]["langgraph_node"]`` when LangGraph
        dispatches a callback event for a specific node.

        Args:
            kwargs: the raw keyword arguments passed to the LangChain callback.

        Returns:
            The node name string (e.g. ``"planner"``, ``"run_tool"``), or ``None``
            if the event is not associated with a specific node.
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
        The ``seq:step:*`` events represent LangGraph's internal sequencing and are
        deliberately filtered out -- they would produce duplicate or misleading spans.

        Args:
            kwargs: the raw keyword arguments passed to the LangChain callback.

        Returns:
            ``True`` if at least one tag starts with ``"graph:step:"``.
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
        """Open a behavior span when LangGraph starts executing a node.

        Called by LangChain's callback system when a node begins execution.
        Only creates a span if the event is a primary graph step with a known
        node name.  Spans are stored keyed by ``run_id`` for later pairing with
        ``on_chain_end`` / ``on_chain_error``.

        Node-to-span mapping:
          * ``"planner"`` -> ``SpanKind.INTERNAL`` span with operation ``"plan"``
          * ``"run_tool"`` -> ``SpanKind.CLIENT`` span with operation ``"execute_tool"``
            and a ``_et.tool`` attribute carrying the tool name from inputs.
          * Everything else -> ``SpanKind.INTERNAL`` span (no special operation name).

        Args:
            serialized: LangChain serialized component metadata (unused).
            inputs: the state dict passed to the node; checked for the ``"plan"``
                field when the node is ``"run_tool"`` to extract the actual tool name.
            **kwargs: forwarded by LangChain; must contain ``"run_id"`` and ``"tags"``.
        """
        # Guard: only process events that map to a known LangGraph node AND are
        # primary graph steps (not internal seq:step wrappers).
        node = self._node_name(kwargs)
        if node is None or not self._is_primary_start(kwargs):
            return

        # Determine the span kind and name based on the node.
        # The mapping is deliberately simple: we want predictable, queryable span
        # names that correspond to the graph's structural vocabulary.
        if node == "planner":
            span = self._tracer.start_span(
                node,
                kind=SpanKind.INTERNAL,
                attributes={GEN_AI_OPERATION_NAME: SPAN_KIND_PLAN},
            )
        elif node == "run_tool":
            # The tool name is carried in the state's ``plan`` field.  If the field
            # is missing (unlikely but defensive), fall back to ``"run_tool"`` so we
            # still get a span with a recognizable name.
            tool_name = (inputs or {}).get("plan", "run_tool")
            span = self._tracer.start_span(
                tool_name,
                kind=SpanKind.CLIENT,
                attributes={
                    GEN_AI_OPERATION_NAME: SPAN_KIND_TOOL,
                    GEN_AI_TOOL_NAME: tool_name,
                },
            )
            # Capture tool args from the input state (everything except "plan"
            # which is the tool name, not an argument).
            if inputs and isinstance(inputs, dict):
                tool_args = {k: str(v)[:200] for k, v in inputs.items() if k != "plan"}
                if tool_args:
                    span.set_attribute(GEN_AI_TOOL_ARGS, str(tool_args)[:500])
        else:
            # ``resolve`` / ``escalate`` or any future node -- produce a generic
            # child span so the timeline shows the node was visited, even without
            # a recognized semantic classification.
            span = self._tracer.start_span(
                node,
                kind=SpanKind.INTERNAL,
            )

        # Store the span AND node name keyed by run_id so ``on_chain_end``
        # knows which span to close and what content to extract.
        rid = str(kwargs.get("run_id", ""))
        if rid:
            self._spans[rid] = span
            self._node_names[rid] = node

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Close the behavior span when LangGraph finishes executing a node.

        Looks up the span by ``run_id`` and calls ``span.end()``.  If the run_id
        is not found in ``_spans`` (either because it wasn't stored -- a
        ``seq:step`` wrapper event -- or because it was already popped by
        ``on_chain_error``), this becomes a no-op.

        Args:
            outputs: the node's output state (unused by the handler).
            **kwargs: forwarded by LangChain; must contain ``"run_id"``.
        """
        rid = str(kwargs.get("run_id", ""))
        span = self._spans.pop(rid, None)
        node = self._node_names.pop(rid, "")
        if span is not None:
            # Capture node output content based on node type.
            if outputs and isinstance(outputs, dict):
                output_str = str(outputs)[:500]
                if node == "run_tool":
                    # Tool node: capture the full return state as tool result.
                    span.set_attribute(GEN_AI_TOOL_RESULT, output_str)
                elif node == "planner":
                    # Planner node: capture the plan/reasoning content.
                    span.set_attribute("gen_ai.plan.content", output_str)
                # All nodes: capture generic output for detectors.
                # All nodes: capture generic output for detectors.
                    span.set_attribute("gen_ai.node.output", output_str)
            span.end()

    def on_chain_error(
        self,
        error: BaseException,
        **kwargs: Any,
    ) -> None:
        """Record an error on the node's span and close it.

        Looks up the span by ``run_id``, records the exception as both a span
        event and a span status (``StatusCode.ERROR``), and pops the span from
        the map so a subsequent ``on_chain_end`` callback is a harmless no-op.

        Args:
            error: the exception that caused the node to fail.
            **kwargs: forwarded by LangChain; must contain ``"run_id"``.
        """
        rid = str(kwargs.get("run_id", ""))
        span = self._spans.pop(rid, None)
        if span is not None:
            # ``record_exception`` adds the exception details as a span event
            # so the trace viewer can show which step failed and why.
            span.record_exception(error)
            # Set the span status to ERROR so backend queries can filter on
            # ``status_code == ERROR`` to find failing runs.
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(error)))
            span.end()


class TracedGraph:
    """A wrapped ``CompiledStateGraph`` whose ``invoke()`` produces traced runs.

    Each call to ``invoke()`` starts one root ``invoke_agent`` span with the agent
    metadata supplied at construction, attaches a callback handler that creates
    nested behavior spans for instrumented nodes, and returns the original graph's
    result.

    The graph's original behavior is preserved -- all callbacks, recursion limits,
    and state are the same.  The adapter only adds instrumentation.

    Attributes:
        _graph: the wrapped ``CompiledStateGraph`` instance.
        _agent_name: agent identity for the root span.
        _agent_version: optional version label.
        _workload_type: optional workload classification.
        _model: optional model name.
        _provider: optional provider name.
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
        """Wrap a compiled graph for tracing.

        Args:
            graph: a compiled ``CompiledStateGraph`` to instrument.
            agent_name: agent identity attached to the root span of every run.
            agent_version: optional version label.
            workload_type: optional workload classification.
            model: optional model name used by the run.
            provider: optional provider name used by the run.
        """
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

        Each call creates a fresh ``RunContext`` (new run id and start timestamp)
        and a fresh ``_NodeCallbackHandler`` (separate span map) so concurrent
        invocations are fully isolated.

        The adapter merges its callback handler into any user-supplied callbacks
        so existing callback-based instrumentation continues to work alongside
        the OTel spans.

        Args:
            input_state: initial state passed to the LangGraph (can be a ``TypedDict``
                or a plain dict).
            config: optional LangGraph runtime config.  The adapter will merge its own
                callback handler into ``config["callbacks"]``.
            **kwargs: forwarded to the underlying ``graph.invoke()``.

        Returns:
            The graph's final state (same type as ``graph.invoke()``).
        """
        # Fresh context per invocation: each call is its own run.
        ctx = RunContext(
            agent_name=self._agent_name,
            agent_version=self._agent_version,
            workload_type=self._workload_type,
            model=self._model,
            provider=self._provider,
        )
        # Fresh handler per invocation: separate span map per concurrent call.
        handler = _NodeCallbackHandler()

        # Merge the adapter's callback handler with any user-supplied callbacks.
        # The adapter's handler goes first so its spans are set up before user
        # callbacks fire (user callbacks may want to access current span state).
        cfg: dict[str, Any] = dict(config or {})
        existing = cfg.get("callbacks")
        if existing:
            cfg["callbacks"] = [handler, *existing]
        else:
            cfg["callbacks"] = [handler]

        with invoke_agent(ctx) as root_span:
            # ``cast`` is safe: ``RunnableConfig`` is a ``TypedDict`` whose
            # ``callbacks`` field accepts ``BaseCallbackHandler`` instances; our
            # ``cfg`` dict is compatible at runtime even if mypy can't prove it.
            result = self._graph.invoke(input_state, config=cast(RunnableConfig, cfg), **kwargs)

            # Capture agent output on the root span so empty_response and
            # output quality detectors can find it. LangGraph returns a
            # state dict — extract the most likely output field.
            if isinstance(result, dict):
                output = (result.get("response") or result.get("output")
                          or result.get("answer") or result.get("outcome") or "")
                if output:
                    root_span.set_attribute(GEN_AI_RESPONSE_CONTENT, str(output)[:500])
                    root_span.set_attribute(GEN_AI_AGENT_OUTPUT, str(output)[:500])

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

    Example::

        from agent_exec_trace.langgraph import trace_graph
        from agent_exec_trace.tracer import configure_tracing, default_config

        configure_tracing(default_config())

        traced = trace_graph(
            graph,
            agent_name="support-bot",
            agent_version="v1.2.0",
            model="gpt-4o",
            provider="openai",
        )
        result = traced.invoke({"messages": [...]})
    """
    return TracedGraph(
        graph,
        agent_name=agent_name,
        agent_version=agent_version,
        workload_type=workload_type,
        model=model,
        provider=provider,
    )