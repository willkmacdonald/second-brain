"""Foundry-agent segment adapter — joins App Insights spans by run_id/thread_id.

Does NOT depend on Foundry Runs API metadata filtering. Uses the IDs we
already generate and store on our own OTel spans.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from second_brain.spine.models import CorrelationKind


class FoundryAgentAdapter:
    """Pulls agent-run details by joining App Insights spans on run_id/thread_id."""

    def __init__(
        self,
        segment_id: str,
        agent_id: str,
        agent_name: str,
        spans_fetcher: Callable[..., Awaitable[list[dict[str, Any]]]],
        native_url_template: str,
    ) -> None:
        self.segment_id = segment_id
        self._agent_id = agent_id
        self._agent_name = agent_name
        self._spans = spans_fetcher
        self.native_url_template = native_url_template

    async def fetch_detail(
        self,
        correlation_kind: CorrelationKind | None = None,
        correlation_id: str | None = None,
        time_range_seconds: int = 3600,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "agent_id": self._agent_id,
            "time_range_seconds": time_range_seconds,
        }
        if correlation_kind == "capture" and correlation_id:
            kwargs["capture_trace_id"] = correlation_id
        elif correlation_kind == "thread" and correlation_id:
            kwargs["thread_id"] = correlation_id

        runs = await self._spans(**kwargs)
        return {
            "schema": "foundry_run",
            "agent_id": self._agent_id,
            "agent_name": self._agent_name,
            "agent_runs": runs,
            "native_url": self.native_url_template,
        }
