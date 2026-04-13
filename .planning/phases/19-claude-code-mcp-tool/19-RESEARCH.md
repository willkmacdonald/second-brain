# Phase 19: Claude Code MCP Tool - Research

**Researched:** 2026-04-13
**Domain:** MCP server (Python), App Insights telemetry queries, Claude Code integration
**Confidence:** HIGH

## Summary

Phase 19 builds a standalone MCP server that exposes the existing `second_brain.observability` query infrastructure directly inside Claude Code via stdio transport. The server wraps 5 Investigation Agent tools (trace_lifecycle, recent_errors, system_health, usage_patterns, admin_audit) plus a raw `execute_kql` tool, using the official `mcp` Python SDK's FastMCP framework. The MCP server lives in a new top-level `mcp/` directory, imports query functions from the backend's `second_brain.observability` module via `uv` editable install, authenticates via `DefaultAzureCredential` (local `az login`), and auto-starts when Claude Code opens the project.

After the MCP server is working, the existing `/investigate` skill (which calls the deployed API at `brain.willmacdonald.com`) is migrated to invoke local MCP tools directly -- one fewer network hop, same query capability.

**Primary recommendation:** Use `mcp` SDK v1.27.0 (`from mcp.server.fastmcp import FastMCP`) with the lifespan pattern to initialize `LogsQueryClient` + `DefaultAzureCredential` at startup. Register via `claude mcp add` with `--scope local` pointing at `uv --directory mcp/ run server.py`. The MCP server's `pyproject.toml` declares an editable dependency on `../backend` to get `second_brain.observability` on the import path.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Full parity with Investigation Agent: all 5 tools (trace_lifecycle, recent_errors, system_health, usage_patterns, admin_audit)
- Plus a raw `execute_kql` tool for ad-hoc KQL queries
- No guardrails on raw KQL -- Log Analytics is read-only, single user
- Mirror Investigation Agent tool parameter signatures exactly
- Tools only -- no MCP resources
- Import query functions from `second_brain.observability` (single source of truth for KQL templates, models, queries)
- Once MCP is working, migrate `/investigate` skill to use local MCP tools instead of calling the deployed API endpoint
- Structured JSON via Pydantic `.model_dump_json()` -- Claude interprets and presents naturally
- Truncate large result sets: return first N records + total count (e.g., "Showing 20 of 47 errors")
- Flag partial results prominently: `is_partial` field + warning message (matches existing `QueryResult.is_partial` pattern)
- Errors returned as structured objects in the tool response: `{error: true, message: "...", type: "auth_failure"}` -- not MCP-level `isError` flags
- DefaultAzureCredential -- uses local `az login` session, no secrets to manage
- Workspace ID from `AZURE_LOG_ANALYTICS_WORKSPACE_ID` environment variable (same pattern as backend)
- MCP server registered in project-level `.claude/settings.json` (scoped to second-brain repo)
- Server code lives in top-level `mcp/` directory (sibling to `backend/` and `mobile/`)
- Auto-start via Claude Code config -- zero manual steps per session
- Server starts even without Azure connectivity; each tool call returns structured error if auth/network fails
- Stderr logging at INFO level (Claude Code captures MCP server stderr for diagnostics)
- Built with official `mcp` Python SDK (pip install mcp) -- handles stdio transport and protocol compliance

