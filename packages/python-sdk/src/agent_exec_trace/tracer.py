"""Tracer bootstrap helper.

========================================================
Why this module owns the provider
========================================================
All adapters and span helpers need a :class:`~opentelemetry.sdk.trace.TracerProvider`.
This module is the single place that builds and hands out the active provider and
tracer, so:
  * exporters are injectable -- tests use an in-memory exporter, Milestone 3.1 swaps
    in an OTLP exporter, and adapter code never changes,
  * there is exactly one ``service.name`` resource per process,
  * a caller can configure the SDK once and then call :func:`get_tracer` anywhere.

Why we do NOT use ``opentelemetry.trace.set_tracer_provider``
-------------------------------------------------------------
OpenTelemetry forbids re-setting the global provider once it has been installed. That
would break the common need to reconfigure (e.g. between tests, or when a user swaps
exporter config). Instead, this module keeps its own ``_provider`` reference and hands
out tracers from it. This is a deliberate, documented divergence -- see the module
docstring in the original spike -- chosen to keep the SDK testable and reconfigurable.
"""

from __future__ import annotations

import threading

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from agent_exec_trace.config import SDKConfig

# Reference to the configured provider, plus a lock that guards reads/writes. The
# lock makes configure/reset/get consistent even if a program configures tracing in
# one thread while other threads start spans. Reads take the lock briefly to publish
# the reference, then release it; span creation itself is lock-free.
_provider: TracerProvider | None = None
_lock = threading.Lock()


def configure_tracing(
    config: SDKConfig,
    *,
    processor: SpanProcessor | None = None,
    resource_attributes: dict[str, str | bool | int | float] | None = None,
) -> TracerProvider:
    """Bootstrap a tracer provider from ``config``.

    Behavior:
      * Builds a provider whose resource carries ``service.name`` (plus any caller
        ``resource_attributes``) so the whole span tree reports under one service.
      * Defaults to a console span processor so traces are visible locally before OTLP
        export is wired in (Milestone 3.1). Pass an explicit ``processor`` (e.g. an
        in-memory exporter in tests) to override.
      * Is idempotent: the first successful call wins and later calls return the same
        provider. This prevents accidentally silently swapping the exporter under a
        running process.

    Args:
        config: the SDK configuration to apply.
        processor: optional custom span processor to attach (overrides the default
            console processor).
        resource_attributes: extra resource attributes merged into the trace resource.

    Returns:
        The configured :class:`TracerProvider`.
    """
    global _provider

    with _lock:
        # Short-circuit on an existing provider. Without this, a second configure()
        # would either try to re-set an OTel global (forbidden) or rebuild silently,
        # both of which are undesirable.
        if _provider is not None:
            return _provider

        # The trace resource is where service identity lives; it is attached to every
        # span the provider produces and is what Jaeger/Tempo show as the service name.
        attributes: dict[str, str | bool | int | float] = {"service.name": config.service_name}
        if resource_attributes:
            attributes.update(resource_attributes)
        resource = Resource.create(attributes)

        provider = TracerProvider(resource=resource)

        # A SpanProcessor is what actually ships finished spans to an exporter. The
        # default (console) gives free local visibility; tests inject in-memory.
        if processor is None:
            processor = BatchSpanProcessor(ConsoleSpanExporter())
        provider.add_span_processor(processor)

        _provider = provider
        return provider


def configure_otlp_tracing(
    config: SDKConfig,
    *,
    endpoint: str | None = None,
    resource_attributes: dict[str, str | bool | int | float] | None = None,
) -> TracerProvider:
    """Configure tracing with an OTLP gRPC exporter.

    Uses ``config.otlp_endpoint`` (or the explicit ``endpoint`` override) as the
    OTLP target.  This can point to the OpenTelemetry Collector, or directly to
    Jaeger / Tempo / any OTLP-gRPC-capable backend.

    The ``opentelemetry-exporter-otlp-proto-grpc`` package is required at runtime.
    It is declared as an optional dependency (``agent-exec-trace[otlp]``) so the
    core SDK stays lightweight.

    Behavior:
      * Builds the same provider as :func:`configure_tracing` (idempotent, same
        resource semantics).
      * Attaches a ``BatchSpanProcessor`` wrapping an ``OTLPSpanExporter`` pointed
        at the configured endpoint.
      * Short-circuits via ``_provider`` idempotency: the first call wins.

    Args:
        config: SDK configuration carrying ``service_name`` and the default
            ``otlp_endpoint``.
        endpoint: override for the OTLP gRPC endpoint.  Defaults to
            ``config.otlp_endpoint``.
        resource_attributes: extra resource attributes merged into the trace
            resource.

    Returns:
        The configured :class:`TracerProvider`.

    Raises:
        ImportError: if ``opentelemetry-exporter-otlp-proto-grpc`` is not installed.
    """
    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
    except ImportError as exc:
        raise ImportError(
            "OTLP export requires the opentelemetry-exporter-otlp-proto-grpc package. "
            'Install it with: pip install "agent-exec-trace[otlp]"'
        ) from exc

    target = endpoint or config.otlp_endpoint
    exporter = OTLPSpanExporter(endpoint=target)
    processor = BatchSpanProcessor(exporter)
    return configure_tracing(config, processor=processor, resource_attributes=resource_attributes)


def get_tracer(name: str = "agent_exec_trace") -> trace.Tracer:
    """Return the active tracer for ``name``.

    Traces emitted through this tracer flow to the provider configured by
    :func:`configure_tracing`. If tracing has not been configured yet, it falls back
    to the OTel global tracer so callers never raise -- useful during early bring-up
    or in code paths that run before an explicit ``configure``.

    Args:
        name: the instrumenting-library/module name attached to spans it creates.

    Returns:
        A :class:`~opentelemetry.trace.Tracer`.
    """
    with _lock:
        provider = _provider
    if provider is not None:
        return provider.get_tracer(name)
    return trace.get_tracer(name)


def reset_tracing() -> None:
    """Drop the configured provider and shut it down.

    Shuts down the provider (drains in-flight spans and stops background exporter
    threads) so the process does not leak ``BatchSpanProcessor`` threads.

    Primarily for test isolation: each test can start from a clean slate instead of
    inheriting a provider configured by a previous test. Not intended for use in
    production runtime code.
    """
    global _provider

    with _lock:
        if _provider is not None:
            # Shutdown before dropping the reference.  This drains buffered spans
            # and terminates the BatchSpanProcessor background thread so the
            # provider does not linger after reset.
            _provider.shutdown()
        _provider = None