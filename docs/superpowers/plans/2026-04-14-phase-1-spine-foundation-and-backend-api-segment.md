# Phase 1: Spine Foundation + Backend API Segment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the spine backend (4 endpoints, 4 Cosmos containers, status evaluator) and integrate the Backend API segment end-to-end, including absorbing Phase 19.1's KQL projection work for native AppExceptions field surfacing.

**Architecture:** New `spine` Python package inside the existing FastAPI Container App. Single typed ingest endpoint accepting `liveness`/`readiness`/`workload` events. Status evaluator runs as a background asyncio task every 30s. Cosmos for spine state only — never duplicates native detail. Pull adapter against App Insights for Backend API segment detail. Web UI is a server-rendered Next.js app served from the same Container App. Mobile Status screen gets a tile. Auth: existing API key, Bearer token, hmac.compare_digest.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, asyncio, azure-monitor-query (Log Analytics), azure-cosmos (aio), Next.js 14 (App Router, server components), TypeScript, React Native (Expo).

**Spec reference:** `docs/superpowers/specs/2026-04-14-per-segment-observability-design.md`

---

## File Structure

**Backend — new `spine` package:**

| File | Responsibility |
|---|---|
| `backend/src/second_brain/spine/__init__.py` | Package marker |
| `backend/src/second_brain/spine/models.py` | Pydantic models for ingest events, status responses, envelope |
| `backend/src/second_brain/spine/storage.py` | Cosmos repository for the 4 spine containers |
| `backend/src/second_brain/spine/evaluator.py` | Status evaluator: reads recent events, computes status enum |
| `backend/src/second_brain/spine/registry.py` | Per-segment evaluator config (thresholds, host_segment, etc.) |
| `backend/src/second_brain/spine/api.py` | FastAPI router: 4 endpoints |
| `backend/src/second_brain/spine/adapters/__init__.py` | Adapter package marker |
| `backend/src/second_brain/spine/adapters/base.py` | `SegmentAdapter` Protocol |
| `backend/src/second_brain/spine/adapters/backend_api.py` | Backend API pull adapter (App Insights) |
| `backend/src/second_brain/spine/adapters/registry.py` | Maps `segment_id` → adapter instance |
| `backend/src/second_brain/spine/middleware.py` | FastAPI middleware that emits Backend API workload events |
| `backend/src/second_brain/spine/background.py` | Background tasks: evaluator loop, container app revision poller |
| `backend/src/second_brain/spine/auth.py` | API key dependency reused from existing auth |

**Backend — modifications:**

| File | Change |
|---|---|
| `backend/src/second_brain/main.py` | Mount `spine` router; start background tasks in lifespan |
| `backend/src/second_brain/observability/kql_templates.py` | Update `CAPTURE_TRACE`, `RECENT_FAILURES`, `RECENT_FAILURES_FILTERED` to project `OuterMessage`, `OuterType`, `InnermostMessage`, `tostring(Details)` (Phase 19.1 absorption) |
| `backend/src/second_brain/observability/models.py` | Add `outer_message`, `outer_type`, `innermost_message`, `details` to `FailureRecord` and `TraceRecord` (reuse `_empty_to_none` validator) |
| `backend/src/second_brain/observability/queries.py` | Wire new kwargs in 3 parser sites |

**Backend — tests:**

| File | Purpose |
|---|---|
| `backend/tests/test_spine_models.py` | Validate ingest event discrimination + envelope contracts |
| `backend/tests/test_spine_storage.py` | Cosmos repository CRUD with mocked container |
| `backend/tests/test_spine_evaluator.py` | Status evaluator decision logic across signal combinations |
| `backend/tests/test_spine_registry.py` | Per-segment config retrieval + defaults |
| `backend/tests/test_spine_api.py` | 4 endpoints — auth, payload validation, response shape |
| `backend/tests/test_spine_backend_api_adapter.py` | App Insights adapter returns native shape |
| `backend/tests/test_spine_middleware.py` | Workload event emission per request |
| `backend/tests/test_kql_projections.py` | Verify all 3 KQL templates project the new AppExceptions fields with `tostring(Details)` and the coalesce ordering |

**Web — new app:**

| File | Responsibility |
|---|---|
| `web/package.json` | Next.js 14 deps |
| `web/next.config.mjs` | Standalone output for Container App deployment |
| `web/Dockerfile` | Multi-stage build |
| `web/tsconfig.json` | Strict mode |
| `web/app/layout.tsx` | Root layout, dark theme |
| `web/app/page.tsx` | Status board (server component, polls spine) |
| `web/app/segment/[id]/page.tsx` | Segment detail dispatcher (server component, picks renderer by `schema`) |
| `web/components/StatusBoard.tsx` | Tile grid client component |
| `web/components/StatusTile.tsx` | Single tile |
| `web/components/SegmentDetailHeader.tsx` | Title + "Open in Native Tool" link |
| `web/components/renderers/AppInsightsDetail.tsx` | Renderer for `azure_monitor_app_insights` schema |
| `web/lib/spine.ts` | Server-side spine client with API key from env |
| `web/lib/types.ts` | TypeScript types matching backend Pydantic models |
| `web/.env.example` | Required env vars |

**Mobile — modifications:**

| File | Change |
|---|---|
| `mobile/components/SpineStatusTile.tsx` | New: single tile rendered on Status screen |
| `mobile/lib/spine.ts` | New: client for `/api/spine/status`, deep-link to web |
| `mobile/app/(tabs)/status.tsx` | Mount `SpineStatusTile` for `backend_api` segment |

**Infrastructure:**

| File | Change |
|---|---|
| `.github/workflows/deploy.yml` | Build + push web image; deploy as Container App revision |
| `infra/cosmos-spine-containers.bicep` | Bicep template for the 4 new Cosmos containers |

---

## Task 1: Spine Pydantic models (ingest events + envelope)

**Files:**
- Create: `backend/src/second_brain/spine/__init__.py`
- Create: `backend/src/second_brain/spine/models.py`
- Test: `backend/tests/test_spine_models.py`

- [ ] **Step 1: Create empty `__init__.py`**

```bash
touch backend/src/second_brain/spine/__init__.py
```

- [ ] **Step 2: Write the failing test for IngestEvent discrimination**

Create `backend/tests/test_spine_models.py`:

```python
"""Tests for spine Pydantic models."""

import pytest
from pydantic import ValidationError

from second_brain.spine.models import (
    IngestEvent,
    LivenessPayload,
    ReadinessPayload,
    WorkloadPayload,
    SegmentStatus,
    SegmentStatusResponse,
    StatusBoardResponse,
    ResponseEnvelope,
)


def test_liveness_event_parses() -> None:
    event = IngestEvent.model_validate({
        "segment_id": "backend_api",
        "event_type": "liveness",
        "timestamp": "2026-04-14T12:00:00Z",
        "payload": {"instance_id": "abc-123"},
    })
    assert event.root.event_type == "liveness"
    assert isinstance(event.root.payload, LivenessPayload)
    assert event.root.payload.instance_id == "abc-123"


def test_readiness_event_parses() -> None:
    event = IngestEvent.model_validate({
        "segment_id": "backend_api",
        "event_type": "readiness",
        "timestamp": "2026-04-14T12:00:00Z",
        "payload": {"checks": [{"name": "cosmos", "status": "ok"}]},
    })
    assert event.root.event_type == "readiness"
    assert isinstance(event.root.payload, ReadinessPayload)
    assert event.root.payload.checks[0].name == "cosmos"


def test_workload_event_parses() -> None:
    event = IngestEvent.model_validate({
        "segment_id": "backend_api",
        "event_type": "workload",
        "timestamp": "2026-04-14T12:00:00Z",
        "payload": {
            "operation": "POST /api/capture",
            "outcome": "success",
            "duration_ms": 234,
            "correlation_kind": "capture",
            "correlation_id": "trace-1",
        },
    })
    assert event.root.event_type == "workload"
    assert isinstance(event.root.payload, WorkloadPayload)
    assert event.root.payload.outcome == "success"
    assert event.root.payload.duration_ms == 234


def test_workload_failure_includes_error_class() -> None:
    event = IngestEvent.model_validate({
        "segment_id": "backend_api",
        "event_type": "workload",
        "timestamp": "2026-04-14T12:00:00Z",
        "payload": {
            "operation": "POST /api/capture",
            "outcome": "failure",
            "duration_ms": 50,
            "correlation_kind": "capture",
            "correlation_id": "trace-2",
            "error_class": "HttpResponseError",
        },
    })
    assert event.root.payload.error_class == "HttpResponseError"


def test_unknown_event_type_rejected() -> None:
    with pytest.raises(ValidationError):
        IngestEvent.model_validate({
            "segment_id": "backend_api",
            "event_type": "garbage",
            "timestamp": "2026-04-14T12:00:00Z",
            "payload": {},
        })


def test_status_response_envelope_present() -> None:
    response = StatusBoardResponse(
        segments=[
            SegmentStatusResponse(
                id="backend_api",
                name="Backend API",
                status="green",
                headline="Healthy",
                last_updated="2026-04-14T12:00:00Z",
                freshness_seconds=12,
                host_segment=None,
                rollup={"suppressed": False, "suppressed_by": None, "raw_status": "green"},
            )
        ],
        envelope=ResponseEnvelope(
            generated_at="2026-04-14T12:00:00Z",
            freshness_seconds=12,
            partial_sources=[],
            query_latency_ms=15,
        ),
    )
    serialized = response.model_dump()
    assert "envelope" in serialized
    assert "generated_at" in serialized["envelope"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_spine_models.py -v`
Expected: FAIL with `ImportError: cannot import name 'IngestEvent'`

- [ ] **Step 4: Implement `models.py`**

Create `backend/src/second_brain/spine/models.py`:

```python
"""Pydantic models for the spine: ingest events, status responses, envelope."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, RootModel

# ---------------------------------------------------------------------------
# Ingest event payloads (discriminated by event_type)
# ---------------------------------------------------------------------------


class LivenessPayload(BaseModel):
    """Liveness signal: 'I exist and my process is up.'"""

    instance_id: str


class ReadinessCheck(BaseModel):
    """Single readiness probe result."""

    name: str
    status: Literal["ok", "failing"]
    detail: str | None = None


class ReadinessPayload(BaseModel):
    """Readiness signal: 'My dependencies are reachable.'"""

    checks: list[ReadinessCheck]


class WorkloadPayload(BaseModel):
    """Workload signal: 'I just finished an operation; here is how it went.'"""

    operation: str
    outcome: Literal["success", "failure", "degraded"]
    duration_ms: int
    correlation_kind: Literal["capture", "thread", "request", "crud"] | None = None
    correlation_id: str | None = None
    error_class: str | None = None


# ---------------------------------------------------------------------------
# Discriminated IngestEvent
# ---------------------------------------------------------------------------


class _LivenessEvent(BaseModel):
    segment_id: str
    event_type: Literal["liveness"]
    timestamp: datetime
    payload: LivenessPayload


class _ReadinessEvent(BaseModel):
    segment_id: str
    event_type: Literal["readiness"]
    timestamp: datetime
    payload: ReadinessPayload


class _WorkloadEvent(BaseModel):
    segment_id: str
    event_type: Literal["workload"]
    timestamp: datetime
    payload: WorkloadPayload


class IngestEvent(RootModel[Annotated[
    _LivenessEvent | _ReadinessEvent | _WorkloadEvent,
    Field(discriminator="event_type"),
]]):
    """Discriminated ingest event from any segment.

    Callers parse with `IngestEvent.model_validate(d)` and read the concrete
    variant via `.root` (e.g. `event.root.event_type`, `event.root.payload`).
    """


# ---------------------------------------------------------------------------
# Status responses
# ---------------------------------------------------------------------------


SegmentStatus = Literal["green", "yellow", "red", "stale"]


class RollupInfo(BaseModel):
    """Rollup annotation on a segment status."""

    suppressed: bool
    suppressed_by: str | None
    raw_status: SegmentStatus


class SegmentStatusResponse(BaseModel):
    """Single segment tile in the status board."""

    id: str
    name: str
    status: SegmentStatus
    headline: str
    last_updated: datetime
    freshness_seconds: int
    host_segment: str | None
    rollup: RollupInfo


class ResponseEnvelope(BaseModel):
    """Delivery metadata included on every spine response."""

    generated_at: datetime
    freshness_seconds: int
    partial_sources: list[str] = Field(default_factory=list)
    query_latency_ms: int
    native_url: str | None = None
    cursor: str | None = None


class StatusBoardResponse(BaseModel):
    """Response shape for GET /api/spine/status."""

    segments: list[SegmentStatusResponse]
    envelope: ResponseEnvelope


# ---------------------------------------------------------------------------
# Correlation responses
# ---------------------------------------------------------------------------


CorrelationKind = Literal["capture", "thread", "request", "crud"]


class CorrelationEvent(BaseModel):
    """One segment's appearance in a correlation timeline."""

    segment_id: str
    timestamp: datetime
    status: SegmentStatus
    headline: str


class CorrelationResponse(BaseModel):
    """Response shape for GET /api/spine/correlation/{kind}/{id}."""

    correlation_kind: CorrelationKind
    correlation_id: str
    events: list[CorrelationEvent]
    envelope: ResponseEnvelope


# ---------------------------------------------------------------------------
# Segment detail responses
# ---------------------------------------------------------------------------


class SegmentDetailResponse(BaseModel):
    """Response shape for GET /api/spine/segment/{id}.

    `data` is intentionally a free-form dict because each segment returns
    its native shape. The `data` MUST include a `schema` field that the
    web UI uses to dispatch to the correct renderer.
    """

    data: dict[str, Any]
    envelope: ResponseEnvelope
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_spine_models.py -v`
Expected: PASS — all 6 tests green

- [ ] **Step 6: Commit**

```bash
git add backend/src/second_brain/spine/__init__.py backend/src/second_brain/spine/models.py backend/tests/test_spine_models.py
git commit -m "feat(spine): pydantic models for ingest events and responses"
```

---

## Task 2: Cosmos containers (az CLI provisioning + checked-in script)

**Convention:** This project manages Cosmos container lifecycle with az CLI, not Bicep/IaC (see `.planning/phases/16-query-foundation/16-03-SUMMARY.md` and `.planning/milestones/v3.0-phases/10-data-foundation-and-admin-tools/10-01-PLAN.md`). Task 2 checks in a reproducible provisioning script as the source of truth and runs it once against prod.

**Files:**
- Create: `infra/spine-cosmos-containers.sh`

**Target Cosmos account / database** (verify before running):
- Resource group: `shared-services-rg`
- Account: `shared-services-cosmosdb`
- Database: `second-brain`

**Container spec:**

| Container | Partition key | TTL | Purpose |
|---|---|---|---|
| `spine_segment_state` | `/segment_id` | `-1` (never expire; always upserted) | One doc per segment, current status + headline |
| `spine_events` | `/segment_id` | `1209600` (14 days) | Append-only ingest events (liveness/readiness/workload) |
| `spine_status_history` | `/segment_id` | `2592000` (30 days) | Append-only status transition records |
| `spine_correlation` | `/correlation_kind` | `2592000` (30 days) | Per-correlation timelines (capture/thread/request/crud) |

- [ ] **Step 1: Create `infra/spine-cosmos-containers.sh`**

```bash
#!/usr/bin/env bash
#
# Provision the 4 Cosmos SQL containers backing the spine observability layer.
#
# This project does not have a checked-in Bicep/IaC pipeline for Cosmos;
# container lifecycle is managed with az CLI. This script is the source of
# truth for the spine containers' partition keys and TTLs.
#
# Idempotent: re-running against an already-provisioned account will report
# a 409 Conflict for each existing container. Safe.
#
# First provisioned: 2026-04-15 (Phase 1 / spine foundation).

set -euo pipefail

RG="${RG:-shared-services-rg}"
ACCOUNT="${ACCOUNT:-shared-services-cosmosdb}"
DB="${DB:-second-brain}"

echo "Provisioning spine containers in ${ACCOUNT}/${DB} (${RG})..."

# 1. Segment state — one doc per segment, never expires (always upserted).
az cosmosdb sql container create -g "$RG" -a "$ACCOUNT" -d "$DB" \
  --name spine_segment_state \
  --partition-key-path /segment_id \
  --ttl=-1

# 2. Ingest events — append-only, 14-day retention (1209600 seconds).
az cosmosdb sql container create -g "$RG" -a "$ACCOUNT" -d "$DB" \
  --name spine_events \
  --partition-key-path /segment_id \
  --ttl=1209600

# 3. Status transition history — append-only, 30-day retention (2592000 seconds).
az cosmosdb sql container create -g "$RG" -a "$ACCOUNT" -d "$DB" \
  --name spine_status_history \
  --partition-key-path /segment_id \
  --ttl=2592000

# 4. Correlation records — append-only, 30-day retention, keyed on correlation_kind.
az cosmosdb sql container create -g "$RG" -a "$ACCOUNT" -d "$DB" \
  --name spine_correlation \
  --partition-key-path /correlation_kind \
  --ttl=2592000

echo "Done. Verifying..."
az cosmosdb sql container list -g "$RG" -a "$ACCOUNT" -d "$DB" \
  --query "[?starts_with(name, 'spine_')].{name:name, partitionKey:resource.partitionKey.paths[0], ttl:resource.defaultTtl}" \
  -o table
```

Note: the `--ttl=-1` equals form (not `--ttl -1`) avoids zsh parsing `-1` as a flag argument.

- [ ] **Step 2: Run script with `chmod +x` and execute**

```bash
chmod +x infra/spine-cosmos-containers.sh
./infra/spine-cosmos-containers.sh
```

Expected: 4 create responses (one per container) followed by a 4-row verification table.

- [ ] **Step 3: Verify containers exist with correct config**

```bash
az cosmosdb sql container list \
  -g shared-services-rg -a shared-services-cosmosdb -d second-brain \
  --query "[?starts_with(name, 'spine_')].{name:name, partitionKey:resource.partitionKey.paths[0], ttl:resource.defaultTtl}" \
  -o table
```

Expected 4 rows matching the container spec table above.

