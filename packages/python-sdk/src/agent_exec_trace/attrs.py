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

========================================================
Usage
========================================================
Import the constant you need by name; never construct a key string directly::

    from agent_exec_trace.attrs import GEN_AI_OPERATION_NAME, SPAN_KIND_PLAN

    span.set_attribute(GEN_AI_OPERATION_NAME, SPAN_KIND_PLAN)

This guarantees that collector pipelines, Jaeger queries, and analytic dashboards
all agree on the same attribute names.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Standard GenAI semantic convention attribute keys.
# ---------------------------------------------------------------------------
# These should be used exactly as written by the upstream OTel semantic conventions
# so collectors and backends recognize them without extra mapping.
# ---------------------------------------------------------------------------

# Identifies which high-level agent behavior this span represents (plan, tool,
# retrieval, memory, or invoke_agent). The analytics service and run-timeline UI
# key on this value to build the behavioral story.
GEN_AI_OPERATION_NAME = "gen_ai.operation.name"

# The agent's logical identity -- the "who" behind the run.  Appears as the
# agent column in dashboards and is used for fleet / version-compare grouping.
GEN_AI_AGENT_NAME = "gen_ai.agent.name"

# The agent's version string.  Used alongside the provisional version label
# (see below) to enable cohort comparisons in the analytics service.
GEN_AI_AGENT_VERSION = "gen_ai.agent.version"

# The provider (e.g. "openai", "anthropic") used during this run.  Helps
# correlate cost and latency patterns per provider.
GEN_AI_PROVIDER_NAME = "gen_ai.provider.name"

# The model identifier used for the agent's LLM calls.  Allows cost-per-model
# and latency-per-model breakdowns in analytics.
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"

# A user-visible conversation / session id that ties multiple agent runs
# together into a single logical interaction.
GEN_AI_CONVERSATION_ID = "gen_ai.conversation.id"

# The identifier of the data source the agent consulted (e.g. a knowledge-base
# or vector-store id).
GEN_AI_DATA_SOURCE_ID = "gen_ai.data_source.id"

# ---------------------------------------------------------------------------
# Provisional extension fields (may change before v0.2.0).
# ---------------------------------------------------------------------------
# These carry behavior / run semantics that the standard conventions do not
# cover yet.  Keep them clearly namespaced under ``gen_ai.agent.*`` and track
# their intended evolution in the architecture doc.
# ---------------------------------------------------------------------------

# Stable, unique run identifier -- one per ``invoke_agent`` span.  This is how
# the run-timeline view groups all child spans under a single run.
GEN_AI_AGENT_RUN_ID = "gen_ai.agent.run.id"

# Total cost (in whatever currency unit the provider reports) consumed by this
# run.  Written at run-end once all tool / LLM costs are known.
GEN_AI_AGENT_RUN_COST_TOTAL = "gen_ai.agent.run.cost.total"

# Number of tool-call loops the agent performed during this run.  Used by the
# loop detector and loop-count cohorts in analytics.
GEN_AI_AGENT_LOOP_COUNT = "gen_ai.agent.loop.count"

# Boolean flag set when the loop-detection heuristic fires.  Lets the analytics
# service isolate runs that may have been stuck in repetitive tool-call patterns.
GEN_AI_AGENT_LOOP_DETECTED = "gen_ai.agent.loop.detected"

# Number of retries across all tool calls in this run.  Aggregated by the
# retry-counter detector and written at run end.
GEN_AI_AGENT_RETRY_COUNT = "gen_ai.agent.retry.count"

# Duplicate of ``gen_ai.agent.version`` stored under a stable provisional key.
# The standard key keeps interop with OTel tooling; the label key is the one
# version-compare cohorts are built from and stays stable even if the standard
# key evolves.  See :meth:`RunContext.to_attributes` for why both are written.
# ---------------------------------------------------------------------------
GEN_AI_AGENT_VERSION_LABEL = "gen_ai.agent.version.label"

# Classification string describing the workload the agent handled (e.g.
# "triage", "escalation", "qa").  Used for workload-based fleet grouping.
GEN_AI_AGENT_WORKLOAD_TYPE = "gen_ai.agent.workload.type"

# Number of times a human intervention was requested or performed during this
# run.  Helps distinguish autonomous runs from guided / supervised runs.
GEN_AI_AGENT_INTERVENTION_COUNT = "gen_ai.agent.intervention.count"

# ---------------------------------------------------------------------------
# Span operation names.
# ---------------------------------------------------------------------------
# Values for ``gen_ai.operation.name``. These are the behavioral vocabulary the
# analytics service and the run-timeline UI key on to tell a behavioral story:
# planning, tool use, retrieval, memory, and the run root.
# ---------------------------------------------------------------------------

# Agent decision-making step: "what should I do next?"
SPAN_KIND_PLAN = "plan"

# One tool invocation (search, API call, code execution, etc.).
SPAN_KIND_TOOL = "execute_tool"

# One retrieval / lookup operation (RAG, vector search, knowledge-base query).
SPAN_KIND_RETRIEVAL = "retrieval"

# One memory read / write operation (set, get, delete).
SPAN_KIND_MEMORY = "memory"

# The root span that contains the entire agent run.  This is the outermost
# container; all other behavior spans are children of this span.
SPAN_KIND_INVOKE_AGENT = "invoke_agent"