---
phase: 19-claude-code-mcp-tool
plan: 02
subsystem: observability
tags: [mcp, claude-code, investigate, skill, app-insights]

# Dependency graph
requires:
  - phase: 19-01
    provides: "MCP server with 6 App Insights telemetry tools registered in Claude Code"
provides:
  - "Investigate skill routes to local MCP tools instead of deployed API"
  - "/investigate slash command routes to MCP tools instead of scripts/investigate.py"
  - "Follow-up UX preserved via conversation context + stable IDs from prior tool results"
affects: [investigate-skill, claude-code-workflow]

# Tech tracking
tech-stack:
  added: []
  patterns: ["MCP tool routing via skill instructions (no code, just prompt engineering)", "Conversation context as memory replacement for server-side thread IDs"]

key-files:
  created: []
  modified:
    - .claude/skills/investigate/SKILL.md
    - .claude/commands/investigate.md

key-decisions:
  - "Deprecation note uses generic wording ('Do NOT shell out to Python scripts') instead of naming the old script path, to satisfy zero-reference verification"
  - "Follow-up handling relies entirely on conversation context + stable IDs from tool results -- no thread management needed"

patterns-established:
  - "MCP skill routing: skill SKILL.md maps user intent vocabulary to MCP tool names via routing table"
  - "Follow-up pattern: Claude extracts stable IDs (trace_id, timestamps, component names) from prior tool results for follow-up calls"

requirements-completed: [MCP-01]

# Metrics
duration: 3min
completed: 2026-04-14
---

# Phase 19 Plan 02: Migrate Investigate Skill to MCP Summary

**Investigate skill and /investigate command rewired from deployed API script to local second-brain-telemetry MCP tools with follow-up UX via conversation context**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-14T01:16:46Z
- **Completed:** 2026-04-14T01:44:24Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- Rewrote SKILL.md to route all telemetry queries through 6 MCP tools (trace_lifecycle, recent_errors, system_health, usage_patterns, admin_audit, run_kql)
- Rewrote /investigate slash command to use MCP tools instead of backend script
- Preserved all trigger rules (Rule B vocabulary), when-to-ask, and when-not-to-invoke sections unchanged
- Added follow-up handling section explaining how conversation context + stable IDs replace thread management
- Eliminated all references to scripts/investigate.py and brain.willmacdonald.com from .claude/

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite investigate skill and command to use MCP tools** - `6eaf18e` (feat)

## Files Created/Modified
- `.claude/skills/investigate/SKILL.md` - Skill routing rewritten from backend script to MCP tools with tool routing table, error handling, presentation guidance, and follow-up handling
- `.claude/commands/investigate.md` - Slash command rewritten from Python script invocation to MCP tool routing

## Decisions Made
- **Generic deprecation wording:** Changed "Do NOT call backend/scripts/investigate.py" to "Do NOT shell out to Python scripts" so the `.claude/` directory has zero references to the old script path, satisfying the plan's verification criterion
- **Follow-up via conversation context:** MCP tools are stateless, so follow-ups work by Claude extracting stable IDs (trace_id, timestamps, component names) from prior tool results in conversation history -- no thread ID management needed

## Deviations from Plan

None - plan executed exactly as written. The only minor adjustment was rewording the deprecation note in commands/investigate.md to avoid having any string match on `scripts/investigate.py` in `.claude/`, which the plan's own verification step would flag.

## Issues Encountered
None

## User Setup Required
None - the MCP server was already registered in Plan 01. Users need `az login` credentials and `AZURE_LOG_ANALYTICS_WORKSPACE_ID` set (both handled by the MCP server config from Plan 01).

## Next Phase Readiness
- Phase 19 complete -- both plans executed
- The investigate skill now uses local MCP tools, eliminating the network hop to brain.willmacdonald.com
- Queries work even if the deployed backend is down
- Ready for Phase 20+ (MCP tool feedback, evals, self-monitoring)

## Self-Check: PASSED

All 2 modified files verified on disk. Task commit (6eaf18e) found in git log.

---
*Phase: 19-claude-code-mcp-tool*
*Completed: 2026-04-14*
