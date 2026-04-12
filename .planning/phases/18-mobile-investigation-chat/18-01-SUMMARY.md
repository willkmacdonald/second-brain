---
phase: 18-mobile-investigation-chat
plan: 01
subsystem: ui
tags: [react-native, expo, sse, markdown, chat, voice, streaming]

# Dependency graph
requires:
  - phase: 17-investigation-agent
    provides: "/api/investigate SSE endpoint with thread support"
provides:
  - "Investigation chat screen with streaming SSE, markdown bubbles, voice input"
  - "SSE client library for /api/investigate endpoint"
  - "Quick action chips for common investigation queries"
  - "Route registration for investigate push screen"
affects: [18-02, mobile-dashboard, mobile-navigation]

# Tech tracking
tech-stack:
  added: [react-native-marked, react-native-svg]
  patterns: [useMarkdown-hook-for-inline-markdown, investigation-sse-client]

key-files:
  created:
    - mobile/lib/investigate-client.ts
    - mobile/components/InvestigateBubble.tsx
    - mobile/components/QuickActionChips.tsx
    - mobile/app/investigate.tsx
  modified:
    - mobile/app/_layout.tsx
    - mobile/package.json
    - mobile/package-lock.json

key-decisions:
  - "Used useMarkdown hook from react-native-marked instead of Markdown component to avoid nested FlatList conflict"
  - "Voice input auto-submits on speech recognition end event (matching capture screen pattern)"
  - "Header 'New' button for chat reset instead of icon to be more explicit"

patterns-established:
  - "useMarkdown hook for rendering markdown inside FlatList items (avoids nested FlatList)"
  - "Investigation SSE client pattern with sendInvestigation() and InvestigateCallbacks"

requirements-completed: [MOBL-01, MOBL-02, MOBL-03, MOBL-04]

# Metrics
duration: 4min
completed: 2026-04-12
---

# Phase 18 Plan 01: Mobile Investigation Chat Screen Summary

**Streaming SSE chat screen with markdown bubbles, voice input, quick action chips, and thread follow-ups using react-native-marked**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-12T04:23:28Z
- **Completed:** 2026-04-12T04:27:31Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- SSE client for /api/investigate with proper event handling (thinking, text, done, error) and silent tool_call/tool_error/rate_warning filtering
- Chat screen with inverted FlatList, streaming text accumulation, and markdown rendering via useMarkdown hook
- Quick action chips ("Recent errors", "Today's captures", "System health") that auto-send and disappear
- Voice input reusing existing expo-speech-recognition pattern with auto-submit on end
- Thread continuity via threadId persistence across follow-up messages
- Route param support for initialQuery deep-link auto-send

## Task Commits

Each task was committed atomically:

1. **Task 1: Install react-native-marked and create SSE client, bubble, and chip components** - `d04ba4a` (feat)
2. **Task 2: Create investigation chat screen with streaming, voice input, and route registration** - `ed54a1e` (feat)

## Files Created/Modified
- `mobile/lib/investigate-client.ts` - SSE client for /api/investigate endpoint
- `mobile/components/InvestigateBubble.tsx` - Chat bubble with user/agent variants and markdown
- `mobile/components/QuickActionChips.tsx` - Three quick action chips for common queries
- `mobile/app/investigate.tsx` - Full chat screen with FlatList, input bar, voice, streaming
- `mobile/app/_layout.tsx` - Added investigate Stack.Screen route
- `mobile/package.json` - Added react-native-marked and react-native-svg dependencies
- `mobile/package-lock.json` - Updated lockfile

## Decisions Made
- Used `useMarkdown` hook from react-native-marked instead of the `Markdown` component to avoid nested FlatList conflict. The Markdown component renders its own FlatList internally, which conflicts with the chat's inverted FlatList.
- Voice input auto-submits transcribed text on the `end` event, matching the existing capture screen pattern. Uses refs to avoid stale closure issues.
- Used text "New" button in header instead of an icon for clarity.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Pre-existing TypeScript error in `_layout.tsx` (line 22) from Phase 17.3 Sentry integration: `ErrorFallback` type incompatible with Sentry's `FallbackRender`. Not caused by this plan's changes. Logged to deferred-items.md.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Chat screen is ready for navigation integration (Plan 02: dashboard cards + status screen header icon)
- All MOBL-01 through MOBL-04 requirements addressed
- MOBL-05 (dashboard cards) and MOBL-06 (deep-link) support infrastructure in place (initialQuery param)

## Self-Check: PASSED

All 5 files verified present. Both commit hashes (d04ba4a, ed54a1e) found in git log.

---
*Phase: 18-mobile-investigation-chat*
*Completed: 2026-04-12*
