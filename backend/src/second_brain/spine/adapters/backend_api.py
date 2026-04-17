"""Backend API segment adapter — pulls from App Insights via existing query layer."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from second_brain.spine.models import CorrelationKind


class BackendApiAdapter:
    """Pulls AppExceptions + AppRequests from App Insights for the Backend API segment.

    Implements the SegmentAdapter protocol.
    """

    segment_id: str = "backend_api"

    def __init__(
        self,
        failures_fetcher: Callable[..., Awaitable[list[dict[str, Any]]]],
        requests_fetcher: Callable[..., Awaitable[list[dict[str, Any]]]],
        native_url_template: str,
    ) -> None:
        self._failures = failures_fetcher
        self._requests = requests_fetcher
        self.native_url_template = native_url_template

    async def fetch_detail(
        self,
        correlation_kind: CorrelationKind | None = None,
        correlation_id: str | None = None,
        time_range_seconds: int = 3600,
    ) -> dict[str, Any]:
        """Return App Insights exceptions and requests for the backend API segment.

        When correlation_kind is "capture" and correlation_id is provided, both
        fetchers receive a capture_trace_id kwarg to scope results to that trace.
        """
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
