"""Tests for the NativeLookup facade — wiring of the three fetchers."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from second_brain.spine.audit.native_lookup import NativeLookup


@pytest.mark.asyncio
async def test_facade_dispatches_to_each_fetcher():
    spans_fetcher = AsyncMock(return_value=[{"Name": "GET /x"}])
    exceptions_fetcher = AsyncMock(return_value=[{"ExceptionType": "Boom"}])
    cosmos_fetcher = AsyncMock(return_value=[{"OperationName": "Read"}])

    lookup = NativeLookup(
        spans_fetcher=spans_fetcher,
        exceptions_fetcher=exceptions_fetcher,
        cosmos_fetcher=cosmos_fetcher,
    )

    spans = await lookup.spans("abc-123", time_range_seconds=600)
    exceptions = await lookup.exceptions("abc-123", time_range_seconds=600)
    cosmos_rows = await lookup.cosmos("abc-123", time_range_seconds=600)

    assert spans == [{"Name": "GET /x"}]
    assert exceptions == [{"ExceptionType": "Boom"}]
    assert cosmos_rows == [{"OperationName": "Read"}]

    spans_fetcher.assert_called_once_with(
        correlation_id="abc-123", time_range_seconds=600
    )
    exceptions_fetcher.assert_called_once_with(
        correlation_id="abc-123", time_range_seconds=600
    )
    cosmos_fetcher.assert_called_once_with(
        correlation_id="abc-123", time_range_seconds=600
    )


@pytest.mark.asyncio
async def test_facade_returns_empty_when_lookup_unconfigured():
    """When no fetchers are wired (e.g. logs_client unavailable), return [].

    Lets the audit endpoint stay up even if Log Analytics isn't configured.
    """
    lookup = NativeLookup(
        spans_fetcher=None,
        exceptions_fetcher=None,
        cosmos_fetcher=None,
    )
    assert await lookup.spans("abc", time_range_seconds=600) == []
    assert await lookup.exceptions("abc", time_range_seconds=600) == []
    assert await lookup.cosmos("abc", time_range_seconds=600) == []
