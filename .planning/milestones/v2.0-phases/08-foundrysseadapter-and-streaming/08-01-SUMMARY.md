---
phase: 08-foundrysseadapter-and-streaming
plan: 01
subsystem: streaming
tags: [sse, fastapi, streaming-response, ag-ui, foundry, async-generator]

# Dependency graph
requires:
  - phase: 07-classifier-agent-baseline
    provides: AzureAIAgentClient with classifier_agent_id, classifier_agent_tools on app.state
provides:
  - streaming/sse.py with encode_sse and 7 event constructors (STEP_START, STEP_END, CLASSIFIED, MISUNDERSTOOD, UNRESOLVED, COMPLETE, ERROR)
  - streaming/adapter.py with stream_text_capture and stream_voice_capture async generators
  - POST /api/capture endpoint for text captures (JSON body -> SSE stream)
  - POST /api/capture/voice endpoint for voice captures (multipart upload -> SSE stream)
affects: [08-02 mobile event parser update, phase-09 HITL flows]

# Tech tracking
tech-stack:
  added: []
  patterns: [async-generator-sse, encode_sse-wire-format, blob-cleanup-on-stream-complete]

key-files:
  created:
    - backend/src/second_brain/streaming/__init__.py
    - backend/src/second_brain/streaming/sse.py
    - backend/src/second_brain/streaming/adapter.py
    - backend/src/second_brain/api/capture.py
    - backend/tests/test_streaming_adapter.py
  modified:
    - backend/src/second_brain/main.py

key-decisions:
  - "Async generator functions (not class) for adapter -- matches CONTEXT recommendation, ~170 lines vs old 540-line class"
  - "BlobStorageManager.delete_audio used for voice blob cleanup (already existed, no new method needed)"
  - "B008 noqa for FastAPI File(...) default -- standard FastAPI pattern, Ruff false positive"

patterns-established:
  - "SSE wire format: data: {json}\\n\\n with no event: field (react-native-sse default 'message' type)"
  - "Event constructors return dicts, encode_sse converts to SSE string -- separation of concerns"
  - "Voice capture blob cleanup in finally block of stream wrapper generator"

requirements-completed: [STRM-01, STRM-02, STRM-03]

# Metrics
duration: 3min
completed: 2026-02-27
---

# Phase 8 Plan 01: FoundrySSEAdapter and Streaming Summary

**Async generator SSE adapter bridging Foundry agent streaming to AG-UI events, with /api/capture (text) and /api/capture/voice (multipart) endpoints**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-27T15:21:20Z
- **Completed:** 2026-02-27T15:25:15Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- streaming/sse.py: encode_sse helper + 7 event constructors with new contract names (STEP_START, STEP_END, CLASSIFIED, MISUNDERSTOOD, UNRESOLVED, COMPLETE, ERROR)
- streaming/adapter.py: stream_text_capture and stream_voice_capture async generators with CoT suppression, 60s timeout, and defensive arg/result parsing
- POST /api/capture (text JSON body) and POST /api/capture/voice (multipart upload) endpoints wired into FastAPI app
- 19 unit tests covering SSE format, event structure, and type name contract -- all pass along with 42 existing tests (61 total)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create streaming module (sse.py + adapter.py) and unit tests** - `14d79fe` (feat)
2. **Task 2: Create POST /api/capture endpoint and wire into main.py** - `de562ce` (feat)

## Files Created/Modified
- `backend/src/second_brain/streaming/__init__.py` - Empty package init
- `backend/src/second_brain/streaming/sse.py` - SSE encoder + 7 event constructors
- `backend/src/second_brain/streaming/adapter.py` - Async generator functions for text and voice capture streaming
- `backend/src/second_brain/api/capture.py` - POST /api/capture and /api/capture/voice endpoints
- `backend/src/second_brain/main.py` - Added capture_router include
- `backend/tests/test_streaming_adapter.py` - 19 unit tests for SSE encoding and event constructors

## Decisions Made
- Used async generator functions (not a class) for the adapter, consistent with CONTEXT recommendation and RESEARCH analysis showing ~170 lines vs old 540-line AGUIWorkflowAdapter class
- BlobStorageManager.delete_audio already existed with the right interface (accepts blob URL, non-fatal on failure) -- no new method needed
- Added noqa: B008 for FastAPI File(...) default parameter -- this is a standard FastAPI pattern that Ruff B008 incorrectly flags

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Backend streaming pipeline is complete and wired into the app
- Plan 02 will update the mobile event parser to handle new top-level event types (CLASSIFIED, MISUNDERSTOOD, UNRESOLVED instead of CUSTOM wrappers)
- Mobile URLs need updating from /api/ag-ui to /api/capture and from /api/voice-capture to /api/capture/voice

---
*Phase: 08-foundrysseadapter-and-streaming*
*Completed: 2026-02-27*
