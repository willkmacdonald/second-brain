---
name: investigate
description: Use when the user asks about the deployed Second Brain system's telemetry -- captures, errors, traces, system health, latency, usage patterns, classifier behavior, admin agent activity -- or asks follow-up questions referring to a recent investigation's output. This is the primary operational support interface for the system.
---

# Investigate Skill

When the user asks a question about the deployed Second Brain system,
use the `second-brain-telemetry` MCP tools to query App Insights
directly. No network hop to the deployed API -- queries run locally
via `az login` credentials against Log Analytics.

## When to invoke (Rule B)

**Invoke AUTOMATICALLY** when the user's message contains explicit
telemetry vocabulary:

- "errors", "exceptions", "failures", "crashes", "broken"
- "captures", "last capture", "most recent capture", "my last ..."
- "traces", "trace lifecycle", "trace ID"
- "system health", "latency", "p95", "p99", "success rate", "error rate"
- "classifier" (with behavior context), "admin agent" (with behavior
  context), "inbox", "bucket"
- "how many X this week/day/hour"
- "what happened with/to Y"
- "is the system healthy/broken/slow/degraded"

**ALSO invoke AUTOMATICALLY** when the user's message is a follow-up
to a recent investigation in this conversation AND uses pronouns or
references to the previous answer:

- "tell me more about that"
- "why did that happen"
- "step 4" / "the first error" / "that trace"
- "go deeper on ..."
- "what about yesterday instead"
- "show me the component breakdown"

## When to ASK first

If the user's question has partial telemetry vocabulary but could
plausibly be about local code, tests, or development:

> "Do you want me to check the deployed system for this, or look at
> the code/tests?"

Examples of ambiguous questions:
- "why is it slow?" (local tests? deployed backend?)
- "is this working?" (code? deployed?)
- "why did it fail?" (tests? production?)

## When NOT to invoke

Do NOT invoke when the user is clearly asking about:
- The codebase itself ("read file X", "how does function Y work")
- Local tests ("run the tests", "why did pytest fail")
- Git state ("show recent commits", "what's on main")
- Planning, designs, specs, documentation
- Anything outside the deployed Second Brain backend

## How to invoke

Use the `second-brain-telemetry` MCP tools directly. No Bash commands,
no scripts, no network calls to the deployed backend.

**Tool routing** -- map user intent to the right MCP tool:

| User asks about... | MCP tool | Key parameters |
|---|---|---|
| "what happened to my capture", specific trace ID, "last capture" | `trace_lifecycle` | `trace_id` (optional -- omit for most recent) |
| "errors", "failures", "exceptions", "crashes" | `recent_errors` | `time_range` (1h/6h/24h/3d/7d), `component` (optional) |
| "system health", "latency", "success rate", "p95/p99" | `system_health` | `time_range` |
| "how many captures", "usage", "distribution", "by bucket/destination" | `usage_patterns` | `time_range`, `group_by` (day/hour/bucket/destination) |
| "admin agent activity", "processing", "admin audit" | `admin_audit` | (no params) |
| Anything requiring custom KQL, complex or unusual queries | `run_kql` | `query` (KQL string), `time_range` |

**Error handling:**
- If a tool returns `{"error": true, "type": "ClientAuthenticationError", ...}`:
  suggest `az login` to refresh Azure credentials
- If a tool returns `{"error": true, "type": "config_error", ...}`:
  explain that `AZURE_LOG_ANALYTICS_WORKSPACE_ID` needs to be set
  (check MCP server registration in `.mcp.json`)
- For other errors: show the error message and suggest retrying or
  simplifying the query

**Presenting results:**
- Format the raw JSON into readable summaries, tables, or bullet points
- For `trace_lifecycle`: show events in chronological order with timestamps
- For `recent_errors`: show as a table with timestamp, component, message;
  note if truncated ("showing N of M")
- For `system_health`: summarize key metrics (capture count, success rate,
  latency) with trend comparison
- For `usage_patterns`: show as a list or table grouped by the requested
  dimension

**Follow-up handling:**
MCP tools are stateless -- there are no thread IDs. Follow-ups work
because Claude has conversation context. Tool results contain stable
identifiers (trace IDs, timestamps, component names) that can be
referenced in follow-up tool calls.

- **"tell me more about that"** / **"the first error"** / **"that trace"**
  -- Extract the specific ID (trace_id, timestamp, component) from the
  previous tool result in the conversation and pass it to the appropriate
  tool. For example, if the user says "trace the first error" after seeing
  `recent_errors` output, extract the `capture_trace_id` from the first
  error record and call `trace_lifecycle(trace_id=<that_id>)`.
- **"what about yesterday instead"** -- Adjust `time_range` parameter and
  re-call the same tool.
- **"show me the component breakdown"** -- Call
  `usage_patterns(group_by="bucket")` or the appropriate dimension.
- **"go deeper on ..."** -- Use `run_kql` with a targeted KQL query based
  on what was returned.

Claude's conversation context IS the memory -- no server-side thread
management needed.

## Examples

User: "show me errors from the last 24 hours"
--> call `recent_errors` with `time_range="24h"`

User: "trace my last capture"
--> call `trace_lifecycle` with no trace_id

User: "is the system healthy?"
--> call `system_health` with `time_range="24h"`

User: "how many captures this week by bucket?"
--> call `usage_patterns` with `time_range="7d"`, `group_by="bucket"`

User: "show me admin agent activity"
--> call `admin_audit`

User: "tell me more about the first one" (after recent_errors)
--> extract `capture_trace_id` from the first result, call
    `trace_lifecycle(trace_id=<id>)`

User: "what about the last 3 days instead?" (after system_health)
--> call `system_health` with `time_range="3d"`

User: "read the investigation_client.py file"
--> Do NOT invoke. This is a code-reading request, not a system query.

User: "is the backend healthy?"
--> ASK first: "Do you want me to check the deployed system for this,
  or look at the code/tests?"
