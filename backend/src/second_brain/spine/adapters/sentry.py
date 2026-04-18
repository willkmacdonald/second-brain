"""Sentry segment adapter — pulls events + issues from Sentry REST API."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from second_brain.spine.models import CorrelationKind

logger = logging.getLogger(__name__)


class SentryAdapter:
    """Pulls Sentry events + issues, filterable by tags.

    The fetcher is injected for testability; the production fetcher
    is a thin wrapper around httpx built by ``make_sentry_fetcher``.
    """

    def __init__(
        self,
        segment_id: str,
        sentry_fetcher: Callable[..., Awaitable[dict[str, Any]]],
        native_url_template: str,
        tag_filter: dict[str, str],
    ) -> None:
        self.segment_id = segment_id
        self._fetcher = sentry_fetcher
        self.native_url_template = native_url_template
        self._base_tag_filter = dict(tag_filter)

    async def fetch_detail(
        self,
        correlation_kind: CorrelationKind | None = None,
        correlation_id: str | None = None,
        time_range_seconds: int = 3600,
    ) -> dict[str, Any]:
        """Return Sentry events and issues, optionally filtered by correlation tags."""
        merged_filter = dict(self._base_tag_filter)
        if correlation_kind == "capture" and correlation_id:
            merged_filter["capture_trace_id"] = correlation_id
        elif correlation_kind == "crud" and correlation_id:
            merged_filter["correlation_id"] = correlation_id

        result = await self._fetcher(
            tag_filter=merged_filter,
            time_range_seconds=time_range_seconds,
        )
        return {
            "schema": "sentry_event",
            "events": result.get("events", []),
            "issues": result.get("issues", []),
            "tag_filter": merged_filter,
            "native_url": self.native_url_template,
        }


async def make_sentry_fetcher(
    auth_token: str,
    org: str,
    project: str,
) -> Callable[..., Awaitable[dict[str, Any]]]:
    """Build a production fetcher closure bound to org/project credentials.

    Returns an async callable suitable for passing to ``SentryAdapter`` as
    ``sentry_fetcher``. Failures are logged and result in empty lists so the
    spine can still render a partial result rather than hard-failing.
    """

    async def _fetch(
        tag_filter: dict[str, str], time_range_seconds: int
    ) -> dict[str, Any]:
        query = " ".join(f"{k}:{v}" for k, v in tag_filter.items())
        url = f"https://sentry.io/api/0/projects/{org}/{project}/events/"
        params = {"query": query, "statsPeriod": f"{time_range_seconds}s"}
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    url,
                    params=params,
                    headers={"Authorization": f"Bearer {auth_token}"},
                    timeout=10.0,
                )
                resp.raise_for_status()
                events = resp.json()
            except Exception:
                logger.warning("Sentry fetch failed", exc_info=True)
                events = []
        return {"events": events, "issues": []}

    return _fetch
