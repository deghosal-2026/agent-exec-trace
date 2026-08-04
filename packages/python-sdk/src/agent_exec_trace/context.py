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
        run_id: stable run identifier (auto-generated when omitted).
        agent_name: agent identity.
        agent_version: agent version label.
        workload_type: workload classification.
        model: optional model name used for the run.
        provider: optional provider name used for the run.
        operation: operation name used for the root span.
        started_at: run start time.
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
        """
        attrs: dict[str, str | bool | int | float] = {
            GEN_AI_AGENT_NAME: self.agent_name,
            GEN_AI_AGENT_RUN_ID: self.run_id,
        }
        if self.agent_version is not None:
            attrs[GEN_AI_AGENT_VERSION_LABEL] = self.agent_version
            attrs[GEN_AI_AGENT_VERSION] = self.agent_version
        if self.workload_type is not None:
            attrs[GEN_AI_AGENT_WORKLOAD_TYPE] = self.workload_type
        if self.provider is not None:
            attrs[GEN_AI_PROVIDER_NAME] = self.provider
        if self.model is not None:
            attrs[GEN_AI_REQUEST_MODEL] = self.model
        return attrs