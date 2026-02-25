---
phase: 05-voice-capture
plan: 02
subsystem: api
tags: [fastapi, multipart, sse, whisper, blob-storage, voice-capture]

# Dependency graph
requires:
  - phase: 05-01
    provides: BlobStorageManager, transcribe_audio, voice capture settings
  - phase: 04-hitl-clarification-and-ag-ui-streaming
    provides: AGUIWorkflowAdapter, _convert_update_to_events, SSE streaming patterns
provides:
  - POST /api/voice-capture endpoint with multipart audio upload + SSE streaming
  - BlobStorageManager lifespan lifecycle (init + cleanup)
  - Orchestrator instructions updated for audio-sourced input awareness
affects: [05-voice-capture]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Synthetic Perception step with manual StepStarted/StepFinished events"
    - "Manual SSE lifecycle in generator (no _stream_sse wrapper) for mixed synthetic + workflow steps"
    - "Blob upload -> transcribe -> delete -> classify pipeline"

key-files:
  created: []
  modified:
    - backend/src/second_brain/main.py
    - backend/src/second_brain/agents/orchestrator.py

key-decisions:
  - "Manual SSE lifecycle (not _stream_sse) to avoid duplicate RunStarted/RunFinished events"
  - "Blob deleted immediately after transcription per CONTEXT.md (no permanent audio storage)"
  - "Settings stored on app.state for voice-capture endpoint access to Whisper config"
  - "B008 noqa for File(...) default — standard FastAPI pattern"

patterns-established:
  - "Synthetic step pattern: yield StepStarted/StepFinished around non-agent operations"
  - "Manual generator with interleaved synthetic steps + workflow stream"

requirements-completed: [ORCH-03, CAPT-04]

# Metrics
duration: 2min
completed: 2026-02-25
---

# Phase 5 Plan 2: Voice Capture Endpoint Summary

**POST /api/voice-capture wiring: multipart audio upload -> Blob Storage -> Whisper transcription -> Orchestrator/Classifier pipeline with SSE streaming**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-25T17:41:51Z
- **Completed:** 2026-02-25T17:44:17Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- POST /api/voice-capture endpoint accepts multipart audio, transcribes, classifies, and streams SSE
- Synthetic Perception step wraps upload/transcribe/delete with step events
- Orchestrator instructions updated to acknowledge Perception Agent audio source

## Task Commits

Each task was committed atomically:

1. **Task 1: Create POST /api/voice-capture endpoint with multipart upload + SSE streaming** - `26c9720` (feat)
2. **Task 2: Update Orchestrator instructions for audio-sourced input routing** - `713d9fe` (feat)

## Files Created/Modified
- `backend/src/second_brain/main.py` - Voice-capture endpoint, BlobStorageManager lifespan lifecycle, size validation, error handling
- `backend/src/second_brain/agents/orchestrator.py` - Instructions updated to mention Perception Agent

## Decisions Made
- [05-02]: Manual SSE lifecycle (not _stream_sse helper) to avoid duplicate RunStarted/RunFinished — voice-capture mixes synthetic Perception step with workflow stream
- [05-02]: Blob deleted immediately after successful transcription per CONTEXT.md decision (no permanent audio storage)
- [05-02]: Settings stored on app.state so voice-capture endpoint can access Whisper deployment name and Azure OpenAI endpoint
- [05-02]: B008 ruff noqa for File(...) default — standard FastAPI multipart pattern that ruff's bugbear rule flags

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added B008 noqa comment for FastAPI File(...) default**
- **Found during:** Task 1 (voice-capture endpoint)
- **Issue:** ruff B008 flags `File(...)` in function defaults, but this is standard FastAPI pattern
- **Fix:** Added `# noqa: B008` comment to the parameter line
- **Files modified:** backend/src/second_brain/main.py
- **Verification:** `ruff check` passes
- **Committed in:** 26c9720 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Trivial lint suppression for standard FastAPI pattern. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required. Blob Storage and Whisper deployment settings already configured in Plan 01.

## Next Phase Readiness
- Voice-capture backend endpoint is fully wired and ready for mobile integration
- Plan 03 (Expo app voice recording) can connect to this endpoint

## Self-Check: PASSED

- [x] backend/src/second_brain/main.py exists and contains voice_capture endpoint
- [x] backend/src/second_brain/agents/orchestrator.py exists and mentions Perception
- [x] Commit 26c9720 exists (Task 1)
- [x] Commit 713d9fe exists (Task 2)
- [x] All 43 existing tests pass (no regressions)
- [x] Ruff lint + format clean

---
*Phase: 05-voice-capture*
*Completed: 2026-02-25*