### Claude's Discretion
- Truncation threshold (how many records before truncating)
- Internal module structure within `mcp/`
- Exact tool descriptions for Claude Code discovery
- Server timeout defaults for KQL execution

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| MCP-01 | User can query App Insights from Claude Code via MCP tool (trace lookups, failures, health) | FastMCP server with stdio transport wrapping `second_brain.observability` query functions; registered in Claude Code via `claude mcp add --scope local`; lifespan pattern initializes Azure credentials + LogsQueryClient at startup |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `mcp` | 1.27.0 | MCP SDK -- FastMCP server, stdio transport, tool decorators | Official MCP Python SDK from `modelcontextprotocol`; built-in FastMCP is the standard way to build MCP servers with Python |
| `azure-identity` | 1.25.2 | `DefaultAzureCredential` (async) for Log Analytics auth | Already used by backend; picks up `az login` session automatically |
| `azure-monitor-query` | 2.0.0 | `LogsQueryClient` (async) for KQL workspace queries | Already used by backend's `second_brain.observability.client` |
| `pydantic` | 2.12.5 | Structured models for tool responses | Already used by backend's `second_brain.observability.models` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `second-brain-backend` | 0.1.0 (editable) | Import `second_brain.observability` module | Always -- single source of truth for KQL templates, query functions, models |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `mcp` (official SDK) | `fastmcp` (standalone package from Prefect) | Standalone `fastmcp` is more feature-rich but adds a separate dependency; official SDK's built-in FastMCP is sufficient for this use case and matches CONTEXT.md decision |
| Editable backend dep | Copy observability module into `mcp/` | Defeats "single source of truth" constraint; any KQL template change requires two updates |

**Installation:**
```bash
cd mcp/
uv init
uv add "mcp[cli]"
uv add --editable ../backend
```

The `--editable ../backend` makes `second_brain.observability` importable without duplicating code. The backend's `pyproject.toml` already uses hatchling with `packages = ["src/second_brain"]`.

## Architecture Patterns

### Recommended Project Structure
```
mcp/
├── pyproject.toml          # Depends on mcp[cli] + editable ../backend
├── server.py               # FastMCP server with lifespan, all 6 tools
└── .python-version         # 3.12 (match backend)
```

A single `server.py` file is sufficient given 6 tool functions plus lifespan. The CONTEXT.md leaves internal structure to Claude's discretion -- a flat single-file approach avoids over-engineering for ~200-300 lines of wrapper code.

### Pattern 1: FastMCP Server with Lifespan for Azure Clients
**What:** Use the lifespan async context manager to initialize and tear down the `DefaultAzureCredential` and `LogsQueryClient` once at server startup, then inject them into tool functions via the Context object.
**When to use:** Always -- these are expensive to create per-call and need proper async cleanup.
**Example:**
```python
# Source: https://deepwiki.com/modelcontextprotocol/python-sdk/2.5-context-injection-and-lifespan
# Verified against official MCP Python SDK documentation

import os
import sys
import logging
from dataclasses import dataclass
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP, Context
from azure.identity.aio import DefaultAzureCredential
from azure.monitor.query.aio import LogsQueryClient

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stderr, level=logging.INFO)

@dataclass
class AppContext:
    logs_client: LogsQueryClient
    workspace_id: str
    credential: DefaultAzureCredential

@asynccontextmanager
async def lifespan(server: FastMCP):
    workspace_id = os.environ.get("AZURE_LOG_ANALYTICS_WORKSPACE_ID", "")
    if not workspace_id:
        logger.warning("AZURE_LOG_ANALYTICS_WORKSPACE_ID not set")
    
    credential = DefaultAzureCredential()
    logs_client = LogsQueryClient(credential=credential)
    try:
        yield AppContext(
            logs_client=logs_client,
            workspace_id=workspace_id,
            credential=credential,
        )
    finally:
        await logs_client.close()
        await credential.close()

mcp = FastMCP("second-brain-telemetry", lifespan=lifespan)
```

### Pattern 2: Tool Functions as Thin Wrappers
**What:** Each MCP tool calls the corresponding function from `second_brain.observability.queries`, passing the `LogsQueryClient` and `workspace_id` from the lifespan context. Tool functions handle only parameter validation, context extraction, and error wrapping.
**When to use:** All 5 mirrored tools + `execute_kql`.
**Example:**
```python
from mcp.server.session import ServerSession

@mcp.tool()
async def system_health(
    time_range: str = "24h",
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Check system health metrics and error trends.
    
    Returns capture counts, success rate, latency percentiles (P95/P99),
    and trend comparison against the previous period.
    
    Args:
        time_range: Time range to query: '1h', '6h', '24h', '3d', or '7d'.
    """
    app = ctx.request_context.lifespan_context
    try:
        # Reuse validation logic from investigation tools
        kql_duration, td = TIME_RANGE_MAP.get(time_range, TIME_RANGE_MAP["24h"])
        summary = await query_enhanced_system_health(
            app.logs_client,
            app.workspace_id,
            time_range_kql=kql_duration,
            timespan=td * 2,
        )
        return summary.model_dump()
    except Exception as exc:
        return {"error": True, "message": str(exc), "type": type(exc).__name__}
```

