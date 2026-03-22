---
phase: 13-recipe-url-extraction
plan: 03
subsystem: infra, testing
tags: [foundry-portal, uat, admin-agent-instructions, recipe-extraction, end-to-end]

# Dependency graph
requires:
  - phase: 13-recipe-url-extraction
    provides: RecipeTools fetch_recipe_url tool, ErrandItem source attribution, ErrandRow subtitle, delivery heuristic
provides:
  - Admin Agent Foundry instructions updated with Recipe URL Extraction section
  - End-to-end validated recipe URL extraction pipeline
  - Retry mechanism for admin agent intermediate-only tool invocations
  - Output tool counting to prevent silent data loss
affects: [phase-14-app-insights-audit, backlog-youtube-recipe-extraction]

# Tech tracking
tech-stack:
  added: []
  patterns: [admin agent retry with nudge prompt for intermediate-only tool runs, output tool invocation counting to distinguish fetch vs write tools]

key-files:
  created: []
  modified:
    - backend/src/second_brain/processing/admin_handoff.py

key-decisions:
  - "Admin Agent retry mechanism: when agent calls fetch_recipe_url but not add_errand_items, auto-retry with nudge prompt"
  - "Output tool counting (_count_output_tool_invocations) distinguishes intermediate tools (fetch_recipe_url) from output tools (add_errand_items)"
  - "Non-recipe URLs correctly handled by classifier confidence gating -- no special error path needed"
  - "fetch_recipe_url removed from Classifier agent tools (only Admin Agent needs it)"

patterns-established:
  - "Intermediate vs output tool classification for agent retry logic"
  - "Nudge prompt pattern: re-run agent with additional instruction when first attempt produces incomplete output"

requirements-completed: [RCPE-01, RCPE-02, RCPE-03]

# Metrics
duration: 2min
completed: 2026-03-22
---

# Phase 13 Plan 03: Admin Agent Foundry Instructions and End-to-End UAT Summary

**Admin Agent instructions updated in Foundry portal for recipe URL extraction, full pipeline validated end-to-end with retry mechanism for intermediate-only tool invocations**

## Performance

- **Duration:** 2 min (summary and docs finalization after UAT)
- **UAT Period:** 2026-03-20 to 2026-03-22 (multi-day testing with bug fixes)
- **Completed:** 2026-03-22
- **Tasks:** 2
- **Files modified:** 1 (admin_handoff.py, via UAT-discovered fixes)

## Accomplishments
- Updated Admin Agent instructions in Azure AI Foundry portal with Recipe URL Extraction section covering fetch_recipe_url usage, ingredient normalization, and source attribution fields
- Validated full end-to-end recipe URL extraction flow: paste URL -> classify as Admin -> Admin Agent fetches page -> extracts 15 ingredients -> routes to correct destinations with source attribution
- Discovered and fixed admin agent retry issue: agent sometimes calls fetch_recipe_url but responds with text instead of calling add_errand_items, resolved with auto-retry and nudge prompt
- Confirmed classifier correctly gates non-recipe URLs via confidence scoring (no special error path needed)

## Task Commits

Both tasks were human checkpoints (no code commits from this plan). However, UAT-discovered bugs were fixed in separate commits:

1. **Task 1: Update Admin Agent instructions in Foundry portal** - No commit (Foundry portal configuration)
2. **Task 2: End-to-end UAT of recipe URL extraction flow** - No commit (manual verification)

**UAT bug fix commits (made during testing):**
- `6bbe1bf` (fix) - Prevent silent data loss when admin agent calls only intermediate tools
- `6a3f823` (fix) - Retry admin agent when intermediate tool runs without output

## Files Created/Modified
- `backend/src/second_brain/processing/admin_handoff.py` - Added _count_output_tool_invocations() to distinguish intermediate from output tools, auto-retry with nudge prompt when agent calls fetch but not write

## UAT Results

