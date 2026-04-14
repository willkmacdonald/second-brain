---
status: complete
phase: 19-claude-code-mcp-tool
source: [19-01-SUMMARY.md, 19-02-SUMMARY.md]
started: 2026-04-14T02:00:00Z
updated: 2026-04-13T12:05:00Z
---

## Current Test

[testing complete]

## Tests

### 1. MCP Server Auto-Starts
expected: Run `claude mcp list` in the project directory. The `second-brain-telemetry` server should appear with status "Connected".
result: issue
reported: "second-brain-telemetry server not listed in `claude mcp list` output — only medtech-pov, ref, microsoft-learn, and exa shown"
severity: blocker

### 2. All 6 MCP Tools Discoverable
expected: The MCP server exposes exactly 6 tools: trace_lifecycle, recent_errors, system_health, usage_patterns, admin_audit, run_kql. You can verify by asking Claude "what MCP tools are available from second-brain-telemetry?" or checking the tool list in conversation context.
result: skipped
reason: blocked by Test 1 failure (server not connected, so tools not discoverable)

### 3. Tools Return Telemetry Data
expected: Ask Claude to run a query like "show me recent errors" or "check system health". The MCP tool should return actual telemetry data from App Insights (not an error), assuming you have `az login` credentials and `AZURE_LOG_ANALYTICS_WORKSPACE_ID` set.
result: skipped
reason: blocked by Test 1 failure

### 4. Investigate Skill Routes to MCP Tools
expected: Type `/investigate what errors happened in the last hour?` — Claude should call an MCP tool (like `recent_errors`) directly, NOT shell out to a Python script or call brain.willmacdonald.com.
result: skipped
reason: blocked by Test 1 failure

### 5. Follow-Up Queries Work
expected: After getting results from an investigate query, ask a follow-up like "show me the trace for that first error". Claude should extract the trace_id or relevant identifier from the prior result and call trace_lifecycle with it — using conversation context, not a thread ID.
result: skipped
reason: blocked by Test 1 failure

## Summary

total: 5
passed: 0
issues: 1
pending: 0
skipped: 4

## Gaps

- truth: "second-brain-telemetry MCP server appears in `claude mcp list` as Connected"
  status: fixed
  reason: "User reported: second-brain-telemetry server not listed in `claude mcp list` output — only medtech-pov, ref, microsoft-learn, and exa shown"
  severity: blocker
  test: 1
  root_cause: |
    Two independent problems surfaced as one symptom:
    1. Session snapshot: `claude mcp get second-brain-telemetry` reported Connected, but `mcp__second-brain-telemetry__*` tools weren't in the live session's tool surface. Claude Code snapshots MCP tools at session start and doesn't hot-reload; the server was approved/connected after this session began. Resolution requires a session restart — no code fix.
    2. Env var naming drift: MCP server read `AZURE_LOG_ANALYTICS_WORKSPACE_ID` but backend uses `LOG_ANALYTICS_WORKSPACE_ID`. Neither was set in the user's shell. Even after session restart, tool calls would have returned "not configured" errors.
    Correct workspace ID (from Container App production config): 2a8ba30f-1bb5-489c-b7d6-bcb22f5814d2 (managed-second-brain-insights-ws, auto-created for classic App Insights migration).
  artifacts:
    - path: "mcp/server.py"
      issue: "lifespan() read only AZURE_LOG_ANALYTICS_WORKSPACE_ID, not matching backend naming"
    - path: ".mcp.json"
      issue: "env block only forwarded AZURE_LOG_ANALYTICS_WORKSPACE_ID"
    - path: "mcp/.env.example"
      issue: "did not exist — no local-setup guidance"
  missing:
    - "Accept LOG_ANALYTICS_WORKSPACE_ID (canonical) with AZURE_LOG_ANALYTICS_WORKSPACE_ID fallback in server.py lifespan()"
    - "Forward LOG_ANALYTICS_WORKSPACE_ID in .mcp.json env block"
    - "Add mcp/.env.example documenting the var + how to find the workspace ID"
    - "User action: export LOG_ANALYTICS_WORKSPACE_ID=2a8ba30f-1bb5-489c-b7d6-bcb22f5814d2 in ~/.zshrc, then restart Claude Code session"
  debug_session: ""
  fix_verified: "Server standalone test with LOG_ANALYTICS_WORKSPACE_ID set emits 'workspace_id=2a8ba30f...' and no warnings"
