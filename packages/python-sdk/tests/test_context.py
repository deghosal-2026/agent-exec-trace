"""Tests for run context attribute mapping.

Covers the ``RunContext.to_attributes`` contract: identity maps to the standard
semconv keys, optional metadata is omitted when unset (never ``None``), and run ids
auto-generate uniquely.
"""

from __future__ import annotations

from agent_exec_trace.attrs import (
    GEN_AI_AGENT_NAME,
    GEN_AI_AGENT_RUN_ID,
    GEN_AI_AGENT_VERSION,
    GEN_AI_AGENT_VERSION_LABEL,
    GEN_AI_AGENT_WORKLOAD_TYPE,
    GEN_AI_PROVIDER_NAME,
    GEN_AI_REQUEST_MODEL,
)
from agent_exec_trace.context import RunContext


def test_to_attributes_maps_identity() -> None:
    # A fully-populated context maps every field to its standard semconv key,
    # including the dual version keys (standard + provisional label).
    ctx = RunContext(
        run_id="run-1",
        agent_name="triage",
        agent_version="v0.1.0",
        workload_type="support",
        provider="acme",
        model="acme-small",
    )
    attrs = ctx.to_attributes()
    assert attrs[GEN_AI_AGENT_NAME] == "triage"
    assert attrs[GEN_AI_AGENT_RUN_ID] == "run-1"
    assert attrs[GEN_AI_AGENT_VERSION] == "v0.1.0"
    assert attrs[GEN_AI_AGENT_VERSION_LABEL] == "v0.1.0"
    assert attrs[GEN_AI_AGENT_WORKLOAD_TYPE] == "support"
    assert attrs[GEN_AI_PROVIDER_NAME] == "acme"
    assert attrs[GEN_AI_REQUEST_MODEL] == "acme-small"


def test_to_attributes_omits_optionals() -> None:
    # Unset optionals are omitted rather than emitted as None, so analytics grouping
    # never has to handle empty attribute values.
    ctx = RunContext(run_id="run-2", agent_name="triage")
    attrs = ctx.to_attributes()
    assert GEN_AI_AGENT_VERSION not in attrs
    assert GEN_AI_AGENT_WORKLOAD_TYPE not in attrs


def test_run_id_is_auto_generated() -> None:
    # Each context gets its own unique run id when none is supplied (a shared default
    # would collapse distinct runs into one).
    a = RunContext(agent_name="x")
    b = RunContext(agent_name="x")
    assert a.run_id != b.run_id
