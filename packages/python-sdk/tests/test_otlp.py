"""Tests for OTLP tracing configuration.

Verifies that ``configure_otlp_tracing`` creates a properly-wired provider.
Since the OTLP exporter requires a live gRPC endpoint to actually export, these
tests validate the configuration plumbing (resource, idempotency, error handling)
rather than full end-to-end export.
"""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest

from agent_exec_trace.config import SDKConfig
from agent_exec_trace.tracer import (
    configure_otlp_tracing,
    get_tracer,
    reset_tracing,
)


@pytest.fixture(autouse=True)
def _reset() -> Iterator[None]:
    reset_tracing()
    yield
    reset_tracing()


def test_configure_otlp_tracing_creates_provider() -> None:
    with patch(
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter",
        return_value=MagicMock(),
    ):
        provider = configure_otlp_tracing(SDKConfig(), endpoint="http://localhost:4317")

    assert provider is not None
    # The provider's tracer is usable (span creation does not raise).
    tracer = get_tracer("test")
    with tracer.start_as_current_span("test"):
        pass


def test_configure_otlp_tracing_is_idempotent() -> None:
    with patch(
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter",
        return_value=MagicMock(),
    ):
        first = configure_otlp_tracing(SDKConfig(), endpoint="http://localhost:4317")
        second = configure_otlp_tracing(SDKConfig(), endpoint="http://other:4317")
        assert first is second


def test_configure_otlp_tracing_uses_custom_endpoint() -> None:
    with patch(
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter",
    ) as mock_cls:
        configure_otlp_tracing(SDKConfig(), endpoint="http://custom:4317")

    mock_cls.assert_called_once_with(endpoint="http://custom:4317")


def test_configure_otlp_tracing_raises_on_missing_package() -> None:
    # When the OTLP exporter package is not installed, the function should raise
    # an ImportError with a helpful message.  Patching ``__import__`` simulates the
    # missing third-party module without uninstalling it.
    with (
        patch("builtins.__import__", side_effect=ImportError("no module named otlp")),
        pytest.raises(ImportError, match="opentelemetry-exporter-otlp-proto-grpc"),
    ):
        configure_otlp_tracing(SDKConfig())