### Pattern 3: Graceful Error Handling (No Crashes)
**What:** Every tool wraps its body in try/except and returns structured error objects. The server never crashes from an Azure auth failure or network timeout.
**When to use:** All tools -- matches CONTEXT.md decision "Server starts even without Azure connectivity; each tool call returns structured error if auth/network fails".
**Example:**
```python
@mcp.tool()
async def recent_errors(
    time_range: str = "24h",
    component: str | None = None,
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Query recent errors and failures from App Insights."""
    app = ctx.request_context.lifespan_context
    if not app.workspace_id:
        return {
            "error": True,
            "message": "AZURE_LOG_ANALYTICS_WORKSPACE_ID not configured",
            "type": "config_error",
        }
    try:
        # ... query logic ...
        pass
    except Exception as exc:
        logger.error("recent_errors failed: %s", exc, file=sys.stderr)
        return {"error": True, "message": str(exc), "type": type(exc).__name__}
```

### Pattern 4: Claude Code Registration via `claude mcp add`
**What:** Register the MCP server with local scope so it auto-starts when Claude Code opens the second-brain project.
**When to use:** One-time setup step.
**Example:**
```bash
# Register the server (from the second-brain repo root)
claude mcp add --transport stdio --scope local \
  --env AZURE_LOG_ANALYTICS_WORKSPACE_ID=$AZURE_LOG_ANALYTICS_WORKSPACE_ID \
  second-brain-telemetry \
  -- uv --directory /Users/willmacdonald/Documents/Code/claude/second-brain/mcp run server.py
```

This writes into `~/.claude.json` under the project path. The server auto-starts via stdio when Claude Code opens.

**Important:** The `--scope local` stores config in `~/.claude.json` scoped to this project path, NOT in `.claude/settings.json`. The CONTEXT.md mentions `.claude/settings.json` but Claude Code's actual mechanism for local MCP servers is `~/.claude.json`. The net effect is the same (scoped to this repo, auto-starts).

### Pattern 5: Skill Migration (Post-MCP)
**What:** After MCP tools are working, rewrite `.claude/skills/investigate/SKILL.md` to use MCP tool calls instead of `backend/scripts/investigate.py`.
**When to use:** After all 6 MCP tools are verified working.
**Example approach:**
The skill instructions change from "run `uv run python scripts/investigate.py`" to "use the `second-brain-telemetry` MCP tools directly". Since Claude Code has native access to MCP tools, the skill becomes a routing guide (when to use which tool) rather than a Bash invocation script. This eliminates the network hop to `brain.willmacdonald.com` and the Key Vault API key fetch.

### Anti-Patterns to Avoid
- **Creating a new LogsQueryClient per tool call:** Expensive and leaks async resources. Use the lifespan pattern to create once.
- **Writing to stdout in the server:** Stdio transport uses stdout for JSON-RPC messages. All logging MUST go to stderr.
- **Using `print()` without `file=sys.stderr`:** Default `print()` goes to stdout, corrupting the MCP protocol.
- **Duplicating KQL templates:** Import from `second_brain.observability.kql_templates`, never copy them.
- **Using `mcp.run()` without `transport="stdio"`:** Default may not be stdio. Always explicit.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| MCP protocol compliance | Custom JSON-RPC over stdio | `mcp` SDK with `FastMCP` | Protocol is complex (negotiation, capabilities, schemas); SDK handles it |
| Tool schema generation | Manual JSON schema from parameters | `@mcp.tool()` decorator with type hints | FastMCP auto-generates input schemas from Python type annotations and docstrings |
| Async credential lifecycle | Manual `__aenter__`/`__aexit__` | FastMCP lifespan context manager | Lifespan handles startup/shutdown automatically |
| KQL query construction | Raw string queries in MCP server | `second_brain.observability.kql_templates` + `queries.py` | Templates are already parameterized and tested; single source of truth |
| Structured error responses | Ad-hoc dict construction | Consistent `{"error": True, "message": ..., "type": ...}` pattern | Claude needs a predictable shape to distinguish errors from data |

