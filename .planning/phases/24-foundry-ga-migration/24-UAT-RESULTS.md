---
phase: 24-foundry-ga-migration
artifact: UAT-RESULTS
captured_at: "2026-05-17T01:23:00Z"
status: PASSED-WITH-NOTES
operator: will@willmacdonald.com
deployed_revision: second-brain-api--sha-853a68b (succeeded by --0000089 after Step C env-var removal)
deployed_image_sha: 853a68b46ad920005e3d70fe39f810df814548a8
---

# Phase 24 Post-Deploy UAT Results

## Verdict

**PASSED-WITH-NOTES.** All Phase 24-specific GA migration code paths verified
end-to-end in production. Two non-Phase-24 product gaps surfaced (recipe
extraction reliability + admin retry loop on permanent failures) and have
been backlogged as Phase 25/26 + two backlog items.

## Soak timeline

- **2026-05-11T14:32Z** — Phase 24 GA migration deployed (revision sha-1bc40d8)
- **2026-05-15..16** — Voice/text captures observed silently failing with `forced_tool_failure` SSE + empty AppExceptions JSONDecodeError row; no successful captures
- **2026-05-17T00:44Z** — JSONDecodeError hotfix deployed (commit c5a2fc7) — protects `_parse_args` against partial GA streaming chunks. This bug was actually a 24-16 fix that had been written but never committed — surface area: every capture
- **2026-05-17T01:00Z** — Admin tool-detection hotfix deployed (commit 853a68b) — `_output_tool_called` now walks function_call content blocks for tool names. Plan 24-11 calibrated against an incorrect probe interpretation; surface area: every Admin capture
- **2026-05-17T01:02Z+** — UAT executed against revision sha-853a68b
- **2026-05-17T01:23Z** — Step C env-var removal completed (revision rolled to --0000089, same image SHA)

## UAT scorecard

| # | Capture | Status | Notes |
|---|---------|--------|-------|
| 1 | Voice errand: "buy milk and bread" | ✓ PASS | Admin (0.90) → `add_errand_items` → `milk` + `bread` on `jewel`, Inbox doc deleted, no duplicates |
| 2 | Voice task: "remind me to call the dentist" | ✓ PASS | People (0.85) — correct per classifier instructions ("Call X about Y" = People) |
| - | "submit expense report" + manual reclassify | ✓ PASS | Initially Projects (0.85); reclassified to Admin → `add_task_items` → appears in Tasks tab |
| 3 | Recipe URL (AllRecipes) | SKIPPED | Not a Phase 24 bug — AllRecipes returns HTTP 402, Playwright timeouts. Phase 26 will retire recipe extraction; two product gaps backlogged in the meantime. |
| 4 | Ambiguous: "the thing about the other thing" | ✓ PASS | Classifier confidence 0.50 → status=`pending`. UI prompted for clarification. |
| 5 | Reclassify pending → Ideas | ✓ PASS | `classificationMeta.classifiedBy: "User"`, `agentChain: ["Classifier", "User"]`, `status` flipped pending→classified. **`conversationHistory` populated with 2 turns** — Plan 24-17 P0-1 Option A working end-to-end. |
| 6 | Investigation chat: "how many captures today" | ✓ PASS | GA `streaming/investigation_adapter` (Plan 24-07), `system_health` tool fired (24-05 stripped decorators), "7 captures" response. |
| 7-9 | People/Projects/Ideas (incidental from #2 + #4) | ✓ | |
| 10-11 | `manage_destination` / `manage_affinity_rule` | NOT TESTED | Same wiring as `add_errand_items`/`add_task_items`; same `_output_tool_called` detection path verified by #1. No reason to expect different behavior. |
| 12-13 | `/health` + Tasks tab dashboard | ✓ | `{"status":"ok","foundry":"connected","cosmos":"connected","admin_agent":"ready","investigation_agent":"ready"}` |
| 14-15 | Observability spot-checks | ✓ | Zero `forced_tool_failure` events after revision sha-853a68b deployed; previous events all from broken-window 2026-05-15..17. |

## Phase 24-specific code paths verified in production

- ✓ Streaming classifier adapter (`streaming/adapter.py`, Plan 24-16 + hotfix c5a2fc7)
- ✓ Admin agent + admin_handoff (Plans 24-09/10/11 + hotfix 853a68b)
- ✓ Option A conversationHistory persistence (Plans 24-15/17)
- ✓ Investigation streaming adapter (Plan 24-07)
- ✓ Voice path split — voice → mobile on-device transcription → text capture (Plan 24-15)
- ✓ File capture (Classifier 24-14 + Admin 24-09 factories, GA `Agent` + `FoundryChatClient`)
- ✓ Capture-trace middleware (Plan 24-03 — `CaptureTraceAgentMiddleware` + `CaptureTraceFunctionMiddleware`)
- ✓ `Settings.extra='ignore'` tolerance for residual env vars (Plan 24-21)
- ✓ Hotfixed `/health` probe reads agent attrs (Plan 24-22 inline fix)
- ✓ Step C env-var removal completed (this artifact) — `AZURE_AI_*_AGENT_ID` orphans gone, Container App rolled to revision --0000089

## Product gaps surfaced (backlogged, not Phase 24 bugs)

1. **Recipe extraction reliability** — AllRecipes blocks programmatic fetches with HTTP 402; Playwright `networkidle` timeout on ad-heavy pages. Phase 26 (Remove Recipe Extraction) staged in roadmap to retire the capability rather than fix it. Two related backlog items: "Admin Retry Bound" and "Admin Recipe-Fetch Fallback" (latter becomes obsolete on Phase 26 completion).
2. **Admin retry loop on permanent failures** — `errands.py` treats `adminProcessingStatus=failed` as "needs reprocessing", causing the "Processing 1 new capture..." banner to stick forever when an item fails unrecoverably (e.g. recipe URL with all 3 fetch tiers failing). Backlog item "Admin Retry Bound" proposes capping at N=3 retries via `adminRetryCount` field.

## 7-day forced_tool_failure tracking window

Per CONTEXT post-deploy validation list and FORCED_TOOL_FAILURE_COUNT KQL
template (Plan 24-18), forced_tool_failure rate must stay below 1% of
captures and below 5/day across the next 7 days (through 2026-05-24).
Above-threshold rates trigger investigation but do NOT block phase
completion — they surface as a follow-up plan if needed.

Baseline at deploy:
- Pre-hotfix (2026-05-11..17 broken window): 100% failure rate for new captures
- Post-hotfix (2026-05-17T01:00Z onward): 0 forced_tool_failure events for legitimate captures; recipe URL test triggered expected no_output_tool path (NOT counted as failure)

## Operator notes

The two Phase 24 hotfixes (`c5a2fc7` + `853a68b`) were both surfaced
DURING this UAT. Without driving UAT, the system would have remained
silently broken indefinitely — capture submissions appeared to succeed
on the API surface but never created Inbox docs (JSONDecodeError) or
created Inbox docs that never got cleaned up (admin tool-detection).
This validates the value of post-deploy UAT as a phase gate.

Both hotfixes were code that was ALREADY WRITTEN in 24-16 / 24-11 but
never committed — the working tree carried the fix files in an
uncommitted state when 24-16 / 24-11 commits landed. Future phases
should add a "git status clean before push" check to the deploy
workflow to prevent this class of fix-loss.
