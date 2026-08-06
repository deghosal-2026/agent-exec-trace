"""Root run instrumentation.

========================================================
Purpose
========================================================
Every agent run must become **one coherent root span** -- the behavioral container
for all nested plan/tool/retrieval/memory spans. The root span carries run identity
and metadata (agent name, version, run id, workload, model, provider) so that:

  * the run-timeline view can reconstruct a full run from a single root,
  * fleet and version-compare views can group by the metadata attached here,
  * cross-adapter runs look structurally consistent (same root shape whether the run
    came from LangGraph or a raw Python agent).

``invoke_agent`` is the entry point every adapter and the raw-Python decorator use.

========================================================
Span portability guarantees
========================================================
Every span produced through this module carries:

  1. ``gen_ai.operation.name = invoke_agent`` -- the behavioral classification
     that the analytics service and run-timeline UI use to identify the root.
  2. All metadata from :meth:`RunContext.to_attributes` -- agent name, run id,
     version, workload type, model, provider (only non-None values).
  3. ``SpanKind.CLIENT`` -- this SDK is a *client* of the agent runtime; the
     semantics of a run are caller/callee, not server-side request handling.

Because every adapter funnels through this single function, the root span shape is
guaranteed to be consistent regardless of whether the agent is a LangGraph graph,
a raw decorated function, or a future adapter.

========================================================
Usage
========================================================

::

    from agent_exec_trace.context import RunContext
    from agent_exec_trace.instrument import invoke_agent

    ctx = RunContext(agent_name="my-agent")
    with invoke_agent(ctx, attributes={"custom.key": "value"}) as root:
        # All nested *_span() helpers started inside this block
        # automatically parent to this root.
        ...
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.trace import Span, SpanKind

from agent_exec_trace.attrs import GEN_AI_OPERATION_NAME, SPAN_KIND_INVOKE_AGENT
from agent_exec_trace.context import RunContext
from agent_exec_trace.tracer import get_tracer


@contextmanager
def invoke_agent(
    ctx: RunContext,
    *,
    attributes: dict[str, str | bool | int | float] | None = None,
    tracer: trace.Tracer | None = None,
) -> Iterator[Span]:
    """Start a root ``invoke_agent`` span for ``ctx`` and run the body inside it.

    Usage wraps the entire agent execution::

        with invoke_agent(run_ctx):
            ...  # nested *_span() helpers parent to this root automatically

    The span carries:
      * ``gen_ai.operation.name = invoke_agent`` (identifies the root),
      * run identity/metadata from :meth:`RunContext.to_attributes`,
      * any extra ``attributes`` the caller wants on the root (e.g. cost totals).

    Parentage: ``start_as_current_span`` makes this the current span for the duration
    of the ``with`` block, so any nested ``*_span()`` helper started inside parents to
    this root automatically -- no explicit parent plumbing required.

    Args:
        ctx: the run identity and metadata for this run.
        attributes: extra root-level attributes merged **after** the context
            metadata, so caller-supplied keys can override defaults when needed.
        tracer: optional explicit tracer (tests inject a tracer bound to an
            in-memory provider; production code leaves it as the default).

    Yields:
        The root :class:`~opentelemetry.trace.Span`.

    Example::

        ctx = RunContext(agent_name="triage", agent_version="v0.1")
        with invoke_agent(ctx, attributes={"_et.cost_total": 0.03}) as root:
            with plan_span("decide"):
                ...
            # root.attributes includes gen_ai.operation.name, gen_ai.agent.name,
            # gen_ai.agent.run.id, gen_ai.agent.version, and _et.cost_total
    """
    t = tracer or get_tracer()

    # Always stamp the operation name first, then merge context metadata, then let
    # caller attributes win on any conflict. Order matters: explicit overrides should
    # be able to replace defaults.
    attrs: dict[str, str | bool | int | float] = {GEN_AI_OPERATION_NAME: SPAN_KIND_INVOKE_AGENT}
    attrs.update(ctx.to_attributes())
    if attributes:
        attrs.update(attributes)

    # SpanKind.CLIENT: this SDK is a client of the agent runtime -- the semantics of a
    # run are caller/callee rather than server-side request handling.
    with t.start_as_current_span(ctx.operation, kind=SpanKind.CLIENT, attributes=attrs) as span:
        # The span object is yielded so the caller can record extra events or
        # attributes on the root span before it ends -- useful for run-level
        # telemetry like total cost, loop count, or error markers.
        yield span