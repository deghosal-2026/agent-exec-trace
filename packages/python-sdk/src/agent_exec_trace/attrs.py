"""Semantic-convention attribute keys.

========================================================
Purpose
========================================================
Attribute names are the contract between the SDK, the collector, and the analytics
service. They must stay stable and centralized: if a key drifts between modules,
traces become unqueryable and analytics silently miss fields.

The standard ``gen_ai.*`` keys come from the OpenTelemetry GenAI semantic
conventions. The ``gen_ai.agent.*`` extension fields are **provisional**:
documented as temporary reference extensions pending upstream OTel adoption
(see docs/architecture-v0.1.0.md, "Schema Evolution Policy"). Any rename here is a
breaking change for stored traces, so keep this file the single source of truth and
never hardcode a key string elsewhere in the codebase.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Standard GenAI semantic convention attribute keys.
# ---------------------------------------------------------------------------
# These should be used exactly as written by the upstream OTel semantic conventions
# so collectors and backends recognize them without extra mapping.
GEN_AI_OPERATION_NAME = "gen_ai.operation.name"
GEN_AI_AGENT_NAME = "gen_ai.agent.name"
GEN_AI_AGENT_VERSION = "gen_ai.agent.version"
GEN_AI_PROVIDER_NAME = "gen_ai.provider.name"
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
GEN_AI_CONVERSATION_ID = "gen_ai.conversation.id"
GEN_AI_DATA_SOURCE_ID = "gen_ai.data_source.id"

# ---------------------------------------------------------------------------
# Provisional extension fields (may change before v0.2.0).
# ---------------------------------------------------------------------------
# These carry behavior/run semantics that the standard conventions do not cover
# yet. Keep them clearly namespaced under ``gen_ai.agent.*`` and track their
# intended evolution in the architecture doc.
GEN_AI_AGENT_RUN_ID = "gen_ai.agent.run.id"
GEN_AI_AGENT_RUN_COST_TOTAL = "gen_ai.agent.run.cost.total"
GEN_AI_AGENT_LOOP_COUNT = "gen_ai.agent.loop.count"
GEN_AI_AGENT_LOOP_DETECTED = "gen_ai.agent.loop.detected"
GEN_AI_AGENT_RETRY_COUNT = "gen_ai.agent.retry.count"
GEN_AI_AGENT_VERSION_LABEL = "gen_ai.agent.version.label"
GEN_AI_AGENT_WORKLOAD_TYPE = "gen_ai.agent.workload.type"
GEN_AI_AGENT_INTERVENTION_COUNT = "gen_ai.agent.intervention.count"

# ---------------------------------------------------------------------------
# Span operation names.
# ---------------------------------------------------------------------------
# Values for ``gen_ai.operation.name``. These are the behavioral vocabulary the
# analytics service and the run-timeline UI key on to tell a behavioral story:
# planning, tool use, retrieval, memory, and the run root.
SPAN_KIND_PLAN = "plan"
SPAN_KIND_TOOL = "execute_tool"
SPAN_KIND_RETRIEVAL = "retrieval"
SPAN_KIND_MEMORY = "memory"
SPAN_KIND_INVOKE_AGENT = "invoke_agent"