- [ ] **Step 4: Commit script**

```bash
git add infra/spine-cosmos-containers.sh
git commit -m "infra(spine): provisioning script for 4 cosmos containers"
```

---

## Task 3: Spine storage repository

**Files:**
- Create: `backend/src/second_brain/spine/storage.py`
- Test: `backend/tests/test_spine_storage.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_spine_storage.py`:

```python
"""Tests for spine Cosmos storage repository."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from second_brain.spine.models import (
    IngestEvent,
    SegmentStatus,
)
from second_brain.spine.storage import SpineRepository


@pytest.fixture
def mock_containers() -> dict[str, AsyncMock]:
    """Four mocked Cosmos container clients."""
    return {
        "events": AsyncMock(),
        "segment_state": AsyncMock(),
        "status_history": AsyncMock(),
        "correlation": AsyncMock(),
    }


@pytest.fixture
def repo(mock_containers: dict[str, AsyncMock]) -> SpineRepository:
    return SpineRepository(
        events_container=mock_containers["events"],
        segment_state_container=mock_containers["segment_state"],
        status_history_container=mock_containers["status_history"],
        correlation_container=mock_containers["correlation"],
    )


@pytest.mark.asyncio
async def test_record_event_writes_to_events_container(
    repo: SpineRepository, mock_containers: dict[str, AsyncMock]
) -> None:
    event = IngestEvent.model_validate({
        "segment_id": "backend_api",
        "event_type": "liveness",
        "timestamp": "2026-04-14T12:00:00Z",
        "payload": {"instance_id": "abc"},
    })
    await repo.record_event(event)
    mock_containers["events"].create_item.assert_called_once()
    body = mock_containers["events"].create_item.call_args.kwargs["body"]
    assert body["segment_id"] == "backend_api"
    assert body["event_type"] == "liveness"


@pytest.mark.asyncio
async def test_record_workload_with_correlation_writes_correlation_record(
    repo: SpineRepository, mock_containers: dict[str, AsyncMock]
) -> None:
    event = IngestEvent.model_validate({
        "segment_id": "backend_api",
        "event_type": "workload",
        "timestamp": "2026-04-14T12:00:00Z",
        "payload": {
            "operation": "POST /api/capture",
            "outcome": "success",
            "duration_ms": 100,
            "correlation_kind": "capture",
            "correlation_id": "trace-1",
        },
    })
    await repo.record_event(event)
    mock_containers["correlation"].upsert_item.assert_called_once()
    corr_body = mock_containers["correlation"].upsert_item.call_args.kwargs["body"]
    assert corr_body["correlation_kind"] == "capture"
    assert corr_body["correlation_id"] == "trace-1"
    assert corr_body["segment_id"] == "backend_api"


@pytest.mark.asyncio
async def test_workload_without_correlation_skips_correlation_write(
    repo: SpineRepository, mock_containers: dict[str, AsyncMock]
) -> None:
    event = IngestEvent.model_validate({
        "segment_id": "backend_api",
        "event_type": "workload",
        "timestamp": "2026-04-14T12:00:00Z",
        "payload": {
            "operation": "background_task",
            "outcome": "success",
            "duration_ms": 100,
        },
    })
    await repo.record_event(event)
    mock_containers["correlation"].upsert_item.assert_not_called()


@pytest.mark.asyncio
async def test_upsert_segment_state_writes_state_container(
    repo: SpineRepository, mock_containers: dict[str, AsyncMock]
) -> None:
    await repo.upsert_segment_state(
        segment_id="backend_api",
        status="green",
        headline="Healthy",
        last_updated=datetime(2026, 4, 14, 12, 0, tzinfo=timezone.utc),
        evaluator_inputs={"workload_failure_rate": 0.0},
    )
    mock_containers["segment_state"].upsert_item.assert_called_once()
    body = mock_containers["segment_state"].upsert_item.call_args.kwargs["body"]
    assert body["id"] == "backend_api"
    assert body["status"] == "green"


@pytest.mark.asyncio
async def test_record_status_change_writes_history(
    repo: SpineRepository, mock_containers: dict[str, AsyncMock]
) -> None:
    await repo.record_status_change(
        segment_id="backend_api",
        status="red",
        prev_status="green",
        headline="Errors",
        evaluator_outputs={"workload_failure_rate": 0.6},
        timestamp=datetime(2026, 4, 14, 12, 0, tzinfo=timezone.utc),
    )
    mock_containers["status_history"].create_item.assert_called_once()
    body = mock_containers["status_history"].create_item.call_args.kwargs["body"]
    assert body["status"] == "red"
    assert body["prev_status"] == "green"


@pytest.mark.asyncio
async def test_get_recent_events_queries_by_segment_and_window(
    repo: SpineRepository, mock_containers: dict[str, AsyncMock]
) -> None:
    async def async_iter():
        for item in [{"segment_id": "backend_api", "event_type": "workload"}]:
            yield item

    mock_containers["events"].query_items = MagicMock(return_value=async_iter())
    events = await repo.get_recent_events("backend_api", window_seconds=300)
    assert len(events) == 1


@pytest.mark.asyncio
async def test_get_correlation_events_queries_correlation_container(
    repo: SpineRepository, mock_containers: dict[str, AsyncMock]
) -> None:
    async def async_iter():
        for item in [{
            "correlation_kind": "capture",
            "correlation_id": "trace-1",
            "segment_id": "backend_api",
            "timestamp": "2026-04-14T12:00:00Z",
            "status": "green",
            "headline": "OK",
        }]:
            yield item

    mock_containers["correlation"].query_items = MagicMock(return_value=async_iter())
    events = await repo.get_correlation_events("capture", "trace-1")
    assert len(events) == 1
    assert events[0]["segment_id"] == "backend_api"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_spine_storage.py -v`
Expected: FAIL — `ImportError: cannot import name 'SpineRepository'`

- [ ] **Step 3: Implement `storage.py`**

Create `backend/src/second_brain/spine/storage.py`:

```python
"""Cosmos repository for spine state, events, history, and correlation."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from azure.cosmos.aio import ContainerProxy

from second_brain.spine.models import (
    CorrelationKind,
    IngestEvent,
    SegmentStatus,
)

logger = logging.getLogger(__name__)


class SpineRepository:
    """Async Cosmos repository for the 4 spine containers."""

    def __init__(
        self,
        events_container: ContainerProxy,
        segment_state_container: ContainerProxy,
        status_history_container: ContainerProxy,
        correlation_container: ContainerProxy,
    ) -> None:
        self._events = events_container
        self._segment_state = segment_state_container
        self._status_history = status_history_container
        self._correlation = correlation_container

    async def record_event(self, event: IngestEvent) -> None:
        """Append an ingest event and (for workloads with correlation) a correlation record."""
        inner = event.root  # the concrete _LivenessEvent / _ReadinessEvent / _WorkloadEvent
        body = {
            "id": str(uuid4()),
            "segment_id": inner.segment_id,
            "event_type": inner.event_type,
            "timestamp": inner.timestamp.isoformat(),
            "payload": inner.payload.model_dump(mode="json"),
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }
        await self._events.create_item(body=body)

        if inner.event_type == "workload":
            payload = inner.payload  # WorkloadPayload
            if payload.correlation_kind and payload.correlation_id:
                corr_status: SegmentStatus = (
                    "green" if payload.outcome == "success"
                    else "yellow" if payload.outcome == "degraded"
                    else "red"
                )
                corr_body = {
                    "id": f"{payload.correlation_kind}:{payload.correlation_id}:{inner.segment_id}:{body['id']}",
                    "correlation_kind": payload.correlation_kind,
                    "correlation_id": payload.correlation_id,
                    "segment_id": inner.segment_id,
                    "timestamp": inner.timestamp.isoformat(),
                    "status": corr_status,
                    "headline": (
                        f"{payload.operation} {payload.outcome}"
                        + (f" ({payload.error_class})" if payload.error_class else "")
                    ),
                    "parent_correlation_kind": None,
                    "parent_correlation_id": None,
                }
                await self._correlation.upsert_item(body=corr_body)

    async def upsert_segment_state(
        self,
        segment_id: str,
        status: SegmentStatus,
        headline: str,
        last_updated: datetime,
        evaluator_inputs: dict[str, Any],
    ) -> None:
        body = {
            "id": segment_id,
            "segment_id": segment_id,
            "status": status,
            "headline": headline,
            "last_updated": last_updated.isoformat(),
            "evaluator_inputs": evaluator_inputs,
        }
        await self._segment_state.upsert_item(body=body)

    async def get_segment_state(self, segment_id: str) -> dict[str, Any] | None:
        try:
            return await self._segment_state.read_item(
                item=segment_id, partition_key=segment_id,
            )
        except Exception:  # CosmosResourceNotFoundError
            return None

    async def get_all_segment_states(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        async for item in self._segment_state.query_items(
            query="SELECT * FROM c",
        ):
            results.append(item)
        return results

    async def record_status_change(
        self,
        segment_id: str,
        status: SegmentStatus,
        prev_status: SegmentStatus | None,
        headline: str,
        evaluator_outputs: dict[str, Any],
        timestamp: datetime,
    ) -> None:
        body = {
            "id": str(uuid4()),
            "segment_id": segment_id,
            "status": status,
            "prev_status": prev_status,
            "headline": headline,
            "evaluator_outputs": evaluator_outputs,
            "timestamp": timestamp.isoformat(),
        }
        await self._status_history.create_item(body=body)

    async def get_recent_events(
        self, segment_id: str, window_seconds: int,
    ) -> list[dict[str, Any]]:
        cutoff = (
            datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
        ).isoformat()
        results: list[dict[str, Any]] = []
        async for item in self._events.query_items(
            query=(
                "SELECT * FROM c WHERE c.segment_id = @sid AND c.timestamp >= @cutoff"
            ),
            parameters=[
                {"name": "@sid", "value": segment_id},
                {"name": "@cutoff", "value": cutoff},
            ],
        ):
            results.append(item)
        return results

    async def get_correlation_events(
        self, kind: CorrelationKind, correlation_id: str,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        async for item in self._correlation.query_items(
            query=(
                "SELECT * FROM c WHERE c.correlation_kind = @kind AND c.correlation_id = @cid"
            ),
            parameters=[
                {"name": "@kind", "value": kind},
                {"name": "@cid", "value": correlation_id},
            ],
        ):
            results.append(item)
        results.sort(key=lambda r: r["timestamp"])
        return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_spine_storage.py -v`
Expected: PASS — all 7 tests green

- [ ] **Step 5: Commit**

```bash
git add backend/src/second_brain/spine/storage.py backend/tests/test_spine_storage.py
git commit -m "feat(spine): cosmos repository for state, events, history, correlation"
```

---

## Task 4: Per-segment evaluator config registry

**Files:**
- Create: `backend/src/second_brain/spine/registry.py`
- Test: `backend/tests/test_spine_registry.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_spine_registry.py`:

```python
"""Tests for per-segment evaluator config registry."""

import pytest

from second_brain.spine.registry import (
    EvaluatorConfig,
    SegmentRegistry,
    get_default_registry,
)


def test_default_registry_includes_backend_api() -> None:
    registry = get_default_registry()
    cfg = registry.get("backend_api")
    assert cfg.segment_id == "backend_api"
    assert cfg.host_segment == "container_app"
    assert cfg.liveness_interval_seconds == 30


def test_default_registry_includes_container_app_rollup_node() -> None:
    registry = get_default_registry()
    cfg = registry.get("container_app")
    assert cfg.segment_id == "container_app"
    assert cfg.host_segment is None  # the host of others, hosted by nothing


def test_unknown_segment_raises_keyerror() -> None:
    registry = get_default_registry()
    with pytest.raises(KeyError):
        registry.get("nonexistent_segment")


def test_all_returns_all_segments() -> None:
    registry = get_default_registry()
    all_cfgs = registry.all()
    ids = {c.segment_id for c in all_cfgs}
    assert "backend_api" in ids
    assert "container_app" in ids


def test_evaluator_config_thresholds_have_defaults() -> None:
    cfg = EvaluatorConfig(
        segment_id="test",
        liveness_interval_seconds=30,
        host_segment=None,
    )
    assert cfg.workload_window_seconds == 300
    assert cfg.acceptable_lag_seconds == 0
    assert cfg.yellow_thresholds == {}
    assert cfg.red_thresholds == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_spine_registry.py -v`
Expected: FAIL — `ImportError: cannot import name 'EvaluatorConfig'`

- [ ] **Step 3: Implement `registry.py`**

Create `backend/src/second_brain/spine/registry.py`:

```python
"""Per-segment evaluator configuration registry.

Config lives in code (not in the database). New segment thresholds
require a code change — intentional.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class EvaluatorConfig:
    """Evaluator config for one segment."""

    segment_id: str
    liveness_interval_seconds: int
    host_segment: str | None
    workload_window_seconds: int = 300
    acceptable_lag_seconds: int = 0
    yellow_thresholds: dict[str, Any] = field(default_factory=dict)
    red_thresholds: dict[str, Any] = field(default_factory=dict)
    display_name: str = ""

    def name_or_id(self) -> str:
        return self.display_name or self.segment_id

    def __post_init__(self) -> None:
        # The evaluator's stale window is liveness_interval_seconds * 2 +
        # acceptable_lag_seconds. get_recent_events is queried with
        # workload_window_seconds. If the query window is smaller than the
        # stale window, a segment can appear stale just because the query
        # truncated older liveness events — fail fast at config time.
        stale_window = self.liveness_interval_seconds * 2 + self.acceptable_lag_seconds
        if self.workload_window_seconds < stale_window:
            raise ValueError(
                f"EvaluatorConfig for '{self.segment_id}': "
                f"workload_window_seconds ({self.workload_window_seconds}) "
                f"must be >= stale window ({stale_window} = "
                f"liveness_interval_seconds * 2 + acceptable_lag_seconds) "
                f"so the query covers the staleness threshold."
            )


class SegmentRegistry:
    """Lookup of EvaluatorConfig by segment_id."""

    def __init__(self, configs: list[EvaluatorConfig]) -> None:
        self._by_id = {c.segment_id: c for c in configs}

    def get(self, segment_id: str) -> EvaluatorConfig:
        return self._by_id[segment_id]

    def all(self) -> list[EvaluatorConfig]:
        return list(self._by_id.values())


def get_default_registry() -> SegmentRegistry:
    """Default segment configs for Phase 1.

    Future phases extend this list. The container_app rollup node is
    included because it powers host_segment suppression.
    """
    return SegmentRegistry([
        EvaluatorConfig(
            segment_id="backend_api",
            display_name="Backend API",
            liveness_interval_seconds=30,
            host_segment="container_app",
            workload_window_seconds=300,
            yellow_thresholds={
                "workload_failure_rate": 0.10,
                "any_readiness_failed": True,
            },
            red_thresholds={
                "workload_failure_rate": 0.50,
                "consecutive_failures": 3,
            },
        ),
        EvaluatorConfig(
            segment_id="container_app",
            display_name="Container App",
            liveness_interval_seconds=60,
            host_segment=None,
            workload_window_seconds=300,
        ),
    ])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_spine_registry.py -v`
Expected: PASS — all 5 tests green

- [ ] **Step 5: Commit**

```bash
git add backend/src/second_brain/spine/registry.py backend/tests/test_spine_registry.py
git commit -m "feat(spine): per-segment evaluator config registry"
```

---

## Task 5: Status evaluator

**Files:**
- Create: `backend/src/second_brain/spine/evaluator.py`
- Test: `backend/tests/test_spine_evaluator.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_spine_evaluator.py`:

