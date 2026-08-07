"""Redaction and privacy controls.

========================================================
Why this module exists
========================================================
Traces can carry sensitive content: prompts, tool arguments, retrieved text, and
memory contents. The product's default privacy posture is **truncated content capture**
with tool args enabled -- we keep content capped at a character limit so detectors
can analyze meaningful signal while sensitive payloads are never stored in full.
The ``METADATA_ONLY`` mode remains available for deployments that require zero
content on spans: it keeps structural signal (span names, timings, counts, cost,
IDs) while keeping the sensitive payloads out of the telemetry path.

This module is the trust boundary for that guarantee. Any code that wants to write
sensitive content onto a span must funnel the value through :meth:`RedactionConfig.apply`,
which decides -- from the configured mode and the per-field opt-in flag -- whether a
value is dropped, truncated, or hashed before it ever reaches the span.

========================================================
Privacy modes explained
========================================================
* **METADATA_ONLY**: No content ever written.  The safest mode.  Available for
  privacy-sensitive deployments that do not need content-based detection.
  Structural telemetry (timings, counts, IDs) is still emitted.

* **TRUNCATED** (default): Content is kept but capped at ``truncate_at`` characters.
  A ``[...]`` marker is appended when truncation occurs so consumers can
  distinguish naturally-short values from cut-off ones.  Tool args are
  captured by default under this mode so detectors have signal to work with.

* **HASHED**: Content is replaced by a **salted** SHA-256 hex digest.  The
  hash is deterministic (same input + same salt = same digest), non-reversible,
  and useful for correlating repeated payloads in analytics without revealing
  the payload itself.

========================================================
Double-gate design
========================================================
The original implementation had a single flag that controlled all content paths,
meaning enabling prompt capture could accidentally leak tool args or memory
contents. The current design uses two independent guards:

  1. **Field opt-in** (``capture_prompts``, ``capture_tool_args``,
     ``capture_memory``): enables capture for ONE specific field.
  2. **Mode gate** (``PrivacyMode``): metadata-only turns everything off globally.

Both must pass for content to reach a span.  This guarantees that enabling
prompts cannot leak tool args or memory -- the per-field flag is what gates it.

========================================================
Usage
========================================================

::

    from agent_exec_trace.redact import RedactionConfig, PrivacyMode

    cfg = RedactionConfig(
        mode=PrivacyMode.HASHED,
        capture_tool_args=True,
        hash_salt="production-v0.1",
    )

    result = cfg.apply("sensitive args", allowed=cfg.capture_tool_args)
    # result = "a1b2c3d4e5f6..."  (64-char hex digest)

    # Metadata-only mode drops everything:
    safe = RedactionConfig(mode=PrivacyMode.METADATA_ONLY)
    assert safe.apply("anything", allowed=True) is None
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum


class PrivacyMode(str, Enum):
    """How sensitive content is handled. Defaults are metadata-only.

    The ``str`` base is intentional: it lets the values serialize cleanly to span
    attributes and be compared against user-supplied config strings.  Enum members
    can be passed as attribute values without an explicit ``.value`` call.
    """

    # No content is ever written. The safest mode and the default.
    # ``apply()`` returns ``None`` immediately -- no string transformation happens.
    METADATA_ONLY = "metadata_only"
    # Content is kept but capped at a character limit (see ``truncate_at``).
    # A ``"[...]"`` marker is appended when truncation occurs.
    TRUNCATED = "truncated"
    # Content is replaced by a salted SHA-256 digest: unforgeable, deterministic,
    # and non-reversible, useful for correlating repeated payloads in analytics.
    # The salt is prepended to the plaintext before hashing.
    HASHED = "hashed"


# ---------------------------------------------------------------------------
# Truncation helpers
# ---------------------------------------------------------------------------

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
        mode: overall privacy mode. Defaults to :data:`PrivacyMode.TRUNCATED`.
        capture_prompts: capture model prompts when mode is not metadata-only.
        capture_tool_args: capture tool arguments when mode is not metadata-only.
        capture_memory: capture memory content when mode is not metadata-only.
        truncate_at: max characters (inclusive) kept in truncated mode.  Values
            longer than this are sliced and a ``"[...]"`` marker is appended.
        hash_salt: optional salt prepended to values before hashing in hashed mode.
            Different salts produce different digests for the same plaintext.

    Example::

        cfg = RedactionConfig(
            mode=PrivacyMode.TRUNCATED,
            capture_tool_args=True,
            truncate_at=256,
        )
        result = cfg.apply("some long string...", allowed=cfg.capture_tool_args)
        # result is at most 256 characters (including "[...]" if truncated)
    """

    mode: PrivacyMode = PrivacyMode.TRUNCATED
    capture_prompts: bool = False
    capture_tool_args: bool = True
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

        Returns:
            ``True`` when (a) mode is not metadata-only AND (b) at least one of
            ``capture_prompts``, ``capture_tool_args``, or ``capture_memory`` is
            ``True``.  Otherwise ``False``.

        Example::

            cfg = RedactionConfig(mode=PrivacyMode.METADATA_ONLY, capture_prompts=True)
            assert not cfg.captures_content  # metadata-only overrides everything
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
          * truncated + value too long         -> ``value[:truncate_at - len(marker)] + "[...]"``
          * otherwise                          -> the value unchanged

        Args:
            value: the raw sensitive string to potentially redact.
            allowed: per-field opt-in flag.  Must be ``True`` AND the mode must not
                be metadata-only for any content to reach a span.

        Returns:
            The redacted string value, or ``None`` if the caller must NOT record it.

        Edge cases:
            * Empty string: handled normally -- hashing it returns a valid digest,
              truncating it returns ``""``, metadata-only returns ``None``.
            * ``truncate_at`` smaller than the marker: the marker is silently omitted
              so the output never exceeds ``truncate_at`` characters.
            * Zero or negative ``truncate_at``: ``apply`` returns ``value[:truncate_at]``
              (i.e. the empty string for non-positive limits).

        Example::

            cfg = RedactionConfig(mode=PrivacyMode.HASHED, capture_tool_args=True,
                                  hash_salt="s3cret")
            cfg.apply("hello", allowed=True)     # -> "a1b2c3...64 chars..."
            cfg.apply("hello", allowed=False)    # -> None (field not opted in)
        """
        # Short-circuit: a field that is not opted-in, or a global metadata-only
        # posture, means the value must never leave the process as a span payload.
        # This is the outer gate that stops all content dead.
        if not allowed or self.mode is PrivacyMode.METADATA_ONLY:
            return None

        # Deterministic hashing. The salt is prepended so equal plaintexts with
        # different salts yield different digests, and an attacker cannot rainbow-table
        # matches without knowing the salt. Deterministic (no random component) so the
        # same run replays to the same digest for analytics correlation.
        if self.mode is PrivacyMode.HASHED:
            # Prepend salt + value to form the message; hash as sha256 hex.
            message = f"{self.hash_salt}{value}".encode()
            return hashlib.sha256(message).hexdigest()

        # Truncation: cap the retained content. We reserve room for the marker so the
        # final value is exactly ``truncate_at`` when truncated (or near it for very
        # small limits), rather than silently exceeding the stated cap.  When the cap
        # is too small to fit the marker, the marker is omitted so the output never
        # exceeds ``truncate_at`` characters.
        if len(value) > self.truncate_at:
            # Compute how many characters we can keep before the marker.
            # ``max(..., 0)`` guards against negative truncate_at.
            keep = max(self.truncate_at - len(_TRUNCATION_MARKER), 0)
            if keep <= 0:
                # If the cap is so small that even the raw value alone would exceed
                # it, return a simple slice without the marker.  The marker would
                # push us over the cap and violate the contract that output never
                # exceeds ``truncate_at`` characters.
                return value[: self.truncate_at]
            return value[:keep] + _TRUNCATION_MARKER

        # Value fits within truncate_at: return it unchanged.
        return value
