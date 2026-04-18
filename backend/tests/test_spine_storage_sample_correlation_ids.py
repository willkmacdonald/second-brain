"""Tests for SpineRepository.get_recent_correlation_ids."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from second_brain.spine.storage import SpineRepository


def _async_iter(items):
    async def _gen():
        for i in items:
            yield i

    return _gen()


@pytest.mark.asyncio
async def test_returns_unique_recent_ids_in_descending_order():
    correlation = MagicMock()
    correlation.query_items = MagicMock(
        return_value=_async_iter(
            [
                {
                    "correlation_id": "id-1",
                    "timestamp": "2026-04-18T12:00:00+00:00",
                },
                {
                    "correlation_id": "id-2",
                    "timestamp": "2026-04-18T12:01:00+00:00",
                },
                {
                    "correlation_id": "id-1",  # duplicate from a different segment
                    "timestamp": "2026-04-18T12:02:00+00:00",
                },
            ]
        )
    )

    repo = SpineRepository(
        events_container=MagicMock(),
        segment_state_container=MagicMock(),
        status_history_container=MagicMock(),
        correlation_container=correlation,
    )

    ids = await repo.get_recent_correlation_ids(
        kind="capture", time_range_seconds=86400, limit=10
    )

    # Most recent first, deduplicated, kind-filtered (caller passes kind).
    assert ids == ["id-1", "id-2"]


@pytest.mark.asyncio
async def test_respects_limit():
    rows = [
        {
            "correlation_id": f"id-{i}",
            "timestamp": f"2026-04-18T12:{i:02d}:00+00:00",
        }
        for i in range(10)
    ]
    correlation = MagicMock()
    correlation.query_items = MagicMock(return_value=_async_iter(rows))

    repo = SpineRepository(
        events_container=MagicMock(),
        segment_state_container=MagicMock(),
        status_history_container=MagicMock(),
        correlation_container=correlation,
    )

    ids = await repo.get_recent_correlation_ids(
        kind="capture", time_range_seconds=86400, limit=3
    )
    assert len(ids) == 3
    assert (
        ids[0] == "id-0"
    )  # most recent first (rows fed in ascending order, first seen wins)


@pytest.mark.asyncio
async def test_query_uses_kind_and_cutoff():
    correlation = MagicMock()
    correlation.query_items = MagicMock(return_value=_async_iter([]))

    repo = SpineRepository(
        events_container=MagicMock(),
        segment_state_container=MagicMock(),
        status_history_container=MagicMock(),
        correlation_container=correlation,
    )

    await repo.get_recent_correlation_ids(
        kind="thread", time_range_seconds=3600, limit=5
    )

    call = correlation.query_items.call_args
    parameters = {p["name"]: p["value"] for p in call.kwargs["parameters"]}
    assert parameters["@kind"] == "thread"
    assert "@cutoff" in parameters