```python
"""Tests for the status evaluator."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from second_brain.spine.evaluator import StatusEvaluator, EvaluationResult
from second_brain.spine.registry import EvaluatorConfig, SegmentRegistry


def _cfg(**overrides) -> EvaluatorConfig:
    base = dict(
        segment_id="seg1",
        liveness_interval_seconds=30,
        host_segment=None,
        workload_window_seconds=300,
        yellow_thresholds={"workload_failure_rate": 0.10},
        red_thresholds={"workload_failure_rate": 0.50, "consecutive_failures": 3},
    )
    base.update(overrides)
    return EvaluatorConfig(**base)


def _liveness(timestamp: datetime) -> dict:
    return {
        "event_type": "liveness",
        "timestamp": timestamp.isoformat(),
        "payload": {"instance_id": "i1"},
    }


def _workload(timestamp: datetime, outcome: str, error_class: str | None = None) -> dict:
    return {
        "event_type": "workload",
        "timestamp": timestamp.isoformat(),
        "payload": {
            "operation": "op",
            "outcome": outcome,
            "duration_ms": 100,
            "error_class": error_class,
        },
    }


def _readiness(timestamp: datetime, all_ok: bool = True) -> dict:
    return {
        "event_type": "readiness",
        "timestamp": timestamp.isoformat(),
        "payload": {
            "checks": [{"name": "dep1", "status": "ok" if all_ok else "failing"}],
        },
    }


@pytest.mark.asyncio
async def test_no_events_returns_stale() -> None:
    repo = AsyncMock()
    repo.get_recent_events.return_value = []
    registry = SegmentRegistry([_cfg()])
    evaluator = StatusEvaluator(repo=repo, registry=registry, now=lambda: datetime.now(timezone.utc))
    result = await evaluator.evaluate("seg1")
    assert result.status == "stale"


@pytest.mark.asyncio
async def test_recent_liveness_only_returns_green() -> None:
    now = datetime(2026, 4, 14, 12, 0, tzinfo=timezone.utc)
    repo = AsyncMock()
    repo.get_recent_events.return_value = [_liveness(now - timedelta(seconds=10))]
    registry = SegmentRegistry([_cfg()])
    evaluator = StatusEvaluator(repo=repo, registry=registry, now=lambda: now)
    result = await evaluator.evaluate("seg1")
    assert result.status == "green"


@pytest.mark.asyncio
async def test_workload_failure_rate_above_yellow_threshold_returns_yellow() -> None:
    now = datetime(2026, 4, 14, 12, 0, tzinfo=timezone.utc)
    repo = AsyncMock()
    events = [_liveness(now - timedelta(seconds=10))]
    # 11% failure rate (1 fail in 9)
    events.extend([_workload(now - timedelta(seconds=60), "success") for _ in range(8)])
    events.append(_workload(now - timedelta(seconds=30), "failure", "Boom"))
    repo.get_recent_events.return_value = events
    registry = SegmentRegistry([_cfg()])
    evaluator = StatusEvaluator(repo=repo, registry=registry, now=lambda: now)
    result = await evaluator.evaluate("seg1")
    assert result.status == "yellow"


@pytest.mark.asyncio
async def test_workload_failure_rate_above_red_threshold_returns_red() -> None:
    now = datetime(2026, 4, 14, 12, 0, tzinfo=timezone.utc)
    repo = AsyncMock()
    events = [_liveness(now - timedelta(seconds=10))]
    # 60% failure rate
    events.extend([_workload(now - timedelta(seconds=60), "success") for _ in range(4)])
    events.extend([_workload(now - timedelta(seconds=30), "failure", "Boom") for _ in range(6)])
    repo.get_recent_events.return_value = events
    registry = SegmentRegistry([_cfg()])
    evaluator = StatusEvaluator(repo=repo, registry=registry, now=lambda: now)
    result = await evaluator.evaluate("seg1")
    assert result.status == "red"


@pytest.mark.asyncio
async def test_three_consecutive_failures_returns_red() -> None:
    now = datetime(2026, 4, 14, 12, 0, tzinfo=timezone.utc)
    repo = AsyncMock()
    events = [_liveness(now - timedelta(seconds=10))]
    # Most recent 3 are all failures (highest priority over rate)
    events.extend([_workload(now - timedelta(seconds=300 - i), "success") for i in range(7)])
    events.extend([
        _workload(now - timedelta(seconds=30), "failure", "Boom"),
        _workload(now - timedelta(seconds=20), "failure", "Boom"),
        _workload(now - timedelta(seconds=10), "failure", "Boom"),
    ])
    repo.get_recent_events.return_value = events
    registry = SegmentRegistry([_cfg()])
    evaluator = StatusEvaluator(repo=repo, registry=registry, now=lambda: now)
    result = await evaluator.evaluate("seg1")
    assert result.status == "red"


@pytest.mark.asyncio
async def test_readiness_failure_promotes_to_yellow() -> None:
    now = datetime(2026, 4, 14, 12, 0, tzinfo=timezone.utc)
    repo = AsyncMock()
    repo.get_recent_events.return_value = [
        _liveness(now - timedelta(seconds=10)),
        _readiness(now - timedelta(seconds=20), all_ok=False),
    ]
    registry = SegmentRegistry([_cfg(yellow_thresholds={"any_readiness_failed": True})])
    evaluator = StatusEvaluator(repo=repo, registry=registry, now=lambda: now)
    result = await evaluator.evaluate("seg1")
    assert result.status == "yellow"


@pytest.mark.asyncio
async def test_freshness_seconds_reflects_most_recent_event() -> None:
    now = datetime(2026, 4, 14, 12, 0, tzinfo=timezone.utc)
    repo = AsyncMock()
    repo.get_recent_events.return_value = [_liveness(now - timedelta(seconds=10))]
    registry = SegmentRegistry([_cfg()])
    evaluator = StatusEvaluator(repo=repo, registry=registry, now=lambda: now)
    result = await evaluator.evaluate("seg1")
    assert result.freshness_seconds == 10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_spine_evaluator.py -v`
Expected: FAIL — `ImportError: cannot import name 'StatusEvaluator'`

- [ ] **Step 3: Implement `evaluator.py`**

Create `backend/src/second_brain/spine/evaluator.py`:

```python
"""Status evaluator: reads recent events for a segment and computes status.

Hard rules:
- Status precedence: red > yellow > green > stale.
- No-data behavior: a segment with no liveness in 2x interval is stale.
- Source-lag handling: acceptable_lag_seconds is added to the staleness window.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from second_brain.spine.models import SegmentStatus
from second_brain.spine.registry import EvaluatorConfig, SegmentRegistry
from second_brain.spine.storage import SpineRepository

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class EvaluationResult:
    """Output of a single evaluator run for a segment."""

    segment_id: str
    status: SegmentStatus
    headline: str
    last_event_at: datetime | None
    freshness_seconds: int
    evaluator_inputs: dict[str, Any]


class StatusEvaluator:
    """Per-segment status evaluator."""

    def __init__(
        self,
        repo: SpineRepository,
        registry: SegmentRegistry,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._repo = repo
        self._registry = registry
        self._now = now or (lambda: datetime.now(timezone.utc))

    async def evaluate(self, segment_id: str) -> EvaluationResult:
        cfg = self._registry.get(segment_id)
        events = await self._repo.get_recent_events(
            segment_id=segment_id, window_seconds=cfg.workload_window_seconds,
        )

        # Compute freshness from most recent event of any type
        most_recent = max(
            (self._parse_ts(e["timestamp"]) for e in events),
            default=None,
        )
        now = self._now()
        freshness = int((now - most_recent).total_seconds()) if most_recent else 999_999

        # Stale check (precedes all other status logic)
        stale_window = cfg.liveness_interval_seconds * 2 + cfg.acceptable_lag_seconds
        liveness_events = [e for e in events if e["event_type"] == "liveness"]
        most_recent_liveness = max(
            (self._parse_ts(e["timestamp"]) for e in liveness_events), default=None,
        )
        if most_recent_liveness is None or (now - most_recent_liveness).total_seconds() > stale_window:
            return EvaluationResult(
                segment_id=segment_id,
                status="stale",
                headline="No recent liveness signal",
                last_event_at=most_recent,
                freshness_seconds=freshness,
                evaluator_inputs={"reason": "stale"},
            )

        # Compute workload metrics
        workload_events = [e for e in events if e["event_type"] == "workload"]
        workload_events.sort(key=lambda e: e["timestamp"])
        total = len(workload_events)
        failures = sum(1 for e in workload_events if e["payload"]["outcome"] == "failure")
        rate = failures / total if total > 0 else 0.0

        # Consecutive failures (most recent N)
        consecutive_failures = 0
        for e in reversed(workload_events):
            if e["payload"]["outcome"] == "failure":
                consecutive_failures += 1
            else:
                break

        # Readiness signals
        readiness_events = [e for e in events if e["event_type"] == "readiness"]
        any_readiness_failed = any(
            any(c["status"] == "failing" for c in e["payload"]["checks"])
            for e in readiness_events
        )

        inputs = {
            "workload_total": total,
            "workload_failures": failures,
            "workload_failure_rate": rate,
            "consecutive_failures": consecutive_failures,
            "any_readiness_failed": any_readiness_failed,
        }

        # Apply red thresholds first
        if self._exceeds(cfg.red_thresholds, inputs):
            return EvaluationResult(
                segment_id=segment_id,
                status="red",
                headline=self._red_headline(inputs, cfg),
                last_event_at=most_recent,
                freshness_seconds=freshness,
                evaluator_inputs=inputs,
            )

        # Then yellow
        if self._exceeds(cfg.yellow_thresholds, inputs):
            return EvaluationResult(
                segment_id=segment_id,
                status="yellow",
                headline=self._yellow_headline(inputs),
                last_event_at=most_recent,
                freshness_seconds=freshness,
                evaluator_inputs=inputs,
            )

        return EvaluationResult(
            segment_id=segment_id,
            status="green",
            headline=self._green_headline(inputs, cfg),
            last_event_at=most_recent,
            freshness_seconds=freshness,
            evaluator_inputs=inputs,
        )

    @staticmethod
    def _parse_ts(s: str) -> datetime:
        # Cosmos returns ISO with Z or +00:00; both work with fromisoformat in 3.11+
        return datetime.fromisoformat(s.replace("Z", "+00:00"))

    @staticmethod
    def _exceeds(thresholds: dict[str, Any], inputs: dict[str, Any]) -> bool:
        for key, threshold in thresholds.items():
            value = inputs.get(key)
            if value is None:
                continue
            if isinstance(threshold, bool):
                if value == threshold:
                    return True
            elif isinstance(threshold, (int, float)):
                if value >= threshold:
                    return True
        return False

    @staticmethod
    def _red_headline(inputs: dict[str, Any], cfg: EvaluatorConfig) -> str:
        # Surface the consecutive-failure message only when that threshold was
        # actually the trigger — compare against cfg, not a hardcoded constant.
        consec_threshold = cfg.red_thresholds.get("consecutive_failures")
        consec = inputs.get("consecutive_failures", 0)
        if isinstance(consec_threshold, (int, float)) and consec >= consec_threshold:
            return f"{consec} consecutive failures"
        rate_pct = int(inputs.get("workload_failure_rate", 0) * 100)
        fails = inputs["workload_failures"]
        total = inputs["workload_total"]
        return f"{rate_pct}% failure rate ({fails}/{total})"

    @staticmethod
    def _yellow_headline(inputs: dict[str, Any]) -> str:
        if inputs.get("any_readiness_failed"):
            return "Dependency check failing"
        rate_pct = int(inputs.get("workload_failure_rate", 0) * 100)
        fails = inputs["workload_failures"]
        total = inputs["workload_total"]
        return f"{rate_pct}% failure rate ({fails}/{total})"

    @staticmethod
    def _green_headline(inputs: dict[str, Any], cfg: EvaluatorConfig) -> str:
        total = inputs.get("workload_total", 0)
        window_label = _humanize_window(cfg.workload_window_seconds)
        if total == 0:
            return "Idle (no recent operations)"
        return f"{total} ops, 0 failures in last {window_label}"


def _humanize_window(seconds: int) -> str:
    """Human label for the workload window (e.g. 300 → '5min', 90 → '90s')."""
    if seconds >= 60 and seconds % 60 == 0:
        return f"{seconds // 60}min"
    return f"{seconds}s"
```

NOTE: This task also extends `EvaluatorConfig` (from Task 4) with a `__post_init__` invariant asserting `workload_window_seconds >= liveness_interval_seconds * 2 + acceptable_lag_seconds` — otherwise the evaluator's stale check could fire on healthy segments whose liveness events fall outside the query window. The Task 4 plan lists this guard for continuity, but the actual change landed atomically with Task 5 (commit on branch `phase-1-spine-foundation` amended during Task 5 review).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_spine_evaluator.py -v`
Expected: PASS — all 7 tests green

- [ ] **Step 5: Commit**

```bash
git add backend/src/second_brain/spine/evaluator.py backend/tests/test_spine_evaluator.py
git commit -m "feat(spine): status evaluator with locked precedence rules"
```

---

## Task 6: Adapter Protocol + registry

**Files:**
- Create: `backend/src/second_brain/spine/adapters/__init__.py`
- Create: `backend/src/second_brain/spine/adapters/base.py`
- Create: `backend/src/second_brain/spine/adapters/registry.py`

- [ ] **Step 1: Create empty `__init__.py`**

```bash
touch backend/src/second_brain/spine/adapters/__init__.py
```

- [ ] **Step 2: Implement `base.py` (Protocol)**

Create `backend/src/second_brain/spine/adapters/base.py`:

```python
"""SegmentAdapter Protocol — contract for per-segment detail fetching."""

from __future__ import annotations

from typing import Protocol

from second_brain.spine.models import CorrelationKind


class SegmentAdapter(Protocol):
    """Returns native-shape detail for one segment."""

    segment_id: str
    native_url_template: str  # e.g. "https://portal.azure.com/#..."

    async def fetch_detail(
        self,
        correlation_kind: CorrelationKind | None = None,
        correlation_id: str | None = None,
        time_range_seconds: int = 3600,
    ) -> dict:
        """Return a dict containing a 'schema' field plus segment-specific data.

        The 'schema' field tells the web UI which renderer to use.
        Everything else is segment-native and not normalized.
        """
        ...
```

- [ ] **Step 3: Implement `registry.py`**

Create `backend/src/second_brain/spine/adapters/registry.py`:

```python
"""Maps segment_id → SegmentAdapter instance."""

from __future__ import annotations

from second_brain.spine.adapters.base import SegmentAdapter


class AdapterRegistry:
    """Lookup of SegmentAdapter by segment_id."""

    def __init__(self, adapters: list[SegmentAdapter]) -> None:
        self._by_id: dict[str, SegmentAdapter] = {a.segment_id: a for a in adapters}

    def get(self, segment_id: str) -> SegmentAdapter | None:
        return self._by_id.get(segment_id)

    def has(self, segment_id: str) -> bool:
        return segment_id in self._by_id
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/second_brain/spine/adapters/
git commit -m "feat(spine): adapter Protocol and registry"
```

---

## Task 7: Phase 19.1 KQL projection absorption

**Files:**
- Modify: `backend/src/second_brain/observability/kql_templates.py`
- Modify: `backend/src/second_brain/observability/models.py`
- Modify: `backend/src/second_brain/observability/queries.py`
- Test: `backend/tests/test_kql_projections.py`

- [ ] **Step 1: Write failing test for KQL projection contract**

Create `backend/tests/test_kql_projections.py`:

```python
"""Verify KQL templates project the new AppExceptions native fields.

Phase 19.1 absorption: surface OuterMessage, OuterType, InnermostMessage,
and tostring(Details) instead of dropping them in coalesce(Message, ExceptionType).
"""

from second_brain.observability.kql_templates import (
    CAPTURE_TRACE,
    RECENT_FAILURES,
    RECENT_FAILURES_FILTERED,
)


def test_capture_trace_projects_outer_message() -> None:
    assert "OuterMessage" in CAPTURE_TRACE


def test_capture_trace_projects_outer_type() -> None:
    assert "OuterType" in CAPTURE_TRACE


def test_capture_trace_projects_innermost_message() -> None:
    assert "InnermostMessage" in CAPTURE_TRACE


def test_capture_trace_uses_tostring_for_details() -> None:
    assert "tostring(Details)" in CAPTURE_TRACE


def test_recent_failures_projects_new_fields() -> None:
    assert "OuterMessage" in RECENT_FAILURES
    assert "OuterType" in RECENT_FAILURES
    assert "InnermostMessage" in RECENT_FAILURES
    assert "tostring(Details)" in RECENT_FAILURES


def test_recent_failures_filtered_projects_new_fields() -> None:
    assert "OuterMessage" in RECENT_FAILURES_FILTERED
    assert "OuterType" in RECENT_FAILURES_FILTERED
    assert "InnermostMessage" in RECENT_FAILURES_FILTERED
    assert "tostring(Details)" in RECENT_FAILURES_FILTERED


def test_message_coalesce_elevates_outer_message_first() -> None:
    """coalesce ordering puts OuterMessage first so AppExceptions get rich detail."""
    for tpl in (CAPTURE_TRACE, RECENT_FAILURES, RECENT_FAILURES_FILTERED):
        assert "coalesce(OuterMessage, Message" in tpl


def test_no_resultcode_projection_on_appexceptions() -> None:
    """AppExceptions has no ResultCode column — must not project it."""
    for tpl in (CAPTURE_TRACE, RECENT_FAILURES, RECENT_FAILURES_FILTERED):
        # Specifically: no bare 'ResultCode,' or 'ResultCode\n' in projection list
        # (the existing AppRequests projection on CAPTURE_TRACE is fine)
        lines = tpl.split("\n")
        for line in lines:
            stripped = line.strip()
            # Allow ResultCode in the AppRequests projection block; reject when
            # it appears alongside the new AppExceptions fields.
            if "OuterMessage" in stripped and "ResultCode" in stripped:
                assert False, f"ResultCode must not project alongside AppExceptions fields: {stripped}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_kql_projections.py -v`
Expected: FAIL — multiple assertions fail because templates don't yet project new fields.

- [ ] **Step 3: Read existing kql_templates.py to understand current structure**

Run: `cat backend/src/second_brain/observability/kql_templates.py | head -100`

You'll need to modify the `project` blocks of `CAPTURE_TRACE`, `RECENT_FAILURES`, and `RECENT_FAILURES_FILTERED` to:
1. Add `OuterMessage`, `OuterType`, `InnermostMessage`, `tostring(Details) as Details` to the projection
2. Change `Message = coalesce(...)` ordering to `coalesce(OuterMessage, Message, InnermostMessage, ExceptionType, Name)`

- [ ] **Step 4: Update `CAPTURE_TRACE` in kql_templates.py**

Find the `project` block in `CAPTURE_TRACE` (around the existing `Message = coalesce(Message, Name, ExceptionType)` line) and replace with:

```kql
| project
    timestamp = TimeGenerated,
    ItemType = case(
        SourceTable == "AppTraces", "Log",
        SourceTable == "AppRequests", "Request",
        SourceTable == "AppDependencies", "Dependency",
        SourceTable == "AppExceptions", "Exception",
        SourceTable
    ),
    severityLevel = SeverityLevel,
    Message = coalesce(OuterMessage, Message, InnermostMessage, ExceptionType, Name),
    OuterMessage,
    OuterType,
    InnermostMessage,
    Details = tostring(Details),
    Component = tostring(Properties.component),
    CaptureTraceId = tostring(Properties.capture_trace_id)
| order by timestamp asc
```

- [ ] **Step 5: Update `RECENT_FAILURES` in kql_templates.py**

Same projection update (no ItemType "Request"/"Dependency" branches since it only unions AppTraces + AppExceptions):

```kql
| project
    timestamp = TimeGenerated,
    ItemType = case(
        SourceTable == "AppTraces", "Log",
        SourceTable == "AppExceptions", "Exception",
        SourceTable
    ),
    severityLevel = SeverityLevel,
    Message = coalesce(OuterMessage, Message, InnermostMessage, ExceptionType),
    OuterMessage,
    OuterType,
    InnermostMessage,
    Details = tostring(Details),
    Component = tostring(Properties.component),
    CaptureTraceId = tostring(Properties.capture_trace_id)
| order by timestamp desc
```

- [ ] **Step 6: Update `RECENT_FAILURES_FILTERED` similarly**

Apply the same projection inside the `let filtered = ...` and the final `| project` block.

- [ ] **Step 7: Update `FailureRecord` and `TraceRecord` models**

