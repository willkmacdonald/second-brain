"""FastAPI middleware that emits a spine workload event per request."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from second_brain.spine.models import IngestEvent, WorkloadPayload, _WorkloadEvent
from second_brain.spine.storage import SpineRepository

logger = logging.getLogger(__name__)


class SpineWorkloadMiddleware(BaseHTTPMiddleware):
    """Records a workload event per request (success/failure + duration)."""

    def __init__(self, app, repo: SpineRepository, segment_id: str) -> None:
        super().__init__(app)
        self._repo = repo
        self._segment_id = segment_id

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.perf_counter()
        operation = f"{request.method} {request.url.path}"
        # ContextVar for capture_trace_id is set elsewhere in the codebase;
        # we read whichever request header carries it for the workload payload.
        correlation_id = request.headers.get("x-trace-id")

        try:
            response = await call_next(request)
            duration_ms = int((time.perf_counter() - start) * 1000)
            outcome = "success" if response.status_code < 500 else "failure"
            event = _WorkloadEvent(
                segment_id=self._segment_id,
                event_type="workload",
                timestamp=datetime.now(UTC),
                payload=WorkloadPayload(
                    operation=operation,
                    outcome=outcome,
                    duration_ms=duration_ms,
                    correlation_kind="capture" if correlation_id else None,
                    correlation_id=correlation_id,
                    error_class=None
                    if outcome == "success"
                    else f"HTTP_{response.status_code}",
                ),
            )
            ingest_event = IngestEvent(root=event)
            try:
                await self._repo.record_event(ingest_event)
            except Exception:  # noqa: BLE001 - never let spine break the request
                logger.warning("Failed to record spine workload event", exc_info=True)
            return response
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            event = _WorkloadEvent(
                segment_id=self._segment_id,
                event_type="workload",
                timestamp=datetime.now(UTC),
                payload=WorkloadPayload(
                    operation=operation,
                    outcome="failure",
                    duration_ms=duration_ms,
                    correlation_kind="capture" if correlation_id else None,
                    correlation_id=correlation_id,
                    error_class=type(exc).__name__,
                ),
            )
            ingest_event = IngestEvent(root=event)
            try:
                await self._repo.record_event(ingest_event)
            except Exception:  # noqa: BLE001
                logger.warning("Failed to record spine workload event", exc_info=True)
            raise
