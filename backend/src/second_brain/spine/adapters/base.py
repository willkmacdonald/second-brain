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
