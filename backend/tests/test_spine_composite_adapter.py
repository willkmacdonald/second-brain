"""Tests for the composite adapter that combines multiple sources."""

from unittest.mock import AsyncMock

import pytest

from second_brain.spine.adapters.composite import CompositeAdapter


@pytest.mark.asyncio
async def test_composite_returns_combined_schema() -> None:
    a1 = AsyncMock()
    a1.segment_id = "mobile_ui"
    a1.native_url_template = "https://sentry.io"
    a1.fetch_detail.return_value = {
        "schema": "sentry_event",
        "events": [{"id": "e1", "timestamp": "2026-04-14T12:00:00Z"}],
        "native_url": "https://sentry.io",
    }
    a2 = AsyncMock()
    a2.segment_id = "mobile_ui"
    a2.fetch_detail.return_value = {
        "schema": "mobile_telemetry",
        "telemetry_events": [
            {
                "payload": {"operation": "load_inbox"},
                "timestamp": "2026-04-14T12:01:00Z",
            }
        ],
        "native_url": "https://portal.azure.com",
    }

    composite = CompositeAdapter(
        segment_id="mobile_ui",
        sources={"sentry": a1, "telemetry": a2},
        native_url="https://sentry.io",
    )

    result = await composite.fetch_detail()
    assert result["schema"] == "mobile_telemetry_combined"
    assert "sources" in result
    assert "sentry" in result["sources"]
    assert "telemetry" in result["sources"]
    assert result["sources"]["sentry"]["schema"] == "sentry_event"


@pytest.mark.asyncio
async def test_composite_handles_partial_failure() -> None:
    good = AsyncMock()
    good.fetch_detail.return_value = {"schema": "mobile_telemetry", "data": []}
    bad = AsyncMock()
    bad.fetch_detail.side_effect = RuntimeError("Sentry down")

    composite = CompositeAdapter(
        segment_id="mobile_ui",
        sources={"telemetry": good, "sentry": bad},
        native_url="x",
    )
    result = await composite.fetch_detail()
    assert "telemetry" in result["sources"]
    assert "sentry" not in result["sources"]
    assert "sentry" in result["partial_failures"]
