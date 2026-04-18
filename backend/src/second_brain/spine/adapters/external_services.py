"""External Services segment adapter.

Reuses App Insights queries from BackendApiAdapter. External Services
(recipe scraping) logs flow through the same App Insights instance as
backend_api logs. This adapter provides drill-down into those logs when
the external_services tile is clicked.
"""

from __future__ import annotations

from second_brain.spine.adapters.backend_api import BackendApiAdapter


class ExternalServicesAdapter(BackendApiAdapter):
    """Same App Insights view as BackendApiAdapter, scoped to external_services."""

    segment_id: str = "external_services"
