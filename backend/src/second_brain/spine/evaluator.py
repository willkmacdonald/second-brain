"""Status evaluator: reads recent events for a segment and computes status.

Hard rules:
- Status precedence: red > yellow > green > stale.
- No-data behavior: a segment with no liveness in 2x interval is stale.
- Source-lag handling: acceptable_lag_seconds is added to the staleness window.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from second_brain.spine.models import (
    STALE_FRESHNESS_SECONDS,
    SegmentStatus,
    parse_cosmos_ts,
)
from second_brain.spine.registry import EvaluatorConfig, SegmentRegistry
from second_brain.spine.storage import SpineRepository

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class EvaluationResult:
    """Output of a single evaluator run for a segment."""

    segment_id: str
    status: SegmentStatus
    headline: str
    last_event_at: datetime | None
    freshness_seconds: int
    evaluator_inputs: dict[str, Any]


class StatusEvaluator:
    """Per-segment status evaluator."""

    def __init__(
        self,
        repo: SpineRepository,
        registry: SegmentRegistry,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._repo = repo
        self._registry = registry
        self._now = now or (lambda: datetime.now(UTC))

    async def evaluate(self, segment_id: str) -> EvaluationResult:
        cfg = self._registry.get(segment_id)
        events = await self._repo.get_recent_events(
            segment_id=segment_id,
            window_seconds=cfg.workload_window_seconds,
        )

        # Compute freshness from most recent event of any type
        most_recent = max(
            (parse_cosmos_ts(e["timestamp"]) for e in events),
            default=None,
        )
        now = self._now()
        freshness = (
            int((now - most_recent).total_seconds())
            if most_recent
            else STALE_FRESHNESS_SECONDS
        )

        # Stale check (precedes all other status logic)
        stale_window = cfg.liveness_interval_seconds * 2 + cfg.acceptable_lag_seconds
        liveness_events = [e for e in events if e["event_type"] == "liveness"]
        most_recent_liveness = max(
            (parse_cosmos_ts(e["timestamp"]) for e in liveness_events),
            default=None,
        )
        if (
            most_recent_liveness is None
            or (now - most_recent_liveness).total_seconds() > stale_window
        ):
            return EvaluationResult(
                segment_id=segment_id,
                status="stale",
                headline="No recent liveness signal",
                last_event_at=most_recent,
                freshness_seconds=freshness,
                evaluator_inputs={"reason": "stale"},
            )

        # Compute workload metrics
        workload_events = [e for e in events if e["event_type"] == "workload"]
        workload_events.sort(key=lambda e: e["timestamp"])
        total = len(workload_events)
        failures = sum(
            1 for e in workload_events if e["payload"]["outcome"] == "failure"
        )
        rate = failures / total if total > 0 else 0.0

        # Consecutive failures (most recent N)
        consecutive_failures = 0
        for e in reversed(workload_events):
            if e["payload"]["outcome"] == "failure":
                consecutive_failures += 1
            else:
                break

        # Readiness signals
        readiness_events = [e for e in events if e["event_type"] == "readiness"]
        any_readiness_failed = any(
            any(c["status"] == "failing" for c in e["payload"]["checks"])
            for e in readiness_events
        )

        inputs = {
            "workload_total": total,
            "workload_failures": failures,
            "workload_failure_rate": rate,
            "consecutive_failures": consecutive_failures,
            "any_readiness_failed": any_readiness_failed,
        }

        # Apply red thresholds first
        if self._exceeds(cfg.red_thresholds, inputs):
            return EvaluationResult(
                segment_id=segment_id,
                status="red",
                headline=self._red_headline(inputs, cfg),
                last_event_at=most_recent,
                freshness_seconds=freshness,
                evaluator_inputs=inputs,
            )

        # Then yellow
        if self._exceeds(cfg.yellow_thresholds, inputs):
            return EvaluationResult(
                segment_id=segment_id,
                status="yellow",
                headline=self._yellow_headline(inputs),
                last_event_at=most_recent,
                freshness_seconds=freshness,
                evaluator_inputs=inputs,
            )

        return EvaluationResult(
            segment_id=segment_id,
            status="green",
            headline=self._green_headline(inputs, cfg),
            last_event_at=most_recent,
            freshness_seconds=freshness,
            evaluator_inputs=inputs,
        )

    @staticmethod
    def _exceeds(thresholds: dict[str, Any], inputs: dict[str, Any]) -> bool:
        for key, threshold in thresholds.items():
            value = inputs.get(key)
            if value is None:
                continue
            # bool is a subclass of int in Python, so bool thresholds MUST be
            # handled before the numeric branch — otherwise a False threshold
            # would match any truthy value via the `value >= threshold` path.
            if isinstance(threshold, bool):
                if value == threshold:
                    return True
            elif isinstance(threshold, (int, float)) and value >= threshold:
                return True
        return False

    @staticmethod
    def _red_headline(inputs: dict[str, Any], cfg: EvaluatorConfig) -> str:
        # Surface the consecutive-failure message only when that threshold was
        # actually the trigger — compare against the configured red threshold,
        # not a hardcoded constant. Falls through to the rate message otherwise.
        consec_threshold = cfg.red_thresholds.get("consecutive_failures")
        consec = inputs.get("consecutive_failures", 0)
        if isinstance(consec_threshold, (int, float)) and consec >= consec_threshold:
            return f"{consec} consecutive failures"
        rate_pct = int(inputs.get("workload_failure_rate", 0) * 100)
        fails = inputs["workload_failures"]
        total = inputs["workload_total"]
        return f"{rate_pct}% failure rate ({fails}/{total})"

    @staticmethod
    def _yellow_headline(inputs: dict[str, Any]) -> str:
        if inputs.get("any_readiness_failed"):
            return "Dependency check failing"
        rate_pct = int(inputs.get("workload_failure_rate", 0) * 100)
        fails = inputs["workload_failures"]
        total = inputs["workload_total"]
        return f"{rate_pct}% failure rate ({fails}/{total})"

    @staticmethod
    def _green_headline(inputs: dict[str, Any], cfg: EvaluatorConfig) -> str:
        total = inputs.get("workload_total", 0)
        window_label = _humanize_window(cfg.workload_window_seconds)
        if total == 0:
            return "Idle (no recent operations)"
        return f"{total} ops, 0 failures in last {window_label}"


def _humanize_window(seconds: int) -> str:
    """Human label for the workload window (e.g. 300 → '5min', 90 → '90s')."""
    if seconds >= 60 and seconds % 60 == 0:
        return f"{seconds // 60}min"
    return f"{seconds}s"
