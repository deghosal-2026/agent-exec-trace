"""Tests for root run instrumentation.

These exercise the ``invoke_agent`` root-span contract: a run produces exactly one
root span carrying run identity, and caller-supplied extra attributes merge on top.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from agent_exec_trace.attrs import (
    GEN_AI_AGENT_NAME,
    GEN_AI_AGENT_RUN_ID,
    GEN_AI_AGENT_VERSION_LABEL,
    GEN_AI_OPERATION_NAME,
    SPAN_KIND_INVOKE_AGENT,
)
from agent_exec_trace.config import SDKConfig
from agent_exec_trace.context import RunContext
from agent_exec_trace.instrument import invoke_agent, set_output
from agent_exec_trace.redact import PrivacyMode, RedactionConfig
from agent_exec_trace.tracer import configure_tracing, reset_tracing


@pytest.fixture(autouse=True)
def _reset() -> Iterator[None]:
    """Start each test from a clean tracer provider.

    Without this, the provider configured by one test would leak into the next and
    spans could be emitted to a stale exporter. Autouse so no test can forget it.
    """
    reset_tracing()
    yield
    reset_tracing()


def _exporter() -> InMemorySpanExporter:
    """Configure tracing with an in-memory exporter and return it for assertions.

    ``SimpleSpanProcessor`` flushes spans synchronously, so spans are inspectable
    as soon as the ``with`` block exits -- no wait/poll needed in tests.
    """
    exporter = InMemorySpanExporter()
    configure_tracing(SDKConfig(), processor=SimpleSpanProcessor(exporter))
    return exporter


def test_invoke_agent_creates_root_span() -> None:
    # One run, one root span, stamped with identity and operation name.
    exporter = _exporter()
    ctx = RunContext(run_id="run-1", agent_name="triage", agent_version="v0.1.0")
    with invoke_agent(ctx):
        pass
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.name == "invoke_agent"
    assert span.attributes is not None
    assert span.attributes[GEN_AI_OPERATION_NAME] == SPAN_KIND_INVOKE_AGENT
    assert span.attributes[GEN_AI_AGENT_NAME] == "triage"
    assert span.attributes[GEN_AI_AGENT_RUN_ID] == "run-1"
    assert span.attributes[GEN_AI_AGENT_VERSION_LABEL] == "v0.1.0"


def test_invoke_agent_merges_extra_attributes() -> None:
    # Caller attributes are layered onto the root span alongside context metadata.
    exporter = _exporter()
    ctx = RunContext(run_id="run-2", agent_name="triage")
    with invoke_agent(ctx, attributes={"gen_ai.agent.workload.type": "support"}):
        pass
    span = exporter.get_finished_spans()[0]
    assert span.attributes is not None
    assert span.attributes["gen_ai.agent.workload.type"] == "support"


def test_set_output_stores_response_on_root() -> None:
    exporter = _exporter()
    ctx = RunContext(run_id="run-1", agent_name="triage")
    with invoke_agent(ctx) as span:
        set_output(span, "Task completed")
    finished = exporter.get_finished_spans()[0]
    assert finished.attributes is not None
    assert finished.attributes["gen_ai.response.content"] == "Task completed"


def test_set_output_with_redaction_truncates() -> None:
    exporter = _exporter()
    ctx = RunContext(run_id="run-1", agent_name="triage")
    redact = RedactionConfig(mode=PrivacyMode.TRUNCATED, capture_prompts=True, truncate_at=10)
    with invoke_agent(ctx) as span:
        set_output(span, "very long output that exceeds cap", redaction=redact)
    finished = exporter.get_finished_spans()[0]
    assert finished.attributes is not None
    output = str(finished.attributes["gen_ai.response.content"])
    assert len(output) <= 10


def test_set_output_with_metadata_only_drops_content() -> None:
    exporter = _exporter()
    ctx = RunContext(run_id="run-1", agent_name="triage")
    redact = RedactionConfig(mode=PrivacyMode.METADATA_ONLY)
    with invoke_agent(ctx) as span:
        set_output(span, "sensitive data", redaction=redact)
    finished = exporter.get_finished_spans()[0]
    assert finished.attributes is not None
    assert "gen_ai.response.content" not in finished.attributes