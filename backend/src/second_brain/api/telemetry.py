"""Telemetry proxy endpoint for mobile client error reporting.

Mobile app cannot use the App Insights React Native plugin (incompatible
with Expo). Instead, client-side errors are POSTed here and logged to
App Insights via the existing Python logging pipeline.
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from second_brain.spine.models import (
    IngestEvent,
    LivenessPayload,
    WorkloadPayload,
    _LivenessEvent,
    _WorkloadEvent,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Telemetry"])


class TelemetryEvent(BaseModel):
    """Client-side telemetry event from the mobile app."""

    event_type: str = Field(
        ..., description="Event type: error, network_failure, performance, crud_failure"
    )
    message: str = Field(..., max_length=5000)
    capture_trace_id: str | None = Field(
        None, description="Trace ID of the capture that triggered the event"
    )
    correlation_kind: str | None = Field(
        None, description="Correlation kind: capture, thread, request, crud"
    )
    correlation_id: str | None = Field(
        None, description="Correlation ID for spine event linkage"
    )
    metadata: dict[str, str | int | float | bool] | None = Field(
        None, description="Additional context (device info, screen, etc.)"
    )


def _segment_for_crud_operation(operation: str) -> str:
    """Route mobile crud failures to the right segment.

    Inbox/conversation operations -> mobile_ui
    Status/errands operations     -> mobile_capture
    """
    if any(k in operation for k in ("inbox", "recategorize", "conversation", "bucket")):
        return "mobile_ui"
    return "mobile_capture"


@router.post("/api/telemetry", status_code=204)
async def report_client_telemetry(body: TelemetryEvent, request: Request) -> None:
    """Log a client-side telemetry event to App Insights.

    Uses WARNING level so events are always visible in App Insights
    queries. Client telemetry is inherently exceptional -- the mobile
    app only reports errors and failures, not routine operations.

    When event_type is "crud_failure", also forward to the spine as a
    workload failure for the appropriate mobile segment.
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

    # Forward crud_failure events to spine
    if body.event_type == "crud_failure":
        spine_repo = getattr(request.app.state, "spine_repo", None)
        if spine_repo is not None:
            operation = str((body.metadata or {}).get("operation", "unknown_crud"))
            segment_id = _segment_for_crud_operation(operation)
            event = _WorkloadEvent(
                segment_id=segment_id,
                event_type="workload",
                timestamp=datetime.now(UTC),
                payload=WorkloadPayload(
                    operation=operation,
                    outcome="failure",
                    duration_ms=0,
                    correlation_kind=body.correlation_kind or "crud",
                    correlation_id=(body.correlation_id or body.capture_trace_id),
                    error_class="MobileCrudFailure",
                ),
            )
            # SPIKE-MEMO §5.2 — wrap in IngestEvent(root=...) so record_event's
            # `event.root` accessor does not raise AttributeError.
            try:
                await spine_repo.record_event(IngestEvent(root=event))
            except Exception:
                logger.warning(
                    "Failed to record mobile crud failure to spine",
                    exc_info=True,
                )
            liveness_event = _LivenessEvent(
                segment_id=segment_id,
                event_type="liveness",
                timestamp=datetime.now(UTC),
                payload=LivenessPayload(
                    instance_id=request.headers.get("user-agent", "unknown")[:64]
                ),
            )
            # SPIKE-MEMO §5.2 — same wrap for the sibling liveness emit.
            try:
                await spine_repo.record_event(IngestEvent(root=liveness_event))
            except Exception:
                logger.warning("Failed to emit mobile liveness", exc_info=True)