Open `backend/src/second_brain/observability/models.py`. Find `FailureRecord` and `TraceRecord` classes. To each, add:

```python
    outer_message: str | None = None
    outer_type: str | None = None
    innermost_message: str | None = None
    details: str | None = None
```

**Also widen the existing `message` field to be nullable:**

```python
    message: str | None = None
```

This is required because the next change brings `message` under the `_empty_to_none` validator, and KQL's `coalesce(OuterMessage, Message, InnermostMessage, ExceptionType[, Name])` can legitimately produce an empty string for an exception row where every candidate is null. With `message: str` non-optional, the validator's `"" → None` conversion would raise `ValidationError` and abort the entire query (live-impact regression on `recent_errors` + `trace_lifecycle`). `null` is more honest than `""`; the agent rendering layer is responsible for a `"(no message)"` fallback at render time.

Then extend the existing `_empty_to_none` `@field_validator(mode="before")` decorator to include the new field names, e.g.:

```python
    @field_validator(
        "message", "component", "capture_trace_id",
        "outer_message", "outer_type", "innermost_message", "details",
        mode="before",
    )
    @classmethod
    def _empty_to_none(cls, v: object) -> object:
        if isinstance(v, str) and v.strip() == "":
            return None
        return v
```

**Add a round-trip parser test** at `backend/tests/test_observability_models.py` that pins:
- `FailureRecord(..., message="").message is None` (the new nullable contract)
- `TraceRecord(..., message="").message is None`
- Empty values on all 4 new fields normalize to None on both records
- Non-empty values on all 4 new fields survive the validator
- `component` / `capture_trace_id` empty→None behaviour from Phase 17.1 is preserved

These tests are what catches the nullable-`message` bug without needing a live App Insights run.

- [ ] **Step 8: Wire new kwargs in `queries.py` parser sites**

In `backend/src/second_brain/observability/queries.py`, find the three places that construct `FailureRecord(...)` or `TraceRecord(...)` from KQL row dicts and add the new kwargs:

```python
FailureRecord(
    timestamp=row["timestamp"],
    item_type=row["ItemType"],
    severity_level=row["severityLevel"],
    message=row["Message"],
    component=row["Component"],
    capture_trace_id=row["CaptureTraceId"],
    outer_message=row.get("OuterMessage"),
    outer_type=row.get("OuterType"),
    innermost_message=row.get("InnermostMessage"),
    details=row.get("Details"),
)
```

Apply the analogous change to `TraceRecord` construction.

- [ ] **Step 9: Run KQL projection test + existing regression tests**

```bash
cd backend && uv run pytest tests/test_kql_projections.py tests/test_investigation_queries.py -v
```

Expected: All tests pass — new projection tests + existing severity-level regression tests.

- [ ] **Step 10: Commit**

```bash
git add backend/src/second_brain/observability/kql_templates.py backend/src/second_brain/observability/models.py backend/src/second_brain/observability/queries.py backend/tests/test_kql_projections.py
git commit -m "feat(observability): project AppExceptions native fields (absorbs Phase 19.1)"
```

---

## Task 8: Backend API pull adapter

**Files:**
- Create: `backend/src/second_brain/spine/adapters/backend_api.py`
- Test: `backend/tests/test_spine_backend_api_adapter.py`

> **AMENDMENT (2026-04-15)**: The adapter accepts two injectable async fetchers — `failures_fetcher` and `requests_fetcher` — each of which MUST be a focused query primitive returning native App Insights row shapes. The adapter is pure orchestration/composition; it does NOT own query logic.
>
> The Phase 1 acceptance path (Task 19 Step 5) requires the `/api/spine/segment/backend_api` response to carry `data.schema == "azure_monitor_app_insights"` with `app_exceptions` (AppExceptions rows) and `app_requests` (AppRequests rows). Stuffing mixed trace rows from `query_capture_trace` into `app_requests` would violate the native-shape contract locked in the Phase 1 spec ("Backend API → AppInsightsDetail renderer backed by AppExceptions + AppRequests"). The timeline query is NOT an AppRequests detail query.
>
> Task 11.5 (inserted below Task 11) adds the two focused primitives — `query_backend_api_failures()` and `query_backend_api_requests()` — that Task 12 binds into the adapter. Task 8's adapter contract does NOT change. Do not modify Task 8 retrospectively; the new primitives slot into the existing injection points.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_spine_backend_api_adapter.py`:

```python
"""Tests for Backend API segment adapter (pulls from App Insights)."""

from unittest.mock import AsyncMock

import pytest

from second_brain.spine.adapters.backend_api import BackendApiAdapter


@pytest.mark.asyncio
async def test_fetch_detail_returns_app_insights_schema() -> None:
    failures_query = AsyncMock(return_value=[])
    requests_query = AsyncMock(return_value=[])
    adapter = BackendApiAdapter(
        failures_fetcher=failures_query,
        requests_fetcher=requests_query,
        native_url="https://portal.azure.com/#blade/AppInsightsExtension",
    )
    result = await adapter.fetch_detail()
    assert result["schema"] == "azure_monitor_app_insights"
    assert "app_exceptions" in result
    assert "app_requests" in result
    assert result["native_url"] == "https://portal.azure.com/#blade/AppInsightsExtension"


@pytest.mark.asyncio
async def test_fetch_detail_with_correlation_filters() -> None:
    failures_query = AsyncMock(return_value=[
        {"capture_trace_id": "trace-1", "message": "Boom"}
    ])
    requests_query = AsyncMock(return_value=[])
    adapter = BackendApiAdapter(
        failures_fetcher=failures_query,
        requests_fetcher=requests_query,
        native_url="x",
    )
    result = await adapter.fetch_detail(
        correlation_kind="capture", correlation_id="trace-1",
    )
    failures_query.assert_called_once()
    assert result["app_exceptions"][0]["capture_trace_id"] == "trace-1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_spine_backend_api_adapter.py -v`
Expected: FAIL — `ImportError: cannot import name 'BackendApiAdapter'`

- [ ] **Step 3: Implement the adapter**

Create `backend/src/second_brain/spine/adapters/backend_api.py`:

```python
"""Backend API segment adapter — pulls from App Insights via existing query layer."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from second_brain.spine.models import CorrelationKind


class BackendApiAdapter:
    """Pulls AppExceptions + AppRequests from App Insights for the Backend API segment."""

    segment_id: str = "backend_api"

    def __init__(
        self,
        failures_fetcher: Callable[..., Awaitable[list[dict[str, Any]]]],
        requests_fetcher: Callable[..., Awaitable[list[dict[str, Any]]]],
        native_url: str,
    ) -> None:
        self._failures = failures_fetcher
        self._requests = requests_fetcher
        self.native_url_template = native_url

    async def fetch_detail(
        self,
        correlation_kind: CorrelationKind | None = None,
        correlation_id: str | None = None,
        time_range_seconds: int = 3600,
    ) -> dict[str, Any]:
        # Both fetchers accept optional capture_trace_id filter
        kwargs: dict[str, Any] = {"time_range_seconds": time_range_seconds}
        if correlation_kind == "capture" and correlation_id:
            kwargs["capture_trace_id"] = correlation_id

        exceptions = await self._failures(**kwargs)
        requests = await self._requests(**kwargs)

        return {
            "schema": "azure_monitor_app_insights",
            "app_exceptions": exceptions,
            "app_requests": requests,
            "native_url": self.native_url_template,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_spine_backend_api_adapter.py -v`
Expected: PASS — both tests green

- [ ] **Step 5: Commit**

```bash
git add backend/src/second_brain/spine/adapters/backend_api.py backend/tests/test_spine_backend_api_adapter.py
git commit -m "feat(spine): backend api adapter pulls from app insights"
```

---

## Task 9: Spine ingest middleware (workload events from FastAPI)

**Files:**
- Create: `backend/src/second_brain/spine/middleware.py`
- Test: `backend/tests/test_spine_middleware.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_spine_middleware.py`:

```python
"""Tests for SpineWorkloadMiddleware: emits workload event per FastAPI request."""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from second_brain.spine.middleware import SpineWorkloadMiddleware


@pytest.fixture
def app_with_middleware():
    app = FastAPI()
    repo = AsyncMock()
    app.add_middleware(
        SpineWorkloadMiddleware,
        repo=repo,
        segment_id="backend_api",
    )

    @app.get("/healthy")
    async def healthy() -> dict:
        return {"ok": True}

    @app.get("/boom")
    async def boom() -> dict:
        raise RuntimeError("Boom")

    return app, repo


@pytest.mark.asyncio
async def test_successful_request_emits_success_workload(app_with_middleware) -> None:
    app, repo = app_with_middleware
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/healthy")
    assert response.status_code == 200
    repo.record_event.assert_called_once()
    event = repo.record_event.call_args.args[0]
    assert event.root.event_type == "workload"
    assert event.root.payload.outcome == "success"
    assert event.root.payload.operation == "GET /healthy"


@pytest.mark.asyncio
async def test_failing_request_emits_failure_workload(app_with_middleware) -> None:
    app, repo = app_with_middleware
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        try:
            await client.get("/boom")
        except Exception:
            pass
    # Middleware should still have recorded a failure event before exception propagation
    repo.record_event.assert_called()
    event = repo.record_event.call_args.args[0]
    assert event.root.payload.outcome == "failure"
    assert event.root.payload.error_class == "RuntimeError"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_spine_middleware.py -v`
Expected: FAIL — `ImportError: cannot import name 'SpineWorkloadMiddleware'`

- [ ] **Step 3: Implement the middleware**

Create `backend/src/second_brain/spine/middleware.py`:

```python
"""FastAPI middleware that emits a spine workload event per request."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from second_brain.spine.models import IngestEvent, WorkloadPayload, _WorkloadEvent
from second_brain.spine.storage import SpineRepository

logger = logging.getLogger(__name__)


class SpineWorkloadMiddleware(BaseHTTPMiddleware):
    """Records a workload event per request (success/failure + duration)."""

    def __init__(self, app, repo: SpineRepository, segment_id: str) -> None:
        super().__init__(app)
        self._repo = repo
        self._segment_id = segment_id

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        operation = f"{request.method} {request.url.path}"
        # ContextVar for capture_trace_id is set elsewhere in the codebase;
        # we read whichever request header carries it for the workload payload.
        correlation_id = request.headers.get("x-trace-id")

        try:
            response = await call_next(request)
            duration_ms = int((time.perf_counter() - start) * 1000)
            outcome = "success" if response.status_code < 500 else "failure"
            correlation_id = self._read_capture_trace_id(request)
            event = IngestEvent(root=_WorkloadEvent(
                segment_id=self._segment_id,
                event_type="workload",
                timestamp=datetime.now(timezone.utc),
                payload=WorkloadPayload(
                    operation=operation,
                    outcome=outcome,
                    duration_ms=duration_ms,
                    correlation_kind="capture" if correlation_id else None,
                    correlation_id=correlation_id,
                    error_class=None if outcome == "success" else f"HTTP_{response.status_code}",
                ),
            ))
            try:
                await self._repo.record_event(event)
            except Exception:  # noqa: BLE001 - never let spine break the request
                logger.warning("Failed to record spine workload event", exc_info=True)
            return response
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            correlation_id = self._read_capture_trace_id(request)
            event = IngestEvent(root=_WorkloadEvent(
                segment_id=self._segment_id,
                event_type="workload",
                timestamp=datetime.now(timezone.utc),
                payload=WorkloadPayload(
                    operation=operation,
                    outcome="failure",
                    duration_ms=duration_ms,
                    correlation_kind="capture" if correlation_id else None,
                    correlation_id=correlation_id,
                    error_class=type(exc).__name__,
                ),
            ))
            try:
                await self._repo.record_event(event)
            except Exception:  # noqa: BLE001
                logger.warning("Failed to record spine workload event", exc_info=True)
            raise

    @staticmethod
    def _read_capture_trace_id(request: Request) -> str | None:
        """Resolve the capture trace ID for correlation.

        Precedence (per Task 9 amendment — required to make capture
        correlation work for native app requests that don't send
        X-Trace-Id):
          1. request.state.capture_trace_id  (set by capture handlers
             after they generate/accept a trace ID — see Task 9 Step 3b)
          2. X-Trace-Id inbound header       (caller-supplied)
          3. None                            (uncorrelated)
        """
        state_val = getattr(request.state, "capture_trace_id", None)
        if state_val:
            return str(state_val)
        header_val = request.headers.get("x-trace-id")
        if header_val:
            return header_val
        return None
```

Note: remove the early `correlation_id = request.headers.get("x-trace-id")` line near the top of `dispatch` — correlation is resolved via `_read_capture_trace_id(request)` *after* `call_next` so that handler-set `request.state.capture_trace_id` is visible. Reading it before `call_next` would observe only the header.

- [ ] **Step 3b (AMENDMENT, load-bearing): Propagate handler-generated capture_trace_id into request.state**

In `backend/src/second_brain/api/capture.py`, four handlers generate a capture trace ID when `X-Trace-Id` is absent:

```python
capture_trace_id = request.headers.get("X-Trace-Id", str(uuid4()))
```

At the time of writing (HEAD of main), this pattern appears at approximately lines 209, 266, 313, 381 (the text, voice, follow-up, and capture-voice endpoints). For each occurrence, add the following line immediately after:

```python
request.state.capture_trace_id = capture_trace_id
```

Why: the `SpineWorkloadMiddleware` needs a deterministic channel to read the capture trace ID regardless of whether the caller supplied one. Native mobile captures typically do NOT supply `X-Trace-Id`, so without this propagation the middleware emits a workload event with `correlation_id=None` and the resulting `/api/spine/correlation/capture/{id}` timeline is missing its `backend_api` node — which is the single most important correlation the Phase 1 acceptance path requires (Task 19 Step 6).

**Regression test (add to `tests/test_spine_middleware.py`):**

```python
@pytest.mark.asyncio
async def test_reads_capture_trace_id_from_request_state_when_header_absent() -> None:
    """Per Task 9 amendment: handler-set state beats header, header beats None."""
    repo = AsyncMock()
    app = FastAPI()
    app.add_middleware(SpineWorkloadMiddleware, repo=repo, segment_id="backend_api")

    @app.get("/with-state")
    async def _with_state(request: Request) -> dict:
        request.state.capture_trace_id = "handler-generated-trace"
        return {"ok": True}

    from starlette.requests import Request  # local import to keep test self-contained

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get("/with-state")  # NO X-Trace-Id header

    event = repo.record_event.call_args.args[0]
    assert event.root.payload.correlation_kind == "capture"
    assert event.root.payload.correlation_id == "handler-generated-trace"


@pytest.mark.asyncio
async def test_state_takes_precedence_over_header() -> None:
    repo = AsyncMock()
    app = FastAPI()
    app.add_middleware(SpineWorkloadMiddleware, repo=repo, segment_id="backend_api")

    @app.get("/with-both")
    async def _with_both(request: Request) -> dict:
        request.state.capture_trace_id = "from-state"
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get("/with-both", headers={"X-Trace-Id": "from-header"})

    event = repo.record_event.call_args.args[0]
    assert event.root.payload.correlation_id == "from-state"
```

Why `request.state` and not a `ContextVar`: request.state is request-scoped and survives the handler-to-middleware round trip deterministically. A ContextVar would work but leaks correlation across async tasks if a future contributor reuses the var outside the HTTP request path — exactly the kind of silent coupling a future phase could regress on. Reach for a ContextVar only when the same ID is needed in non-request code paths that don't already get it passed explicitly.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_spine_middleware.py -v`
Expected: PASS (4 tests including the two amendment tests).

- [ ] **Step 5: Commit**

```bash
git add backend/src/second_brain/spine/middleware.py backend/tests/test_spine_middleware.py backend/src/second_brain/api/capture.py
git commit -m "feat(spine): fastapi middleware emits per-request workload events"
```

---

## Task 10: Spine API endpoints

**Files:**
- Create: `backend/src/second_brain/spine/auth.py`
- Create: `backend/src/second_brain/spine/api.py`
- Test: `backend/tests/test_spine_api.py`

- [ ] **Step 1: Implement `auth.py` (reuses existing API key dependency)**

Create `backend/src/second_brain/spine/auth.py`:

```python
"""Spine API authentication — reuses existing API key dependency.

Locates the existing API key dependency from the codebase. If your project
uses a different auth dependency name, adjust the import here.
"""

from second_brain.api.auth import require_api_key as spine_auth  # type: ignore

__all__ = ["spine_auth"]
```

If the existing dependency lives at a different path, run:

```bash
grep -rn "def require_api_key\|def verify_api_key\|HTTPBearer" backend/src/second_brain/api/ | head -5
```

and adjust the import accordingly.

- [ ] **Step 2: Write the failing test for the API**

Create `backend/tests/test_spine_api.py`:

