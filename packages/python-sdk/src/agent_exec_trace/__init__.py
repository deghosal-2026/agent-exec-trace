"""agent-exec-trace SDK: execution traces for agent behavior.

========================================================
What this package provides
========================================================
A thin, OTel-native instrumentation layer that turns an agent run into a coherent
trace tree -- one root ``invoke_agent`` span containing nested ``plan``,
``execute_tool``, ``retrieval``, and ``memory`` spans -- plus privacy-safe
redaction, so the same run is comparable across frameworks and visible in Jaeger.

Public modules:
  * :mod:`agent_exec_trace.context` -- ``RunContext`` run identity/metadata carrier.
  * :mod:`agent_exec_trace.instrument` -- ``invoke_agent`` root-span entry point.
  * :mod:`agent_exec_trace.spans` -- nested behavior span helpers (plan/tool/...).
  * :mod:`agent_exec_trace.redact` -- privacy boundary (``RedactionConfig``,
    ``PrivacyMode``) used by the span helpers.
  * :mod:`agent_exec_trace.config` -- ``SDKConfig`` / ``default_config``.
  * :mod:`agent_exec_trace.tracer` -- ``configure_tracing`` / ``get_tracer`` /
    ``reset_tracing`` provider bootstrap.
  * :mod:`agent_exec_trace.attrs` -- centralized semantic-convention attribute keys.

Typical usage::

    from agent_exec_trace.config import default_config
    from agent_exec_trace.tracer import configure_tracing
    from agent_exec_trace.context import RunContext
    from agent_exec_trace.instrument import invoke_agent
    from agent_exec_trace.spans import plan_span

    configure_tracing(default_config())   # once at startup
    with invoke_agent(RunContext(agent_name="request-triage")):
        with plan_span("decide next action"):
            ...
"""

__version__ = "0.1.0"