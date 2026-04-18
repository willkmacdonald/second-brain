"""Tests for the mobile telemetry adapter."""

from unittest.mock import AsyncMock

import pytest

from second_brain.spine.adapters.mobile_telemetry import MobileTelemetryAdapter


@pytest.mark.asyncio
async def test_fetch_detail_returns_telemetry_schema() -> None:
    repo = AsyncMock()
    repo.get_recent_events.return_value = []
    adapter = MobileTelemetryAdapter(
        segment_id="mobile_ui",
        repo=repo,
        native_url="https://portal.azure.com/#blade/AppInsightsExtension",
    )
    result = await adapter.fetch_detail()
    assert result["schema"] == "mobile_telemetry"
    assert "telemetry_events" in result


@pytest.mark.asyncio
async def test_fetch_detail_filters_to_segment_workload_failures() -> None:
    repo = AsyncMock()
    repo.get_recent_events.return_value = [
        {
            "event_type": "workload",
            "payload": {"outcome": "failure", "operation": "load_inbox"},
        },
        {
            "event_type": "workload",
            "payload": {"outcome": "success", "operation": "load_inbox"},
        },
        {"event_type": "liveness", "payload": {"instance_id": "i1"}},
    ]
    adapter = MobileTelemetryAdapter(
        segment_id="mobile_ui",
        repo=repo,
        native_url="x",
    )
    result = await adapter.fetch_detail()
    assert len(result["telemetry_events"]) == 1
    assert result["telemetry_events"][0]["payload"]["outcome"] == "failure"
