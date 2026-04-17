"""Tests for the Foundry-agent pull adapter (joins by run_id/thread_id)."""

from unittest.mock import AsyncMock

import pytest

from second_brain.spine.adapters.foundry_agent import FoundryAgentAdapter


@pytest.mark.asyncio
async def test_fetch_detail_returns_foundry_run_schema() -> None:
    spans_query = AsyncMock(return_value=[])
    adapter = FoundryAgentAdapter(
        segment_id="classifier",
        agent_id="asst_1",
        agent_name="Classifier",
        spans_fetcher=spans_query,
        native_url_template="https://ai.azure.com/build/agents/asst_1",
    )
    result = await adapter.fetch_detail()
    assert result["schema"] == "foundry_run"
    assert result["agent_id"] == "asst_1"
    assert result["agent_name"] == "Classifier"
    assert "agent_runs" in result
    assert result["native_url"] == "https://ai.azure.com/build/agents/asst_1"


@pytest.mark.asyncio
async def test_fetch_detail_with_thread_correlation_filters_spans() -> None:
    spans_query = AsyncMock(
        return_value=[
            {
                "thread_id": "thr-1",
                "run_id": "run-1",
                "duration_ms": 1234,
                "outcome": "success",
            }
        ]
    )
    adapter = FoundryAgentAdapter(
        segment_id="investigation",
        agent_id="asst_2",
        agent_name="Investigation",
        spans_fetcher=spans_query,
        native_url_template="https://ai.azure.com/build/agents/asst_2",
    )
    result = await adapter.fetch_detail(
        correlation_kind="thread",
        correlation_id="thr-1",
    )
    spans_query.assert_called_once()
    call_kwargs = spans_query.call_args.kwargs
    assert call_kwargs.get("thread_id") == "thr-1"
    assert len(result["agent_runs"]) == 1


@pytest.mark.asyncio
async def test_fetch_detail_with_capture_correlation_passes_capture_filter() -> None:
    spans_query = AsyncMock(return_value=[])
    adapter = FoundryAgentAdapter(
        segment_id="classifier",
        agent_id="asst_1",
        agent_name="Classifier",
        spans_fetcher=spans_query,
        native_url_template="x",
    )
    await adapter.fetch_detail(
        correlation_kind="capture",
        correlation_id="trace-1",
    )
    call_kwargs = spans_query.call_args.kwargs
    assert call_kwargs.get("capture_trace_id") == "trace-1"
