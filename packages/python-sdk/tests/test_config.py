"""Tests for SDK configuration defaults.

Guards the safe-by-default trust posture (``default_config`` is metadata-only) and
the documented field defaults, so a refactor can't silently change what users get
out of the box.
"""

from __future__ import annotations

from agent_exec_trace.config import SDKConfig, default_config
from agent_exec_trace.redact import PrivacyMode


def test_default_config_is_metadata_only() -> None:
    # The SDK's out-of-the-box posture must never capture content: mode is
    # METADATA_ONLY and no capture flags are enabled.
    cfg = default_config()
    assert cfg.redaction.mode is PrivacyMode.METADATA_ONLY
    assert cfg.redaction.captures_content is False


def test_config_defaults() -> None:
    # Documented defaults for service identity and the future OTLP exporter endpoint.
    cfg = SDKConfig()
    assert cfg.service_name == "agent-exec-trace"
    assert cfg.otlp_endpoint == "http://localhost:4317"
    assert cfg.default_agent_name == "unnamed_agent"
    assert cfg.default_agent_version is None