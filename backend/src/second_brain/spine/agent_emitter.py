"""Helper for emitting workload events from agent wrappers.

Correlation kind precedence: capture > thread > request > crud
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Literal

from second_brain.spine.models import (
    CorrelationKind,
    WorkloadPayload,
    _WorkloadEvent,
)
from second_brain.spine.storage import SpineRepository

logger = logging.getLogger(__name__)

Outcome = Literal["success", "failure", "degraded"]


async def emit_agent_workload(
    repo: SpineRepository,
    segment_id: str,
    operation: str,
    outcome: Outcome,
    duration_ms: int,
    capture_trace_id: str | None,
    run_id: str | None,
    thread_id: str | None,
    error_class: str | None = None,
) -> None:
    """Emit a single workload event for an agent invocation."""
    correlation_kind: CorrelationKind | None
    correlation_id: str | None
    if capture_trace_id:
        correlation_kind = "capture"
        correlation_id = capture_trace_id
    elif thread_id:
        correlation_kind = "thread"
        correlation_id = thread_id
    else:
        correlation_kind = None
        correlation_id = None

    op_suffix = f" run={run_id}" if run_id else ""
    event = _WorkloadEvent(
        segment_id=segment_id,
        event_type="workload",
        timestamp=datetime.now(UTC),
        payload=WorkloadPayload(
            operation=f"{operation}{op_suffix}",
            outcome=outcome,
            duration_ms=duration_ms,
            correlation_kind=correlation_kind,
            correlation_id=correlation_id,
            error_class=error_class,
        ),
    )
    try:
        await repo.record_event(event)
    except Exception:  # noqa: BLE001
        logger.warning("emit_agent_workload failed", exc_info=True)
