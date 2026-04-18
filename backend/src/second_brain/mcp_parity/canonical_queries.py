"""Canonical query set per MCP tool for the parity check.

Each entry is (tool_name, args_dict). The runner calls the tool
both via legacy direct-App-Insights path and via spine path,
then compares.
"""

from typing import Any

CANONICAL_QUERIES: list[tuple[str, dict[str, Any]]] = [
    ("recent_errors", {"time_range": "1h"}),
    ("recent_errors", {"time_range": "24h"}),
    ("recent_errors", {"time_range": "1h", "component": "classifier"}),
    ("system_health", {"time_range": "1h"}),
    ("system_health", {"time_range": "24h"}),
    ("trace_lifecycle", {"trace_id": "__LATEST__"}),
    ("usage_patterns", {"time_range": "24h", "group_by": "bucket"}),
    ("usage_patterns", {"time_range": "24h", "group_by": "destination"}),
    ("usage_patterns", {"time_range": "7d", "group_by": "day"}),
    ("admin_audit", {}),
    ("run_kql", {"query": "AppRequests | take 5", "time_range": "1h"}),
]
