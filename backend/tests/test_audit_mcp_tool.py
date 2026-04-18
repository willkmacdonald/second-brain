"""Tests for the audit_correlation MCP tool wrapper."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_audit_correlation_calls_spine_endpoint():
    """The MCP tool POSTs to /api/spine/audit/correlation and returns the body."""
    expected_response = {
        "correlation_kind": "capture",
        "sample_size_requested": 5,
        "sample_size_returned": 1,
        "time_range_seconds": 86400,
        "traces": [],
        "summary": {
            "clean_count": 0,
            "warn_count": 0,
            "broken_count": 0,
            "segments_with_missing_required": {},
            "segments_with_misattribution": {},
            "segments_with_orphans": {},
            "overall_verdict": "clean",
            "headline": "no traces sampled",
        },
        "instrumentation_warning": None,
    }

    with patch("mcp.server._spine_post", new=AsyncMock(return_value=expected_response)):
        # Import inside the patch so the tool sees the patched helper.
        from mcp.server import audit_correlation  # noqa: WPS433

        result = await audit_correlation(
            correlation_kind="capture",
            correlation_id=None,
            sample_size=5,
            time_range_seconds=86400,
            ctx=None,
        )
    assert result == expected_response


@pytest.mark.asyncio
async def test_audit_correlation_returns_error_on_exception():
    with patch(
        "mcp.server._spine_post",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        from mcp.server import audit_correlation  # noqa: WPS433

        result = await audit_correlation(
            correlation_kind="capture",
            correlation_id="abc-1",
            sample_size=5,
            time_range_seconds=86400,
            ctx=None,
        )
    assert result == {"error": True, "message": "boom", "type": "RuntimeError"}
