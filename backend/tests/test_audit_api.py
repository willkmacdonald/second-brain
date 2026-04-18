"""Tests for POST /api/spine/audit/correlation."""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from second_brain.spine.api import build_spine_router
from second_brain.spine.auth import spine_auth

TEST_API_KEY = "test-api-key-12345"


def _make_app(auditor):
    repo = AsyncMock()
    evaluator = AsyncMock()
    adapter_registry = AsyncMock()
    segment_registry = AsyncMock()

    app = FastAPI()
    app.state.api_key = TEST_API_KEY
    router = build_spine_router(
        repo=repo,
        evaluator=evaluator,
        adapter_registry=adapter_registry,
        segment_registry=segment_registry,
        auth_dependency=spine_auth,
        auditor=auditor,
    )
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_audit_endpoint_requires_auth():
    auditor = AsyncMock()
    app = _make_app(auditor)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post(
            "/api/spine/audit/correlation",
            json={"correlation_kind": "capture", "correlation_id": "abc-1"},
        )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_audit_endpoint_single_id_calls_auditor_audit():
    from datetime import UTC, datetime

    from second_brain.spine.audit.models import (
        AuditReport,
        AuditSummary,
        TimeWindow,
        TraceAudit,
    )

    trace_audit = TraceAudit(
        correlation_kind="capture",
        correlation_id="abc-1",
        verdict="clean",
        headline="all good",
        trace_window=TimeWindow(
            start=datetime(2026, 4, 18, tzinfo=UTC),
            end=datetime(2026, 4, 18, tzinfo=UTC),
        ),
    )
    auditor = AsyncMock()
    auditor.audit.return_value = trace_audit
    auditor.audit_sample.return_value = AuditReport(
        correlation_kind="capture",
        sample_size_requested=1,
        sample_size_returned=1,
        time_range_seconds=86400,
        traces=[trace_audit],
        summary=AuditSummary(
            clean_count=1,
            warn_count=0,
            broken_count=0,
            segments_with_missing_required={},
            segments_with_misattribution={},
            segments_with_orphans={},
            overall_verdict="clean",
            headline="all 1 traces clean",
        ),
    )

    app = _make_app(auditor)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post(
            "/api/spine/audit/correlation",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "correlation_kind": "capture",
                "correlation_id": "abc-1",
                "time_range_seconds": 86400,
            },
        )

    assert r.status_code == 200
    auditor.audit.assert_called_once_with(
        kind="capture",
        correlation_id="abc-1",
        time_range_seconds=86400,
    )
    auditor.audit_sample.assert_not_called()
    body = r.json()
    assert body["sample_size_returned"] == 1
    assert body["traces"][0]["correlation_id"] == "abc-1"


@pytest.mark.asyncio
async def test_audit_endpoint_sample_mode_calls_audit_sample():
    from second_brain.spine.audit.models import AuditReport, AuditSummary

    auditor = AsyncMock()
    auditor.audit_sample.return_value = AuditReport(
        correlation_kind="capture",
        sample_size_requested=5,
        sample_size_returned=0,
        time_range_seconds=86400,
        traces=[],
        summary=AuditSummary(
            clean_count=0,
            warn_count=0,
            broken_count=0,
            segments_with_missing_required={},
            segments_with_misattribution={},
            segments_with_orphans={},
            overall_verdict="clean",
            headline="no traces sampled",
        ),
    )

    app = _make_app(auditor)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post(
            "/api/spine/audit/correlation",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "correlation_kind": "capture",
                "sample_size": 5,
            },
        )

    assert r.status_code == 200
    auditor.audit_sample.assert_called_once_with(
        kind="capture",
        sample_size=5,
        time_range_seconds=86400,
    )
    auditor.audit.assert_not_called()


@pytest.mark.asyncio
async def test_audit_endpoint_validates_sample_size_bounds():
    auditor = AsyncMock()
    app = _make_app(auditor)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post(
            "/api/spine/audit/correlation",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={"correlation_kind": "capture", "sample_size": 100},
        )
    assert r.status_code == 422
