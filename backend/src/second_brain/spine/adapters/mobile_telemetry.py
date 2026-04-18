"""Mobile telemetry adapter — reads from spine_events for crud_failure data."""

from __future__ import annotations

from typing import Any

from second_brain.spine.models import CorrelationKind
from second_brain.spine.storage import SpineRepository


class MobileTelemetryAdapter:
    """Pulls mobile crud_failure workload events from spine_events."""

    def __init__(
        self,
        segment_id: str,
        repo: SpineRepository,
        native_url: str,
    ) -> None:
        self.segment_id = segment_id
        self._repo = repo
        self.native_url_template = native_url

    async def fetch_detail(
        self,
        correlation_kind: CorrelationKind | None = None,
        correlation_id: str | None = None,
        time_range_seconds: int = 3600,
    ) -> dict[str, Any]:
        """Return mobile workload failure events from spine_events."""
        events = await self._repo.get_recent_events(
            segment_id=self.segment_id,
            window_seconds=time_range_seconds,
        )
        failures = [
            e
            for e in events
            if e.get("event_type") == "workload"
            and e.get("payload", {}).get("outcome") == "failure"
        ]
        return {
            "schema": "mobile_telemetry",
            "telemetry_events": failures,
            "native_url": self.native_url_template,
        }
