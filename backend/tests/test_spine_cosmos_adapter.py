"""Tests for the Cosmos diagnostic-logs pull adapter."""

from unittest.mock import AsyncMock

import pytest

from second_brain.spine.adapters.cosmos import CosmosAdapter


@pytest.mark.asyncio
async def test_fetch_detail_returns_cosmos_schema() -> None:
    diag_query = AsyncMock(return_value=[])
    adapter = CosmosAdapter(
        diagnostics_fetcher=diag_query,
        native_url="https://portal.azure.com/#blade/CosmosDB",
    )
    result = await adapter.fetch_detail()
    assert result["schema"] == "azure_monitor_cosmos"
    assert "diagnostic_logs" in result
    assert result["native_url"] == "https://portal.azure.com/#blade/CosmosDB"


@pytest.mark.asyncio
async def test_fetch_detail_with_capture_correlation() -> None:
    diag_query = AsyncMock(
        return_value=[
            {
                "client_request_id": "trace-1",
                "operation_name": "Create",
                "status_code": 201,
            }
        ]
    )
    adapter = CosmosAdapter(
        diagnostics_fetcher=diag_query,
        native_url="x",
    )
    result = await adapter.fetch_detail(
        correlation_kind="capture",
        correlation_id="trace-1",
    )
    diag_query.assert_called_once()
    assert diag_query.call_args.kwargs.get("capture_trace_id") == "trace-1"
    assert result["diagnostic_logs"][0]["client_request_id"] == "trace-1"


@pytest.mark.asyncio
async def test_fetch_detail_without_correlation() -> None:
    diag_query = AsyncMock(return_value=[])
    adapter = CosmosAdapter(
        diagnostics_fetcher=diag_query,
        native_url="x",
    )
    await adapter.fetch_detail(time_range_seconds=7200)
    assert diag_query.call_args.kwargs.get("time_range_seconds") == 7200
    assert "capture_trace_id" not in diag_query.call_args.kwargs
