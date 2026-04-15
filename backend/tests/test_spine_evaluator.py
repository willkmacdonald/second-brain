"""Tests for the status evaluator."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from second_brain.spine.evaluator import StatusEvaluator
from second_brain.spine.registry import EvaluatorConfig, SegmentRegistry


def _cfg(**overrides) -> EvaluatorConfig:
    base = dict(
        segment_id="seg1",
        liveness_interval_seconds=30,
        host_segment=None,
        workload_window_seconds=300,
        yellow_thresholds={"workload_failure_rate": 0.10},
        red_thresholds={"workload_failure_rate": 0.50, "consecutive_failures": 3},
    )
    base.update(overrides)
    return EvaluatorConfig(**base)


def _liveness(timestamp: datetime) -> dict:
    return {
        "event_type": "liveness",
        "timestamp": timestamp.isoformat(),
        "payload": {"instance_id": "i1"},
    }


def _workload(
    timestamp: datetime, outcome: str, error_class: str | None = None
) -> dict:
    return {
        "event_type": "workload",
        "timestamp": timestamp.isoformat(),
        "payload": {
            "operation": "op",
            "outcome": outcome,
            "duration_ms": 100,
            "error_class": error_class,
        },
    }


def _readiness(timestamp: datetime, all_ok: bool = True) -> dict:
    return {
        "event_type": "readiness",
        "timestamp": timestamp.isoformat(),
        "payload": {
            "checks": [{"name": "dep1", "status": "ok" if all_ok else "failing"}],
        },
    }


@pytest.mark.asyncio
async def test_no_events_returns_stale() -> None:
    repo = AsyncMock()
    repo.get_recent_events.return_value = []
    registry = SegmentRegistry([_cfg()])
    evaluator = StatusEvaluator(
        repo=repo, registry=registry, now=lambda: datetime.now(UTC)
    )
    result = await evaluator.evaluate("seg1")
    assert result.status == "stale"


@pytest.mark.asyncio
async def test_recent_liveness_only_returns_green() -> None:
    now = datetime(2026, 4, 14, 12, 0, tzinfo=UTC)
    repo = AsyncMock()
    repo.get_recent_events.return_value = [_liveness(now - timedelta(seconds=10))]
    registry = SegmentRegistry([_cfg()])
    evaluator = StatusEvaluator(repo=repo, registry=registry, now=lambda: now)
    result = await evaluator.evaluate("seg1")
    assert result.status == "green"


@pytest.mark.asyncio
async def test_workload_failure_rate_above_yellow_threshold_returns_yellow() -> None:
    now = datetime(2026, 4, 14, 12, 0, tzinfo=UTC)
    repo = AsyncMock()
    events = [_liveness(now - timedelta(seconds=10))]
    # 11% failure rate (1 fail in 9)
    events.extend([_workload(now - timedelta(seconds=60), "success") for _ in range(8)])
    events.append(_workload(now - timedelta(seconds=30), "failure", "Boom"))
    repo.get_recent_events.return_value = events
    registry = SegmentRegistry([_cfg()])
    evaluator = StatusEvaluator(repo=repo, registry=registry, now=lambda: now)
    result = await evaluator.evaluate("seg1")
    assert result.status == "yellow"


@pytest.mark.asyncio
async def test_workload_failure_rate_above_red_threshold_returns_red() -> None:
    now = datetime(2026, 4, 14, 12, 0, tzinfo=UTC)
    repo = AsyncMock()
    events = [_liveness(now - timedelta(seconds=10))]
    # 60% failure rate
    events.extend([_workload(now - timedelta(seconds=60), "success") for _ in range(4)])
    events.extend(
        [_workload(now - timedelta(seconds=30), "failure", "Boom") for _ in range(6)]
    )
    repo.get_recent_events.return_value = events
    registry = SegmentRegistry([_cfg()])
    evaluator = StatusEvaluator(repo=repo, registry=registry, now=lambda: now)
    result = await evaluator.evaluate("seg1")
    assert result.status == "red"


@pytest.mark.asyncio
async def test_three_consecutive_failures_returns_red() -> None:
    now = datetime(2026, 4, 14, 12, 0, tzinfo=UTC)
    repo = AsyncMock()
    events = [_liveness(now - timedelta(seconds=10))]
    # Most recent 3 are all failures (highest priority over rate)
    events.extend(
        [_workload(now - timedelta(seconds=300 - i), "success") for i in range(7)]
    )
    events.extend(
        [
            _workload(now - timedelta(seconds=30), "failure", "Boom"),
            _workload(now - timedelta(seconds=20), "failure", "Boom"),
            _workload(now - timedelta(seconds=10), "failure", "Boom"),
        ]
    )
    repo.get_recent_events.return_value = events
    registry = SegmentRegistry([_cfg()])
    evaluator = StatusEvaluator(repo=repo, registry=registry, now=lambda: now)
    result = await evaluator.evaluate("seg1")
    assert result.status == "red"


@pytest.mark.asyncio
async def test_readiness_failure_promotes_to_yellow() -> None:
    now = datetime(2026, 4, 14, 12, 0, tzinfo=UTC)
    repo = AsyncMock()
    repo.get_recent_events.return_value = [
        _liveness(now - timedelta(seconds=10)),
        _readiness(now - timedelta(seconds=20), all_ok=False),
    ]
    registry = SegmentRegistry([_cfg(yellow_thresholds={"any_readiness_failed": True})])
    evaluator = StatusEvaluator(repo=repo, registry=registry, now=lambda: now)
    result = await evaluator.evaluate("seg1")
    assert result.status == "yellow"


@pytest.mark.asyncio
async def test_freshness_seconds_reflects_most_recent_event() -> None:
    now = datetime(2026, 4, 14, 12, 0, tzinfo=UTC)
    repo = AsyncMock()
    repo.get_recent_events.return_value = [_liveness(now - timedelta(seconds=10))]
    registry = SegmentRegistry([_cfg()])
    evaluator = StatusEvaluator(repo=repo, registry=registry, now=lambda: now)
    result = await evaluator.evaluate("seg1")
    assert result.freshness_seconds == 10


@pytest.mark.asyncio
async def test_red_headline_uses_configured_consecutive_threshold_not_hardcoded() -> (
    None
):
    # The red headline must use the configured consecutive_failures threshold,
    # not a hardcoded constant. Config with threshold=2 must surface the
    # consecutive-failure headline on 2 consecutive failures, not fall through
    # to the rate message.
    now = datetime(2026, 4, 14, 12, 0, tzinfo=UTC)
    repo = AsyncMock()
    events = [_liveness(now - timedelta(seconds=10))]
    events.append(_workload(now - timedelta(seconds=40), "success"))
    events.append(_workload(now - timedelta(seconds=20), "failure", "Boom"))
    events.append(_workload(now - timedelta(seconds=10), "failure", "Boom"))
    repo.get_recent_events.return_value = events
    registry = SegmentRegistry([_cfg(red_thresholds={"consecutive_failures": 2})])
    evaluator = StatusEvaluator(repo=repo, registry=registry, now=lambda: now)
    result = await evaluator.evaluate("seg1")
    assert result.status == "red"
    assert result.headline == "2 consecutive failures"


@pytest.mark.asyncio
async def test_green_headline_uses_configured_window_not_hardcoded_5min() -> None:
    # The green headline must reflect cfg.workload_window_seconds, not a
    # hardcoded "5min". A 60-second window must display "1min".
    now = datetime(2026, 4, 14, 12, 0, tzinfo=UTC)
    repo = AsyncMock()
    repo.get_recent_events.return_value = [
        _liveness(now - timedelta(seconds=10)),
        _workload(now - timedelta(seconds=20), "success"),
    ]
    # 60s window requires liveness_interval=15 to satisfy stale-window invariant
    registry = SegmentRegistry(
        [_cfg(workload_window_seconds=60, liveness_interval_seconds=15)]
    )
    evaluator = StatusEvaluator(repo=repo, registry=registry, now=lambda: now)
    result = await evaluator.evaluate("seg1")
    assert result.status == "green"
    assert "1min" in result.headline
    assert "5min" not in result.headline


def test_exceeds_bool_threshold_does_not_fall_through_to_numeric_branch() -> None:
    # Regression: bool is a subclass of int in Python. If the `_exceeds` bool
    # and numeric branches are combined with `and/or` (instead of if/elif), a
    # bool threshold of False would still match truthy values via the numeric
    # `value >= threshold` path (because `True >= False` is True). The bool
    # branch MUST short-circuit the numeric branch for bool thresholds.
    #
    # threshold=False, value=True: MUST return False (bool equality fails)
    assert StatusEvaluator._exceeds({"flag": False}, {"flag": True}) is False
    # threshold=True, value=False: MUST return False
    assert StatusEvaluator._exceeds({"flag": True}, {"flag": False}) is False
    # Sanity: matching bool equality returns True
    assert StatusEvaluator._exceeds({"flag": True}, {"flag": True}) is True
    # Sanity: numeric threshold still works alongside bool thresholds
    assert (
        StatusEvaluator._exceeds(
            {"flag": True, "rate": 0.5}, {"flag": False, "rate": 0.6}
        )
        is True
    )