**Key insight:** The MCP server is a ~200-line glue layer. All query logic, KQL templates, and result models already exist in `second_brain.observability`. The value is in wiring, not reimplementation.

## Common Pitfalls

### Pitfall 1: stdout Corruption in Stdio Transport
**What goes wrong:** Any `print()` or logging to stdout corrupts JSON-RPC messages, causing the MCP server to appear dead to Claude Code.
**Why it happens:** Stdio transport shares stdout between the server's JSON-RPC responses and any other output.
**How to avoid:** Configure Python logging to write to stderr: `logging.basicConfig(stream=sys.stderr, level=logging.INFO)`. Never use bare `print()`.
**Warning signs:** MCP server appears "disconnected" in Claude Code; `/mcp` shows the server as errored.

### Pitfall 2: Missing Workspace ID Environment Variable
**What goes wrong:** All queries return empty results or crash if `AZURE_LOG_ANALYTICS_WORKSPACE_ID` is not set.
**Why it happens:** The env var must be passed via `--env` flag in `claude mcp add` or set in the shell environment before Claude Code starts.
**How to avoid:** Check for the env var at lifespan init, log a warning to stderr if missing, and return structured error from each tool if workspace_id is empty.
**Warning signs:** Tools return `{"error": True, "type": "config_error"}`.

### Pitfall 3: Async Credential Not Closed
**What goes wrong:** `DefaultAzureCredential` (async variant) holds open connections. If not closed, the server process leaks resources on shutdown.
**Why it happens:** Forgetting the `finally` block in the lifespan.
**How to avoid:** Always close both the `LogsQueryClient` and the `DefaultAzureCredential` in the lifespan's `finally` block.
**Warning signs:** Orphaned HTTP connections, slow server shutdown.

### Pitfall 4: Editable Backend Install Breaks on Missing Deps
**What goes wrong:** `uv add --editable ../backend` pulls in ALL backend dependencies (FastAPI, Playwright, etc.) which are unnecessary for the MCP server.
**Why it happens:** The backend's `pyproject.toml` lists all its runtime dependencies.
**How to avoid:** This is acceptable -- the extra deps don't affect the MCP server at runtime. Alternatively, could factor `observability` into its own package, but that's over-engineering for a single-user project. Accept the larger venv.
**Warning signs:** Slow initial `uv sync` (one-time cost, not per-session).

### Pitfall 5: Stale `az login` Token
**What goes wrong:** `DefaultAzureCredential` fails with authentication errors if the `az login` session has expired.
**Why it happens:** Azure CLI tokens expire (typically after 1-24 hours depending on tenant config).
**How to avoid:** Return a structured error with `"type": "auth_failure"` and message suggesting `az login`. The investigate skill already handles this pattern.
**Warning signs:** Tools return `{"error": True, "type": "ClientAuthenticationError"}`.

### Pitfall 6: Context Injection Syntax
**What goes wrong:** FastMCP's Context injection requires the parameter to be typed as `Context[ServerSession, AppContext]`. If typed differently (e.g., just `Context`), the lifespan context won't be accessible.
**Why it happens:** The generic type parameters tell FastMCP which lifespan type to inject.
**How to avoid:** Always use the full generic type: `ctx: Context[ServerSession, AppContext]`. FastMCP automatically excludes this from the tool's input schema.
**Warning signs:** `ctx.request_context.lifespan_context` returns `None` or wrong type.

