"""SDK configuration object.

========================================================
Why one central config
========================================================
Every adapter (LangGraph, raw Python) and every span helper needs the same runtime
settings: which OTel service to report as, what the exporter endpoint is, what to
do when a run omits identity metadata, and how strictly to treat sensitive content.

Centralizing these in a single frozen object means:
  * setup logic is never duplicated across adapters,
  * a user configures the SDK in exactly one place,
  * the object can be shared safely across threads (immutable),
  * defaults stay consistent and documented in one location.

========================================================
Usage
========================================================

::

    from agent_exec_trace.config import SDKConfig, default_config
    from agent_exec_trace.tracer import configure_tracing

    # Safe-by-default (metadata-only privacy posture)
    configure_tracing(default_config())

    # Full control
    cfg = SDKConfig(
        service_name="my-agent",
        redaction=RedactionConfig(mode=PrivacyMode.TRUNCATED, capture_tool_args=True),
    )
    configure_tracing(cfg)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agent_exec_trace.redact import PrivacyMode, RedactionConfig

# ---------------------------------------------------------------------------
# Module-level defaults
# ---------------------------------------------------------------------------
# Kept as module constants so tests and docs can reference the canonical values
# without importing the dataclass.  If a default changes, it changes in exactly
# one place.
# ---------------------------------------------------------------------------

# Default OTel service name.  Shows up as the service column in Jaeger / Tempo
# and as the ``service.name`` resource attribute on every exported span.
DEFAULT_SERVICE_NAME = "agent-exec-trace"

# OTLP gRPC endpoint for the local OpenTelemetry Collector.  Milestone 3.1 wires
# the actual exporter; this is the default target the collector listens on.
DEFAULT_OTLP_ENDPOINT = "http://localhost:4317"


@dataclass(frozen=True)
class SDKConfig:
    """Immutable runtime configuration for the instrumentation SDK.

    Frozen so a single config object can be shared safely across threads, adapters,
    and span helpers without copy-on-write concerns.

    Attributes:
        service_name: OTel service name attached to the trace resource (shows up as
            the service column in Jaeger/Tempo).
        otlp_endpoint: OTLP gRPC endpoint for the exporter (configured in 3.1).
        default_agent_name: fallback agent name when a run provides none.
        default_agent_version: fallback agent version when a run provides none.
        default_workload_type: fallback workload classification when none is given.
        redaction: privacy/capture configuration (see :mod:`agent_exec_trace.redact`).

    Example::

        from agent_exec_trace.redact import PrivacyMode, RedactionConfig

        cfg = SDKConfig(
            service_name="my-tuning-agent",
            redaction=RedactionConfig(
                mode=PrivacyMode.HASHED,
                capture_tool_args=True,
                hash_salt="production-v0.1",
            ),
        )
    """

    # The ``field(default_factory=...)`` for the dataclass is required rather than a
    # bare default because ``RedactionConfig`` is itself a dataclass; a shared mutable
    # default would be a bug, and frozen-ness makes per-instance defaults the right
    # pattern here.
    service_name: str = DEFAULT_SERVICE_NAME
    otlp_endpoint: str = DEFAULT_OTLP_ENDPOINT
    default_agent_name: str = "unnamed_agent"
    default_agent_version: str | None = None
    default_workload_type: str | None = None
    redaction: RedactionConfig = field(default_factory=RedactionConfig)


def default_config() -> SDKConfig:
    """Return the safe-by-default configuration.

    Explicitly pins ``PrivacyMode.METADATA_ONLY`` rather than relying on the dataclass
    default so the trust posture is obvious at the call site and cannot silently drift
    if the class default ever changes.

    Returns:
        An ``SDKConfig`` with metadata-only redaction (no content leaks by default).

    Example::

        from agent_exec_trace.config import default_config
        from agent_exec_trace.tracer import configure_tracing

        configure_tracing(default_config())
    """
    return SDKConfig(
        redaction=RedactionConfig(mode=PrivacyMode.METADATA_ONLY),
    )