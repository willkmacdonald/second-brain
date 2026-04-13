# Phase 19: Claude Code MCP Tool - Context

**Gathered:** 2026-04-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Standalone MCP server exposing App Insights telemetry queries directly in Claude Code via stdio transport. Wraps the existing `second_brain.observability` query infrastructure. Runs locally as a separate process, not inside the Docker container. Migrates the `/investigate` skill to use MCP tools instead of the deployed API endpoint.

</domain>

<decisions>
## Implementation Decisions

### Tool surface area
- Full parity with Investigation Agent: all 5 tools (trace_lifecycle, recent_errors, system_health, usage_patterns, admin_audit)
- Plus a raw `execute_kql` tool for ad-hoc KQL queries
- No guardrails on raw KQL — Log Analytics is read-only, single user
- Mirror Investigation Agent tool parameter signatures exactly
- Tools only — no MCP resources
- Import query functions from `second_brain.observability` (single source of truth for KQL templates, models, queries)

### /investigate skill migration
- Once MCP is working, migrate `/investigate` skill to use local MCP tools instead of calling the deployed API endpoint
- One fewer network hop, same query capability

### Output formatting
- Structured JSON via Pydantic `.model_dump_json()` — Claude interprets and presents naturally
- Truncate large result sets: return first N records + total count (e.g., "Showing 20 of 47 errors")
- Flag partial results prominently: `is_partial` field + warning message (matches existing `QueryResult.is_partial` pattern)
- Errors returned as structured objects in the tool response: `{error: true, message: "...", type: "auth_failure"}` — not MCP-level `isError` flags

### Auth & config
- DefaultAzureCredential — uses local `az login` session, no secrets to manage
- Workspace ID from `AZURE_LOG_ANALYTICS_WORKSPACE_ID` environment variable (same pattern as backend)
- MCP server registered in project-level `.claude/settings.json` (scoped to second-brain repo)
- Server code lives in top-level `mcp/` directory (sibling to `backend/` and `mobile/`)

### Server lifecycle
- Auto-start via Claude Code config — zero manual steps per session
- Server starts even without Azure connectivity; each tool call returns structured error if auth/network fails
- Stderr logging at INFO level (Claude Code captures MCP server stderr for diagnostics)
- Built with official `mcp` Python SDK (pip install mcp) — handles stdio transport and protocol compliance

### Claude's Discretion
- Truncation threshold (how many records before truncating)
- Internal module structure within `mcp/`
- Exact tool descriptions for Claude Code discovery
- Server timeout defaults for KQL execution

</decisions>

<specifics>
## Specific Ideas

- The existing `second_brain.observability` module (queries.py, kql_templates.py, models.py) is the foundation — MCP tools are thin wrappers around `execute_kql`, `query_recent_failures`, `query_system_health`, etc.
- Project-level `.claude/settings.json` registration means the tools are only available when working in this repo
- `/investigate` skill currently calls the deployed Investigation Agent at `brain.willmacdonald.com` — after this phase, it calls the local MCP tools directly

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 19-claude-code-mcp-tool*
*Context gathered: 2026-04-13*
