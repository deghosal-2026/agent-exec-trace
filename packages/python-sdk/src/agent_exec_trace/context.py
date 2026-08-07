"""Run context model.

========================================================
Why this exists
========================================================
Every agent run needs a stable identity plus metadata that is attached consistently
to every span it produces. If each adapter invented its own attribute mapping, the
same run would look different in Jaeger depending on which framework produced it --
which is exactly the cross-adapter inconsistency the product must avoid
(see the "Release Blockers" in wbs-v0.1.0.md).

``RunContext`` is the single carrier for that identity. It is created once per run
and passed into :func:`agent_exec_trace.instrument.invoke_agent`, which fans its
attributes out onto the root span and, transitively, the whole span tree.

========================================================
Design decisions
========================================================
* **Frozen (immutable):** The context is created once per run and never modified.
  No code can accidentally swap an agent name or run id mid-flight.

* **Auto-generated run id:** ``uuid4().hex`` (no dashes) gives a compact, unique,
  URL-safe identifier.  The factory default ensures every ``RunContext()`` gets its
  own id without the caller remembering to generate one.

* **UTC timestamps only:** ``started_at`` defaults to ``datetime.now(timezone.utc)``.
  Naive timestamps are ambiguous across machines and can cause ordering bugs in
  distributed trace views.

* **Optional fields are optional on spans:** ``to_attributes()`` only emits keys
  whose values are not ``None``.  Traces never carry empty attribute values that
  could confuse analytics grouping queries.

* **Dual version write:** The agent version is written under both the standard
  ``gen_ai.agent.version`` key (for OTel interop) and the provisional
  ``gen_ai.agent.version.label`` key (the stable key version-compare cohorts use).
  This dual-write is intentional -- see the docstring in
  :class:`agent_exec_trace.attrs`.

========================================================
Usage
========================================================

::

    from agent_exec_trace.context import RunContext
    from agent_exec_trace.instrument import invoke_agent

    ctx = RunContext(
        agent_name="request-triage",
        agent_version="v0.2.0",
        workload_type="escalation",
        model="gpt-4o",
        provider="openai",
    )
    with invoke_agent(ctx):
        ...
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from agent_exec_trace.attrs import (
    GEN_AI_AGENT_NAME,
    GEN_AI_AGENT_RUN_ID,
    GEN_AI_AGENT_VERSION,
    GEN_AI_AGENT_VERSION_LABEL,
    GEN_AI_AGENT_WORKLOAD_TYPE,
    GEN_AI_PROVIDER_NAME,
    GEN_AI_REQUEST_MODEL,
)


@dataclass(frozen=True)
class RunContext:
    """Identity and metadata for one agent run.

    Frozen so the same context object can be shared safely (it is never mutated
    mid-run). ``run_id`` and ``started_at`` auto-generate when omitted so a caller
    always gets a coherent, timestamped run without extra work.

    Attributes:
        run_id: stable run identifier (auto-generated when omitted via
            ``uuid.uuid4().hex`` -- no dashes for compact URL-safe ids).
        agent_name: agent identity (shows as the agent column in dashboards).
        agent_version: agent version label (optional; written to both the
            standard and provisional attribute keys when set).
        workload_type: workload classification string (optional).
        model: optional model name used for the run (e.g. ``"gpt-4o"``).
        provider: optional provider name used for the run (e.g. ``"openai"``).
        operation: operation name used for the root span (default: ``"invoke_agent"``).
        started_at: run start time (defaults to ``datetime.now(timezone.utc)``).

    Example::

        ctx = RunContext(
            agent_name="my-agent",
            agent_version="v1.0.0",
            model="gpt-4o-mini",
        )
        attrs = ctx.to_attributes()
        # attrs = {
        #     "gen_ai.agent.name": "my-agent",
        #     "gen_ai.agent.run.id": "a1b2c3...",
        #     "gen_ai.agent.version": "v1.0.0",
        #     "gen_ai.agent.version.label": "v1.0.0",
        #     "gen_ai.request.model": "gpt-4o-mini",
        # }
    """

    # ``uuid4().hex`` (no dashes) gives a compact, unique, URL-safe run id. Defaults
    # via factory so every instance gets its own value (a bare default would share one
    # id across runs).
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    agent_name: str = "unnamed_agent"
    agent_version: str | None = None
    workload_type: str | None = None
    model: str | None = None
    provider: str | None = None
    operation: str = "invoke_agent"
    # Naive timestamps would be ambiguous across machines; store UTC explicitly.
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_attributes(self) -> dict[str, str | bool | int | float]:
        """Return the OTel attribute mapping for this run.

        Only present keys are emitted -- optional metadata (version, workload,
        model, provider) is omitted when unset so traces never carry empty or
        ``None`` attribute values that could confuse analytics grouping.

        Note: ``agent_version`` is written twice (``gen_ai.agent.version`` and the
        provisional ``gen_ai.agent.version.label``) intentionally. The standard key
        keeps interop with OTel tooling; the label key is the one version-compare
        cohorts are built from and stays stable even if the standard key evolves.

        Returns:
            A dict mapping OTel attribute key strings to their values.  Only
            non-``None`` optional fields are included.  Guaranteed to contain
            at minimum ``gen_ai.agent.name`` and ``gen_ai.agent.run.id``.

        Example::

            >>> ctx = RunContext(agent_name="triage", agent_version="v1.0")
            >>> ctx.to_attributes()
            {
                'gen_ai.agent.name': 'triage',
                'gen_ai.agent.run.id': 'e4f5a6b7...',
                'gen_ai.agent.version': 'v1.0',
                'gen_ai.agent.version.label': 'v1.0',
            }
        """
        # Always emit the two mandatory fields: agent identity and run id.
        # These are required for any meaningful analytics grouping.
        attrs: dict[str, str | bool | int | float] = {
            GEN_AI_AGENT_NAME: self.agent_name,
            GEN_AI_AGENT_RUN_ID: self.run_id,
        }
        # Dual-write version: both keys for interop and analytics stability.
        if self.agent_version is not None:
            attrs[GEN_AI_AGENT_VERSION_LABEL] = self.agent_version
            attrs[GEN_AI_AGENT_VERSION] = self.agent_version
        # Optional metadata -- only emitted when the caller provides it.
        # ``None`` is never written as an attribute value because it would
        # break Span.set_attribute() and confuse query predicates.
        if self.workload_type is not None:
            attrs[GEN_AI_AGENT_WORKLOAD_TYPE] = self.workload_type
        if self.provider is not None:
            attrs[GEN_AI_PROVIDER_NAME] = self.provider
        if self.model is not None:
            attrs[GEN_AI_REQUEST_MODEL] = self.model
        return attrs
