---
phase: 19-claude-code-mcp-tool
plan: 01
subsystem: observability
tags: [mcp, fastmcp, app-insights, kql, azure-monitor, stdio, claude-code]

# Dependency graph
requires:
  - phase: 17-investigation-agent
    provides: "observability query functions and models in second_brain.observability"
provides:
  - "MCP server with 6 App Insights telemetry tools for Claude Code"
  - "Project-scope MCP registration via .mcp.json"
  - "Direct local telemetry access via DefaultAzureCredential (no API key needed)"
affects: [19-02, investigate-skill]

# Tech tracking
tech-stack:
  added: ["mcp[cli] 1.27.0 (FastMCP server + stdio transport)"]
  patterns: ["FastMCP lifespan for Azure client lifecycle", "Context[ServerSession, AppContext] injection", "Structured error returns (never crash)", "Editable backend dependency for single-source-of-truth queries"]

key-files:
  created:
    - mcp/server.py
    - mcp/pyproject.toml
    - mcp/.python-version
    - mcp/uv.lock
    - .mcp.json
  modified: []

key-decisions:
  - "MCP server is single-file (server.py ~300 lines) -- sufficient for 6 wrapper tools"
  - "RESULT_LIMIT=20 (higher than Investigation Agent's 10) since Claude Code has more screen space"
  - "trace_lifecycle truncation keeps LAST N records (not first N) to preserve terminal outcome"
  - "Claude Code CLI writes MCP config to .mcp.json (not .claude/settings.json as plan expected)"
  - "prerelease=allow in pyproject.toml [tool.uv] section for agent-framework-azure-ai RC dependency"

patterns-established:
  - "FastMCP lifespan: async context manager yields AppContext with LogsQueryClient + credential"
  - "Every tool: _get_app(ctx) -> _check_config(app) -> try/except with structured error return"
  - "MCP project registration via .mcp.json at repo root (committed, project-scope)"

requirements-completed: [MCP-01]

# Metrics
duration: 5min
completed: 2026-04-14
---

# Phase 19 Plan 01: MCP Server Foundation Summary

**FastMCP server with 6 App Insights telemetry tools (5 mirroring Investigation Agent + raw KQL) registered in Claude Code via stdio transport**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-13T23:56:21Z
- **Completed:** 2026-04-14T01:13:42Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Created standalone MCP server package at `mcp/` with editable backend dependency for single-source-of-truth query functions
- All 6 tools registered and discoverable: trace_lifecycle, recent_errors, system_health, usage_patterns, admin_audit (NEW), run_kql
- Server starts gracefully without Azure credentials -- tools return structured config_error
- MCP server auto-starts when Claude Code opens the project

## Task Commits

Each task was committed atomically:

1. **Task 1: Create MCP server package with pyproject.toml and server.py** - `3135472` (feat)
2. **Task 2: Register MCP server in Claude Code and verify tool discovery** - `96e0fcd` (chore)

## Files Created/Modified
- `mcp/server.py` - FastMCP server with lifespan, 6 tool functions, stdio transport
- `mcp/pyproject.toml` - Package definition with mcp[cli] + editable backend dependency
- `mcp/.python-version` - Python version pinned to 3.12
- `mcp/uv.lock` - Resolved dependency lockfile
- `.mcp.json` - MCP server registration (project scope)

## Decisions Made
- **Single-file server:** 6 tools are thin wrappers around existing query functions; splitting across modules would over-engineer ~300 lines
- **RESULT_LIMIT=20:** Claude Code has more screen space than the mobile Investigation Agent (which uses 10)
- **Tail truncation for trace_lifecycle:** When truncating, keep the LAST N records since the terminal event (success/failure) is at the end
- **.mcp.json vs .claude/settings.json:** The Claude Code CLI (`claude mcp add --scope project`) writes to `.mcp.json` at repo root, not `.claude/settings.json` as the plan documented. This is the correct current behavior
- **prerelease=allow in pyproject.toml:** Added under `[tool.uv]` so `uv sync` works without CLI flag (agent-framework-azure-ai is RC)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] MCP config file location differs from plan**
- **Found during:** Task 2 (MCP registration)
- **Issue:** Plan specified `.claude/settings.json` but `claude mcp add --scope project` writes to `.mcp.json` at repo root
- **Fix:** Used the CLI's actual output location (`.mcp.json`), added AZURE_LOG_ANALYTICS_WORKSPACE_ID env var reference manually
- **Files modified:** `.mcp.json`
- **Verification:** `claude mcp list` shows server as Connected
- **Committed in:** 96e0fcd

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Config file location change is cosmetic -- the MCP server registration works correctly regardless of which file stores the config. No functional impact.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required. The MCP server uses `DefaultAzureCredential` which picks up the existing `az login` session. The `AZURE_LOG_ANALYTICS_WORKSPACE_ID` env var must be set in the shell environment for tools to function (they return structured config_error if unset).

## Next Phase Readiness
- All 6 MCP tools are registered and discoverable
- Ready for Plan 02: migrate `/investigate` skill to use local MCP tools instead of deployed API
- Server verified with `claude mcp list` showing Connected status

## Self-Check: PASSED

All 5 created files verified on disk. Both task commits (3135472, 96e0fcd) found in git log.

---
*Phase: 19-claude-code-mcp-tool*
*Completed: 2026-04-14*
