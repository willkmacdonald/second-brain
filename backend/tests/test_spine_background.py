"""Regression tests for evaluator_loop per-segment isolation invariant.

Design invariant: if one segment's evaluator raises, the remaining segments
in the same tick still run. This is load-bearing for a health monitor whose
job is to report on OTHER segments.
"""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

import pytest

from second_brain.spine.background import evaluator_loop


class _FakeEvaluator:
    """Raises for segments in fail_for; returns a minimal green result otherwise."""

    def __init__(self, fail_for: set[str]) -> None:
        self._fail_for = fail_for
        self.calls: list[str] = []

    async def evaluate(self, segment_id: str) -> SimpleNamespace:
        self.calls.append(segment_id)
        if segment_id in self._fail_for:
            raise RuntimeError(f"boom for {segment_id}")
        return SimpleNamespace(
            status="green",
            headline="all good",
            evaluator_inputs={"workload_total": 0},
        )


class _FakeRepo:
    """Records upserts; other async methods are no-ops."""

    def __init__(self) -> None:
        self.upserts: list[dict] = []

    async def get_segment_state(self, segment_id: str) -> None:
        return None

    async def upsert_segment_state(self, **kwargs) -> None:
        self.upserts.append(kwargs)

    async def record_status_change(self, **kwargs) -> None:
        pass

    async def record_event(self, event) -> None:
        pass


class _FakeRegistry:
    """Returns a fixed list of fake EvaluatorConfig objects by segment_id."""

    def __init__(self, ids: list[str]) -> None:
        self._ids = ids

    def all(self) -> list[SimpleNamespace]:
        return [SimpleNamespace(segment_id=i) for i in self._ids]


async def test_per_segment_isolation_on_evaluator_failure(caplog):
    """If segment A raises, segments B and C are still evaluated and upserted.

    This is the core isolation invariant. The all-or-nothing try/except that
    wrapped the entire for-loop would cause this test to fail because B and C
    would be skipped after A raises.
    """
    evaluator = _FakeEvaluator(fail_for={"a"})
    repo = _FakeRepo()
    registry = _FakeRegistry(["a", "b", "c"])

    caplog.set_level(logging.WARNING, logger="second_brain.spine.background")

    # Run one tick (interval_seconds=3600 ensures it suspends after the sweep)
    task = asyncio.create_task(
        evaluator_loop(evaluator, repo, registry, interval_seconds=3600)
    )
    # Yield enough times for all three segments to complete their awaits
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # B and C must have been upserted despite A failing
    upserted_ids = {u["segment_id"] for u in repo.upserts}
    assert "b" in upserted_ids, f"Expected 'b' in upserted segments, got {upserted_ids}"
    assert "c" in upserted_ids, f"Expected 'c' in upserted segments, got {upserted_ids}"

    # A must NOT have been upserted (it raised before upsert)
    assert "a" not in upserted_ids, (
        f"'a' should not be upserted after its evaluator raised, got {upserted_ids}"
    )

    # A warning must name the failing segment
    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warning_records, (
        "Expected at least one WARNING log entry for the failing segment"
    )
    segment_named = any(
        "segment_id=a" in r.getMessage() or (r.args and "a" in r.args)
        for r in warning_records
    )
    messages = [r.getMessage() for r in warning_records]
    assert segment_named, f"Expected a WARNING log naming segment 'a', got: {messages}"
