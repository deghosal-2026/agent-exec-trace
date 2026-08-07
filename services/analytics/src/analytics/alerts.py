"""Webhook-based alerting for detected anomalies.

Sends anomaly notifications to an external webhook URL when configured.  The
alerter is invoked by the worker after anomaly detection completes, and is
designed to be pluggable — future alerters (Slack, PagerDuty, email) can
share the same interface (``send_alert`` returning ``bool``).

**Design decisions:**

- **Best-effort only**: Failures are logged but never raised.  The alerting
  path must not block the processing pipeline.  If the webhook is down,
  anomalies are still persisted to the database.
- **10-second timeout**: Balances delivery expectation with resilience.  A
  longer timeout could stall the worker loop; a shorter one would never
  deliver.
- **No batch/buffer**: Each anomaly triggers an immediate POST.  This is
  intentional: anomalies are rare events (by design) and batch would add
  latency for the most actionable alerts.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class WebhookAlerter:
    """Dispatch anomaly alerts to an external HTTP endpoint.

    The webhook payload includes the anomaly's identity, type, severity,
    explanation, and a link to the run timeline.  Failures are logged but
    never raised — the alerting path is best-effort and should not block
    the processing pipeline.

    Args:
        webhook_url: target URL for the HTTP POST.  An empty string disables
            alerting entirely (all ``send_alert`` calls become no-ops).
    """

    def __init__(self, webhook_url: str = "") -> None:
        self.webhook_url = webhook_url

    async def send_alert(self, anomaly: Any) -> bool:
        """POST the anomaly payload to the configured webhook URL.

        Constructs a JSON payload with the anomaly's key fields (id, run_id,
        type, severity, explanation, timestamp) and a link to the run timeline.
        The request has a 10-second timeout and logs but swallows HTTP errors.

        Args:
            anomaly: An anomaly model object (must have ``id``, ``run_id``,
                ``agent_name``, ``anomaly_type``, ``severity``,
                ``explanation``, ``detected_at`` attributes).

        Returns:
            ``True`` if the request succeeded, ``False`` if no URL is
            configured or the request failed (including network errors,
            non-2xx status codes, and timeouts).
        """
        # No URL configured: silently skip.  This is the "no alerting" mode.
        if not self.webhook_url:
            logger.debug("No webhook URL configured, skipping alert")
            return False

        # Build payload with all anomaly fields needed by the receiver.
        # The run_url points to the timeline page so an engineer can click
        # straight through from Slack/PagerDuty.
        payload = {
            "anomaly_id": anomaly.id,
            "run_id": anomaly.run_id,
            "agent_name": anomaly.agent_name,
            "anomaly_type": anomaly.anomaly_type,
            "severity": anomaly.severity,
            "explanation": anomaly.explanation,
            "detected_at": anomaly.detected_at.isoformat() if anomaly.detected_at else None,
            "run_url": f"http://localhost:8000/runs/{anomaly.run_id}",
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10,  # seconds — prevents hanging on slow endpoints
                )
                # raise_for_status() turns 4xx/5xx into httpx.HTTPStatusError
                resp.raise_for_status()
                logger.info("Alert sent for anomaly %s (%s)", anomaly.id, anomaly.anomaly_type)
                return True
        except httpx.HTTPError as e:
            # Catch-all for connection errors, timeouts, redirect loops, and
            # 4xx/5xx status codes.  We log and return False rather than
            # raising so the worker continues processing.
            logger.warning("Failed to send webhook alert for anomaly %s: %s", anomaly.id, e)
            return False