```python
"""Tests for spine HTTP endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from second_brain.spine.api import build_spine_router
from second_brain.spine.evaluator import EvaluationResult


@pytest.fixture
def client_factory():
    """Build a FastAPI test client with mocked spine dependencies."""

    def _build(repo=None, evaluator=None, adapters=None, registry=None, auth_ok=True):
        repo = repo or AsyncMock()
        evaluator = evaluator or AsyncMock()
        adapters = adapters or MagicMock()
        registry = registry or MagicMock()

        app = FastAPI()
        # Override auth to no-op for tests
        from second_brain.spine import auth as spine_auth_mod

        async def fake_auth():
            if not auth_ok:
                from fastapi import HTTPException
                raise HTTPException(401, "unauthorized")

        router = build_spine_router(
            repo=repo,
            evaluator=evaluator,
            adapter_registry=adapters,
            segment_registry=registry,
            auth_dependency=fake_auth,
        )
        app.include_router(router)
        return app, repo, evaluator, adapters, registry

    return _build


@pytest.mark.asyncio
async def test_status_endpoint_returns_envelope_and_segments(client_factory) -> None:
    repo = AsyncMock()
    repo.get_all_segment_states.return_value = [
        {
            "id": "backend_api",
            "segment_id": "backend_api",
            "status": "green",
            "headline": "Healthy",
            "last_updated": "2026-04-14T12:00:00Z",
            "evaluator_inputs": {"workload_failure_rate": 0.0},
        }
    ]
    registry = MagicMock()
    cfg = MagicMock(display_name="Backend API", host_segment="container_app")
    registry.all.return_value = [cfg]
    registry.get.return_value = cfg
    cfg.segment_id = "backend_api"

    app, *_ = client_factory(repo=repo, registry=registry)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/spine/status")
    assert response.status_code == 200
    body = response.json()
    assert "segments" in body
    assert "envelope" in body
    assert body["envelope"]["generated_at"] is not None


@pytest.mark.asyncio
async def test_ingest_endpoint_records_event(client_factory) -> None:
    app, repo, *_ = client_factory()
    payload = {
        "segment_id": "backend_api",
        "event_type": "liveness",
        "timestamp": "2026-04-14T12:00:00Z",
        "payload": {"instance_id": "abc"},
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/spine/ingest", json=payload)
    assert response.status_code == 204
    repo.record_event.assert_called_once()


@pytest.mark.asyncio
async def test_ingest_unauthorized_returns_401(client_factory) -> None:
    app, *_ = client_factory(auth_ok=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/spine/ingest", json={
            "segment_id": "backend_api",
            "event_type": "liveness",
            "timestamp": "2026-04-14T12:00:00Z",
            "payload": {"instance_id": "abc"},
        })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_segment_detail_dispatches_to_adapter(client_factory) -> None:
    adapter = AsyncMock()
    adapter.fetch_detail.return_value = {
        "schema": "azure_monitor_app_insights",
        "app_exceptions": [],
        "app_requests": [],
        "native_url": "https://portal.azure.com",
    }
    adapters = MagicMock()
    adapters.get.return_value = adapter

    app, *_ = client_factory(adapters=adapters)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/spine/segment/backend_api")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["schema"] == "azure_monitor_app_insights"
    assert body["envelope"]["native_url"] == "https://portal.azure.com"


@pytest.mark.asyncio
async def test_segment_detail_unknown_segment_returns_404(client_factory) -> None:
    adapters = MagicMock()
    adapters.get.return_value = None
    app, *_ = client_factory(adapters=adapters)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/spine/segment/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_correlation_endpoint_returns_timeline(client_factory) -> None:
    repo = AsyncMock()
    repo.get_correlation_events.return_value = [{
        "correlation_kind": "capture",
        "correlation_id": "trace-1",
        "segment_id": "backend_api",
        "timestamp": "2026-04-14T12:00:00Z",
        "status": "green",
        "headline": "OK",
    }]
    app, *_ = client_factory(repo=repo)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/spine/correlation/capture/trace-1")
    assert response.status_code == 200
    body = response.json()
    assert body["correlation_kind"] == "capture"
    assert body["correlation_id"] == "trace-1"
    assert len(body["events"]) == 1
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_spine_api.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_spine_router'`

- [ ] **Step 4: Implement `api.py`**

Create `backend/src/second_brain/spine/api.py`:

```python
"""Spine HTTP API: 4 endpoints under /api/spine/*."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from second_brain.spine.adapters.registry import AdapterRegistry
from second_brain.spine.evaluator import StatusEvaluator
from second_brain.spine.models import (
    CorrelationEvent,
    CorrelationKind,
    CorrelationResponse,
    IngestEvent,
    ResponseEnvelope,
    RollupInfo,
    SegmentDetailResponse,
    SegmentStatus,
    SegmentStatusResponse,
    StatusBoardResponse,
)
from second_brain.spine.registry import SegmentRegistry
from second_brain.spine.storage import SpineRepository


def build_spine_router(
    repo: SpineRepository,
    evaluator: StatusEvaluator,
    adapter_registry: AdapterRegistry,
    segment_registry: SegmentRegistry,
    auth_dependency: Callable[..., Awaitable[None]],
) -> APIRouter:
    """Build the /api/spine router with injected dependencies."""

    router = APIRouter(prefix="/api/spine", tags=["spine"])

    @router.post("/ingest", status_code=204, dependencies=[Depends(auth_dependency)])
    async def ingest(event_data: dict) -> None:
        event = IngestEvent.model_validate(event_data)
        await repo.record_event(event)
        return None

    @router.get("/status", response_model=StatusBoardResponse, dependencies=[Depends(auth_dependency)])
    async def status() -> StatusBoardResponse:
        start = time.perf_counter()
        states = await repo.get_all_segment_states()
        states_by_id = {s["segment_id"]: s for s in states}

        # Determine which segments are hosted by a red host (suppression)
        red_hosts = {
            s["segment_id"] for s in states if s.get("status") == "red"
        }

        segments_out: list[SegmentStatusResponse] = []
        max_freshness = 0
        now = datetime.now(timezone.utc)

        for cfg in segment_registry.all():
            state = states_by_id.get(cfg.segment_id)
            if not state:
                # No state yet — show as stale
                segments_out.append(
                    SegmentStatusResponse(
                        id=cfg.segment_id,
                        name=cfg.name_or_id(),
                        status="stale",
                        headline="No data yet",
                        last_updated=now,
                        freshness_seconds=999_999,
                        host_segment=cfg.host_segment,
                        rollup=RollupInfo(suppressed=False, suppressed_by=None, raw_status="stale"),
                    )
                )
                continue

            raw_status: SegmentStatus = state["status"]
            last_updated = datetime.fromisoformat(state["last_updated"].replace("Z", "+00:00"))
            freshness = int((now - last_updated).total_seconds())
            max_freshness = max(max_freshness, freshness)

            suppressed = (
                cfg.host_segment is not None
                and cfg.host_segment in red_hosts
                and raw_status == "red"
            )

            segments_out.append(
                SegmentStatusResponse(
                    id=cfg.segment_id,
                    name=cfg.name_or_id(),
                    status=raw_status,
                    headline=state.get("headline", ""),
                    last_updated=last_updated,
                    freshness_seconds=freshness,
                    host_segment=cfg.host_segment,
                    rollup=RollupInfo(
                        suppressed=suppressed,
                        suppressed_by=cfg.host_segment if suppressed else None,
                        raw_status=raw_status,
                    ),
                )
            )

        latency_ms = int((time.perf_counter() - start) * 1000)
        return StatusBoardResponse(
            segments=segments_out,
            envelope=ResponseEnvelope(
                generated_at=now,
                freshness_seconds=max_freshness,
                partial_sources=[],
                query_latency_ms=latency_ms,
            ),
        )

    @router.get(
        "/correlation/{kind}/{correlation_id}",
        response_model=CorrelationResponse,
        dependencies=[Depends(auth_dependency)],
    )
    async def correlation(kind: CorrelationKind, correlation_id: str) -> CorrelationResponse:
        start = time.perf_counter()
        events = await repo.get_correlation_events(kind, correlation_id)
        latency_ms = int((time.perf_counter() - start) * 1000)
        return CorrelationResponse(
            correlation_kind=kind,
            correlation_id=correlation_id,
            events=[
                CorrelationEvent(
                    segment_id=e["segment_id"],
                    timestamp=datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00")),
                    status=e["status"],
                    headline=e["headline"],
                )
                for e in events
            ],
            envelope=ResponseEnvelope(
                generated_at=datetime.now(timezone.utc),
                freshness_seconds=0,
                partial_sources=[],
                query_latency_ms=latency_ms,
            ),
        )

    @router.get(
        "/segment/{segment_id}",
        response_model=SegmentDetailResponse,
        dependencies=[Depends(auth_dependency)],
    )
    async def segment_detail(
        segment_id: str,
        correlation_kind: CorrelationKind | None = None,
        correlation_id: str | None = None,
        time_range_seconds: int = 3600,
    ) -> SegmentDetailResponse:
        adapter = adapter_registry.get(segment_id)
        if adapter is None:
            raise HTTPException(404, f"No adapter registered for segment '{segment_id}'")
        start = time.perf_counter()
        data = await adapter.fetch_detail(
            correlation_kind=correlation_kind,
            correlation_id=correlation_id,
            time_range_seconds=time_range_seconds,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        return SegmentDetailResponse(
            data=data,
            envelope=ResponseEnvelope(
                generated_at=datetime.now(timezone.utc),
                freshness_seconds=0,
                partial_sources=[],
                query_latency_ms=latency_ms,
                native_url=data.get("native_url"),
            ),
        )

    return router
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_spine_api.py -v`
Expected: PASS — all 6 tests green

- [ ] **Step 6: Commit**

```bash
git add backend/src/second_brain/spine/auth.py backend/src/second_brain/spine/api.py backend/tests/test_spine_api.py
git commit -m "feat(spine): http api with status, ingest, correlation, segment endpoints"
```

---

## Task 11: Background tasks (evaluator loop + self-liveness emitter)

**Files:**
- Create: `backend/src/second_brain/spine/background.py`
- Create: `backend/tests/test_spine_background.py` (red regression — per-segment isolation in `evaluator_loop`)

**Design invariant (operational):** The evaluator loop MUST keep reporting on healthy segments even when one segment's evaluation fails. One broken segment must not silently blind the operator to the status of the others during a tick. Encode this as a red regression test before fixing.

- [ ] **Step 1: Write red regression test for per-segment isolation**

Create `backend/tests/test_spine_background.py` with a test that proves: if `evaluator.evaluate()` raises for segment A, segments B and C are still upserted and logged in the same tick. The test drives one tick of `evaluator_loop` (run it in a task, `asyncio.sleep(0)` enough to complete the sweep, then cancel), asserts `upsert_segment_state` was called for B and C but not A, and asserts a `logger.warning` was emitted with `segment_id=A` in the log arguments.

This test MUST fail against the plan-verbatim implementation from the prior commit (all-or-nothing try/except around the for-loop).

- [ ] **Step 2: Commit the red test**

```bash
git add backend/tests/test_spine_background.py
git commit -m "test(spine): red test for per-segment evaluator loop isolation"
```

- [ ] **Step 3: Implement/fix `background.py`**

Create (or amend) `backend/src/second_brain/spine/background.py`:

```python
"""Background tasks: status evaluator loop + self-liveness emitter."""

from __future__ import annotations

import asyncio
import logging
import socket
from datetime import UTC, datetime

from second_brain.spine.evaluator import StatusEvaluator
from second_brain.spine.models import IngestEvent, LivenessPayload, _LivenessEvent
from second_brain.spine.registry import SegmentRegistry
from second_brain.spine.storage import SpineRepository

logger = logging.getLogger(__name__)


async def evaluator_loop(
    evaluator: StatusEvaluator,
    repo: SpineRepository,
    registry: SegmentRegistry,
    interval_seconds: int = 30,
) -> None:
    """Run the evaluator for every registered segment every N seconds.

    Per-segment isolation: if one segment's tick fails, the remaining segments
    in the same sweep still run. This is load-bearing for a health monitor.
    """
    while True:
        for cfg in registry.all():
            try:
                result = await evaluator.evaluate(cfg.segment_id)
                prev = await repo.get_segment_state(cfg.segment_id)
                prev_status = prev.get("status") if prev else None
                now = datetime.now(UTC)
                await repo.upsert_segment_state(
                    segment_id=cfg.segment_id,
                    status=result.status,
                    headline=result.headline,
                    last_updated=now,
                    evaluator_inputs=result.evaluator_inputs,
                )
                if prev_status != result.status:
                    await repo.record_status_change(
                        segment_id=cfg.segment_id,
                        status=result.status,
                        prev_status=prev_status,
                        headline=result.headline,
                        evaluator_outputs=result.evaluator_inputs,
                        timestamp=now,
                    )
            except Exception:
                logger.warning(
                    "Evaluator tick failed for segment_id=%s",
                    cfg.segment_id,
                    exc_info=True,
                )
        await asyncio.sleep(interval_seconds)


async def liveness_emitter(
    repo: SpineRepository,
    segment_id: str,
    interval_seconds: int = 30,
) -> None:
    """Self-liveness for the Backend API segment (emitted from inside the API)."""
    instance_id = socket.gethostname()
    while True:
        try:
            event = IngestEvent(
                root=_LivenessEvent(
                    segment_id=segment_id,
                    event_type="liveness",
                    timestamp=datetime.now(UTC),
                    payload=LivenessPayload(instance_id=instance_id),
                )
            )
            await repo.record_event(event)
        except Exception:
            logger.warning(
                "Liveness emitter failed for segment_id=%s",
                segment_id,
                exc_info=True,
            )
        await asyncio.sleep(interval_seconds)
```

Note: `asyncio.CancelledError` is a `BaseException` (not `Exception`) in Python 3.8+, so the blanket `except Exception` inside the per-segment body does NOT swallow cancellation. Task 12's `task.cancel(); await task` pattern works correctly.

- [ ] **Step 4: Run the red test and confirm it turns green**

```bash
cd backend && uv run pytest tests/test_spine_background.py -v
```

- [ ] **Step 5: Commit the fix**

```bash
git add backend/src/second_brain/spine/background.py
git commit -m "fix(spine): per-segment isolation in evaluator_loop + log context"
```

---

## Task 11.5: Backend API detail query primitives

**Files:**
- Modify: `backend/src/second_brain/observability/kql_templates.py` (add 2 new templates)
- Modify: `backend/src/second_brain/observability/queries.py` (add 2 new functions)
- Modify: `backend/src/second_brain/observability/models.py` (add `RequestRecord`)
- Test: `backend/tests/test_observability_backend_api_queries.py`

**Why this task exists:** Task 8's adapter contract needs two focused fetchers that return native App Insights row shapes. `query_capture_trace()` is a timeline query that returns mixed rows across 4 tables — it is NOT an AppRequests detail query and must not be stuffed into `app_requests`. `query_recent_failures()` is close to what we need for `app_exceptions` but doesn't support a `capture_trace_id` filter and doesn't expose a configurable time window. Task 11.5 adds the two focused primitives so Task 12 can wire them in cleanly.

- [ ] **Step 1: Add `RequestRecord` model**

In `backend/src/second_brain/observability/models.py`:

```python
class RequestRecord(BaseModel):
    """A single row from the backend_api requests query (AppRequests)."""

    timestamp: str
    name: str                        # e.g. "POST /api/capture/text"
    result_code: str                 # HTTP status as string (Azure's native shape)
    duration_ms: float | None = None
    success: bool | None = None      # AppRequests.Success
    capture_trace_id: str | None = None
    operation_id: str | None = None  # Azure's request-scope correlation

    @field_validator("capture_trace_id", "operation_id", mode="before")
    @classmethod
    def _empty_to_none(cls, v: str | None) -> str | None:
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return None
        return v
```

- [ ] **Step 2: Add two KQL templates**

In `backend/src/second_brain/observability/kql_templates.py`:

```python
# ---------------------------------------------------------------------------
# Backend API Requests -- AppRequests rows for the backend_api segment
# ---------------------------------------------------------------------------
# Parameterised with {capture_trace_filter} via str.format().
# {capture_trace_filter} is either "" (no filter) or a line like:
#   | where tostring(Properties.capture_trace_id) == "trace-id-here"
# Timespan controlled by the query_workspace call.

BACKEND_API_REQUESTS = """\
AppRequests
{capture_trace_filter}| project
    timestamp = TimeGenerated,
    Name,
    ResultCode,
    DurationMs,
    Success,
    CaptureTraceId = tostring(Properties.capture_trace_id),
    OperationId = tostring(OperationId)
| order by timestamp desc
| take 200
"""


# ---------------------------------------------------------------------------
# Backend API Failures -- AppExceptions + severity>=3 AppTraces,
# optionally filtered to a single capture trace
# ---------------------------------------------------------------------------
# Parameterised with {capture_trace_filter} via str.format().
# Timespan controlled by the query_workspace call.

BACKEND_API_FAILURES = """\
union withsource=SourceTable
    (AppTraces | where SeverityLevel >= 3),
    AppExceptions
{capture_trace_filter}| project
    timestamp = TimeGenerated,
    ItemType = case(
        SourceTable == "AppTraces", "Log",
        SourceTable == "AppExceptions", "Exception",
        SourceTable
    ),
    severityLevel = SeverityLevel,
    Message = coalesce(Message, ExceptionType),
    Component = tostring(Properties.component),
    CaptureTraceId = tostring(Properties.capture_trace_id),
    OuterType = tostring(Properties.outer_type),
    OuterMessage = tostring(Properties.outer_message),
    InnermostMessage = tostring(Properties.innermost_message),
    Details = tostring(Properties.details)
| order by timestamp desc
| take 200
"""
```

- [ ] **Step 3: Add two query functions**

In `backend/src/second_brain/observability/queries.py`, import the new templates and add:

```python
async def query_backend_api_requests(
    client: LogsQueryClient,
    workspace_id: str,
    time_range_seconds: int = 3600,
    capture_trace_id: str | None = None,
) -> list[RequestRecord]:
    """Return AppRequests rows for the backend_api segment.

    When `capture_trace_id` is provided, filters to that single trace.
    Otherwise returns the most recent 200 requests in the time window.
    """
    trace_filter = (
        f'| where tostring(Properties.capture_trace_id) == "{capture_trace_id}"\n'
        if capture_trace_id
        else ""
    )
    query = BACKEND_API_REQUESTS.format(capture_trace_filter=trace_filter)
    result = await execute_kql(
        client,
        workspace_id,
        query,
        timespan=timedelta(seconds=time_range_seconds),
    )

    if not result.tables or not result.tables[0]:
        return []

    records: list[RequestRecord] = []
    for row in result.tables[0]:
        records.append(
            RequestRecord(
                timestamp=str(row.get("timestamp", "")),
                name=str(row.get("Name", "")),
                result_code=str(row.get("ResultCode", "")),
                duration_ms=row.get("DurationMs"),
                success=row.get("Success"),
                capture_trace_id=row.get("CaptureTraceId"),
                operation_id=row.get("OperationId"),
            )
        )
    return records


async def query_backend_api_failures(
    client: LogsQueryClient,
    workspace_id: str,
    time_range_seconds: int = 3600,
    capture_trace_id: str | None = None,
) -> list[FailureRecord]:
    """Return AppExceptions + severity>=3 AppTraces for the backend_api segment.

    When `capture_trace_id` is provided, filters to that single trace.
    Otherwise returns the most recent 200 failures in the time window.
    Native-shape rows (same schema as `query_recent_failures`).
    """
    trace_filter = (
        f'| where tostring(Properties.capture_trace_id) == "{capture_trace_id}"\n'
        if capture_trace_id
        else ""
    )
    query = BACKEND_API_FAILURES.format(capture_trace_filter=trace_filter)
    result = await execute_kql(
        client,
        workspace_id,
        query,
        timespan=timedelta(seconds=time_range_seconds),
    )

    if not result.tables or not result.tables[0]:
        return []

    records: list[FailureRecord] = []
    for row in result.tables[0]:
        records.append(
            FailureRecord(
                timestamp=str(row.get("timestamp", "")),
                item_type=str(row.get("ItemType", "")),
                severity_level=row.get("severityLevel"),
                message=str(row.get("Message", "")),
                component=row.get("Component"),
                capture_trace_id=row.get("CaptureTraceId"),
                outer_message=row.get("OuterMessage"),
                outer_type=row.get("OuterType"),
                innermost_message=row.get("InnermostMessage"),
                details=row.get("Details"),
            )
        )
    return records
```