## Code Examples

Verified patterns from official sources:

### Complete Server Structure
```python
# mcp/server.py
# Source: MCP Python SDK docs + Azure Monitor Query SDK

import os
import sys
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta

from mcp.server.fastmcp import FastMCP, Context
from mcp.server.session import ServerSession
from azure.identity.aio import DefaultAzureCredential
from azure.monitor.query.aio import LogsQueryClient

from second_brain.observability.queries import (
    execute_kql,
    query_capture_trace,
    query_enhanced_system_health,
    query_latest_capture_trace_id,
    query_recent_failures_filtered,
    query_usage_patterns,
    query_admin_audit,
)
from second_brain.observability.models import QueryResult

# Logging to stderr (CRITICAL for stdio transport)
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("second-brain-mcp")

# Time range validation (mirrors backend/src/second_brain/tools/investigation.py)
TIME_RANGE_MAP: dict[str, tuple[str, timedelta]] = {
    "1h": ("1h", timedelta(hours=1)),
    "6h": ("6h", timedelta(hours=6)),
    "24h": ("24h", timedelta(hours=24)),
    "3d": ("3d", timedelta(days=3)),
    "7d": ("7d", timedelta(days=7)),
}

RESULT_LIMIT = 20  # Truncation threshold for MCP (higher than agent's 10)


@dataclass
class AppContext:
    logs_client: LogsQueryClient
    workspace_id: str
    credential: DefaultAzureCredential


@asynccontextmanager
async def lifespan(server: FastMCP):
    workspace_id = os.environ.get("AZURE_LOG_ANALYTICS_WORKSPACE_ID", "")
    if not workspace_id:
        logger.warning("AZURE_LOG_ANALYTICS_WORKSPACE_ID not set -- tools will return errors")
    
    credential = DefaultAzureCredential()
    logs_client = LogsQueryClient(credential=credential)
    logger.info("MCP server started (workspace_id=%s)", workspace_id[:8] + "..." if workspace_id else "UNSET")
    try:
        yield AppContext(
            logs_client=logs_client,
            workspace_id=workspace_id,
            credential=credential,
        )
    finally:
        await logs_client.close()
        await credential.close()
        logger.info("MCP server shutdown -- clients closed")


mcp = FastMCP("second-brain-telemetry", lifespan=lifespan)


def _get_app(ctx: Context) -> AppContext:
    """Extract the AppContext from the MCP Context."""
    return ctx.request_context.lifespan_context


def _check_config(app: AppContext) -> dict | None:
    """Return error dict if workspace_id is missing, else None."""
    if not app.workspace_id:
        return {
            "error": True,
            "message": "AZURE_LOG_ANALYTICS_WORKSPACE_ID not configured",
            "type": "config_error",
        }
    return None


# --- Tool definitions follow (see individual tool patterns above) ---

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

### Tool: execute_kql (Raw KQL)
```python
@mcp.tool()
async def run_kql(
    query: str,
    time_range: str = "24h",
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Execute a raw KQL query against the App Insights Log Analytics workspace.
    
    Use this for ad-hoc queries not covered by the other tools.
    Log Analytics is read-only -- no risk of data modification.
    
    Args:
        query: KQL query string to execute.
        time_range: Time window: '1h', '6h', '24h', '3d', or '7d'.
    """
    app = _get_app(ctx)
    if err := _check_config(app):
        return err
    try:
        _, td = TIME_RANGE_MAP.get(time_range, TIME_RANGE_MAP["24h"])
        result = await execute_kql(
            app.logs_client, app.workspace_id, query, timespan=td
        )
        return {
            "tables": result.tables,
            "is_partial": result.is_partial,
            "partial_error": result.partial_error,
        }
    except Exception as exc:
        return {"error": True, "message": str(exc), "type": type(exc).__name__}
```

### Claude Code Registration Command
```bash
# From the second-brain repo root directory:
claude mcp add --transport stdio --scope local \
  --env AZURE_LOG_ANALYTICS_WORKSPACE_ID=$AZURE_LOG_ANALYTICS_WORKSPACE_ID \
  second-brain-telemetry \
  -- uv --directory "$PWD/mcp" run server.py
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `/investigate` skill calls deployed API at brain.willmacdonald.com | MCP tools query Log Analytics directly from local machine | Phase 19 (this phase) | Eliminates network hop + Key Vault API key fetch; faster, works offline from deployed backend |
| SSE transport for MCP | Streamable HTTP is new default; stdio still standard for local | MCP SDK 1.2.0+ (2025) | No impact -- we use stdio for local process, which remains the standard for local tools |
| Standalone `fastmcp` package | `mcp.server.fastmcp` included in official SDK | FastMCP 1.0 merged into SDK (2024) | Use `from mcp.server.fastmcp import FastMCP` -- no separate package needed |

**Deprecated/outdated:**
- SSE transport: deprecated in favor of Streamable HTTP for remote servers. Not relevant here (we use stdio).
- `mcp.server.lowlevel`: Still available but FastMCP is the recommended high-level API.

## Open Questions

1. **Context type annotation with lifespan**
   - What we know: Official docs show `Context[ServerSession, AppContext]` as the generic type for tools that need lifespan context. DeepWiki and multiple examples confirm this pattern.
   - What's unclear: Whether `ctx` parameter needs an explicit default value (e.g., `= None`) or if FastMCP handles injection without it. Some examples show `= None`, others don't.
   - Recommendation: Use `= None` as default for safety (HIGH confidence this works based on multiple examples). Verify during implementation by checking if the tool schema excludes the ctx parameter.

2. **Backend editable install viability**
   - What we know: `uv add --editable ../backend` should work since hatchling with `packages = ["src/second_brain"]` is the backend's build config. The backend package is already installed as editable in its own venv.
   - What's unclear: Whether `uv` handles cross-directory editable installs smoothly when both directories have their own `pyproject.toml` and different dependency trees.
   - Recommendation: Test during Wave 0 setup. Fallback: use `sys.path.insert()` to add `backend/src` to the Python path in `server.py` (less clean but guaranteed to work).

## Sources

### Primary (HIGH confidence)
- [MCP Python SDK - GitHub](https://github.com/modelcontextprotocol/python-sdk) - FastMCP server pattern, tool decorators, stdio transport, version info
- [MCP Build Server Guide](https://modelcontextprotocol.io/docs/develop/build-server) - Complete Python MCP server example with FastMCP, tool definitions, stdio running
- [Claude Code MCP Docs](https://code.claude.com/docs/en/mcp) - `claude mcp add` command, scope options, env vars, local/project/user scope config format
- [MCP SDK Context & Lifespan](https://deepwiki.com/modelcontextprotocol/python-sdk/2.5-context-injection-and-lifespan) - Lifespan async context manager, Context injection, generic type parameters

### Secondary (MEDIUM confidence)
- [FastMCP Claude Code Integration](https://gofastmcp.com/integrations/claude-code) - `fastmcp install claude-code` and `uv run` patterns (from standalone fastmcp docs but concepts apply to SDK's built-in FastMCP)
- [PyPI mcp package](https://pypi.org/project/mcp/) - Version 1.27.0, Python 3.10+ requirement, extras (`[cli]`)

### Tertiary (LOW confidence)
- None -- all critical claims verified against official documentation.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Official MCP SDK, existing Azure libraries already in use, patterns verified against official docs
- Architecture: HIGH - Lifespan pattern is the documented approach for shared resources; wrapper-over-existing-queries is straightforward
- Pitfalls: HIGH - Stdio stdout corruption is well-documented; Azure credential lifecycle is understood from backend experience

**Research date:** 2026-04-13
**Valid until:** 2026-05-13 (stable -- MCP SDK and Azure SDKs have slow release cadence)
