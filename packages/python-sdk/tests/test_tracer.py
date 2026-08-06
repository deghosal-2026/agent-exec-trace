"""Tests for tracer bootstrap and span emission.

These cover the provider lifecycle: spans flow to whatever exporter was configured,
the tracer is a stable singleton, untracked use falls back safely, and
reconfiguration is idempotent (the SDK never silently swaps the exporter).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from agent_exec_trace.config import SDKConfig
from agent_exec_trace.tracer import configure_tracing, get_tracer, reset_tracing


@pytest.fixture(autouse=True)
def _reset() -> Iterator[None]:
    """Start each test from a clean tracer provider (see test_instrument.py)."""
    reset_tracing()
    yield
    reset_tracing()


def test_emit_span_is_captured() -> None:
    # A span emitted through the configured tracer reaches the in-memory exporter
    # with its name and attributes intact.
    exporter = InMemorySpanExporter()
    configure_tracing(SDKConfig(), processor=SimpleSpanProcessor(exporter))
    tracer = get_tracer("tests")
    with tracer.start_as_current_span("root") as span:
        span.set_attribute("key", "value")
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "root"
    attrs = spans[0].attributes
    assert attrs is not None
    assert attrs["key"] == "value"


def test_get_tracer_returns_stable_tracer() -> None:
    # The SDK hands out the same tracer object from one provider, so a caller can
    # cache it safely.
    exporter = InMemorySpanExporter()
    configure_tracing(SDKConfig(), processor=SimpleSpanProcessor(exporter))
    assert get_tracer("tests") is get_tracer("tests")


def test_get_tracer_falls_back_without_configure() -> None:
    # Before configure, get_tracer must still return a usable tracer (the OTel
    # global) rather than raising -- important during early bring-up.
    reset_tracing()
    tracer = get_tracer("tests")
    assert tracer is not None


def test_configure_tracing_is_idempotent() -> None:
    # The first configure wins; a second call returns the same provider and never
    # silently swaps exporters out from under running spans.
    first = configure_tracing(SDKConfig(), processor=SimpleSpanProcessor(InMemorySpanExporter()))
    second = configure_tracing(SDKConfig(), processor=SimpleSpanProcessor(InMemorySpanExporter()))
    assert first is second


def test_reset_tracing_shuts_down_provider() -> None:
    # reset_tracing must shut down the old provider so BatchSpanProcessor background
    # threads do not leak across tests.  After reset, a new configure call creates a
    # fresh provider with clean state.
    configure_tracing(SDKConfig())  # uses BatchSpanProcessor (background thread)
    reset_tracing()
    # Reconfigure should work cleanly (no stale thread).
    exporter = InMemorySpanExporter()
    configure_tracing(SDKConfig(), processor=SimpleSpanProcessor(exporter))
    tracer = get_tracer("test")
    with tracer.start_as_current_span("post-reset"):
        pass
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "post-reset"


def test_configure_tracing_with_resource_attributes() -> None:
    exporter = InMemorySpanExporter()
    configure_tracing(
        SDKConfig(service_name="custom-svc"),
        processor=SimpleSpanProcessor(exporter),
        resource_attributes={"env": "test", "version": "1.0"},
    )
    tracer = get_tracer("test")
    with tracer.start_as_current_span("with-resource"):
        pass
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    attrs = spans[0].resource.attributes
    assert attrs["service.name"] == "custom-svc"
    assert attrs["env"] == "test"
    assert attrs["version"] == "1.0"