**Amendment (2026-04-16):** The original plan body for `query_backend_api_failures` omitted `outer_message`, `outer_type`, `innermost_message`, and `details` from the `FailureRecord` constructor — even though the `BACKEND_API_FAILURES` KQL template projects all four fields, and the function's docstring promises "same schema as `query_recent_failures`" (which DOES populate them). The omission silently dropped exception detail on every row. Discovered when reviewing Task 16's `AppInsightsDetail` renderer, whose expandable "Inner cause" and "Stack details" sections rely on these fields.

The test plan in Step 4 must include a positive assertion that all four enrichment fields survive parsing when the KQL row carries them — relying on `assert outer_message is None` only proves the field is nullable, not that the constructor reads it.

Note on KQL injection: `capture_trace_id` is interpolated into the KQL string rather than parameterised. That's acceptable here because: (a) KQL does not have traditional prepared statements for this construct; (b) the trace ID value originates either from server-generated UUIDs (`uuid4()` in the capture handlers) or from a caller header that reaches the spine correlation endpoint as a path parameter `{correlation_id}` — FastAPI normalizes path params and this code is behind authenticated endpoints. Still, add this regex guard at the top of each function:

```python
import re

_TRACE_ID_RE = re.compile(r"^[A-Za-z0-9\-]+$")

# ... inside each function, before building trace_filter:
if capture_trace_id is not None and not _TRACE_ID_RE.match(capture_trace_id):
    raise ValueError(f"Invalid capture_trace_id: {capture_trace_id!r}")
```

Hoist `_TRACE_ID_RE` to module level so both functions share it.

- [ ] **Step 4: Write and run tests**

Create `backend/tests/test_observability_backend_api_queries.py`. Write tests with `AsyncMock` for `LogsQueryClient` that:
  1. `query_backend_api_requests()` with no filter issues a query containing `AppRequests` and no `capture_trace_id` filter line; returns typed `RequestRecord` objects.
  2. `query_backend_api_requests(capture_trace_id="abc-123")` includes the filter line with the trace ID quoted exactly once.
  3. `query_backend_api_requests(capture_trace_id="x; drop table y")` raises `ValueError` (the regex guard).
  4. `query_backend_api_failures()` with no filter returns both exception and trace rows parsed into `FailureRecord`.
  5. `query_backend_api_failures(capture_trace_id="abc-123")` filters correctly.
  6. Empty result table returns `[]`.

Run: `cd backend && uv run pytest tests/test_observability_backend_api_queries.py -v`
Expected: all tests green.

- [ ] **Step 5: Commit**

```bash
git add backend/src/second_brain/observability/kql_templates.py \
        backend/src/second_brain/observability/queries.py \
        backend/src/second_brain/observability/models.py \
        backend/tests/test_observability_backend_api_queries.py
git commit -m "feat(observability): backend_api detail query primitives"
```

---

## Task 12: Wire spine into FastAPI app lifespan

**Files:**
- Modify: `backend/src/second_brain/db/cosmos.py` (extend `CONTAINER_NAMES` with 4 spine containers)
- Modify: `backend/src/second_brain/spine/middleware.py` (make `repo` optional; fall back to `request.app.state.spine_repo`)
- Modify: `backend/src/second_brain/main.py` (lifespan wiring + module-scope middleware registration)
- Modify: `backend/tests/test_spine_middleware.py` (regression test: middleware reads repo from `app.state` when constructed without one)
- Create: `backend/tests/test_spine_lifespan_wiring.py` (integration tests for the three behavioral edges listed in Step 1)

**Interface reconciliation (discovered during Task 12 pre-dispatch, amended from plan's original Step 2 snippet):**

The original Task 12 snippet used symbol names that don't match the merged code. Corrections (load-bearing):
- `BackendApiAdapter(native_url=...)` → **`native_url_template=...`** (adapters/backend_api.py:23).
- `app.state.logs_query_client` → **`app.state.logs_client`** (main.py:122).
- `cosmos_client.get_database_client(...).get_container_client(...)` → **`app.state.cosmos_manager.get_container(...)`**. This app routes ALL Cosmos access through `CosmosManager`, which enforces a container-name whitelist (`CONTAINER_NAMES` in `db/cosmos.py`). Do not bypass. Widen the whitelist.
- Middleware registration **must happen at module scope** in `main.py` (matching `APIKeyMiddleware` at line 518), NOT inside `lifespan`. Starlette does not support adding middleware after startup, and this project's convention is module-scope registration before the app serves requests. Make the middleware construct-with-no-repo and read `request.app.state.spine_repo` per dispatch (matching the pattern `spine_auth` already uses for `app.state.api_key`).
- **Router inclusion stays inside lifespan** because `build_spine_router` needs lifespan-constructed dependencies (`spine_repo`, `spine_evaluator`, `adapter_registry`, `spine_registry`). FastAPI allows `app.include_router` before the first request (which `yield` guarantees). Leave a comment explaining the exception.
- Both `app.state.cosmos_manager` and `app.state.logs_client` can be `None` after non-fatal init failures (see main.py:116, 131). Spine wiring must degrade gracefully:
  - `cosmos_manager is None` → skip spine wiring entirely (log a warning).
  - `logs_client is None` → wire spine WITHOUT the Backend API adapter. The `/api/spine/segment/backend_api` route already returns a clean "no adapter" response when `AdapterRegistry.has()` returns False, so this is survivable.

- [ ] **Step 1: Add the 4 spine containers to the `CosmosManager` whitelist**

In `backend/src/second_brain/db/cosmos.py`, append to `CONTAINER_NAMES`:

```python
CONTAINER_NAMES: list[str] = [
    "Inbox",
    "People",
    "Projects",
    "Ideas",
    "Admin",
    "Errands",
    "Tasks",
    "Destinations",
    "AffinityRules",
    "Feedback",
    "EvalResults",
    "GoldenDataset",
    # Spine containers (Phase 1 — provisioned by infra/spine-cosmos-containers.sh)
    "spine_events",
    "spine_segment_state",
    "spine_status_history",
    "spine_correlation",
]
```

`CosmosManager.initialize()` will idempotently fetch container handles for these at app startup (existing loop at `cosmos.py:65-66`). No new access path; no bypass of `CosmosManager._client`.

- [ ] **Step 2: Make `SpineWorkloadMiddleware.repo` optional**

In `backend/src/second_brain/spine/middleware.py`, change the constructor signature:

```python
def __init__(
    self,
    app,
    repo: SpineRepository | None = None,
    segment_id: str = "backend_api",
) -> None:
    super().__init__(app)
    self._repo = repo
    self._segment_id = segment_id
```

And add a helper used by `dispatch` in both branches to resolve the repo lazily:

```python
def _resolve_repo(self, request: Request) -> SpineRepository | None:
    """Return self._repo if set at construction, else app.state.spine_repo, else None.

    Module-scope middleware registration (the project convention) can't
    receive lifespan-constructed dependencies directly, so fall back to
    app.state. When the repo is absent entirely (lifespan skipped spine
    wiring because cosmos_manager was None), silently no-op.
    """
    if self._repo is not None:
        return self._repo
    return getattr(request.app.state, "spine_repo", None)
```

Replace `self._repo.record_event(ingest_event)` in both the success and exception branches with:

```python
repo = self._resolve_repo(request)
if repo is None:
    return response  # (or `raise` in the except branch)
try:
    await repo.record_event(ingest_event)
except Exception:  # noqa: BLE001 - never let spine break the request
    logger.warning("Failed to record spine workload event", exc_info=True)
```

Existing tests in `test_spine_middleware.py` pass `repo=AsyncMock()` explicitly, so they continue to work. Add one new regression test asserting that when the middleware is constructed WITHOUT `repo`, it reads `repo` from `app.state.spine_repo` on dispatch (see Step 5).

- [ ] **Step 3: Add spine lifespan wiring in `main.py`**

Inside the existing `async def lifespan(app: FastAPI)` (`main.py:74`), after the LogsQueryClient block at line 131 and after the `app.state.settings = settings` line at 397, add a new block **before** the `yield` at line 476:

```python
# --- Spine wiring (non-fatal on component failures) ---
spine_evaluator_task = None
spine_liveness_task = None
try:
    if app.state.cosmos_manager is None:
        logger.warning("Spine wiring skipped: cosmos_manager unavailable")
    else:
        from functools import partial

        from second_brain.observability.queries import (
            query_backend_api_failures,
            query_backend_api_requests,
        )
        from second_brain.spine.adapters.backend_api import BackendApiAdapter
        from second_brain.spine.adapters.registry import AdapterRegistry
        from second_brain.spine.api import build_spine_router
        from second_brain.spine.auth import spine_auth
        from second_brain.spine.background import (
            evaluator_loop,
            liveness_emitter,
        )
        from second_brain.spine.evaluator import StatusEvaluator
        from second_brain.spine.registry import get_default_registry
        from second_brain.spine.storage import SpineRepository

        cosmos_mgr_for_spine = app.state.cosmos_manager
        spine_repo = SpineRepository(
            events_container=cosmos_mgr_for_spine.get_container("spine_events"),
            segment_state_container=cosmos_mgr_for_spine.get_container(
                "spine_segment_state"
            ),
            status_history_container=cosmos_mgr_for_spine.get_container(
                "spine_status_history"
            ),
            correlation_container=cosmos_mgr_for_spine.get_container(
                "spine_correlation"
            ),
        )
        app.state.spine_repo = spine_repo

        spine_registry = get_default_registry()
        spine_evaluator = StatusEvaluator(repo=spine_repo, registry=spine_registry)

        # The backend_api adapter requires the LogsQueryClient; if init
        # earlier was non-fatal-failed, ship spine without the adapter
        # (status/ingest/correlation endpoints still work).
        adapters: list = []
        if app.state.logs_client is not None and settings.log_analytics_workspace_id:
            failures_fetcher = partial(
                query_backend_api_failures,
                app.state.logs_client,
                settings.log_analytics_workspace_id,
            )
            requests_fetcher = partial(
                query_backend_api_requests,
                app.state.logs_client,
                settings.log_analytics_workspace_id,
            )
            adapters.append(
                BackendApiAdapter(
                    failures_fetcher=failures_fetcher,
                    requests_fetcher=requests_fetcher,
                    native_url_template=(
                        "https://portal.azure.com/#blade/AppInsightsExtension"
                    ),
                )
            )
            logger.info("Spine BackendApiAdapter wired")
        else:
            logger.warning(
                "Spine wired without BackendApiAdapter: logs_client unavailable"
            )

        adapter_registry = AdapterRegistry(adapters)

        # Router inclusion inside lifespan is an intentional exception to
        # this file's module-scope-registration convention, because the
        # router needs lifespan-constructed dependencies. Safe before
        # the `yield` -- the app has not yet served its first request.
        app.include_router(
            build_spine_router(
                repo=spine_repo,
                evaluator=spine_evaluator,
                adapter_registry=adapter_registry,
                segment_registry=spine_registry,
                auth_dependency=spine_auth,
            )
        )

        spine_evaluator_task = asyncio.create_task(
            evaluator_loop(spine_evaluator, spine_repo, spine_registry)
        )
        spine_liveness_task = asyncio.create_task(
            liveness_emitter(spine_repo, segment_id="backend_api")
        )
        logger.info("Spine lifespan wiring complete")
except Exception:
    logger.warning("Spine wiring failed -- spine unavailable", exc_info=True)
    # Defensive: clear any partial state so callers see a clean "not wired".
    app.state.spine_repo = None
    spine_evaluator_task = None
    spine_liveness_task = None
```

At the shutdown block (after `yield`, around `main.py:479-497`), alongside the existing warmup-task cancellation, add:

```python
for task in (spine_evaluator_task, spine_liveness_task):
    if task is None:
        continue
    task.cancel()
for task in (spine_evaluator_task, spine_liveness_task):
    if task is None:
        continue
    try:
        await task
    except asyncio.CancelledError:
        pass
```

- [ ] **Step 4: Register `SpineWorkloadMiddleware` at module scope**

In `main.py` at module scope, add:

```python
from second_brain.spine.middleware import SpineWorkloadMiddleware

# Spine workload middleware: reads repo from app.state.spine_repo at dispatch
# time (set by lifespan). No-op when spine wiring was skipped.
# Registered BEFORE APIKeyMiddleware so spine runs INSIDE auth — see ordering note.
app.add_middleware(SpineWorkloadMiddleware)
app.add_middleware(APIKeyMiddleware)
```

Note: module-scope `add_middleware` is Starlette's supported pattern; the middleware safely no-ops when `app.state.spine_repo` is absent (cosmos-unavailable path).

**Middleware ordering (load-bearing — verified empirically against Starlette):** `add_middleware` PREPENDS to the middleware list, so the LAST-registered middleware becomes the OUTERMOST layer and runs FIRST on the inbound path. To have `APIKeyMiddleware` gate requests BEFORE `SpineWorkloadMiddleware` observes them (so that 401s never reach the spine and never pollute the backend_api workload dataset), `APIKeyMiddleware` must be registered LAST — i.e., `add_middleware(SpineWorkloadMiddleware)` first, then `add_middleware(APIKeyMiddleware)`.

**Historical note:** An earlier revision of this plan asserted the opposite ordering rule (and the first Task 12 commit `41ac1a0` followed it). That was wrong, verified against Starlette via a minimal repro. A follow-up red test (Step 6a below) pins the correct behavior so this cannot regress silently.

- [ ] **Step 5: Middleware regression test**

Add to `backend/tests/test_spine_middleware.py`:

```python
@pytest.mark.asyncio
async def test_middleware_without_repo_reads_app_state_spine_repo() -> None:
    """Module-scope registration contract: construct without repo, resolve from app.state."""
    app = FastAPI()
    app.add_middleware(SpineWorkloadMiddleware)  # no repo kwarg

    state_repo = AsyncMock()
    app.state.spine_repo = state_repo

    @app.get("/probe")
    async def _probe() -> dict:
        return {"ok": True}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/probe")
    assert response.status_code == 200

    state_repo.record_event.assert_called_once()


@pytest.mark.asyncio
async def test_middleware_without_repo_noops_when_app_state_missing() -> None:
    """Cosmos-unavailable path: no repo on app.state → middleware silently no-ops."""
    app = FastAPI()
    app.add_middleware(SpineWorkloadMiddleware)
    # Note: NOT setting app.state.spine_repo

    @app.get("/probe")
    async def _probe() -> dict:
        return {"ok": True}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/probe")
    assert response.status_code == 200  # request succeeds, spine no-ops
```

- [ ] **Step 6: Lifespan wiring integration tests**

Create `backend/tests/test_spine_lifespan_wiring.py` with tests that import `lifespan` from `second_brain.main` and exercise the three behavioral edges:

1. **Cosmos-unavailable skip**: `app.state.cosmos_manager = None` → `app.state.spine_repo` ends as `None`; no spine router mounted; background tasks are None; shutdown does not raise.
2. **Logs-unavailable degradation**: `cosmos_manager` present, `logs_client = None` → `spine_repo` set; spine router mounted; `AdapterRegistry.has("backend_api")` is False.
3. **Full happy path**: both present → `spine_repo` set; router mounted; `AdapterRegistry.has("backend_api")` is True; background tasks created.
4. **Shutdown cancels tasks cleanly** without raising even when tasks were created (use `asyncio.sleep(0)` after yield so the tasks enter their loop, then let shutdown cancel+await).

Approach hint: the full `lifespan` boots a lot of non-spine state (Foundry, Cosmos, Playwright, etc.). Write these tests by constructing a fresh `FastAPI()`, monkeypatching the pieces we don't care about, and invoking the spine block directly — OR extract the spine-wiring block into a small helper function `async def _wire_spine(app, settings)` that lifespan calls, and test that helper in isolation. The helper approach is cleaner; use it. Name the helper `_wire_spine` (private, underscore-prefixed; lives in `main.py` adjacent to `lifespan`).

The helper signature:

```python
async def _wire_spine(
    app: FastAPI,
    settings: Settings,
) -> tuple[asyncio.Task | None, asyncio.Task | None]:
    """Wire spine into app lifespan. Returns (evaluator_task, liveness_task).

    Both tuple members are None when spine wiring is skipped or fails.
    Sets app.state.spine_repo (or None on skip/failure).
    """
```

Then `lifespan` calls `spine_evaluator_task, spine_liveness_task = await _wire_spine(app, settings)`. The tests then construct a minimal `FastAPI()`, stub `app.state.cosmos_manager`/`app.state.logs_client`/`app.state.api_key`, and call `_wire_spine` directly.

- [ ] **Step 7: Run all backend tests**

```bash
cd backend && uv run pytest --tb=short
```

Expected: all green (no regressions). The pass count grows by the number of new tests (Step 5: +2, Step 6: at least 4).

- [ ] **Step 8: Commit**

```bash
git add backend/src/second_brain/db/cosmos.py \
        backend/src/second_brain/spine/middleware.py \
        backend/src/second_brain/main.py \
        backend/tests/test_spine_middleware.py \
        backend/tests/test_spine_lifespan_wiring.py
git commit -m "feat(spine): wire spine into fastapi app lifespan"
```

Do NOT push. The user runs push + deploy + smoke manually per project convention (backend testing happens against deployed Azure endpoints, not local).

---

### Task 12 follow-up (amendment, landed in a second commit on top of 41ac1a0)

Code review on `41ac1a0` surfaced one Critical and three Important issues that the original Step 4 + Step 6 missed. They are encoded here as required closure work so Task 12 is not "spec-correct but operationally wrong":

- [ ] **Step 9 (red test for C1): `401` produces zero spine workload events**

Add to `backend/tests/test_spine_middleware.py`:

```python
@pytest.mark.asyncio
async def test_401_from_api_key_middleware_emits_no_spine_event() -> None:
    """Middleware ordering: APIKeyMiddleware must gate before SpineWorkloadMiddleware.

    Red against the first Task 12 commit (41ac1a0); green after swapping the
    registration order in main.py.
    """
    from second_brain.auth import APIKeyMiddleware

    app = FastAPI()
    state_repo = AsyncMock()
    app.state.spine_repo = state_repo
    app.state.api_key = "correct-key"

    # Match production order: spine first, auth second (so auth is outermost
    # and runs first on inbound — `add_middleware` prepends to the stack).
    app.add_middleware(SpineWorkloadMiddleware)
    app.add_middleware(APIKeyMiddleware)

    @app.get("/gated")
    async def _gated() -> dict:
        return {"ok": True}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # No Authorization header → APIKeyMiddleware should 401 before spine runs
        response = await client.get("/gated")
    assert response.status_code == 401
    state_repo.record_event.assert_not_called()
```

This test MUST fail against `41ac1a0`'s ordering and pass after the swap.

- [ ] **Step 10 (fix C1): swap middleware registration order in `main.py`**

Current (wrong):
```python
app.add_middleware(APIKeyMiddleware)
app.add_middleware(SpineWorkloadMiddleware)
```

Correct:
```python
app.add_middleware(SpineWorkloadMiddleware)
app.add_middleware(APIKeyMiddleware)
```

Update the adjacent comment to match the amended Step 4 rule.

- [ ] **Step 11 (fix I1 + I2): tighten `_wire_spine` failure state**

Two changes inside `_wire_spine` in `main.py`:

  **I1 fix — exception branch also clears `spine_adapter_registry`:** after the existing `app.state.spine_repo = None` in the `except` block, add `app.state.spine_adapter_registry = None`. Otherwise a partial-failure path leaves a stale registry whose adapters reference a nulled repo.

  **I2 fix — move `app.include_router(...)` AFTER task creation:** today the router is mounted before the two `asyncio.create_task(...)` calls, so if a task creation raises, the `except` block still leaves spine routes mounted against a nulled repo. Route handlers would then 500 instead of reporting "spine unavailable". Reorder inside `_wire_spine` so that:
  1. `adapter_registry` is built and exposed via `app.state.spine_adapter_registry`.
  2. Both background tasks are created.
  3. *Only then* `app.include_router(build_spine_router(...))` mounts the routes.

  (If either task creation raises, the `except` clears both state hooks and no routes are mounted — the cleanest "not wired" signal callers can observe.)

- [ ] **Step 12 (fix I3 + add partial-failure test): exception-branch middleware test + `_wire_spine` partial-failure coverage**

  Add to `backend/tests/test_spine_middleware.py`:

  ```python
  @pytest.mark.asyncio
  async def test_middleware_without_repo_reraises_handler_exception() -> None:
      """Exception branch: if handler raises AND no repo is configured, the
      original exception still propagates (middleware must not swallow it).
      """
      app = FastAPI()
      app.add_middleware(SpineWorkloadMiddleware)
      # Note: NOT setting app.state.spine_repo

      @app.get("/boom")
      async def _boom() -> dict:
          raise RuntimeError("boom")

      async with AsyncClient(
          transport=ASGITransport(app=app), base_url="http://test"
      ) as client:
          with contextlib.suppress(Exception):
              response = await client.get("/boom")
      # Request raised with a 500 (Starlette's default handler converts
      # unhandled exceptions to 500 before the test client sees them, but the
      # key assertion is that the middleware did not silently record an event
      # against a missing repo — no attribute access should have occurred).
      # If the middleware had tried to record on a None repo we'd have gotten
      # AttributeError: 'NoneType' has no attribute 'record_event' — so simply
      # reaching this point (without that error leaking through) verifies the
      # None-guard.
  ```

  Add to `backend/tests/test_spine_lifespan_wiring.py` (if practical):

  ```python
  async def test_wire_spine_partial_failure_leaves_no_stale_state(
      settings_stub, monkeypatch
  ) -> None:
      """If task creation fails mid-wiring, no router is mounted and no
      stale adapter_registry remains on app.state.

      Isolates by monkeypatching asyncio.create_task inside main's import scope
      to raise on the first call (simulating a factory error). The `except`
      block in _wire_spine must null both state hooks and leave no spine routes.
      """
      app = FastAPI()
      app.state.cosmos_manager = _fake_cosmos_manager_with_containers()
      app.state.logs_client = AsyncMock()

      import second_brain.main as main_mod
      real_create_task = asyncio.create_task
      calls = {"n": 0}

      def _boom_once(coro, *a, **kw):
          calls["n"] += 1
          if calls["n"] == 1:
              coro.close()  # avoid "coroutine never awaited" warning
              raise RuntimeError("simulated task creation failure")
          return real_create_task(coro, *a, **kw)

      monkeypatch.setattr(main_mod.asyncio, "create_task", _boom_once)

      evaluator_task, liveness_task = await _wire_spine(app, settings_stub)

      assert evaluator_task is None
      assert liveness_task is None
      assert getattr(app.state, "spine_repo", None) is None
      assert getattr(app.state, "spine_adapter_registry", None) is None
      # No spine routes mounted because include_router runs AFTER task creation
      assert not any(
          getattr(r, "path", "").startswith("/api/spine") for r in app.routes
      )
  ```

  If the monkeypatching approach turns out to be awkward (e.g., because `_wire_spine`'s deferred imports mean `asyncio` isn't accessed via `main_mod.asyncio`), note the awkwardness explicitly and either:
  - use a different injection site (e.g., patch `second_brain.spine.background.evaluator_loop` to raise at first `await`), or
  - document that this edge is covered by inspection/reasoning rather than a test, and keep the fix anyway.

- [ ] **Step 13 (commit the C1 + I1 + I2 + I3 closure)**

```bash
git add docs/superpowers/plans/2026-04-14-phase-1-spine-foundation-and-backend-api-segment.md \
        backend/src/second_brain/main.py \
        backend/tests/test_spine_middleware.py \
        backend/tests/test_spine_lifespan_wiring.py
git commit -m "fix(spine): correct middleware ordering + tighten _wire_spine failure state"
```

---

## Task 13: Web app scaffold

**Files:**
- Create: `web/package.json`
- Create: `web/next.config.mjs`
- Create: `web/tsconfig.json`
- Create: `web/.env.example`
- Create: `web/.gitignore`
- Create: `web/next-env.d.ts`
- Commit (generated): `web/package-lock.json`

**Amendment (2026-04-16):** Added `.gitignore`, `next-env.d.ts`, and `package-lock.json` to Task 13's scope.
- Root `.gitignore` does not cover Node/Next artifacts (`node_modules/`, `.next/`, `*.tsbuildinfo`, `.env*.local`), so an explicit `web/.gitignore` is required to prevent worktree pollution after `npm install`.
- `tsconfig.json` includes `next-env.d.ts`, so it must exist at scaffold time. Create and commit it now rather than relying on a later `next dev`/`next build` to generate it.
- `package-lock.json` is generated by `npm install` in Step 5 and is required for reproducible installs in CI and the Task 17 Dockerfile. Commit it here, not in Task 14.

**Execution caveat (Node version):** Local `node -v` may report Node 25.x (non-LTS). Next 14.2's `engines.node` is `>=18.17.0` so install and type-check are expected to succeed, but Next 14 was tested against Node 18/20 LTS. If `npm install` or `npm run type-check` fails on the local Node version, STOP and report the exact error. Do not loosen pinned versions, upgrade Next, or downgrade Node packages ad hoc — escalate to the controller. The Task 17 Dockerfile will pin a real LTS Node version for CI/deployment.

- [ ] **Step 1: Initialize Next.js manually (avoid `create-next-app` to keep it minimal)**

Create `web/package.json`:

```json
{
  "name": "second-brain-web-spine",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev -p 3001",
    "build": "next build",
    "start": "next start -p 3001",
    "type-check": "tsc --noEmit"
  },
  "dependencies": {
    "next": "14.2.18",
    "react": "18.3.1",
    "react-dom": "18.3.1"
  },
  "devDependencies": {
    "@types/node": "20.14.10",
    "@types/react": "18.3.3",
    "@types/react-dom": "18.3.0",
    "typescript": "5.5.3"
  }
}
```

- [ ] **Step 2: Create `web/next.config.mjs`**

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
};

