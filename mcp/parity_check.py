"""Standalone parity check -- runs canonical queries through both legacy and spine paths.

Usage (from the repo root):

    SPINE_API_KEY=<key> python3 mcp/parity_check.py

The script invokes the legacy helpers and the spine transform functions
directly, so the MCP_SPINE_* per-tool feature flags are not needed here.

Exit code 0 means all checked tools matched; exit code 1 means at least one
diverged (or a tool failed on one of the two paths).

Requirements:
- Azure credentials must be available (az login or environment variables) so
  the legacy App Insights queries can authenticate.
- SPINE_API_KEY and SPINE_BASE_URL must be set for the spine path.
- LOG_ANALYTICS_WORKSPACE_ID must be set (or present in backend/.env).
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

# ---------------------------------------------------------------------------
# Path setup -- must happen before any second_brain or server imports
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent
_MCP_DIR = Path(__file__).parent

# Add backend/src so second_brain.* is importable without an editable install.
sys.path.insert(0, str(_REPO_ROOT / "backend" / "src"))
# Add the mcp/ directory so `import server` resolves to our server.py, not to
# the installed mcp package's server module.
sys.path.insert(0, str(_MCP_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_REPO_ROOT / "backend" / ".env")

from azure.identity.aio import DefaultAzureCredential  # noqa: E402
from azure.monitor.query.aio import LogsQueryClient  # noqa: E402
from second_brain.mcp_parity.canonical_queries import CANONICAL_QUERIES  # noqa: E402
from second_brain.mcp_parity.runner import ParityResult, run_parity  # noqa: E402
from second_brain.observability.queries import (  # noqa: E402
    query_latest_capture_trace_id,
)

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [parity] %(levelname)s: %(message)s",
)
logger = logging.getLogger("parity-check")

# ---------------------------------------------------------------------------
# Import server.py as a module named 'mcp_server' to avoid collision with the
# installed 'mcp' package which also has a 'server' submodule.
# ---------------------------------------------------------------------------


def _load_server_module() -> ModuleType:
    """Load mcp/server.py as 'mcp_server' via importlib to avoid name collisions."""
    spec = importlib.util.spec_from_file_location(
        "mcp_server", str(_MCP_DIR / "server.py")
    )
    if spec is None or spec.loader is None:
        raise ImportError("Could not load mcp/server.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["mcp_server"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# Minimal AppContext shim -- replicates the lifespan-injected context shape
# that _get_app() expects without running the MCP lifespan machinery.
# ---------------------------------------------------------------------------


@dataclass
class _LifespanContext:
    logs_client: LogsQueryClient
    workspace_id: str
    credential: DefaultAzureCredential


@dataclass
class _RequestContext:
    lifespan_context: _LifespanContext


class _AppCtxShim:
    """Stand-in for mcp.server.fastmcp.Context compatible with _get_app()."""

    def __init__(
        self,
        logs_client: LogsQueryClient,
        workspace_id: str,
        credential: DefaultAzureCredential,
    ) -> None:
        self.request_context = _RequestContext(
            lifespan_context=_LifespanContext(
                logs_client=logs_client,
                workspace_id=workspace_id,
                credential=credential,
            )
        )


# ---------------------------------------------------------------------------
# Build per-tool (legacy_fn, spine_fn) pairs
# ---------------------------------------------------------------------------


def _make_tool_callables(
    srv: ModuleType,
    logs_client: LogsQueryClient,
    workspace_id: str,
    credential: DefaultAzureCredential,
) -> dict[str, tuple]:
    """Return {tool_name: (legacy_fn, spine_fn)} for each tool with a spine path.

    The legacy helpers (_legacy_*) are called with the shared AppContext shim.
    The spine helpers call _spine_call directly and apply the response transformers
    from server.py, keeping the transformation logic in a single place.
    """
    ctx = _AppCtxShim(logs_client, workspace_id, credential)

    async def legacy_recent_errors(
        time_range: str = "24h", component: str | None = None
    ) -> dict:
        return await srv._legacy_recent_errors(time_range, component, ctx)

    async def spine_recent_errors(
        time_range: str = "24h", component: str | None = None
    ) -> dict:
        seconds = srv._time_range_to_seconds(time_range)
        data = await srv._spine_call(
            "/api/spine/segment/backend_api",
            params={"time_range_seconds": seconds},
        )
        return srv._transform_recent_errors_from_spine(data, time_range, component)

    async def legacy_trace_lifecycle(trace_id: str | None = None) -> dict:
        return await srv._legacy_trace_lifecycle(trace_id, ctx)

    async def spine_trace_lifecycle(trace_id: str | None = None) -> dict:
        resolved_id = trace_id
        if not resolved_id:
            resolved_id = await query_latest_capture_trace_id(logs_client, workspace_id)
            if not resolved_id:
                return {
                    "error": True,
                    "message": "No recent captures found",
                    "type": "no_data",
                }
        data = await srv._spine_call(f"/api/spine/correlation/capture/{resolved_id}")
        return srv._transform_trace_lifecycle_from_spine(data, resolved_id)

    async def legacy_admin_audit() -> dict:
        return await srv._legacy_admin_audit(ctx)

    async def spine_admin_audit() -> dict:
        data = await srv._spine_call("/api/spine/segment/admin")
        return srv._transform_admin_audit_from_spine(data)

    return {
        "recent_errors": (legacy_recent_errors, spine_recent_errors),
        "trace_lifecycle": (legacy_trace_lifecycle, spine_trace_lifecycle),
        "admin_audit": (legacy_admin_audit, spine_admin_audit),
        # system_health, usage_patterns, run_kql are legacy-only; excluded
        # from parity. system_health has no spine equivalent -- /status
        # tracks traffic lights, not ops metrics.
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> int:
    workspace_id = os.environ.get("LOG_ANALYTICS_WORKSPACE_ID", "")
    if not workspace_id:
        logger.error("LOG_ANALYTICS_WORKSPACE_ID is not set -- cannot run legacy path")
        return 1

    srv = _load_server_module()

    credential = DefaultAzureCredential()
    logs_client = LogsQueryClient(credential=credential)

    results: list[ParityResult] = []
    try:
        tool_pairs = _make_tool_callables(srv, logs_client, workspace_id, credential)

        for tool_name, args in CANONICAL_QUERIES:
            if tool_name not in tool_pairs:
                logger.info("Skipping %s (no spine path)", tool_name)
                continue

            legacy_fn, spine_fn = tool_pairs[tool_name]

            # Resolve __LATEST__ sentinel -- the underlying spine_trace_lifecycle
            # wrapper already handles None, so map the sentinel to None here.
            effective_args = dict(args)
            if (
                tool_name == "trace_lifecycle"
                and effective_args.get("trace_id") == "__LATEST__"
            ):
                effective_args["trace_id"] = None

            logger.info("Checking parity: %s %s", tool_name, effective_args)
            result = await run_parity(legacy_fn, spine_fn, tool_name, effective_args)
            results.append(result)

            status = "MATCH" if result.matched else "DIVERGE"
            logger.info(
                "  %s: legacy_ok=%s spine_ok=%s",
                status,
                result.legacy_ok,
                result.spine_ok,
            )
            if result.diff_summary:
                logger.info("  diff: %s", result.diff_summary)

    finally:
        await logs_client.close()
        await credential.close()

    report = {
        "run_at": datetime.now(UTC).isoformat(),
        "results": [
            {
                "tool": r.tool_name,
                "args": r.args,
                "legacy_ok": r.legacy_ok,
                "spine_ok": r.spine_ok,
                "matched": r.matched,
                "diff_summary": r.diff_summary,
            }
            for r in results
        ],
        "summary": {
            "total": len(results),
            "matched": sum(1 for r in results if r.matched),
            "diverged": sum(1 for r in results if not r.matched),
        },
    }
    print(json.dumps(report, indent=2))
    return 0 if all(r.matched for r in results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
