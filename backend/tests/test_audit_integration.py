"""Integration test for the audit endpoint against the deployed backend.

Marked @pytest.mark.integration — skipped by default. Run with:
  uv run pytest backend/tests/test_audit_integration.py -m integration -v

Requires:
  - SPINE_API_KEY in env (or in backend/.env)
  - SPINE_BASE_URL (defaults to https://brain.willmacdonald.com)
"""

from __future__ import annotations

import os

import httpx
import pytest

SPINE_BASE_URL = os.environ.get("SPINE_BASE_URL", "https://brain.willmacdonald.com")
SPINE_API_KEY = os.environ.get("SPINE_API_KEY", "")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sample_capture_returns_well_formed_report():
    """Sample mode returns a structurally-valid AuditReport."""
    if not SPINE_API_KEY:
        pytest.skip("SPINE_API_KEY not set")

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{SPINE_BASE_URL}/api/spine/audit/correlation",
            headers={"Authorization": f"Bearer {SPINE_API_KEY}"},
            json={
                "correlation_kind": "capture",
                "sample_size": 3,
                "time_range_seconds": 86400,
            },
        )
    resp.raise_for_status()
    body = resp.json()

    # Shape assertions only — values reflect live system state.
    assert body["correlation_kind"] == "capture"
    assert body["sample_size_requested"] == 3
    assert "traces" in body
    assert "summary" in body
    assert body["summary"]["overall_verdict"] in {"clean", "warn", "broken"}
    for trace in body["traces"]:
        assert trace["verdict"] in {"clean", "warn", "broken"}
        assert "trace_window" in trace
        assert "native_links" in trace
