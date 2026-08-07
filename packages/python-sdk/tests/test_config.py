"""Tests for SDK configuration defaults.

Guards the default trust posture (``default_config`` is truncated with tool args
enabled) and the documented field defaults, so a refactor can't silently change
what users get out of the box.
"""

from __future__ import annotations

from agent_exec_trace.config import SDKConfig, default_config
from agent_exec_trace.redact import PrivacyMode


def test_default_config_is_truncated_with_tool_args() -> None:
    # The SDK's out-of-the-box posture captures tool args in truncated mode
    # so detectors have content to analyze without additional configuration.
    cfg = default_config()
    assert cfg.redaction.mode is PrivacyMode.TRUNCATED
    assert cfg.redaction.capture_tool_args is True
    assert cfg.redaction.captures_content is True


def test_config_defaults() -> None:
    # Documented defaults for service identity and the future OTLP exporter endpoint.
    cfg = SDKConfig()
    assert cfg.service_name == "agent-exec-trace"
    assert cfg.otlp_endpoint == "http://localhost:4317"
    assert cfg.default_agent_name == "unnamed_agent"
    assert cfg.default_agent_version is None
