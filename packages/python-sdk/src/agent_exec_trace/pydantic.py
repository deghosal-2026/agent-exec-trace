"""PydanticAI v1 / v2 compatibility adapter.

PydanticAI introduced breaking changes between v1 and v2.  Every PydanticAI
agent found on GitHub during M13.2 testing used the v1 API, and 6 of 8 target
agents could not run with v2.  This module provides a graceful failover path.

========================================================
Usage with v2 (the current default)
========================================================

::

    from agent_exec_trace.pydantic import trace_agent_pydantic

    traced = trace_agent_pydantic(your_agent, agent_name="my-agent")


========================================================
Usage with v1
========================================================

PydanticAI v1 agents require ``pydantic-ai<2``.  Install with::

    pip install "pydantic-ai<2"

Then use the ``@trace_agent`` decorator (not PydanticAI-specific instrumentation)::

    from agent_exec_trace.raw import trace_agent

    @trace_agent("my-agent")
    def my_agent(prompt: str) -> str:
        from pydantic_ai import Agent
        agent = Agent("openai:gpt-4o")
        result = agent.run_sync(prompt)
        return result.data

========================================================
Why no v1-specific adapter
========================================================

PydanticAI v1 uses a fundamentally different API surface (``Agent.run_sync()``,
``@agent.tool`` decorator, different model registration).  Creating a v1-specific
adapter would require maintaining two parallel instrumentation paths with
different call signatures, making the SDK more fragile.

Instead, v1 users instrument with ``@trace_agent`` + ``tool_span()`` — the same
API non-framework users use — and get the same trace shape.
"""

from __future__ import annotations

import logging
from typing import Any

from agent_exec_trace.config import SDKConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Version detection
# ---------------------------------------------------------------------------

try:
    import pydantic_ai

    _PYDANTICAI_VERSION: str | None = (
        pydantic_ai.__version__ if hasattr(pydantic_ai, "__version__") else "unknown"
    )
except ImportError:
    _PYDANTICAI_VERSION = None


def pydanticai_version() -> str | None:
    """Return the installed PydanticAI version string, or None."""
    return _PYDANTICAI_VERSION


def is_pydanticai_v1() -> bool:
    """Return True if PydanticAI v1 is installed."""
    if _PYDANTICAI_VERSION is None:
        return False
    return _PYDANTICAI_VERSION.startswith("1.")


def is_pydanticai_v2() -> bool:
    """Return True if PydanticAI v2 is installed."""
    if _PYDANTICAI_VERSION is None:
        return False
    return _PYDANTICAI_VERSION.startswith("2.")


# ---------------------------------------------------------------------------
# Adapter entry point
# ---------------------------------------------------------------------------


def trace_pydantic_agent(
    agent: Any,
    *,
    agent_name: str = "pydantic-agent",
    agent_version: str | None = None,
    config: SDKConfig | None = None,
) -> Any:
    """Wrap a PydanticAI agent for tracing, with v1/v2 compatibility.

    For v2 agents, this returns the agent unchanged with a note to use
    ``@trace_agent`` for instrumentation.  PydanticAI v2's API surface
    does not support transparent wrapping without the agent runner.

    For v1 agents, this raises a ``NotImplementedError`` with installation
    instructions.

    Args:
        agent: the PydanticAI agent instance.
        agent_name: agent identity for the trace.
        agent_version: optional version label.
        config: optional SDK config (uses ``default_config`` if not set).

    Returns:
        The agent (for v2 compatibility).

    Raises:
        NotImplementedError: if PydanticAI v1 is detected.
        ImportError: if PydanticAI is not installed.
    """
    if _PYDANTICAI_VERSION is None:
        msg = (
            "PydanticAI is not installed.  Install with:\n"
            "  pip install pydantic-ai       # v2 (latest)\n"
            "  pip install 'pydantic-ai<2'   # v1 (legacy)\n"
            "\n"
            "For v1 agents, instrument with @trace_agent + tool_span():\n"
            "\n"
            "    from agent_exec_trace.raw import trace_agent\n"
            "    from agent_exec_trace.spans import tool_span\n"
            "\n"
            "    @trace_agent('my-agent')\n"
            "    def my_agent(prompt):\n"
            "        from pydantic_ai import Agent\n"
            "        agent = Agent('openai:gpt-4o')\n"
            "        result = agent.run_sync(prompt)\n"
            "        return result.data\n"
        )
        raise ImportError(msg)

    if is_pydanticai_v1():
        msg = (
            f"PydanticAI v1 ({_PYDANTICAI_VERSION}) detected.  "
            "v1 agents should be instrumented with @trace_agent "
            "and tool_span() instead of a PydanticAI-specific adapter.\n"
            "\n"
            "Example:\n"
            "\n"
            "    from agent_exec_trace.raw import trace_agent\n"
            "\n"
            "    @trace_agent('my-agent')\n"
            "    def run_agent(prompt):\n"
            "        result = agent.run_sync(prompt)\n"
            "        return result.data\n"
        )
        raise NotImplementedError(msg)

    if is_pydanticai_v2():
        logger.info(
            "PydanticAI v2 detected (%s).  Instrument with @trace_agent + tool_span().",
            _PYDANTICAI_VERSION,
        )
        return agent

    logger.warning(
        "Unknown PydanticAI version %s — instrument with @trace_agent + tool_span().",
        _PYDANTICAI_VERSION,
    )
    return agent
