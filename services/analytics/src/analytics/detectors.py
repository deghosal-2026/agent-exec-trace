"""Backward-compatible re-exports from the detectors package.

This file exists so existing imports like::

    from analytics.detectors import LoopDetector, CostSpikeDetector, RetryStormDetector

continue to work after the detectors were moved into the ``analytics.detectors``
package.  New code should import directly from the sub-modules::

    from analytics.detectors.tool import LoopDetector
    from analytics.detectors.cost import CostSpikeDetector
    from analytics.detectors.retry import RetryStormDetector

The ``__all__`` only exposes the three original detectors to avoid confusing
users who might think this module contains all detectors (use
``analytics.detectors.create_all_detectors`` for that).
"""

from __future__ import annotations

from analytics.detectors.cost import CostSpikeDetector
from analytics.detectors.retry import RetryStormDetector
from analytics.detectors.tool import LoopDetector

__all__ = ["LoopDetector", "RetryStormDetector", "CostSpikeDetector"]
