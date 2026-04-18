"""Tests for the MCP parity runner."""

from unittest.mock import AsyncMock

import pytest

from second_brain.mcp_parity.runner import run_parity


@pytest.mark.asyncio
async def test_identical_results_match() -> None:
    legacy = AsyncMock(return_value={"errors": [], "count": 0})
    spine = AsyncMock(return_value={"errors": [], "count": 0})
    result = await run_parity(legacy, spine, "recent_errors", {"time_range": "1h"})
    assert result.matched is True
    assert result.legacy_ok and result.spine_ok


@pytest.mark.asyncio
async def test_different_counts_do_not_match() -> None:
    legacy = AsyncMock(return_value={"errors": [], "count": 0})
    spine = AsyncMock(return_value={"errors": [], "count": 1})
    result = await run_parity(legacy, spine, "recent_errors", {"time_range": "1h"})
    assert result.matched is False
    assert "value mismatch" in result.diff_summary


@pytest.mark.asyncio
async def test_legacy_failure_only_recorded() -> None:
    legacy = AsyncMock(side_effect=RuntimeError("kql failed"))
    spine = AsyncMock(return_value={"errors": [], "count": 0})
    result = await run_parity(legacy, spine, "recent_errors", {})
    assert result.legacy_ok is False
    assert result.spine_ok is True
    assert result.matched is False


@pytest.mark.asyncio
async def test_timestamps_normalized_out_of_comparison() -> None:
    legacy = AsyncMock(
        return_value={"timestamp": "2026-04-14T12:00:00Z", "data": [1, 2, 3]}
    )
    spine = AsyncMock(
        return_value={"timestamp": "2026-04-14T12:00:01Z", "data": [1, 2, 3]}
    )
    result = await run_parity(legacy, spine, "x", {})
    assert result.matched is True
