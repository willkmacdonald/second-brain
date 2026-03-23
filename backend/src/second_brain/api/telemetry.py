"""Telemetry proxy endpoint for mobile client error reporting.

Mobile app cannot use the App Insights React Native plugin (incompatible
with Expo). Instead, client-side errors are POSTed here and logged to
App Insights via the existing Python logging pipeline.
"""

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Telemetry"])


class TelemetryEvent(BaseModel):
    """Client-side telemetry event from the mobile app."""

    event_type: str = Field(
        ..., description="Event type: error, network_failure, performance"
    )
    message: str = Field(..., max_length=5000)
    capture_trace_id: str | None = Field(
        None, description="Trace ID of the capture that triggered the event"
    )
    metadata: dict[str, str | int | float | bool] | None = Field(
        None, description="Additional context (device info, screen, etc.)"
    )


@router.post("/api/telemetry", status_code=204)
async def report_client_telemetry(body: TelemetryEvent) -> None:
    """Log a client-side telemetry event to App Insights.

    Uses WARNING level so events are always visible in App Insights
    queries. Client telemetry is inherently exceptional -- the mobile
    app only reports errors and failures, not routine operations.
    """
    extra: dict = {
        "component": "mobile",
        "event_type": body.event_type,
    }
    if body.capture_trace_id:
        extra["capture_trace_id"] = body.capture_trace_id
    if body.metadata:
        extra.update(body.metadata)

    logger.warning(
        "Client %s: %s",
        body.event_type,
        body.message,
        extra=extra,
    )
