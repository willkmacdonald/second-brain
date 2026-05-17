"""Spine-aware stream wrapper for agent workload emission.

Wraps an async generator (SSE stream) to time the full iteration and
emit a workload event when the stream completes or errors.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncGenerator

from second_brain.spine.agent_emitter import emit_agent_workload
from second_brain.spine.storage import SpineRepository

logger = logging.getLogger(__name__)


async def spine_stream_wrapper(
    inner: AsyncGenerator[str, None],
    repo: SpineRepository,
    segment_id: str,
    operation: str,
    capture_trace_id: str | None = None,
    thread_id: str | None = None,
    run_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """Wrap an SSE stream generator with spine workload emission."""
    start = time.perf_counter()
    outcome = "success"
    error_class: str | None = None
    try:
        async for event in inner:
            yield event
    except Exception as exc:
        outcome = "failure"
        error_class = type(exc).__name__
        # Phase 24 diagnostic patch (2026-05-17): adapter's own except handler
        # may not be reaching App Insights. Log eagerly here too, with
        # structured fields populated BEFORE any traceback formatting that
        # might itself raise.
        try:
            from typing import Any

            diag_extra: dict[str, Any] = {
                "capture_trace_id": capture_trace_id or "",
                "segment_id": segment_id,
                "operation": operation,
                "exception.type": type(exc).__name__,
                "exception.module": type(exc).__module__,
                "exception.repr": repr(exc)[:1000],
                "exception.str": str(exc)[:1000],
            }
            if isinstance(exc, json.JSONDecodeError):
                diag_extra["jsondecodeerror.msg"] = exc.msg
                diag_extra["jsondecodeerror.pos"] = exc.pos
                diag_extra["jsondecodeerror.lineno"] = exc.lineno
                diag_extra["jsondecodeerror.colno"] = exc.colno
                diag_extra["jsondecodeerror.doc_len"] = len(exc.doc or "")
                diag_extra["jsondecodeerror.doc_head"] = (exc.doc or "")[:500]
                diag_extra["jsondecodeerror.doc_around_pos"] = (exc.doc or "")[
                    max(0, exc.pos - 100) : exc.pos + 100
                ]
            logger.error(
                "PHASE24-DIAG spine_stream_wrapper exception: %s",
                type(exc).__name__,
                extra=diag_extra,
            )
        except Exception:
            pass
        raise
    finally:
        duration_ms = int((time.perf_counter() - start) * 1000)
        await emit_agent_workload(
            repo=repo,
            segment_id=segment_id,
            operation=operation,
            outcome=outcome,
            duration_ms=duration_ms,
            capture_trace_id=capture_trace_id,
            run_id=run_id,
            thread_id=thread_id,
            error_class=error_class,
        )