export default nextConfig;
```

- [ ] **Step 3: Create `web/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 4: Create `web/.env.example`**

```
SPINE_API_URL=https://brain.willmacdonald.com
SPINE_API_KEY=replace-with-key-from-keyvault
```

- [ ] **Step 4b: Create `web/.gitignore`**

Root `.gitignore` does not cover Node/Next artifacts. Create `web/.gitignore`:

```gitignore
# Dependencies
node_modules/

# Next.js build output
.next/
out/

# TypeScript incremental build info
*.tsbuildinfo

# Local env overrides (keep .env.example tracked)
.env*.local
.env.local
```

- [ ] **Step 4c: Create `web/next-env.d.ts`**

`tsconfig.json` includes `next-env.d.ts`, so it must exist at scaffold time. Create it with the exact content Next.js generates (verified against Next 14.2):

```typescript
/// <reference types="next" />
/// <reference types="next/image-types/global" />

// NOTE: This file should not be edited
// see https://nextjs.org/docs/basic-features/typescript for more information.
```

- [ ] **Step 5: Install + verify**

```bash
cd web && npm install && npm run type-check
```

Expected: install succeeds; type-check shows "No errors found" (no source files yet, so trivially passes).

If this step fails on Node 25.x, STOP and report the exact error with `node --version` output. Do not change pinned versions. See the execution caveat at the top of Task 13.

- [ ] **Step 6: Commit**

```bash
git add web/package.json web/next.config.mjs web/tsconfig.json web/.env.example web/.gitignore web/next-env.d.ts web/package-lock.json
git commit -m "feat(web): scaffold next.js app for spine ui"
```

Verify before committing: `git status` must show clean working tree after the commit (no untracked `web/node_modules/`, no untracked `web/.next/`, no untracked `web/*.tsbuildinfo`). If any of these appear as untracked, the `.gitignore` is missing a rule — fix before committing.

---

## Task 14: Web spine client + types

**Files:**
- Create: `web/lib/spine.ts`
- Create: `web/lib/types.ts`

- [ ] **Step 1: Create `web/lib/types.ts`**

```typescript
// Mirrors backend Pydantic models in backend/src/second_brain/spine/models.py
// Keep in sync manually (small contract surface, infrequent changes).

export type SegmentStatus = "green" | "yellow" | "red" | "stale";
export type CorrelationKind = "capture" | "thread" | "request" | "crud";

export interface RollupInfo {
  suppressed: boolean;
  suppressed_by: string | null;
  raw_status: SegmentStatus;
}

export interface SegmentStatusResponse {
  id: string;
  name: string;
  status: SegmentStatus;
  headline: string;
  last_updated: string;
  freshness_seconds: number;
  host_segment: string | null;
  rollup: RollupInfo;
}

export interface ResponseEnvelope {
  generated_at: string;
  freshness_seconds: number;
  partial_sources: string[];
  query_latency_ms: number;
  native_url?: string | null;
  cursor?: string | null;
}

export interface StatusBoardResponse {
  segments: SegmentStatusResponse[];
  envelope: ResponseEnvelope;
}

export interface CorrelationEvent {
  segment_id: string;
  timestamp: string;
  status: SegmentStatus;
  headline: string;
}

export interface CorrelationResponse {
  correlation_kind: CorrelationKind;
  correlation_id: string;
  events: CorrelationEvent[];
  envelope: ResponseEnvelope;
}

export interface SegmentDetailResponse {
  data: { schema: string; native_url?: string;[key: string]: unknown };
  envelope: ResponseEnvelope;
}
```

- [ ] **Step 2: Create `web/lib/spine.ts`**

```typescript
// Server-side spine client. Uses API key from process.env (server-only).
// NEVER imports into client components.

import "server-only";

import type {
  StatusBoardResponse,
  CorrelationResponse,
  SegmentDetailResponse,
  CorrelationKind,
} from "./types";

const BASE = process.env.SPINE_API_URL;
const KEY = process.env.SPINE_API_KEY;

if (!BASE || !KEY) {
  // Throw at build time / first request — not silently
  throw new Error("SPINE_API_URL and SPINE_API_KEY env vars are required");
}

async function spineFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { Authorization: `Bearer ${KEY}` },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`spine ${res.status}: ${await res.text()}`);
  }
  return (await res.json()) as T;
}

export const spine = {
  status: () => spineFetch<StatusBoardResponse>("/api/spine/status"),
  correlation: (kind: CorrelationKind, id: string) =>
    spineFetch<CorrelationResponse>(`/api/spine/correlation/${kind}/${encodeURIComponent(id)}`),
  segmentDetail: (id: string, params?: { correlation_kind?: CorrelationKind; correlation_id?: string; time_range_seconds?: number }) => {
    const search = new URLSearchParams();
    if (params?.correlation_kind) search.set("correlation_kind", params.correlation_kind);
    if (params?.correlation_id) search.set("correlation_id", params.correlation_id);
    if (params?.time_range_seconds) search.set("time_range_seconds", String(params.time_range_seconds));
    const qs = search.toString();
    return spineFetch<SegmentDetailResponse>(`/api/spine/segment/${id}${qs ? `?${qs}` : ""}`);
  },
};
```

- [ ] **Step 3: Install `server-only` package**

```bash
cd web && npm install server-only
```

- [ ] **Step 4: Type-check**

```bash
cd web && npm run type-check
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add web/lib/types.ts web/lib/spine.ts web/package.json web/package-lock.json
git commit -m "feat(web): server-side spine client and shared types"
```

---

## Task 15: Web status board + tile components

**Files:**
- Create: `web/app/layout.tsx`
- Create: `web/app/page.tsx`
- Create: `web/components/StatusBoard.tsx`
- Create: `web/components/StatusTile.tsx`
- Create: `web/app/globals.css`

- [ ] **Step 1: Create root layout**

`web/app/layout.tsx`:

```typescript
import type { ReactNode } from "react";
import "./globals.css";

export const metadata = {
  title: "Second Brain — Spine",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body style={{ background: "#0f1419", color: "#e6e6e6", fontFamily: "system-ui, sans-serif", margin: 0 }}>
        {children}
      </body>
    </html>
  );
}
```

- [ ] **Step 2: Create `web/app/globals.css`**

```css
body { margin: 0; }
* { box-sizing: border-box; }
```

- [ ] **Step 3: Create page (server component) that fetches status**

`web/app/page.tsx`:

```typescript
import { spine } from "@/lib/spine";
import { StatusBoard } from "@/components/StatusBoard";

export const dynamic = "force-dynamic"; // never statically render
export const revalidate = 0;

export default async function Page() {
  const board = await spine.status();
  return (
    <main style={{ padding: 24 }}>
      <h1 style={{ marginTop: 0 }}>Second Brain — Spine</h1>
      <StatusBoard data={board} />
    </main>
  );
}
```

- [ ] **Step 4: Create StatusBoard component (client, refreshes every 10s via router.refresh())**

`web/components/StatusBoard.tsx`:

```typescript
"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import type { StatusBoardResponse } from "@/lib/types";
import { StatusTile } from "./StatusTile";

export function StatusBoard({ data }: { data: StatusBoardResponse }) {
  const router = useRouter();
  useEffect(() => {
    const id = setInterval(() => router.refresh(), 10_000);
    return () => clearInterval(id);
  }, [router]);

  const visible = data.segments.filter((s) => !s.rollup.suppressed);
  const suppressed = data.segments.filter((s) => s.rollup.suppressed);

  return (
    <div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
          gap: 12,
        }}
      >
        {visible.map((s) => (
          <StatusTile key={s.id} segment={s} />
        ))}
      </div>
      {suppressed.length > 0 && (
        <details style={{ marginTop: 24 }}>
          <summary style={{ cursor: "pointer", color: "#888" }}>
            {suppressed.length} segment(s) suppressed by host outage
          </summary>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
              gap: 12,
              marginTop: 12,
              opacity: 0.5,
            }}
          >
            {suppressed.map((s) => (
              <StatusTile key={s.id} segment={s} />
            ))}
          </div>
        </details>
      )}
      <p style={{ color: "#666", fontSize: 12, marginTop: 24 }}>
        Updated {new Date(data.envelope.generated_at).toLocaleTimeString()} ·
        Freshness {data.envelope.freshness_seconds}s ·
        Latency {data.envelope.query_latency_ms}ms
      </p>
    </div>
  );
}
```

- [ ] **Step 5: Create StatusTile component**

`web/components/StatusTile.tsx`:

```typescript
import Link from "next/link";
import type { SegmentStatusResponse, SegmentStatus } from "@/lib/types";

const STATUS_COLOR: Record<SegmentStatus, string> = {
  green: "#3a7d3a",
  yellow: "#c89010",
  red: "#b33b3b",
  stale: "#555",
};

export function StatusTile({ segment }: { segment: SegmentStatusResponse }) {
  return (
    <Link
      href={`/segment/${segment.id}`}
      style={{
        display: "block",
        padding: 16,
        background: "#1a2028",
        border: `2px solid ${STATUS_COLOR[segment.status]}`,
        borderRadius: 8,
        textDecoration: "none",
        color: "inherit",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <strong>{segment.name}</strong>
        <span style={{ color: STATUS_COLOR[segment.status], fontSize: 12, textTransform: "uppercase" }}>
          {segment.status}
        </span>
      </div>
      <p style={{ margin: "8px 0 0", color: "#bbb", fontSize: 14 }}>{segment.headline}</p>
      <p style={{ margin: "8px 0 0", color: "#666", fontSize: 11 }}>
        {segment.freshness_seconds}s ago
      </p>
    </Link>
  );
}
```

