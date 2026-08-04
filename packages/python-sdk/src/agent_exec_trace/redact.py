"""Redaction and privacy controls.

========================================================
Why this module exists
========================================================
Traces can carry sensitive content: prompts, tool arguments, retrieved text, and
memory contents. The product's locked privacy posture (see architecture-v0.1.0.md)
is **metadata-only by default** -- we keep structural signal (span names, timings,
counts, cost, IDs) while keeping the sensitive payloads out of the telemetry path.

This module is the trust boundary for that guarantee. Any code that wants to write
sensitive content onto a span must funnel the value through :meth:`RedactionConfig.apply`,
which decides -- from the configured mode and the per-field opt-in flag -- whether a
value is dropped, truncated, or hashed before it ever reaches the span.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum


class PrivacyMode(str, Enum):
    """How sensitive content is handled. Defaults are metadata-only.

    The ``str`` base is intentional: it lets the values serialize cleanly to span
    attributes and be compared against user-supplied config strings.
    """

    # No content is ever written. The safest mode and the default.
    METADATA_ONLY = "metadata_only"
    # Content is kept but capped at a character limit (see ``truncate_at``).
    TRUNCATED = "truncated"
    # Content is replaced by a salted SHA-256 digest: unforgeable, deterministic,
    # and non-reversible, useful for correlating repeated payloads in analytics.
    HASHED = "hashed"


# Marker appended to a truncated payload. Its length is subtracted when slicing so
# the stored value never exceeds ``truncate_at`` characters. Kept as a named
# constant because it is referenced in both ``apply()`` and the tests.
_TRUNCATION_MARKER = "[...]"


@dataclass(frozen=True)
class RedactionConfig:
    """Configuration for content capture defaults.

    The mode decides HOW content is stored (when it is stored at all). The three
    ``capture_*`` flags decide WHETHER a specific field is allowed out at all.

    Frozen (immutable): a config can be shared safely across threads and adapters
    without copy-on-write concerns, matching the SDK's design principle that each
    run / adapter reads from a single shared config.

    Attributes:
        mode: overall privacy mode. Defaults to :data:`PrivacyMode.METADATA_ONLY`.
        capture_prompts: capture model prompts when mode is not metadata-only.
        capture_tool_args: capture tool arguments when mode is not metadata-only.
        capture_memory: capture memory content when mode is not metadata-only.
        truncate_at: max characters (inclusive) kept in truncated mode.
        hash_salt: optional salt used for deterministic hashing in hashed mode.
    """

    mode: PrivacyMode = PrivacyMode.METADATA_ONLY
    capture_prompts: bool = False
    capture_tool_args: bool = False
    capture_memory: bool = False
    truncate_at: int = 512
    hash_salt: str = ""

    @property
    def captures_content(self) -> bool:
        """True if any sensitive content path is actually enabled.

        This is a fast short-circuit used by callers that want to skip work entirely
        when nothing is being captured. Note it is independent of which field opts in:
        enabling prompts alone makes this True even though tools/memory stay off --
        the per-field gating is enforced separately in ``apply``.
        """
        return self.mode is not PrivacyMode.METADATA_ONLY and (
            self.capture_prompts or self.capture_tool_args or self.capture_memory
        )

    def apply(self, value: str, *, allowed: bool) -> str | None:
        """Redact a sensitive ``value``, or return ``None`` to signal "do not record".

        ``allowed`` is the caller-supplied opt-in flag for the specific field being
        written (e.g. ``capture_tool_args``). Two independent guards:

          1. Field opt-in (``allowed``): enables capture for ONE field without
             accidentally enabling the others.
          2. Mode gate: metadata-only turns everything off globally.

        The double gate is what makes the "enabling prompts can't leak tool args or
        memory" property hold -- the original all-modes-are-equal bug this replaced.

        Return values, by mode:
          * metadata-only or ``allowed=False``  -> ``None`` (skip the span write)
          * hashed                              -> 64-char salted SHA-256 hex digest
          * truncated + value too long         -> value[:truncate_at-len(marker)] + "[...]"
          * otherwise                          -> the value unchanged
        """
        # Short-circuit: a field that is not opted-in, or a global metadata-only
        # posture, means the value must never leave the process as a span payload.
        if not allowed or self.mode is PrivacyMode.METADATA_ONLY:
            return None

        # Deterministic hashing. The salt is prepended so equal plaintexts with
        # different salts yield different digests, and an attacker cannot rainbow-table
        # matches without knowing the salt. Deterministic (no random component) so the
        # same run replays to the same digest for analytics correlation.
        if self.mode is PrivacyMode.HASHED:
            message = f"{self.hash_salt}{value}".encode()
            return hashlib.sha256(message).hexdigest()

        # Truncation: cap the retained content. We reserve room for the marker so the
        # final value is exactly ``truncate_at`` when truncated (or near it for very
        # small limits), rather than silently exceeding the stated cap.  When the cap
        # is too small to fit the marker, the marker is omitted so the output never
        # exceeds ``truncate_at`` characters.
        if len(value) > self.truncate_at:
            keep = max(self.truncate_at - len(_TRUNCATION_MARKER), 0)
            if keep <= 0:
                return value[: self.truncate_at]
            return value[:keep] + _TRUNCATION_MARKER

        return value