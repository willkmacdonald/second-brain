---
phase: 07-classifier-agent-baseline
plan: 01
subsystem: agents
tags: [foundry, classifier, transcription, middleware, gpt-4o-transcribe, cosmos-db]

# Dependency graph
requires:
  - phase: 06-foundry-infrastructure
    provides: AzureAIAgentClient setup, AsyncDefaultAzureCredential on app.state
provides:
  - ClassifierTools with file_capture @tool returning structured dicts
  - TranscriptionTools with transcribe_audio @tool using gpt-4o-transcribe
  - AuditAgentMiddleware and ToolTimingMiddleware for agent observability
  - ensure_classifier_agent function for self-healing Foundry agent registration
  - CLASSIFIER_INSTRUCTIONS covering classified/pending/misunderstood outcomes
affects: [07-02-PLAN, 08-streaming-pipeline, 09-observability]

# Tech tracking
tech-stack:
  added: [openai (direct dep for AsyncAzureOpenAI transcription)]
  patterns: [structured dict returns from tools, class-based middleware, self-healing agent registration]

key-files:
  created:
    - backend/src/second_brain/tools/transcription.py
    - backend/src/second_brain/agents/middleware.py
    - backend/tests/test_transcription.py
  modified:
    - backend/src/second_brain/tools/classification.py
    - backend/src/second_brain/agents/classifier.py
    - backend/src/second_brain/config.py
    - backend/.env.example
    - backend/pyproject.toml
    - backend/tests/test_classification.py

key-decisions:
  - "file_capture returns structured dicts instead of strings for machine-readable tool results"
  - "Misunderstood status writes Inbox only with classificationMeta=None and filedRecordId=None"
  - "agentChain updated from [Orchestrator, Classifier] to [Classifier] (no orchestrator in v2)"
  - "allScores is empty dict {} -- agent determines scores, no per-bucket tracking in v2"
  - "openai added as direct dep (was transitive) for explicit AsyncAzureOpenAI usage"

patterns-established:
  - "Tool dict returns: success={bucket, confidence, item_id}, error={error, detail}"
  - "Class-based middleware: AgentMiddleware for runs, FunctionMiddleware for tools"
  - "Self-healing agent registration: check stored ID, create-if-missing, log new ID"

requirements-completed: [AGNT-01, AGNT-02, AGNT-05, AGNT-06]

# Metrics
duration: 5min
completed: 2026-02-27
---

# Phase 7 Plan 01: Classifier Agent Baseline - Tools, Middleware, and Agent Registration Summary

**ClassifierTools.file_capture with dict returns, TranscriptionTools.transcribe_audio via gpt-4o-transcribe, middleware pair, and ensure_classifier_agent for Foundry registration**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-27T05:49:18Z
- **Completed:** 2026-02-27T05:54:17Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- Rewrote ClassificationTools to ClassifierTools with file_capture replacing classify_and_file, returning structured dicts
- Created TranscriptionTools with transcribe_audio using gpt-4o-transcribe via AsyncAzureOpenAI
- Created AuditAgentMiddleware and ToolTimingMiddleware with structured logging for AppInsights
- Rewrote classifier.py with CLASSIFIER_INSTRUCTIONS and ensure_classifier_agent for Foundry registration
- All 15 unit tests pass (12 classification + 3 transcription)

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite classification tools and create transcription tool** - `7b8b2cb` (feat)
2. **Task 2: Create middleware, rewrite classifier module, and update tests** - `3c33d7d` (feat)

## Files Created/Modified
- `backend/src/second_brain/tools/classification.py` - Rewritten: ClassifierTools with file_capture, dict returns, misunderstood handling
- `backend/src/second_brain/tools/transcription.py` - New: TranscriptionTools with transcribe_audio using gpt-4o-transcribe
- `backend/src/second_brain/agents/classifier.py` - Rewritten: CLASSIFIER_INSTRUCTIONS + ensure_classifier_agent
- `backend/src/second_brain/agents/middleware.py` - New: AuditAgentMiddleware + ToolTimingMiddleware
- `backend/src/second_brain/config.py` - Added azure_openai_endpoint and azure_openai_transcription_deployment
- `backend/.env.example` - Added AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_TRANSCRIPTION_DEPLOYMENT
- `backend/pyproject.toml` - Added openai as direct dependency, ruff per-file-ignore for transcription.py
- `backend/tests/test_classification.py` - Rewritten for file_capture with dict assertions, misunderstood test added
- `backend/tests/test_transcription.py` - New: 3 tests for transcribe_audio success/blob-failure/api-failure

## Decisions Made
- file_capture returns structured dicts (`{bucket, confidence, item_id}` or `{error, detail}`) instead of format strings for machine-readable tool results
- Misunderstood items write only to Inbox with `classificationMeta=None` and `filedRecordId=None` -- no bucket container write
- `agentChain` updated from `["Orchestrator", "Classifier"]` to `["Classifier"]` reflecting v2 architecture without orchestrator
- `allScores` set to empty dict `{}` since the agent determines classification, not per-bucket score tracking
- `openai` added as direct dependency (was previously transitive via azure-ai-agents) for explicit `AsyncAzureOpenAI` import

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. The AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_TRANSCRIPTION_DEPLOYMENT env vars are documented in .env.example but not required until Plan 02 wires the lifespan.

## Next Phase Readiness
- All building blocks (tools, middleware, agent management) ready for Plan 02 to wire into FastAPI lifespan
- Plan 02 will connect ensure_classifier_agent to app startup and create the FoundrySSEAdapter for streaming
- No blockers identified

## Self-Check: PASSED

All 10 files verified present. Both task commits (7b8b2cb, 3c33d7d) verified in git log.

---
*Phase: 07-classifier-agent-baseline*
*Completed: 2026-02-27*
