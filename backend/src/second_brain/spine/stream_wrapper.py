"""Spine-aware stream wrapper for agent workload emission.

Wraps an async generator (SSE stream) to time the full iteration and
emit a workload event when the stream completes or errors.
"""

from __future__ import annotations

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
