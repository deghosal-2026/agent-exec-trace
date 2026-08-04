"""Tests for redaction/privacy controls.

Covers the two-layer privacy contract: mode (drop/truncate/hash) AND per-field opt-in
flags. A field is only ever stored when both layers allow it; hashing is
deterministic and never reversible to plaintext.
"""

from __future__ import annotations

from agent_exec_trace.redact import PrivacyMode, RedactionConfig


def test_metadata_only_returns_none() -> None:
    # Default posture: no content may be captured at all, even for an "allowed" field.
    cfg = RedactionConfig(mode=PrivacyMode.METADATA_ONLY)
    assert cfg.apply("prompt with secret", allowed=True) is None


def test_disallowed_field_returns_none_even_when_mode_enabled() -> None:
    # Second gate: a capture-enabled mode does NOT bypass per-field opt-in. Here
    # prompts are opted in but the value is a disallowed field -> still dropped.
    cfg = RedactionConfig(mode=PrivacyMode.TRUNCATED, capture_prompts=True)
    assert cfg.apply("tool args that should not leak", allowed=False) is None


def test_truncated_caps_length() -> None:
    # Truncation respects truncate_at exactly and the output keeps a prefix.
    cfg = RedactionConfig(mode=PrivacyMode.TRUNCATED, truncate_at=10)
    out = cfg.apply("0123456789abcdef", allowed=True)
    assert out is not None
    assert out.startswith("0123456")
    assert len(out) == 10


def test_truncated_keeps_short_values() -> None:
    # Values shorter than the cap pass through untouched.
    cfg = RedactionConfig(mode=PrivacyMode.TRUNCATED)
    assert cfg.apply("short", allowed=True) == "short"


def test_truncated_respects_cap_when_marker_is_too_long() -> None:
    # When truncate_at is too small for the "[...]" marker, the marker is omitted
    # so the output never exceeds truncate_at (boundary cases for 0, 1, 2, 3).
    def _apply(cap: int) -> str:
        cfg = RedactionConfig(mode=PrivacyMode.TRUNCATED, truncate_at=cap)
        return cfg.apply("abcdefgh", allowed=True) or ""

    assert len(_apply(0)) == 0
    assert len(_apply(1)) == 1
    assert len(_apply(2)) == 2
    assert len(_apply(3)) == 3
    assert len(_apply(4)) == 4


def test_hashed_is_deterministic_and_not_plaintext() -> None:
    # Hashing is salted and deterministic: same input -> same digest, but the digest
    # is never the plaintext and is fixed-length (sha256 -> 64 hex chars).
    cfg = RedactionConfig(mode=PrivacyMode.HASHED, hash_salt="s3cret")
    first = cfg.apply("password123", allowed=True)
    second = cfg.apply("password123", allowed=True)
    assert first is not None and second is not None
    assert first == second
    assert first != "password123"
    assert len(first) == 64


def test_captures_content_flag() -> None:
    # captures_content is a single summary flag: true only when some field is opted
    # in under a mode that can store content.
    assert not RedactionConfig().captures_content
    assert not RedactionConfig(mode=PrivacyMode.TRUNCATED).captures_content
    assert RedactionConfig(
        mode=PrivacyMode.TRUNCATED, capture_prompts=True
    ).captures_content