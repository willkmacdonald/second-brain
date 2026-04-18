"""Tests for the Sentry pull adapter."""

from unittest.mock import AsyncMock

import pytest

from second_brain.spine.adapters.sentry import SentryAdapter


@pytest.mark.asyncio
async def test_fetch_detail_returns_sentry_schema() -> None:
    fetcher = AsyncMock(return_value={"events": [], "issues": []})
    adapter = SentryAdapter(
        segment_id="mobile_ui",
        sentry_fetcher=fetcher,
        native_url_template="https://sentry.io/organizations/test/issues",
        tag_filter={"app_segment": "mobile_ui"},
    )
    result = await adapter.fetch_detail()
    assert result["schema"] == "sentry_event"
    assert "events" in result
    assert "issues" in result


@pytest.mark.asyncio
async def test_fetch_detail_with_capture_correlation_filters_by_tag() -> None:
    fetcher = AsyncMock(return_value={"events": [], "issues": []})
    adapter = SentryAdapter(
        segment_id="mobile_ui",
        sentry_fetcher=fetcher,
        native_url_template="x",
        tag_filter={"app_segment": "mobile_ui"},
    )
    await adapter.fetch_detail(correlation_kind="capture", correlation_id="trace-1")
    fetcher.assert_called_once()
    kwargs = fetcher.call_args.kwargs
    assert kwargs["tag_filter"]["capture_trace_id"] == "trace-1"
    assert kwargs["tag_filter"]["app_segment"] == "mobile_ui"


@pytest.mark.asyncio
async def test_fetch_detail_with_crud_correlation_filters_by_correlation_id() -> None:
    fetcher = AsyncMock(return_value={"events": [], "issues": []})
    adapter = SentryAdapter(
        segment_id="backend_api",
        sentry_fetcher=fetcher,
        native_url_template="x",
        tag_filter={"app_segment": "backend_api"},
    )
    await adapter.fetch_detail(correlation_kind="crud", correlation_id="op-42")
    kwargs = fetcher.call_args.kwargs
    assert kwargs["tag_filter"]["correlation_id"] == "op-42"
    assert kwargs["tag_filter"]["app_segment"] == "backend_api"


@pytest.mark.asyncio
async def test_fetch_detail_without_correlation_uses_base_tag_filter() -> None:
    fetcher = AsyncMock(return_value={"events": [], "issues": []})
    adapter = SentryAdapter(
        segment_id="mobile_ui",
        sentry_fetcher=fetcher,
        native_url_template="x",
        tag_filter={"app_segment": "mobile_ui"},
    )
    await adapter.fetch_detail(time_range_seconds=7200)
    kwargs = fetcher.call_args.kwargs
    assert kwargs["tag_filter"] == {"app_segment": "mobile_ui"}
    assert kwargs["time_range_seconds"] == 7200
    assert "capture_trace_id" not in kwargs["tag_filter"]


@pytest.mark.asyncio
async def test_fetch_detail_base_tag_filter_is_not_mutated() -> None:
    """Correlation tags must not bleed into subsequent calls."""
    fetcher = AsyncMock(return_value={"events": [], "issues": []})
    adapter = SentryAdapter(
        segment_id="mobile_ui",
        sentry_fetcher=fetcher,
        native_url_template="x",
        tag_filter={"app_segment": "mobile_ui"},
    )
    await adapter.fetch_detail(correlation_kind="capture", correlation_id="trace-1")
    await adapter.fetch_detail()
    second_call_kwargs = fetcher.call_args.kwargs
    assert "capture_trace_id" not in second_call_kwargs["tag_filter"]


@pytest.mark.asyncio
async def test_fetch_detail_result_contains_native_url() -> None:
    fetcher = AsyncMock(return_value={"events": [], "issues": []})
    url = "https://sentry.io/organizations/my-org/issues"
    adapter = SentryAdapter(
        segment_id="mobile_ui",
        sentry_fetcher=fetcher,
        native_url_template=url,
        tag_filter={"app_segment": "mobile_ui"},
    )
    result = await adapter.fetch_detail()
    assert result["native_url"] == url


@pytest.mark.asyncio
async def test_fetch_detail_passes_through_events_and_issues() -> None:
    events = [{"id": "evt-1", "message": "TypeError"}]
    issues = [{"id": "iss-1", "title": "Error in capture"}]
    fetcher = AsyncMock(return_value={"events": events, "issues": issues})
    adapter = SentryAdapter(
        segment_id="mobile_ui",
        sentry_fetcher=fetcher,
        native_url_template="x",
        tag_filter={"app_segment": "mobile_ui"},
    )
    result = await adapter.fetch_detail()
    assert result["events"] == events
    assert result["issues"] == issues
