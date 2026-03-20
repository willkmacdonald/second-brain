---
phase: 13-recipe-url-extraction
plan: 02
subsystem: api, mobile
tags: [pydantic, react-native, source-attribution, admin-notifications, linking]

# Dependency graph
requires:
  - phase: 13-recipe-url-extraction
    provides: ErrandItem sourceName/sourceUrl fields, RecipeTools fetch_recipe_url tool
provides:
  - ErrandItemResponse with sourceName/sourceUrl fields in API responses
  - Recipe success/failure delivery heuristic for admin notifications
  - ErrandRow source attribution subtitle with tappable URL
affects: [13-03-PLAN, mobile Status screen, admin notification display]

# Tech tracking
tech-stack:
  added: []
  patterns: [source attribution passthrough from Cosmos to API to mobile, delivery heuristic compound keyword matching]

key-files:
  created: []
  modified:
    - backend/src/second_brain/api/errands.py
    - backend/src/second_brain/processing/admin_handoff.py
    - mobile/components/ErrandRow.tsx
    - mobile/app/(tabs)/status.tsx

key-decisions:
  - "Recipe delivery indicators use specific phrases (items added, no recipe found, error fetching) -- bare 'from' too broad"
  - "Source attribution subtitle uses Pressable+Linking.openURL for browser navigation on tap"
  - "Source fields are optional (None default) -- regular errand items unaffected"

patterns-established:
  - "Optional API response fields with None defaults for backward compatibility"
  - "Conditional UI subtitle rendering based on presence of optional source fields"

requirements-completed: [RCPE-02, RCPE-03]

# Metrics
duration: 2min
completed: 2026-03-20
---

# Phase 13 Plan 02: API Source Attribution and Mobile ErrandRow Source Subtitle Summary

**ErrandItemResponse extended with sourceName/sourceUrl, delivery heuristic updated for recipe notifications, ErrandRow shows tappable "from: Recipe Name" subtitle**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-20T14:46:29Z
- **Completed:** 2026-03-20T14:48:58Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Extended ErrandItemResponse with optional sourceName and sourceUrl fields, passing through from Cosmos documents at both destination and unrouted item construction sites
- Added recipe success/failure indicators (items added, no recipe found, error fetching) to the admin notification delivery heuristic
- Added source attribution subtitle to ErrandRow that renders "from: Recipe Name" in muted gray text, with tap-to-open browser functionality via Linking.openURL

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend API response model and update delivery heuristic** - `2a8b96f` (feat)
2. **Task 2: Add source attribution subtitle to mobile ErrandRow** - `264087c` (feat)

## Files Created/Modified
- `backend/src/second_brain/api/errands.py` - Added sourceName/sourceUrl fields to ErrandItemResponse, updated both construction sites
- `backend/src/second_brain/processing/admin_handoff.py` - Added recipe-specific delivery indicators to _response_needs_delivery
- `mobile/components/ErrandRow.tsx` - Source attribution subtitle with Pressable/Linking for tappable URL
- `mobile/app/(tabs)/status.tsx` - Added sourceName/sourceUrl to ErrandItem interface

## Decisions Made
- Recipe delivery indicators use specific phrases ("items added", "no recipe found", "error fetching") rather than broad terms like "from" which would false-positive on many responses
- Source attribution uses Pressable wrapping Text for the tap target, with Linking.openURL for browser navigation
- Source fields default to None so existing non-recipe errand items are completely unaffected

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- API now returns source attribution fields for recipe-sourced errand items
- Mobile UI renders source attribution with tappable URLs
- Admin Agent recipe success summaries will now appear as notifications
- Plan 03 (Admin Agent instructions update and end-to-end testing) is ready to proceed

## Self-Check: PASSED

All 4 modified files verified present. Both task commits (2a8b96f, 264087c) verified in git log.

---
*Phase: 13-recipe-url-extraction*
*Completed: 2026-03-20*
