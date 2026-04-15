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
