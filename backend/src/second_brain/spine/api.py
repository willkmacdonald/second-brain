"""Spine HTTP API: 4 endpoints under /api/spine/*."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from second_brain.spine.adapters.registry import AdapterRegistry
from second_brain.spine.audit.models import AuditReport, build_summary
from second_brain.spine.audit.walker import CorrelationAuditor
from second_brain.spine.evaluator import StatusEvaluator
from second_brain.spine.models import (
    STALE_FRESHNESS_SECONDS,
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
    parse_cosmos_ts,
)
from second_brain.spine.registry import SegmentRegistry
from second_brain.spine.storage import SpineRepository


class AuditRequest(BaseModel):
    """Request body for POST /api/spine/audit/correlation."""

    correlation_kind: CorrelationKind
    correlation_id: str | None = None
    sample_size: int = Field(5, ge=1, le=20)
    time_range_seconds: int = Field(86400, ge=60, le=604800)  # 1min - 7d


def build_spine_router(
    repo: SpineRepository,
    evaluator: StatusEvaluator,
    adapter_registry: AdapterRegistry,
    segment_registry: SegmentRegistry,
    auth_dependency: Callable[..., Awaitable[None]],
    auditor: CorrelationAuditor | None = None,
) -> APIRouter:
    """Build the /api/spine router with injected dependencies."""

    # `evaluator` is accepted for construction parity with Task 11's
    # background loop; the endpoints read pre-computed state from the
    # segment_state container instead of evaluating on demand.

    router = APIRouter(prefix="/api/spine", tags=["spine"])

    @router.post("/ingest", status_code=204, dependencies=[Depends(auth_dependency)])
    async def ingest(event: IngestEvent) -> None:
        await repo.record_event(event)
        return None

    @router.get(
        "/status",
        response_model=StatusBoardResponse,
        dependencies=[Depends(auth_dependency)],
    )
    async def status() -> StatusBoardResponse:
        start = time.perf_counter()
        states = await repo.get_all_segment_states()
        states_by_id = {s["segment_id"]: s for s in states}

        # Determine which segments are hosted by a red host (suppression)
        red_hosts = {s["segment_id"] for s in states if s.get("status") == "red"}

        segments_out: list[SegmentStatusResponse] = []
        max_freshness = 0
        now = datetime.now(UTC)

        for cfg in segment_registry.all():
            state = states_by_id.get(cfg.segment_id)
            if not state:
                # No state yet - show as stale
                segments_out.append(
                    SegmentStatusResponse(
                        id=cfg.segment_id,
                        name=cfg.name_or_id(),
                        status="stale",
                        headline="No data yet",
                        last_updated=now,
                        freshness_seconds=STALE_FRESHNESS_SECONDS,
                        host_segment=cfg.host_segment,
                        rollup=RollupInfo(
                            suppressed=False,
                            suppressed_by=None,
                            raw_status="stale",
                        ),
                    )
                )
                continue

            raw_status: SegmentStatus = state["status"]
            last_updated = parse_cosmos_ts(state["last_updated"])
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
    async def correlation(
        kind: CorrelationKind, correlation_id: str
    ) -> CorrelationResponse:
        start = time.perf_counter()
        events = await repo.get_correlation_events(kind, correlation_id)
        latency_ms = int((time.perf_counter() - start) * 1000)
        return CorrelationResponse(
            correlation_kind=kind,
            correlation_id=correlation_id,
            events=[
                CorrelationEvent(
                    segment_id=e["segment_id"],
                    timestamp=parse_cosmos_ts(e["timestamp"]),
                    status=e["status"],
                    headline=e["headline"],
                )
                for e in events
            ],
            envelope=ResponseEnvelope(
                generated_at=datetime.now(UTC),
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
            raise HTTPException(
                404, f"No adapter registered for segment '{segment_id}'"
            )
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
                generated_at=datetime.now(UTC),
                freshness_seconds=0,
                partial_sources=[],
                query_latency_ms=latency_ms,
                native_url=data.get("native_url"),
            ),
        )

    @router.post(
        "/audit/correlation",
        response_model=AuditReport,
        dependencies=[Depends(auth_dependency)],
    )
    async def audit_correlation(req: AuditRequest) -> AuditReport:
        if auditor is None:
            raise HTTPException(503, "Audit not configured")
        if req.correlation_id:
            trace = await auditor.audit(
                kind=req.correlation_kind,
                correlation_id=req.correlation_id,
                time_range_seconds=req.time_range_seconds,
            )
            summary = build_summary([trace])
            return AuditReport(
                correlation_kind=req.correlation_kind,
                sample_size_requested=1,
                sample_size_returned=1,
                time_range_seconds=req.time_range_seconds,
                traces=[trace],
                summary=summary,
            )
        return await auditor.audit_sample(
            kind=req.correlation_kind,
            sample_size=req.sample_size,
            time_range_seconds=req.time_range_seconds,
        )

    return router
