"""Container App segment adapter.

Reuses App Insights queries from BackendApiAdapter. The container_app
segment is a rollup node — its drill-down shows the same requests and
failures as backend_api, confirming the container is serving traffic.
"""

from __future__ import annotations

from second_brain.spine.adapters.backend_api import BackendApiAdapter


class ContainerAppAdapter(BackendApiAdapter):
    """App Insights view for the container_app rollup segment."""

    segment_id: str = "container_app"
