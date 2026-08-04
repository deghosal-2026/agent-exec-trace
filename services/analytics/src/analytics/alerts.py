"""Webhook-based alerting for detected anomalies.

Sends anomaly notifications to an external webhook URL when configured. The
alerter is invoked by the worker after anomaly detection completes, and is
designed to be pluggable -- future alerters (Slack, PagerDuty, email) can
share the same interface.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class WebhookAlerter:
    """Dispatch anomaly alerts to an external HTTP endpoint.

    The webhook payload includes the anomaly's identity, type, severity, explanation,
    and a link to the run timeline.  Failures are logged but never raised -- the
    alerting path is best-effort and should not block the processing pipeline.

    Args:
        webhook_url: target URL for the HTTP POST.  An empty string disables alerting.
    """

    def __init__(self, webhook_url: str = "") -> None:
        self.webhook_url = webhook_url

    async def send_alert(self, anomaly: Any) -> bool:
        """POST the anomaly payload to the configured webhook URL.

        Constructs a JSON payload with the anomaly's key fields (id, run_id, type,
        severity, explanation, timestamp) and a link to the run timeline.  The
        request has a 10-second timeout and logs but swallows HTTP errors.

        Args:
            anomaly: An anomaly model object (must have ``id``, ``run_id``,
                ``agent_name``, ``anomaly_type``, ``severity``, ``explanation``,
                ``detected_at`` attributes).

        Returns:
            True if the request succeeded, False if no URL is configured or the
            request failed.
        """
        if not self.webhook_url:
            logger.debug("No webhook URL configured, skipping alert")
            return False

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
                    timeout=10,
                )
                resp.raise_for_status()
                logger.info("Alert sent for anomaly %s (%s)", anomaly.id, anomaly.anomaly_type)
                return True
        except httpx.HTTPError as e:
            logger.warning("Failed to send webhook alert for anomaly %s: %s", anomaly.id, e)
            return False