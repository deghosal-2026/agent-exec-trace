"""Raw Python adapter.

========================================================
Purpose
========================================================
The ``@trace_agent`` decorator is the "no-framework" onboarding path. It proves the
SDK is not locked to LangGraph: any plain Python agent function can be wrapped so
every invocation becomes a coherent root ``invoke_agent`` span, and the nested
behavior helpers (``plan_span``, ``execute_tool_span``, ``retrieval_span`` from
:mod:`agent_exec_trace.spans`) used *inside* the function parent to that root
automatically -- no manual span plumbing required.

This keeps raw-Python output structurally consistent with the LangGraph adapter
(same root shape, same metadata keys), which is a Release Blocker in the WBS.

========================================================
How the decorator works
========================================================
1. ``trace_agent(agent_name, agent_version=..., ...)`` returns a decorator.

2. The decorator wraps the target function in a wrapper that, on each call:
   a. Creates a fresh ``RunContext`` (new run id, new start timestamp).
   b. Opens a root ``invoke_agent`` span via ``invoke_agent()``.
   c. Calls the original function inside the span context.
   d. Returns the function's result unchanged; exceptions propagate naturally
      after being recorded on the span by the context manager machinery.

3. ``functools.wraps`` preserves the original function's name, docstring, and
   signature so the decorated function is indistinguishable to callers.

========================================================
Usage
========================================================

::

    from agent_exec_trace.raw import trace_agent
    from agent_exec_trace.spans import plan_span, execute_tool_span

    @trace_agent("my-agent", agent_version="v0.2.0")
    def my_agent(request: str) -> str:
        with plan_span("decide next action"):
            with execute_tool_span("search"):
                ...
        return "done"

    result = my_agent("help me with ...")  # traced automatically
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, cast

from agent_exec_trace.context import RunContext
from agent_exec_trace.instrument import invoke_agent

# Bound so the decorator preserves the exact callable shape of the wrapped agent.
# ``Callable[..., Any]`` accepts any arity and returns any type, so the decorated
# function's type signature flows through unchanged.
AgentFn = TypeVar("AgentFn", bound=Callable[..., Any])


def trace_agent(
    agent_name: str,
    *,
    agent_version: str | None = None,
    workload_type: str | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> Callable[[AgentFn], AgentFn]:
    """Decorate a plain Python agent function to trace each invocation.

    Usage::

        @trace_agent("my-agent", agent_version="v0.2.0")
        def my_agent(request: str) -> str:
            with plan_span("decide"):
                with execute_tool_span("search"):
                    ...
            return "done"

    Each call to the decorated function starts one root ``invoke_agent`` span (with
    a freshly generated run id) and runs the body inside it. Nested behavior helpers
    called within the body parent to that root. The function's return value passes
    through unchanged and exceptions propagate after being recorded on the span.

    Args:
        agent_name: agent identity attached to the root span.
        agent_version: optional version label for the agent.
        workload_type: optional workload classification for the run.
        model: optional model name used by the run.
        provider: optional provider name used by the run.

    Returns:
        A decorator that wraps ``fn`` in a root ``invoke_agent`` span.

    Example::

        from agent_exec_trace.raw import trace_agent
        from agent_exec_trace.spans import plan_span, execute_tool_span

        @trace_agent(
            "support-bot",
            agent_version="v1.3.0",
            model="gpt-4o",
            provider="openai",
        )
        def handle_support(request: str) -> dict:
            with plan_span("classify intent"):
                ...
            return {"response": "..."}
    """

    def decorator(fn: AgentFn) -> AgentFn:
        # ``functools.wraps`` copies __name__, __doc__, __module__, __wrapped__,
        # and the type annotations so the wrapper is transparent to callers and
        # to introspection tools (mypy, pyright, Sphinx).
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            ctx = RunContext(
                agent_name=agent_name,
                agent_version=agent_version,
                workload_type=workload_type,
                model=model,
                provider=provider,
            )
            with invoke_agent(ctx):
                return fn(*args, **kwargs)

        @wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            ctx = RunContext(
                agent_name=agent_name,
                agent_version=agent_version,
                workload_type=workload_type,
                model=model,
                provider=provider,
            )
            with invoke_agent(ctx):
                return await fn(*args, **kwargs)

        # Preserve the callable's sync/async nature so nested coroutines can
        # still resolve their OTel parent trace context.  A sync wrapper calling
        # an ``async fn`` returns the coroutine object *after* the root span
        # context has closed, so the awaited body would escape to its own root
        # trace.  An async wrapper awaiting ``fn`` keeps the root span active for
        # the full coroutine lifetime, so plan_span/tool spans parent correctly.
        if inspect.iscoroutinefunction(fn):
            return cast(AgentFn, async_wrapper)
        return cast(AgentFn, wrapper)

    return decorator
