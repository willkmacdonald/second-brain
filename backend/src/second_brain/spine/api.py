"""Spine HTTP API: endpoints under /api/spine/*."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from second_brain.spine.adapters.registry import AdapterRegistry
from second_brain.spine.audit.models import AuditReport, build_summary
from second_brain.spine.audit.walker import CorrelationAuditor
from second_brain.spine.evaluator import StatusEvaluator
from second_brain.spine.ledger_policy import (
    LEDGER_EXPECTED_CHAINS,
    ledger_metadata_for,
)
from second_brain.spine.models import (
    STALE_FRESHNESS_SECONDS,
    CorrelationEvent,
    CorrelationKind,
    CorrelationResponse,
    IngestEvent,
    ResponseEnvelope,
    RollupInfo,
    SegmentDetailResponse,
    SegmentLedgerResponse,
    SegmentStatus,
    SegmentStatusResponse,
    StatusBoardResponse,
    TransactionEvent,
    TransactionLedgerRow,
    TransactionPathResponse,
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

    # -----------------------------------------------------------------------
    # Phase 19.2 — Transaction ledger read paths
    # -----------------------------------------------------------------------

    @router.get(
        "/ledger/segment/{segment_id}",
        response_model=SegmentLedgerResponse,
        dependencies=[Depends(auth_dependency)],
    )
    async def segment_ledger(
        segment_id: str,
        window_seconds: int = Query(3600, ge=60, le=86400),  # 1 min - 1 day
        limit: int = Query(50, ge=1, le=200),
    ) -> SegmentLedgerResponse:
        """Return correlated workload events for a segment, newest-first.

        Carries purposeful empty-state metadata so native-only segments render
        a clear reason (e.g. "Cosmos emits no workload events by design")
        instead of looking silently broken.
        """
        start = time.perf_counter()
        raw = await repo.get_recent_transaction_events(
            segment_id=segment_id,
            window_seconds=window_seconds,
            limit=limit,
        )
        metadata = ledger_metadata_for(segment_id)
        rows: list[TransactionLedgerRow] = []
        for r in raw:
            payload = r.get("payload", {})
            rows.append(
                TransactionLedgerRow(
                    segment_id=r["segment_id"],
                    timestamp=parse_cosmos_ts(r["timestamp"]),
                    operation=payload["operation"],
                    outcome=payload["outcome"],
                    duration_ms=payload["duration_ms"],
                    correlation_kind=payload.get("correlation_kind"),
                    correlation_id=payload.get("correlation_id"),
                    error_class=payload.get("error_class"),
                )
            )
        latency_ms = int((time.perf_counter() - start) * 1000)
        return SegmentLedgerResponse(
            segment_id=segment_id,
            mode=metadata["mode"],
            empty_state_reason=metadata["empty_state_reason"],
            rows=rows,
            envelope=ResponseEnvelope(
                generated_at=datetime.now(UTC),
                freshness_seconds=0,
                partial_sources=[],
                query_latency_ms=latency_ms,
            ),
        )

    @router.get(
        "/ledger/correlation/{kind}/{correlation_id}",
        response_model=TransactionPathResponse,
        dependencies=[Depends(auth_dependency)],
    )
    async def transaction_path(
        kind: CorrelationKind,
        correlation_id: str,
        window_seconds: int = Query(86400, ge=60, le=604800),  # 1 min - 7 days
    ) -> TransactionPathResponse:
        """Return the full cross-segment transaction path for one correlation id.

        RESEARCH Option A enrichment: join `spine_correlation` (which segments)
        with `spine_events` (duration/operation) in the read path — no schema
        change to the correlation container.

        Gaps are reported explicitly via `missing_required` /
        `present_optional` / `unexpected` derived from
        `LEDGER_EXPECTED_CHAINS` (the operator-facing ledger policy, NOT the
        raw audit registry).
        """
        start = time.perf_counter()
        # "Which segments" — from spine_correlation (sorted ASC by timestamp
        # by the repository).
        corr_rows = await repo.get_correlation_events(kind, correlation_id)
        # "Operation/duration enrichment" — from spine_events filtered by
        # correlation within the window.
        raw_events = await repo.get_workload_events_for_correlation(
            correlation_kind=kind,
            correlation_id=correlation_id,
            window_seconds=window_seconds,
        )
        # Index raw events by (segment_id, timestamp) for the enrichment join.
        raw_by_segment_ts: dict[tuple[str, str], dict[str, Any]] = {
            (e["segment_id"], e["timestamp"]): e for e in raw_events
        }
        events: list[TransactionEvent] = []
        for cr in corr_rows:
            key = (cr["segment_id"], cr["timestamp"])
            raw = raw_by_segment_ts.get(key)
            payload = raw.get("payload", {}) if raw else {}
            events.append(
                TransactionEvent(
                    segment_id=cr["segment_id"],
                    timestamp=parse_cosmos_ts(cr["timestamp"]),
                    status=cr["status"],
                    headline=cr["headline"],
                    operation=payload.get("operation"),
                    outcome=payload.get("outcome"),
                    duration_ms=payload.get("duration_ms"),
                    error_class=payload.get("error_class"),
                )
            )
        # Explicit gap reporting — use operator-facing ledger policy.
        chain = LEDGER_EXPECTED_CHAINS[kind]
        chain_ids = {s.segment_id for s in chain}
        required = {s.segment_id for s in chain if s.required}
        optional = {s.segment_id for s in chain if not s.required}
        segments_seen = {e.segment_id for e in events}
        missing_required = sorted(required - segments_seen)
        present_optional = sorted(optional & segments_seen)
        unexpected = sorted(segments_seen - chain_ids)
        latency_ms = int((time.perf_counter() - start) * 1000)
        return TransactionPathResponse(
            correlation_kind=kind,
            correlation_id=correlation_id,
            events=events,
            missing_required=missing_required,
            present_optional=present_optional,
            unexpected=unexpected,
            envelope=ResponseEnvelope(
                generated_at=datetime.now(UTC),
                freshness_seconds=0,
                partial_sources=[],
                query_latency_ms=latency_ms,
            ),
        )

    return router
