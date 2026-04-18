"""Tests for the audit native-lookup KQL helpers (parameterization, parsing)."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from azure.monitor.query import LogsQueryStatus

from second_brain.observability.queries import (
    fetch_audit_cosmos_diagnostics_for_correlation,
    fetch_audit_exceptions_for_correlation,
    fetch_audit_spans_for_correlation,
)


def _mock_response(rows: list[dict], columns: list[str]):
    """Return a fake LogsQueryResult-shaped object with one table."""
    table = type(
        "T",
        (),
        {
            "columns": columns,
            "rows": [tuple(r.get(c) for c in columns) for r in rows],
        },
    )()
    return type(
        "R",
        (),
        {
            "status": LogsQueryStatus.SUCCESS,
            "tables": [table],
            "partial_data": None,
            "partial_error": None,
        },
    )()


@pytest.mark.asyncio
async def test_fetch_audit_spans_returns_dicts():
    client = AsyncMock()
    client.query_workspace.return_value = _mock_response(
        rows=[
            {
                "timestamp": "2026-04-18T12:00:00Z",
                "Name": "POST /api/capture",
                "Component": "backend_api",
                "DurationMs": 123.4,
                "ResultCode": "200",
                "CorrelationId": "abc-123",
                "CorrelationKind": "capture",
            }
        ],
        columns=[
            "timestamp",
            "Name",
            "Component",
            "DurationMs",
            "ResultCode",
            "CorrelationId",
            "CorrelationKind",
        ],
    )
    spans = await fetch_audit_spans_for_correlation(
        client,
        workspace_id="ws-123",
        correlation_id="abc-123",
        time_range_seconds=3600,
    )
    assert spans == [
        {
            "timestamp": "2026-04-18T12:00:00Z",
            "Name": "POST /api/capture",
            "Component": "backend_api",
            "DurationMs": 123.4,
            "ResultCode": "200",
            "CorrelationId": "abc-123",
            "CorrelationKind": "capture",
        }
    ]
    sent_query = client.query_workspace.call_args.kwargs["query"]
    assert "abc-123" in sent_query


@pytest.mark.asyncio
async def test_fetch_audit_spans_empty_table_returns_empty_list():
    client = AsyncMock()
    client.query_workspace.return_value = _mock_response(rows=[], columns=["timestamp"])
    assert (
        await fetch_audit_spans_for_correlation(
            client,
            workspace_id="ws-123",
            correlation_id="abc-123",
            time_range_seconds=3600,
        )
        == []
    )


@pytest.mark.asyncio
async def test_fetch_audit_exceptions_round_trip():
    client = AsyncMock()
    client.query_workspace.return_value = _mock_response(
        rows=[
            {
                "timestamp": "2026-04-18T12:00:05Z",
                "Component": "classifier",
                "ExceptionType": "HttpResponseError",
                "OuterMessage": "boom",
                "CorrelationId": "abc-123",
            }
        ],
        columns=[
            "timestamp",
            "Component",
            "ExceptionType",
            "OuterMessage",
            "CorrelationId",
        ],
    )
    exceptions = await fetch_audit_exceptions_for_correlation(
        client,
        workspace_id="ws-123",
        correlation_id="abc-123",
        time_range_seconds=3600,
    )
    assert exceptions[0]["ExceptionType"] == "HttpResponseError"


@pytest.mark.asyncio
async def test_fetch_audit_cosmos_diagnostics_round_trip():
    client = AsyncMock()
    client.query_workspace.return_value = _mock_response(
        rows=[
            {
                "timestamp": "2026-04-18T12:00:00Z",
                "OperationName": "Read",
                "statusCode_s": "200",
                "duration_s": "10.2",
                "activityId_g": "abc-123",
            }
        ],
        columns=[
            "timestamp",
            "OperationName",
            "statusCode_s",
            "duration_s",
            "activityId_g",
        ],
    )
    rows = await fetch_audit_cosmos_diagnostics_for_correlation(
        client,
        workspace_id="ws-123",
        correlation_id="abc-123",
        time_range_seconds=3600,
    )
    assert rows[0]["activityId_g"] == "abc-123"


@pytest.mark.asyncio
async def test_timespan_passed_to_client():
    """Verify the timespan derived from time_range_seconds reaches the client."""
    client = AsyncMock()
    client.query_workspace.return_value = _mock_response(rows=[], columns=["timestamp"])
    await fetch_audit_spans_for_correlation(
        client,
        workspace_id="ws-123",
        correlation_id="abc-123",
        time_range_seconds=600,
    )
    timespan = client.query_workspace.call_args.kwargs["timespan"]
    assert timespan == timedelta(seconds=600)
