"""Composite adapter — fans out to multiple source adapters and combines results."""

from __future__ import annotations

import asyncio
from typing import Any, Protocol

from second_brain.spine.models import CorrelationKind


class _SourceAdapter(Protocol):
    """Minimal protocol for source adapters within the composite."""

    async def fetch_detail(
        self,
        correlation_kind: CorrelationKind | None = None,
        correlation_id: str | None = None,
        time_range_seconds: int = 3600,
    ) -> dict[str, Any]: ...


class CompositeAdapter:
    """Fan-out adapter that aggregates results from named sources.

    Calls all sub-adapters concurrently via asyncio.gather with
    return_exceptions=True so a single failing source does not prevent
    the rest from being returned.  Failed sources are reported in
    ``partial_failures`` rather than raising.
    """

    def __init__(
        self,
        segment_id: str,
        sources: dict[str, _SourceAdapter],
        native_url: str,
    ) -> None:
        self.segment_id = segment_id
        self._sources = sources
        self.native_url_template = native_url

    async def fetch_detail(
        self,
        correlation_kind: CorrelationKind | None = None,
        correlation_id: str | None = None,
        time_range_seconds: int = 3600,
    ) -> dict[str, Any]:
        """Fan out to all sources and return a combined mobile_telemetry_combined dict.

        Partial failures are recorded in ``partial_failures``; successful
        source results are keyed by source name under ``sources``.
        """
        names = list(self._sources.keys())
        results = await asyncio.gather(
            *[
                src.fetch_detail(
                    correlation_kind=correlation_kind,
                    correlation_id=correlation_id,
                    time_range_seconds=time_range_seconds,
                )
                for src in self._sources.values()
            ],
            return_exceptions=True,
        )

        sources_out: dict[str, Any] = {}
        partial_failures: list[str] = []
        for name, res in zip(names, results, strict=False):
            if isinstance(res, Exception):
                partial_failures.append(name)
                continue
            sources_out[name] = res

        return {
            "schema": "mobile_telemetry_combined",
            "sources": sources_out,
            "partial_failures": partial_failures,
            "native_url": self.native_url_template,
        }
