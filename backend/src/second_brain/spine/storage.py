"""Cosmos repository for spine state, events, history, and correlation."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
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
        """Append an ingest event and (for workloads with correlation)
        a correlation record.
        """
        inner = (
            event.root
        )  # the concrete _LivenessEvent / _ReadinessEvent / _WorkloadEvent
        body = {
            "id": str(uuid4()),
            "segment_id": inner.segment_id,
            "event_type": inner.event_type,
            "timestamp": inner.timestamp.isoformat(),
            "payload": inner.payload.model_dump(mode="json"),
            "ingested_at": datetime.now(UTC).isoformat(),
        }
        await self._events.create_item(body=body)

        if inner.event_type == "workload":
            payload = inner.payload  # WorkloadPayload
            if payload.correlation_kind and payload.correlation_id:
                corr_status: SegmentStatus = (
                    "green"
                    if payload.outcome == "success"
                    else "yellow"
                    if payload.outcome == "degraded"
                    else "red"
                )
                corr_id = (
                    f"{payload.correlation_kind}:{payload.correlation_id}"
                    f":{inner.segment_id}:{body['id']}"
                )
                corr_body = {
                    "id": corr_id,
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
                item=segment_id,
                partition_key=segment_id,
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
        self,
        segment_id: str,
        window_seconds: int,
    ) -> list[dict[str, Any]]:
        cutoff = (datetime.now(UTC) - timedelta(seconds=window_seconds)).isoformat()
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
        self,
        kind: CorrelationKind,
        correlation_id: str,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        async for item in self._correlation.query_items(
            query=(
                "SELECT * FROM c"
                " WHERE c.correlation_kind = @kind AND c.correlation_id = @cid"
            ),
            parameters=[
                {"name": "@kind", "value": kind},
                {"name": "@cid", "value": correlation_id},
            ],
        ):
            results.append(item)
        results.sort(key=lambda r: r["timestamp"])
        return results
