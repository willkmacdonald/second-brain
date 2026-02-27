# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-25)

**Core value:** One-tap capture from a phone instantly routes through an agent chain that classifies, files, and proactively follows up -- with zero organizational effort.
**Current focus:** Phase 9 -- HITL Parity and Observability (v2.0 Proactive Second Brain)

## Current Position

Phase: 9 of 12 (HITL Parity and Observability) -- gap closure in progress
Plan: 5 of 6 complete in current phase
Status: Phase 09 gap closure plan 05 complete (voice follow-up)
Last activity: 2026-02-27 -- Phase 9 Plan 05 complete (voice follow-up endpoint + voice-first UI)

Progress: [===========░░░░░░░░░] 40/TBD plans (v1.0 complete, v2.0 phase 9 gap closure)

## Performance Metrics

**Velocity (v1.0):**
- Total plans completed: 28
- Average duration: 3.2 min
- Total execution time: 1.5 hours

**v2.0:**
- Plans completed: 12
- 06-01: 3 min (2 tasks, 9 files)
- 06-02: 4 min (2 tasks, 6 files)
- 06-03: 5 min (3 tasks, 4 files)
- 07-01: 5 min (2 tasks, 9 files)
- 07-02: 3 min (2 tasks, 2 files)
- 08-01: 3 min (2 tasks, 6 files)
- 08-02: 2 min (2 tasks, 2 files)
- 09-01: 5 min (2 tasks, 7 files)
- 09-02: 3 min (2 tasks, 4 files)
- 09-03: 3 min (2 tasks, 6 files)
- 09-04: 2 min (2 tasks, 7 files)
- 09-05: 5 min (2 tasks, 5 files)

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [v2.0]: FastAPI is the orchestrator via if/elif routing -- Connected Agents not used (local @tool constraint)
- [v2.0]: HandoffBuilder, AGUIWorkflowAdapter, Orchestrator, Perception Agent all hard deleted
- [v2.0]: gpt-4o-transcribe replaces Whisper as @tool on Classifier agent
- [v2.0]: should_cleanup_agent=False for all persistent agents; IDs stored as env vars
- [v2.0]: Notification budget (3/day) and quiet hours (9pm-8am) built before any scheduler connects to push
- [v2.0]: Projects Agent is a stub -- action item extraction deferred to v2.1
- [v2.0]: Geofencing deferred to v3.0 -- Saturday morning time-window heuristic instead
- [06-01]: AsyncDefaultAzureCredential persisted on app.state across lifespan for Foundry client use
- [06-02]: model_deployment_name='gpt-4o' passed to AzureAIAgentClient constructor (required when no agent_id)
- [06-02]: agents_client.list_agents(limit=1) used as probe call for fail-fast auth validation
- [06-02]: fastapi + uvicorn added as direct deps (previously transitive via agent-framework-ag-ui)
- [06-03]: Custom 'integration' pytest marker registered for deployed endpoint tests
- [06-03]: RBAC triple verified: developer Azure AI User + Container App MI Azure AI User + Foundry MI Cognitive Services User
- [07-01]: file_capture returns structured dicts {bucket, confidence, item_id} instead of format strings
- [07-01]: Misunderstood status writes Inbox only (classificationMeta=None, filedRecordId=None)
- [07-01]: agentChain updated to ["Classifier"] -- no orchestrator in v2
- [07-01]: allScores is empty dict {} -- agent-determined, not per-bucket tracking
- [07-01]: openai added as direct dep for explicit AsyncAzureOpenAI transcription usage
- [07-02]: Tools passed via ChatOptions at get_response() time, not at AzureAIAgentClient constructor
- [07-02]: Separate AzureAIAgentClient per agent role (classifier vs probe client)
- [07-02]: Agent tools stored on app.state.classifier_agent_tools for request-time reuse
- [08-01]: Async generator functions (not class) for adapter -- ~170 lines vs old 540-line class
- [08-01]: BlobStorageManager.delete_audio used for voice blob cleanup (already existed)
- [08-01]: Event names: STEP_START/STEP_END/CLASSIFIED/MISUNDERSTOOD/UNRESOLVED/COMPLETE/ERROR (top-level, no CUSTOM wrapper)
- [08-02]: CLASSIFIED fires onComplete immediately; COMPLETE only closes EventSource (no double-fire)
- [08-02]: Legacy v1 event types retained in union and switch for backward compat during dev
- [08-02]: sendClarification and sendFollowUp unchanged -- Phase 9 scope
- [09-01]: Wrapper generator pattern for post-stream side effects (persistence, reconciliation) -- adapter stays pure
- [09-01]: foundryConversationId in MISUNDERSTOOD event payload for wrapper extraction
- [09-01]: Orphan reconciliation copies classification to original doc and deletes new doc (same as v1)
- [09-01]: handlePendingResolve delegates to handleRecategorize for instant PATCH confirm (no SSE)
- [09-02]: OTel spans inside async generators (not endpoint handlers) to preserve context across async boundaries
- [09-02]: Debug-level logging retained alongside OTel spans as dual observability output
- [09-02]: Defensive result extraction in middleware (hasattr/isinstance) handles both raw dict and FunctionResult wrapper
- [09-03]: Guard handleBucketSelect on hitlInboxItemId (not hitlThreadId) -- PATCH uses inbox ID
- [09-03]: No SSE connection needed for bucket filing -- simple PATCH/response sufficient
- [09-04]: LOW_CONFIDENCE event uses same value shape as CLASSIFIED (inboxItemId, bucket, confidence)
- [09-04]: Follow-up LOW_CONFIDENCE auto-accepts with toast (user already provided extra context)
- [09-04]: hitlTriggered=true on LOW_CONFIDENCE prevents COMPLETE from double-firing onComplete
- [09-05]: Voice follow-up transcribes in endpoint (not agent tool) -- avoids extra round-trip
- [09-05]: In-memory audio_bytes used for transcription -- blob is audit trail only, no re-download
- [09-05]: Voice is default follow-up mode; text is fallback via toggle

### Research Findings (Critical)

- HandoffBuilder incompatible with AzureAIAgentClient (HTTP 400, GitHub #3097)
- Connected Agents cannot call local @tool functions (server-side only)
- AzureAIAgentClient requires azure.identity.aio.DefaultAzureCredential (async)
- Three RBAC assignments: dev Entra ID, Container App MI, Foundry project MI
- AGUIWorkflowAdapter is complete rewrite (~150 lines FoundrySSEAdapter)
- FoundrySSEAdapter event surface needs empirical confirmation during Phase 7

### Pending Todos

None.

### Blockers/Concerns

- [Open]: Foundry pricing vs Chat Completions pricing -- monitor during execution
- [Open]: FoundrySSEAdapter AgentResponseUpdate event surface -- confirm empirically in Phase 7
- [Open]: gpt-4o-transcribe East US2 region availability -- validate at deployment time
- [Open]: 5 persistent agent connections + APScheduler memory stability -- monitor in Phase 12

## Session Continuity

Last session: 2026-02-27
Stopped at: Completed 09-05-PLAN.md (voice follow-up endpoint + voice-first UI)
Resume file: .planning/phases/09-hitl-parity-and-observability/09-05-SUMMARY.md
Resume action: Execute 09-06-PLAN.md (instruction tuning)
