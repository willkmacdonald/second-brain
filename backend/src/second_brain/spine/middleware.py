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

    def __init__(
        self,
        app,
        repo: SpineRepository | None = None,
        segment_id: str = "backend_api",
    ) -> None:
        super().__init__(app)
        self._repo = repo
        self._segment_id = segment_id

    def _resolve_repo(self, request: Request) -> SpineRepository | None:
        """Return self._repo, then app.state.spine_repo, then None.

        Module-scope middleware registration (the project convention) can't
        receive lifespan-constructed dependencies directly, so fall back to
        app.state. When the repo is absent entirely (lifespan skipped spine
        wiring because cosmos_manager was None), silently no-op.
        """
        if self._repo is not None:
            return self._repo
        return getattr(request.app.state, "spine_repo", None)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.perf_counter()
        operation = f"{request.method} {request.url.path}"

        try:
            response = await call_next(request)
            duration_ms = int((time.perf_counter() - start) * 1000)
            outcome = "success" if response.status_code < 500 else "failure"
            correlation_id = self._read_capture_trace_id(request)
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
            repo = self._resolve_repo(request)
            if repo is None:
                return response
            try:
                await repo.record_event(ingest_event)
            except Exception:  # noqa: BLE001 - never let spine break the request
                logger.warning("Failed to record spine workload event", exc_info=True)
            return response
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            correlation_id = self._read_capture_trace_id(request)
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
            repo = self._resolve_repo(request)
            if repo is None:
                raise
            try:
                await repo.record_event(ingest_event)
            except Exception:  # noqa: BLE001
                logger.warning("Failed to record spine workload event", exc_info=True)
            raise

    @staticmethod
    def _read_capture_trace_id(request: Request) -> str | None:
        """Resolve the capture trace ID for correlation.

        Precedence (per Task 9 amendment — required to make capture
        correlation work for native app requests that don't send
        X-Trace-Id):
          1. request.state.capture_trace_id  (set by capture handlers
             after they generate/accept a trace ID — see Task 9 Step 3b)
          2. X-Trace-Id inbound header       (caller-supplied)
          3. None                            (uncorrelated)
        """
        state_val = getattr(request.state, "capture_trace_id", None)
        if state_val:
            return str(state_val)
        header_val = request.headers.get("x-trace-id")
        if header_val:
            return header_val
        return None
