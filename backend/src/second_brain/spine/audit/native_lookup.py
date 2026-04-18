"""Facade for native-source lookups used by the audit walker.

Bundles the three async fetchers behind one object so the walker has a single
dependency to inject and tests have a single mock surface. When a fetcher is
None (e.g. LogsQueryClient unavailable at app startup), the corresponding
method returns an empty list — keeps the audit endpoint from 500-ing in
degraded environments.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

NativeFetcher = Callable[..., Awaitable[list[dict[str, Any]]]]


class NativeLookup:
    """Thin facade around the three native-source query helpers."""

    def __init__(
        self,
        *,
        spans_fetcher: NativeFetcher | None,
        exceptions_fetcher: NativeFetcher | None,
        cosmos_fetcher: NativeFetcher | None,
    ) -> None:
        self._spans = spans_fetcher
        self._exceptions = exceptions_fetcher
        self._cosmos = cosmos_fetcher

    async def spans(
        self, correlation_id: str, *, time_range_seconds: int
    ) -> list[dict[str, Any]]:
        if self._spans is None:
            return []
        return await self._spans(
            correlation_id=correlation_id,
            time_range_seconds=time_range_seconds,
        )

    async def exceptions(
        self, correlation_id: str, *, time_range_seconds: int
    ) -> list[dict[str, Any]]:
        if self._exceptions is None:
            return []
        return await self._exceptions(
            correlation_id=correlation_id,
            time_range_seconds=time_range_seconds,
        )

    async def cosmos(
        self, correlation_id: str, *, time_range_seconds: int
    ) -> list[dict[str, Any]]:
        if self._cosmos is None:
            return []
        return await self._cosmos(
            correlation_id=correlation_id,
            time_range_seconds=time_range_seconds,
        )
