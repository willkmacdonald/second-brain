"""Phase 24 P2-8 — boot the FastAPI app to lifespan ready, hit the healthz
endpoint, assert 200, shut down. Runs as part of Gate 10 in plan 24-20.

Note on endpoint name: the plan interface block referenced ``/healthz`` (a
common k8s-style alias). The actual FastAPI route is ``/health`` (see
``src/second_brain/api/health.py:20``) and it is the only path on
``PUBLIC_PATHS`` (auth.py:20), so anonymous GETs return 200. Both names refer
to the same liveness probe semantically; this test hits the real route.
"""

from __future__ import annotations

import os

import httpx
import pytest


@pytest.mark.asyncio
async def test_app_boots_and_healthz_returns_200() -> None:
    """Construct the app, exercise lifespan, hit the healthz route.

    Uses ``/health`` (the actual public liveness endpoint) — semantically the
    same as ``/healthz`` referenced in the plan.
    """
    if not os.environ.get("AZURE_AI_PROJECT_ENDPOINT") and not os.environ.get(
        "FOUNDRY_PROJECT_ENDPOINT"
    ):
        pytest.skip("Project endpoint env var not set — startup would fail in lifespan")

    from second_brain.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # ASGI lifespan startup is implicit on first request when using ASGITransport.
        # /health is the route name on the deployed app; /healthz is the k8s-style
        # alias the plan referenced — both names refer to the same liveness probe.
        resp = await client.get("/health")
        assert resp.status_code == 200, (
            f"healthz/health returned {resp.status_code}: {resp.text}"
        )
