---
phase: 09-hitl-parity-and-observability
plan: 05
subsystem: capture, mobile
tags: [voice, follow-up, transcription, gpt-4o-transcribe, multipart, sse, ag-ui]

# Dependency graph
requires:
  - phase: 09-04
    provides: _stream_with_reconciliation handles LOW_CONFIDENCE events in follow-up
  - phase: 08-ag-ui-streaming
    provides: SSE event constructors and adapter pattern
provides:
  - POST /api/capture/follow-up/voice endpoint for voice follow-up
  - sendFollowUpVoice client function for mobile
  - Voice-first follow-up UI on both capture screens
affects: [09-06, uat]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Voice follow-up transcribes in endpoint (not via agent tool) to avoid extra round-trip"
    - "In-memory audio bytes used for transcription -- no blob re-download"
    - "followUpMode state toggles voice/text for follow-up input on both screens"

key-files:
  created: []
  modified:
    - backend/src/second_brain/api/capture.py
    - mobile/lib/types.ts
    - mobile/lib/ag-ui-client.ts
    - mobile/app/capture/text.tsx
    - mobile/app/(tabs)/index.tsx

key-decisions:
  - "Transcribe in endpoint (not via agent tool) because follow-up only needs text for reclassification"
  - "Use in-memory audio_bytes directly for transcription -- no blob re-download needed"
  - "Voice is default follow-up mode; text is fallback via toggle"

patterns-established:
  - "Voice follow-up uses same _stream_with_reconciliation wrapper as text follow-up"
  - "Compact 60x60 record button for follow-up (vs 80x80 for main capture)"
  - "text.tsx gains audio recording infrastructure for follow-up mode only"

requirements-completed: [HITL-02]

# Metrics
duration: 5min
completed: 2026-02-27
---

# Phase 9 Plan 5: Voice Follow-Up Summary

**Voice-first follow-up for misunderstood captures with gpt-4o-transcribe endpoint and toggle UI on both screens**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-27T23:52:08Z
- **Completed:** 2026-02-27T23:56:46Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- New POST /api/capture/follow-up/voice endpoint transcribes audio from in-memory bytes and streams follow-up reclassification
- Mobile follow-up defaults to voice recording with compact 60x60 record button
- "Type instead" / "Record instead" toggle switches between voice and text follow-up modes
- text.tsx gains complete audio recording infrastructure (useAudioRecorder, AudioModule, permissions)
- All five SSE callbacks (onMisunderstood, onUnresolved, onComplete, onError, onLowConfidence) on both screens
- TypeScript compiles cleanly with no type errors

## Task Commits

Each task was committed atomically:

1. **Task 1: Add POST /api/capture/follow-up/voice endpoint** - `12c5347` (feat)
2. **Task 2: Add voice follow-up client and voice-first UI on follow-up screens** - `a39bd24` (feat)

## Files Created/Modified
- `backend/src/second_brain/api/capture.py` - Added follow_up_voice endpoint with multipart audio, transcription, and reconciliation
- `mobile/lib/types.ts` - Added SendFollowUpVoiceOptions interface
- `mobile/lib/ag-ui-client.ts` - Added sendFollowUpVoice function
- `mobile/app/capture/text.tsx` - Added voice-first follow-up with audio recorder, toggle, and all callbacks
- `mobile/app/(tabs)/index.tsx` - Added voice-first follow-up with toggle (reuses existing audio infrastructure)

## Decisions Made
- Transcribe in the endpoint (not via agent tool) because the follow-up only needs the text for reclassification -- avoids an extra agent round-trip
- Use in-memory audio_bytes directly for gpt-4o-transcribe transcription -- blob is only for audit trail, no re-download needed
- Voice is the default follow-up mode on both screens, consistent with the app's voice-first philosophy

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Voice follow-up flow complete end-to-end (mobile -> backend -> transcribe -> reclassify -> SSE)
- Ready for 09-06 (instruction tuning) which is the final gap closure plan
- All capture and follow-up paths now support voice-first input

---
*Phase: 09-hitl-parity-and-observability*
*Completed: 2026-02-27*
