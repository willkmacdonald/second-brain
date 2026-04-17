"""Background tasks: status evaluator loop + self-liveness emitter."""

from __future__ import annotations

import asyncio
import logging
import socket
from datetime import UTC, datetime

from second_brain.spine.evaluator import StatusEvaluator
from second_brain.spine.models import IngestEvent, LivenessPayload, _LivenessEvent
from second_brain.spine.registry import SegmentRegistry
from second_brain.spine.storage import SpineRepository

logger = logging.getLogger(__name__)


async def evaluator_loop(
    evaluator: StatusEvaluator,
    repo: SpineRepository,
    registry: SegmentRegistry,
    interval_seconds: int = 30,
) -> None:
    """Run the evaluator for every registered segment every N seconds.

    Per-segment isolation: if one segment's tick fails, the remaining segments
    in the same sweep still run. This is load-bearing for a health monitor.
    """
    while True:
        for cfg in registry.all():
            try:
                result = await evaluator.evaluate(cfg.segment_id)
                prev = await repo.get_segment_state(cfg.segment_id)
                prev_status = prev.get("status") if prev else None
                now = datetime.now(UTC)
                await repo.upsert_segment_state(
                    segment_id=cfg.segment_id,
                    status=result.status,
                    headline=result.headline,
                    last_updated=now,
                    evaluator_inputs=result.evaluator_inputs,
                )
                if prev_status != result.status:
                    await repo.record_status_change(
                        segment_id=cfg.segment_id,
                        status=result.status,
                        prev_status=prev_status,
                        headline=result.headline,
                        evaluator_outputs=result.evaluator_inputs,
                        timestamp=now,
                    )
            except Exception:
                logger.warning(
                    "Evaluator tick failed for segment_id=%s",
                    cfg.segment_id,
                    exc_info=True,
                )
        await asyncio.sleep(interval_seconds)


async def liveness_emitter(
    repo: SpineRepository,
    segment_id: str,
    interval_seconds: int = 30,
) -> None:
    """Self-liveness for the Backend API segment (emitted from inside the API)."""
    instance_id = socket.gethostname()
    while True:
        try:
            event = IngestEvent(
                root=_LivenessEvent(
                    segment_id=segment_id,
                    event_type="liveness",
                    timestamp=datetime.now(UTC),
                    payload=LivenessPayload(instance_id=instance_id),
                )
            )
            await repo.record_event(event)
        except Exception:
            logger.warning(
                "Liveness emitter failed for segment_id=%s",
                segment_id,
                exc_info=True,
            )
        await asyncio.sleep(interval_seconds)
