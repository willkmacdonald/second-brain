---
phase: 18-mobile-investigation-chat
plan: 03
subsystem: ui
tags: [expo-speech-recognition, sentry, mime-type, voice-capture, react-native]

# Dependency graph
requires:
  - phase: 18-mobile-investigation-chat (18-01)
    provides: Investigation chat screen with voice input and SSE streaming
  - phase: 18-mobile-investigation-chat (18-02)
    provides: Dashboard health cards on Status screen with error deep-link
provides:
  - Guarded speech event handlers preventing cross-screen voice event leaks
  - Sentry.captureMessage instrumentation on caught errors for production observability
  - Correct MIME type detection for WAV vs M4A voice uploads
  - Extended ALLOWED_AUDIO_TYPES including audio/vnd.wave
affects: [mobile-investigation-chat, observability, voice-capture]

# Tech tracking
tech-stack:
  added: []
  patterns: [isRecordingRef guard for global speech recognition events, URI-based MIME type detection]

key-files:
  created: []
  modified:
    - mobile/app/(tabs)/index.tsx
    - mobile/lib/ag-ui-client.ts
    - backend/src/second_brain/api/capture.py

key-decisions:
  - "Use ref (not state) for isRecording guard to avoid stale closures in global event handlers"
  - "Sentry.captureMessage is additive alongside console.error -- not a replacement"
  - "Detect WAV vs M4A from URI extension rather than adding a parameter to sendVoiceCapture"

patterns-established:
  - "Guard global useSpeechRecognitionEvent hooks with a ref tracking whether this screen owns the active recording"
  - "Add Sentry.captureMessage alongside every console.error for caught errors in production"

requirements-completed: [MOBL-05, MOBL-06, OBS-01]

# Metrics
duration: 3min
completed: 2026-04-13
---

# Phase 18 Plan 03: UAT Gap Closure Summary

**Fixed cross-screen voice event leak and Sentry blind spot for caught errors to restore error observability pipeline**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-13T02:58:53Z
- **Completed:** 2026-04-13T03:01:39Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Guarded capture screen's `audiostart` and `error` speech event handlers with `isRecordingRef` to prevent cross-screen event leaks from the investigate screen's voice session
- Added `Sentry.captureMessage` at both `console.error` sites in `index.tsx` so caught errors reach Sentry in production builds
- Fixed `sendVoiceCapture` to detect WAV vs M4A from URI extension and set correct MIME type/filename
- Added `audio/vnd.wave` to backend `ALLOWED_AUDIO_TYPES` for iOS compatibility

## Task Commits

Each task was committed atomically:

1. **Task 1: Guard capture screen speech handlers and fix MIME types** - `cb8fe29` (fix)
2. **Task 2: Verify backend tests pass and no regressions** - verification only, no commit (182 tests passed, 0 new TS errors)

**Plan metadata:** pending (docs: complete plan)

## Files Created/Modified
- `mobile/app/(tabs)/index.tsx` - Added isRecordingRef guard on audiostart/error handlers, Sentry.captureMessage at both console.error sites, Sentry import
- `mobile/lib/ag-ui-client.ts` - WAV vs M4A MIME type detection from URI extension in sendVoiceCapture
- `backend/src/second_brain/api/capture.py` - Added audio/vnd.wave to ALLOWED_AUDIO_TYPES frozenset

## Decisions Made
- Used a ref (`isRecordingRef`) rather than reading `isRecording` state directly in event handlers, because global `useSpeechRecognitionEvent` hooks create closures that would capture stale state values
- Kept `Sentry.captureMessage` additive alongside `console.error` -- console.error provides local dev visibility, Sentry provides production observability. The `enabled: !__DEV__` setting (Phase 17.3 decision) means captureMessage is a no-op in dev builds but active in production EAS builds
- Detected MIME type from URI extension rather than threading a format parameter through the call chain -- simpler and works for both speech recognition persist (WAV) and cloud fallback audio recorder (M4A) paths

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- `pytest --timeout=30` flag not recognized (pytest-timeout not installed); ran without timeout, tests completed in 1.92s
- System python3 pointed to Python 3.14 without pytest; used `uv run` to invoke correct backend virtualenv

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- UAT blockers 8 (dashboard cards showing "None") and 9 (error deep-link) should now pass on next EAS build
- Voice event leak is fixed at the source (guard on handlers) rather than as a workaround
- Error observability pipeline is complete: caught errors flow through Sentry.captureMessage -> Sentry -> dashboard cards -> investigation agent
- Ready to proceed to Phase 19 or re-run UAT to confirm fixes

## Self-Check: PASSED

All files exist. All commits verified.

---
*Phase: 18-mobile-investigation-chat*
*Completed: 2026-04-13*
