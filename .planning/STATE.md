# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-25)

**Core value:** One-tap capture from a phone instantly routes through an agent chain that classifies, files, and proactively follows up -- with zero organizational effort.
**Current focus:** Phase 7 -- Classifier Agent Baseline (v2.0 Proactive Second Brain)

## Current Position

Phase: 7 of 12 (Classifier Agent Baseline)
Plan: 0 of TBD in current phase
Status: Ready
Last activity: 2026-02-27 -- Phase 6 complete (Foundry Infrastructure -- all 3 plans done)

Progress: [======░░░░░░░░░░░░░░] 31/TBD plans (v1.0 complete, v2.0 phase 6 complete)

## Performance Metrics

**Velocity (v1.0):**
- Total plans completed: 28
- Average duration: 3.2 min
- Total execution time: 1.5 hours

**v2.0:**
- Plans completed: 3
- 06-01: 3 min (2 tasks, 9 files)
- 06-02: 4 min (2 tasks, 6 files)
- 06-03: 5 min (3 tasks, 4 files)

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

Last session: 2026-02-26
Stopped at: Phase 7 context gathered
Resume file: .planning/phases/07-classifier-agent-baseline/07-CONTEXT.md
Resume action: /gsd:plan-phase 7
