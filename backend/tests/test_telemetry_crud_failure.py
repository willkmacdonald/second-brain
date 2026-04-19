"""Telemetry endpoint forwards crud_failure to spine."""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from second_brain.api.telemetry import router


@pytest.fixture
def app_with_spine():
    app = FastAPI()
    app.include_router(router)
    app.state.spine_repo = AsyncMock()
    return app


@pytest.mark.asyncio
async def test_crud_failure_records_spine_event(app_with_spine) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app_with_spine),
        base_url="http://test",
    ) as client:
        resp = await client.post(
            "/api/telemetry",
            json={
                "event_type": "crud_failure",
                "message": "Inbox load failed: 500",
                "metadata": {"operation": "load_inbox", "status": 500},
            },
        )
    assert resp.status_code == 204
    # 2 calls: workload failure event + synthetic liveness event
    assert app_with_spine.state.spine_repo.record_event.call_count == 2
    workload_event = app_with_spine.state.spine_repo.record_event.call_args_list[0][0][
        0
    ]
    # SPIKE-MEMO §5.2 — emits now wrap in IngestEvent(root=...).
    assert workload_event.root.segment_id == "mobile_ui"
    assert workload_event.root.event_type == "workload"
    assert workload_event.root.payload.outcome == "failure"
    assert workload_event.root.payload.operation == "load_inbox"
    liveness_event = app_with_spine.state.spine_repo.record_event.call_args_list[1][0][
        0
    ]
    assert liveness_event.root.segment_id == "mobile_ui"
    assert liveness_event.root.event_type == "liveness"


@pytest.mark.asyncio
async def test_crud_failure_routes_errands_to_mobile_capture(
    app_with_spine,
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app_with_spine),
        base_url="http://test",
    ) as client:
        resp = await client.post(
            "/api/telemetry",
            json={
                "event_type": "crud_failure",
                "message": "Delete errand failed",
                "metadata": {"operation": "delete_errand"},
            },
        )
    assert resp.status_code == 204
    workload_event = app_with_spine.state.spine_repo.record_event.call_args_list[0][0][
        0
    ]
    assert workload_event.root.segment_id == "mobile_capture"


@pytest.mark.asyncio
async def test_non_crud_event_does_not_record_spine(
    app_with_spine,
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app_with_spine),
        base_url="http://test",
    ) as client:
        resp = await client.post(
            "/api/telemetry",
            json={
                "event_type": "error",
                "message": "Something went wrong",
            },
        )
    assert resp.status_code == 204
    app_with_spine.state.spine_repo.record_event.assert_not_called()


@pytest.mark.asyncio
async def test_crud_failure_with_no_spine_repo() -> None:
    """When spine_repo is None (spine wiring failed), don't crash."""
    app = FastAPI()
    app.include_router(router)
    app.state.spine_repo = None
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post(
            "/api/telemetry",
            json={
                "event_type": "crud_failure",
                "message": "Inbox load failed: 500",
                "metadata": {"operation": "load_inbox"},
            },
        )
    assert resp.status_code == 204
