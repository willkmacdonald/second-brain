"""Integration tests against the deployed Container App."""

import os

import httpx
import pytest

SECOND_BRAIN_URL = os.environ.get("SECOND_BRAIN_URL", "")
SECOND_BRAIN_API_KEY = os.environ.get("SECOND_BRAIN_API_KEY", "")

pytestmark = pytest.mark.skipif(
    not SECOND_BRAIN_URL or not SECOND_BRAIN_API_KEY,
    reason="SECOND_BRAIN_URL and SECOND_BRAIN_API_KEY must be set",
)


@pytest.mark.integration
def test_health_endpoint_reports_foundry_connected() -> None:
    """GET /health on the deployed backend returns foundry: connected."""
    response = httpx.get(
        f"{SECOND_BRAIN_URL}/health",
        headers={"Authorization": f"Bearer {SECOND_BRAIN_API_KEY}"},
        timeout=10.0,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["foundry"] == "connected", f"Unexpected foundry status: {data}"
    assert data["status"] == "ok", f"Unexpected overall status: {data}"