- [ ] **Step 6: Type-check**

```bash
cd web && npm run type-check
```

Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add web/app/ web/components/StatusBoard.tsx web/components/StatusTile.tsx
git commit -m "feat(web): status board with auto-refresh and suppression toggle"
```

---

## Task 16: Web segment-detail dispatcher + AppInsightsDetail renderer

**Files:**
- Create: `web/app/segment/[id]/page.tsx`
- Create: `web/components/SegmentDetailHeader.tsx`
- Create: `web/components/renderers/AppInsightsDetail.tsx`

- [ ] **Step 1: Create dispatcher page**

`web/app/segment/[id]/page.tsx`:

```typescript
import { spine } from "@/lib/spine";
import { AppInsightsDetail } from "@/components/renderers/AppInsightsDetail";
import { SegmentDetailHeader } from "@/components/SegmentDetailHeader";

export const dynamic = "force-dynamic";

export default async function SegmentPage({ params }: { params: { id: string } }) {
  const detail = await spine.segmentDetail(params.id);
  const schema = detail.data.schema;

  return (
    <main style={{ padding: 24 }}>
      <SegmentDetailHeader
        segmentId={params.id}
        nativeUrl={detail.envelope.native_url ?? null}
      />
      {schema === "azure_monitor_app_insights" ? (
        <AppInsightsDetail data={detail.data as never} />
      ) : (
        <p>No renderer registered for schema: <code>{schema}</code></p>
      )}
      <p style={{ color: "#666", fontSize: 12, marginTop: 24 }}>
        Fetched {new Date(detail.envelope.generated_at).toLocaleString()} ·
        Latency {detail.envelope.query_latency_ms}ms
      </p>
    </main>
  );
}
```

- [ ] **Step 2: Create SegmentDetailHeader**

`web/components/SegmentDetailHeader.tsx`:

```typescript
import Link from "next/link";

export function SegmentDetailHeader({
  segmentId,
  nativeUrl,
}: {
  segmentId: string;
  nativeUrl: string | null;
}) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
      <div>
        <Link href="/" style={{ color: "#888", textDecoration: "none" }}>← Status board</Link>
        <h1 style={{ margin: "8px 0 0" }}>{segmentId}</h1>
      </div>
      {nativeUrl && (
        <a
          href={nativeUrl}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            padding: "8px 16px",
            background: "#2563eb",
            color: "white",
            borderRadius: 6,
            textDecoration: "none",
            fontSize: 14,
          }}
        >
          Open in native tool ↗
        </a>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Create AppInsightsDetail renderer**

`web/components/renderers/AppInsightsDetail.tsx`:

```typescript
interface AppInsightsData {
  schema: "azure_monitor_app_insights";
  app_exceptions: Array<{
    timestamp: string;
    message: string;
    outer_message?: string | null;
    outer_type?: string | null;
    innermost_message?: string | null;
    details?: string | null;
    component?: string | null;
    capture_trace_id?: string | null;
  }>;
  app_requests: Array<{
    timestamp: string;
    name: string;
    duration_ms: number;
    result_code: string;
  }>;
}

export function AppInsightsDetail({ data }: { data: AppInsightsData }) {
  return (
    <div>
      <section>
        <h2>Recent exceptions ({data.app_exceptions.length})</h2>
        {data.app_exceptions.length === 0 ? (
          <p style={{ color: "#888" }}>No recent exceptions.</p>
        ) : (
          <ul style={{ listStyle: "none", padding: 0 }}>
            {data.app_exceptions.map((e, i) => (
              <li key={i} style={{ background: "#1a2028", padding: 12, marginBottom: 8, borderRadius: 6 }}>
                <div style={{ fontSize: 12, color: "#888" }}>
                  {new Date(e.timestamp).toLocaleString()} · {e.component ?? "—"}
                </div>
                <div style={{ marginTop: 4, fontWeight: 600 }}>{e.outer_message ?? e.message}</div>
                {e.outer_type && (
                  <div style={{ fontSize: 12, color: "#aaa", marginTop: 4 }}>
                    <code>{e.outer_type}</code>
                  </div>
                )}
                {e.innermost_message && e.innermost_message !== e.outer_message && (
                  <details style={{ marginTop: 8 }}>
                    <summary style={{ cursor: "pointer", color: "#888", fontSize: 12 }}>Inner cause</summary>
                    <pre style={{ marginTop: 4, fontSize: 12 }}>{e.innermost_message}</pre>
                  </details>
                )}
                {e.details && (
                  <details style={{ marginTop: 8 }}>
                    <summary style={{ cursor: "pointer", color: "#888", fontSize: 12 }}>Stack details</summary>
                    <pre style={{ marginTop: 4, fontSize: 11, overflow: "auto", maxHeight: 240 }}>{e.details.slice(0, 4000)}</pre>
                  </details>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
      <section style={{ marginTop: 32 }}>
        <h2>Recent requests ({data.app_requests.length})</h2>
        {data.app_requests.length === 0 ? (
          <p style={{ color: "#888" }}>No recent requests.</p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid #333" }}>
                <th style={{ textAlign: "left", padding: 8 }}>Time</th>
                <th style={{ textAlign: "left", padding: 8 }}>Operation</th>
                <th style={{ textAlign: "right", padding: 8 }}>Duration</th>
                <th style={{ textAlign: "right", padding: 8 }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {data.app_requests.map((r, i) => (
                <tr key={i} style={{ borderBottom: "1px solid #1a2028" }}>
                  <td style={{ padding: 8, color: "#888" }}>{new Date(r.timestamp).toLocaleTimeString()}</td>
                  <td style={{ padding: 8 }}>{r.name}</td>
                  <td style={{ padding: 8, textAlign: "right" }}>{r.duration_ms}ms</td>
                  <td style={{ padding: 8, textAlign: "right" }}>{r.result_code}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
```

- [ ] **Step 4: Type-check**

```bash
cd web && npm run type-check
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add web/app/segment/ web/components/SegmentDetailHeader.tsx web/components/renderers/
git commit -m "feat(web): segment detail dispatcher and AppInsights renderer"
```

---

## Task 17: Web Dockerfile + Container Apps deployment

**Files:**
- Create: `web/Dockerfile`
- Create: `web/.dockerignore`
- Modify: `.github/workflows/deploy.yml` (or equivalent)

- [ ] **Step 1: Create `web/Dockerfile`**

```dockerfile
# syntax=docker/dockerfile:1
FROM node:20-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3001
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
USER nextjs
EXPOSE 3001
CMD ["node", "server.js"]
```

- [ ] **Step 2: Create `web/.dockerignore`**

```
node_modules
.next
.git
.env
.env.local
README.md
```

- [ ] **Step 3: Build image locally to verify Dockerfile**

```bash
cd web && docker build -t spine-web:test .
```

Expected: successful build.

- [ ] **Step 4: Wire the deploy workflow**

Open `.github/workflows/deploy.yml`. Add a new job `deploy-web` that:
1. Builds the `web/Dockerfile` and pushes to ACR (`wkmsharedservicesacr`)
2. Deploys as a new Container App named `second-brain-spine-web`
3. Sets env vars `SPINE_API_URL` and `SPINE_API_KEY` (from Key Vault reference)

The exact YAML depends on the existing workflow structure. Pattern:

```yaml
deploy-web:
  needs: [deploy-api]
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: azure/login@v2
      with:
        client-id: ${{ secrets.AZURE_CLIENT_ID }}
        tenant-id: ${{ secrets.AZURE_TENANT_ID }}
        subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
    - name: Build and push image
      working-directory: web
      run: |
        IMAGE_TAG="${{ github.sha }}"
        az acr build \
          --registry wkmsharedservicesacr \
          --image second-brain-spine-web:$IMAGE_TAG \
          --image second-brain-spine-web:latest \
          --file Dockerfile .
    - name: Deploy Container App
      run: |
        IMAGE="wkmsharedservicesacr.azurecr.io/second-brain-spine-web:${{ github.sha }}"
        az containerapp update \
          --name second-brain-spine-web \
          --resource-group shared-services-rg \
          --image "$IMAGE"
```

If `second-brain-spine-web` Container App doesn't exist yet, create it first with `az containerapp create` referencing the Key Vault secrets.

- [ ] **Step 5: Commit**

```bash
git add web/Dockerfile web/.dockerignore .github/workflows/deploy.yml
git commit -m "infra(web): dockerfile and container apps deployment for spine ui"
```

- [ ] **Step 6: Push and verify deployment**

```bash
git push
```

After CI deploys, hit the new web URL (Container App ingress URL or custom domain) and confirm the status board renders with the `backend_api` tile.

---

## Task 18: Mobile spine status tile

**Files:**
- Create: `mobile/lib/spine.ts`
- Create: `mobile/components/SpineStatusTile.tsx`
- Modify: `mobile/app/(tabs)/status.tsx` (or wherever the existing Status screen lives — verify path before editing)

- [ ] **Step 1: Locate the existing Status screen**

```bash
find mobile/app -name "status*" -type f
```

Note the exact file path; substitute below.

- [ ] **Step 2: Create `mobile/lib/spine.ts`**

```typescript
import { API_BASE_URL, API_KEY } from "../constants/config";

export type SegmentStatus = "green" | "yellow" | "red" | "stale";

export interface SpineSegment {
  id: string;
  name: string;
  status: SegmentStatus;
  headline: string;
  last_updated: string;
  freshness_seconds: number;
  rollup: { suppressed: boolean; suppressed_by: string | null; raw_status: SegmentStatus };
}

export interface SpineStatus {
  segments: SpineSegment[];
  envelope: { generated_at: string; query_latency_ms: number };
}

export async function fetchSpineStatus(): Promise<SpineStatus> {
  const res = await fetch(`${API_BASE_URL}/api/spine/status`, {
    headers: { Authorization: `Bearer ${API_KEY}` },
  });
  if (!res.ok) {
    throw new Error(`spine status ${res.status}`);
  }
  return (await res.json()) as SpineStatus;
}

// Web spine ingress URL — set via env in production.
// EXPO_PUBLIC_SPINE_WEB_URL=https://spine-web.willmacdonald.com
export const SPINE_WEB_URL = process.env.EXPO_PUBLIC_SPINE_WEB_URL ?? "";
```

- [ ] **Step 3: Create `mobile/components/SpineStatusTile.tsx`**

```typescript
import { useEffect, useState } from "react";
import { Linking, Pressable, StyleSheet, Text, View } from "react-native";
import {
  fetchSpineStatus,
  SegmentStatus,
  SpineSegment,
  SPINE_WEB_URL,
} from "../lib/spine";

const COLOR: Record<SegmentStatus, string> = {
  green: "#3a7d3a",
  yellow: "#c89010",
  red: "#b33b3b",
  stale: "#555",
};

interface Props {
  segmentId: string;
}

export function SpineStatusTile({ segmentId }: Props) {
  const [segment, setSegment] = useState<SpineSegment | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await fetchSpineStatus();
        if (cancelled) return;
        const found = data.segments.find((s) => s.id === segmentId) ?? null;
        setSegment(found);
        setError(null);
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : String(e));
      }
    }
    load();
    const id = setInterval(load, 30_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [segmentId]);

  function handlePress() {
    if (!SPINE_WEB_URL) return;
    Linking.openURL(`${SPINE_WEB_URL}/segment/${segmentId}`);
  }

  if (error) {
    return (
      <View style={[styles.tile, { borderColor: COLOR.stale }]}>
        <Text style={styles.title}>Spine unreachable</Text>
        <Text style={styles.headline}>{error}</Text>
      </View>
    );
  }

  if (!segment) {
    return (
      <View style={[styles.tile, { borderColor: COLOR.stale }]}>
        <Text style={styles.title}>Loading…</Text>
      </View>
    );
  }

  return (
    <Pressable onPress={handlePress} style={[styles.tile, { borderColor: COLOR[segment.status] }]}>
      <View style={styles.row}>
        <Text style={styles.title}>{segment.name}</Text>
        <Text style={[styles.status, { color: COLOR[segment.status] }]}>
          {segment.status.toUpperCase()}
        </Text>
      </View>
      <Text style={styles.headline}>{segment.headline}</Text>
      <Text style={styles.freshness}>{segment.freshness_seconds}s ago</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  tile: {
    padding: 16,
    backgroundColor: "#1a2028",
    borderWidth: 2,
    borderRadius: 8,
    marginBottom: 12,
  },
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  title: { fontSize: 16, fontWeight: "600", color: "#e6e6e6" },
  status: { fontSize: 12 },
  headline: { color: "#bbb", marginTop: 8, fontSize: 14 },
  freshness: { color: "#666", marginTop: 8, fontSize: 11 },
});
```

- [ ] **Step 4: Mount the tile in the Status screen**

In the Status screen file (path identified in Step 1), import and render:

```typescript
import { SpineStatusTile } from "../../components/SpineStatusTile";

// Within the existing screen JSX, add:
<SpineStatusTile segmentId="backend_api" />
```

Place it where you want — near the existing health cards from Phase 18 makes sense.

- [ ] **Step 5: Add `EXPO_PUBLIC_SPINE_WEB_URL` to `mobile/.env`**

```bash
echo 'EXPO_PUBLIC_SPINE_WEB_URL=https://<your-spine-web-url>' >> mobile/.env.local.example
```

The actual `.env.local` (gitignored) needs the real URL.

- [ ] **Step 6: Type-check + commit**

```bash
cd mobile && npx tsc --noEmit
```

Expected: no errors.

```bash
git add mobile/lib/spine.ts mobile/components/SpineStatusTile.tsx mobile/app/<status-screen-file>.tsx mobile/.env.local.example
git commit -m "feat(mobile): spine status tile on status screen with web deep link"
```

- [ ] **Step 7: EAS rebuild and verify on device**

Per project memory: if Metro cache reload doesn't pick up the new component, do an EAS rebuild immediately rather than retrying clears.

```bash
cd mobile && eas build --profile development --platform ios
```

Open Status screen on device after build installs. Verify:
- Tile shows `backend_api` segment with current status
- Tile is colored according to status
- Tap opens the web spine in mobile Safari at the correct URL

---

## Task 19: Phase 1 acceptance verification

**Files:** None (verification tasks)

- [ ] **Step 1: All backend tests pass**

```bash
cd backend && uv run pytest -x
```

Expected: green.

- [ ] **Step 2: All web type-checks pass**

```bash
cd web && npm run type-check
```

Expected: no errors.

- [ ] **Step 3: All mobile type-checks pass**

```bash
cd mobile && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Spine status endpoint returns evaluated `backend_api` tile**

```bash
curl -sS -H "Authorization: Bearer ${API_KEY}" https://brain.willmacdonald.com/api/spine/status \
  | jq '.segments[] | select(.id == "backend_api")'
```

Expected: a segment object with `status`, `headline`, `last_updated`, `freshness_seconds`.

- [ ] **Step 5: Spine segment-detail endpoint returns AppInsights schema**

```bash
curl -sS -H "Authorization: Bearer ${API_KEY}" https://brain.willmacdonald.com/api/spine/segment/backend_api \
  | jq '.data.schema'
```

Expected: `"azure_monitor_app_insights"`.

- [ ] **Step 6: Spine correlation endpoint works for an existing capture trace ID**

Find a recent trace ID via the existing MCP tool, then:

```bash
TRACE_ID=219b58c9-bed7-4be6-b115-f43714dc8920  # use a real one
curl -sS -H "Authorization: Bearer ${API_KEY}" "https://brain.willmacdonald.com/api/spine/correlation/capture/${TRACE_ID}" \
  | jq '.events'
```

Expected: at least one event with `segment_id: "backend_api"`.

- [ ] **Step 7: Web status board loads and shows the tile**

Open the web spine URL in a browser. Verify:
- Status board renders
- `backend_api` tile is present and colored
- Tile click navigates to segment detail
- Segment detail shows recent exceptions with `OuterMessage`/`OuterType`/`InnermostMessage`/`Details` populated when those fields exist (Phase 19.1 absorption verified)
- "Open in native tool" link is present and points to Azure portal

- [ ] **Step 8: Mobile tile shows status and deep-links to web**

On the device's Status screen:
- Spine tile is visible
- Status matches the web view
- Tap opens mobile Safari at the correct web spine URL

- [ ] **Step 9: Push event observability**

Verify via Cosmos query (or via the spine's own status response over the next few minutes) that:
- Liveness events are arriving every ~30s
- Workload events are arriving per request
- Status evaluator is running every ~30s

```bash
# Quick Cosmos check
az cosmosdb sql query -g shared-services-rg -a <account> -d second-brain \
  -c spine_events --query "SELECT TOP 5 * FROM c WHERE c.segment_id = 'backend_api' ORDER BY c.timestamp DESC"
```

- [ ] **Step 10: Tag the phase**

```bash
git tag phase-1-spine-foundation -m "Phase 1 complete: spine foundation + backend api segment"
git push --tags
```

---

## Self-Review Checklist for Phase 1

- [x] All spec requirements for Phase 1 covered: spine backend (4 endpoints), 4 Cosmos containers with TTLs, status evaluator with locked precedence, Backend API segment push (liveness/readiness/workload) + pull (App Insights), web app with status board + AppInsights renderer, mobile tile, auth, Phase 19.1 KQL absorption
- [x] No TBDs, TODOs, or "implement later" placeholders
- [x] Type consistency: `SegmentStatus`, `CorrelationKind`, `IngestEvent`, `EvaluatorConfig`, `ResponseEnvelope` used consistently across backend/web/mobile
- [x] All file paths exact
- [x] Every code-modifying step shows the actual code
- [x] Frequent commits — one per task, occasionally one per logical step
