"""Tests for Backend API segment adapter (pulls from App Insights)."""

from unittest.mock import AsyncMock

import pytest

from second_brain.spine.adapters.backend_api import BackendApiAdapter


@pytest.mark.asyncio
async def test_fetch_detail_returns_app_insights_schema() -> None:
    failures_query = AsyncMock(return_value=[])
    requests_query = AsyncMock(return_value=[])
    adapter = BackendApiAdapter(
        failures_fetcher=failures_query,
        requests_fetcher=requests_query,
        native_url_template="https://portal.azure.com/#blade/AppInsightsExtension",
    )
    result = await adapter.fetch_detail()
    assert result["schema"] == "azure_monitor_app_insights"
    assert "app_exceptions" in result
    assert "app_requests" in result
    assert (
        result["native_url"] == "https://portal.azure.com/#blade/AppInsightsExtension"
    )


@pytest.mark.asyncio
async def test_fetch_detail_with_correlation_filters() -> None:
    failures_query = AsyncMock(
        return_value=[{"capture_trace_id": "trace-1", "message": "Boom"}]
    )
    requests_query = AsyncMock(return_value=[])
    adapter = BackendApiAdapter(
        failures_fetcher=failures_query,
        requests_fetcher=requests_query,
        native_url_template="x",
    )
    result = await adapter.fetch_detail(
        correlation_kind="capture",
        correlation_id="trace-1",
    )
    failures_query.assert_called_once_with(
        time_range_seconds=3600, capture_trace_id="trace-1"
    )
    requests_query.assert_called_once_with(
        time_range_seconds=3600, capture_trace_id="trace-1"
    )
    assert result["app_exceptions"][0]["capture_trace_id"] == "trace-1"
