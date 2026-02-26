# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-25)

**Core value:** One-tap capture from a phone instantly routes through an agent chain that classifies, files, and sharpens thoughts into concrete next actions -- with zero organizational effort.
**Current focus:** v2.0 Proactive Second Brain -- Foundry migration + specialist agents with proactive follow-up

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-02-25 — Milestone v2.0 started (Proactive Second Brain)

## Performance Metrics

**Velocity (v1.0):**
- Total plans completed: 28
- Average duration: 3.2 min
- Total execution time: 1.5 hours

**v2.0:** No plans executed yet.

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [v2.0 REJECTED]: Single-agent architecture conflicts with core project vision
- [v2.0 Vision]: Multi-agent orchestration is the GOAL, not just infrastructure migration
- [v2.0 Vision]: Specialist agents per bucket: Admin Agent, Projects Agent, People Agent, Ideas Agent
- [v2.0 Vision]: Orchestrator + Classifier + specialist agents -- Foundry manages orchestration
- [v2.0 Confirmed]: gpt-4o-transcribe replaces Whisper for voice transcription
- [v2.0 Confirmed]: Hard delete approach -- Orchestrator, HandoffBuilder, Perception Agent, Whisper code all go
- [v2.0 Confirmed]: Keep Blob Storage manager and all Cosmos DB code (models, CRUD, classify_and_file)
- [v2.0 Confirmed]: Backend must boot cleanly throughout migration, CI must stay green

### Research Findings (Critical)

- HandoffBuilder is incompatible with AzureAIAgentClient (HTTP 400 on JSON schema validation)
- Connected Agents cannot call local @tool functions (server-side execution only)
- should_cleanup_agent=False required for persistent agents in FastAPI lifespan
- AzureAIAgentClient requires azure.identity.aio.DefaultAzureCredential (async, not sync)
- Three RBAC assignments required: dev Entra ID, Container App MI, Foundry project MI
- AGUIWorkflowAdapter is a complete rewrite (~150 lines), not a migration

### Pending Todos

None.

### Blockers/Concerns

- [Reopened]: Connected Agents @tool constraint -- needs re-research for multi-agent architecture
- [Resolved]: AG-UI adapter redesign -- FoundrySSEAdapter approach confirmed by research
- [Resolved]: Agent lifecycle -- should_cleanup_agent=False with stable agent IDs
- [Resolved]: Thread management -- fresh Foundry thread per follow-up, no history contamination
- [Open]: Foundry pricing vs Chat Completions pricing -- monitor during v2.0 execution
- [Open]: How do specialist agents (Admin, Projects, People, Ideas) interact with local @tools in Foundry?

## Session Continuity

Last session: 2026-02-25
Stopped at: discuss-phase 6 revealed v2.0 needs multi-agent architecture. Redefine v2.0 via /gsd:new-milestone.
Resume file: None
Resume action: /gsd:new-milestone (redefine v2.0 with specialist agents vision)
