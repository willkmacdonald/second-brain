"""Cosmos DB segment adapter — pulls from Azure Monitor diagnostic logs."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from second_brain.spine.models import CorrelationKind


class CosmosAdapter:
    """Pulls Cosmos data-plane diagnostic logs from Log Analytics workspace.

    Implements the SegmentAdapter protocol.
    """

    segment_id: str = "cosmos"

    def __init__(
        self,
        diagnostics_fetcher: Callable[..., Awaitable[list[dict[str, Any]]]],
        native_url: str,
    ) -> None:
        self._diagnostics = diagnostics_fetcher
        self.native_url_template = native_url

    async def fetch_detail(
        self,
        correlation_kind: CorrelationKind | None = None,
        correlation_id: str | None = None,
        time_range_seconds: int = 3600,
    ) -> dict[str, Any]:
        """Return Cosmos diagnostic logs, optionally filtered by capture trace."""
        kwargs: dict[str, Any] = {"time_range_seconds": time_range_seconds}
        if correlation_kind == "capture" and correlation_id:
            kwargs["capture_trace_id"] = correlation_id

        logs = await self._diagnostics(**kwargs)
        return {
            "schema": "azure_monitor_cosmos",
            "diagnostic_logs": logs,
            "native_url": self.native_url_template,
        }
