"""Per-segment evaluator configuration registry.

Config lives in code (not in the database). New segment thresholds
require a code change — intentional.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class EvaluatorConfig:
    """Evaluator config for one segment."""

    segment_id: str
    liveness_interval_seconds: int
    host_segment: str | None
    workload_window_seconds: int = 300
    acceptable_lag_seconds: int = 0
    yellow_thresholds: dict[str, Any] = field(default_factory=dict)
    red_thresholds: dict[str, Any] = field(default_factory=dict)
    display_name: str = ""

    def name_or_id(self) -> str:
        return self.display_name or self.segment_id

    def __post_init__(self) -> None:
        # The evaluator's stale window is liveness_interval_seconds * 2 +
        # acceptable_lag_seconds. get_recent_events is queried with
        # workload_window_seconds. If the query window is smaller than the
        # stale window, a segment can appear stale just because the query
        # truncated older liveness events — fail fast at config time.
        stale_window = self.liveness_interval_seconds * 2 + self.acceptable_lag_seconds
        if self.workload_window_seconds < stale_window:
            raise ValueError(
                f"EvaluatorConfig for '{self.segment_id}': "
                f"workload_window_seconds ({self.workload_window_seconds}) "
                f"must be >= stale window ({stale_window} = "
                f"liveness_interval_seconds * 2 + acceptable_lag_seconds) "
                f"so the query covers the staleness threshold."
            )


class SegmentRegistry:
    """Lookup of EvaluatorConfig by segment_id."""

    def __init__(self, configs: list[EvaluatorConfig]) -> None:
        self._by_id = {c.segment_id: c for c in configs}

    def get(self, segment_id: str) -> EvaluatorConfig:
        return self._by_id[segment_id]

    def all(self) -> list[EvaluatorConfig]:
        """Return configs in insertion order (driven by factory order)."""
        return list(self._by_id.values())


def get_default_registry() -> SegmentRegistry:
    """Default segment configs for Phase 1.

    Future phases extend this list. The container_app rollup node is
    included because it powers host_segment suppression.
    """
    return SegmentRegistry(
        [
            EvaluatorConfig(
                segment_id="backend_api",
                display_name="Backend API",
                liveness_interval_seconds=30,
                host_segment="container_app",
                workload_window_seconds=300,
                yellow_thresholds={
                    "workload_failure_rate": 0.10,
                    "any_readiness_failed": True,
                },
                red_thresholds={
                    "workload_failure_rate": 0.50,
                    "consecutive_failures": 3,
                },
            ),
            EvaluatorConfig(
                segment_id="container_app",
                display_name="Container App",
                liveness_interval_seconds=60,
                host_segment=None,
                workload_window_seconds=300,
            ),
        ]
    )