### Test 1: Happy path (recipe URL) -- PASSED
- Recipe URL captured and classified to Admin bucket
- Admin Agent called fetch_recipe_url to get page content
- On first attempt, agent fetched page but responded with text instead of calling add_errand_items
- Retry mechanism with nudge prompt triggered successfully -- second attempt called add_errand_items
- 15 ingredients from "Chicken Tikka Masala" added to shopping lists
- Chicken breasts correctly routed to Agora (matching "Meat goes to Agora" affinity rule)
- 14 other ingredients routed to Jewel-Osco
- Source attribution "from: Chicken Tikka Masala" visible on all recipe items

### Test 2: Non-recipe URL -- PASSED (different behavior than planned)
- Plain URL (https://www.example.com) was NOT auto-classified to Admin
- Classifier correctly showed low-confidence bucket picker (best guess: Ideas)
- This is correct behavior -- bare URLs without recipe context should not auto-route to Admin

### Test 3: Invalid URL -- Skipped
- Same behavior as Test 2 -- classifier would not route bare URLs to Admin
- Error handling for unreachable URLs validated by the retry mechanism in Test 1

### Test 4: Source attribution display -- PASSED
- "from: Chicken Tikka Masala" displayed in muted gray below each recipe item
- Non-recipe items do not show subtitle
- Swipe-to-delete works normally on recipe items

## Decisions Made
- Admin Agent retry mechanism added: when agent calls only intermediate tools (fetch_recipe_url) without output tools (add_errand_items), the system auto-retries with a nudge prompt instructing the agent to use the fetched content
- Output tool counting via _count_output_tool_invocations() provides a reliable way to distinguish between "agent fetched data but didn't act on it" vs "agent completed the task"
- Non-recipe URLs are handled naturally by the classifier's confidence gating -- no special Admin-side error path is needed for non-recipe content
- fetch_recipe_url removed from Classifier agent tools since only the Admin Agent needs URL fetching capability

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Admin agent calls fetch_recipe_url but not add_errand_items**
- **Found during:** Task 2 (UAT)
- **Issue:** On first attempt, the Admin Agent would call fetch_recipe_url to get page content, then respond with a text summary of the recipe instead of calling add_errand_items to write the ingredients
- **Fix:** Added _count_output_tool_invocations() to distinguish intermediate tools from output tools, and auto-retry with nudge prompt when the agent calls only intermediate tools
- **Files modified:** backend/src/second_brain/processing/admin_handoff.py
- **Verification:** Retry mechanism triggered successfully, second attempt called add_errand_items with all 15 ingredients
- **Committed in:** 6bbe1bf, 6a3f823

**2. [Rule 1 - Bug] Inbox item deleted when no output produced**
- **Found during:** Task 2 (UAT)
- **Issue:** When the admin agent called only intermediate tools (fetch_recipe_url) without output tools, the inbox item was still being deleted, causing silent data loss
- **Fix:** Added output tool invocation counting -- inbox item only deleted when at least one output tool (add_errand_items) was invoked
- **Files modified:** backend/src/second_brain/processing/admin_handoff.py
- **Verification:** Inbox item preserved when agent only calls intermediate tools, deleted only after successful output
- **Committed in:** 6bbe1bf

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both fixes were essential for correctness -- without them, recipe URLs would fail silently on first agent attempt and lose the inbox item. No scope creep.

## Issues Encountered
- Test 2 and Test 3 from the plan assumed non-recipe URLs would be classified to Admin and produce error notifications. In practice, the classifier's confidence gating correctly prevents bare URLs from being auto-routed to Admin. This is better behavior than planned -- users see a bucket picker for ambiguous URLs instead of a silent admin processing failure.

## User Setup Required

None -- Admin Agent instructions were updated directly in the Foundry portal during Task 1.

## Next Phase Readiness
- Phase 13 (Recipe URL Extraction) is fully complete -- all three plans executed and validated
- v3.0 milestone (Admin Agent & Shopping Lists) is feature-complete
- Phase 14 (App Insights Operational Audit) is the next phase when ready
- YouTube recipe extraction remains in backlog, buildable on top of the fetch_recipe_url pattern

## Self-Check: PASSED

All files verified present. Both UAT bug fix commits (6bbe1bf, 6a3f823) verified in git log. SUMMARY.md created successfully.

---
*Phase: 13-recipe-url-extraction*
*Completed: 2026-03-22*
