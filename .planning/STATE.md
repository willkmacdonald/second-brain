# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-25)

**Core value:** One-tap capture from a phone instantly routes through an agent chain that classifies, files, and sharpens thoughts into concrete next actions -- with zero organizational effort.
**Current focus:** Milestone v2.0 -- Foundry Agent Service Migration

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements for v2.0 milestone
Last activity: 2026-02-25 -- Milestone v2.0 started (Foundry Agent Service migration)

Progress: [----------] 0%

## Performance Metrics

**Velocity (v1.0):**
- Total plans completed: 28
- Average duration: 3.2 min
- Total execution time: 1.5 hours

*v2.0 metrics will be tracked here once execution begins*

## Accumulated Context

### v1.0 Decisions (Carried Forward)

Key patterns and decisions from v1.0 that inform v2.0 migration:

**Data layer (unchanged):**
- Cosmos DB with 5 containers (Inbox, People, Projects, Ideas, Admin), partitioned by /userId
- CosmosCrudTools class-based pattern to bind container references
- Graceful fallback pattern: server starts without Cosmos/Blob/OpenAI configured
- BlobStorageManager singleton pattern for voice capture storage

**Mobile app (unchanged):**
- Expo/React Native with expo-router tab navigation
- AG-UI SSE streaming via react-native-sse (EventSource<AGUIEventType>)
- sendVoiceCapture uses fetch + ReadableStream (not EventSource) for multipart upload + SSE
- In-place voice recording mode on main capture screen
- HITL flows: misunderstood (conversation), low-confidence (silent pending), recategorize (inbox)

**Backend patterns (CHANGING in v2.0):**
- AzureOpenAIChatClient + HandoffBuilder → AzureAIAgentClient + Connected Agents
- AGUIWorkflowAdapter → to be replaced
- workflow.py → to be replaced entirely
- Custom AG-UI endpoint with echo filter → to be redesigned for Foundry streaming
- API key auth middleware → unchanged
- Ruff per-file ignores for main.py (E402, I001) and camelCase Cosmos fields (N815)

**Infrastructure (evolving):**
- Azure Container Apps deployment with CI/CD (GitHub Actions, OIDC, SHA-tagged images)
- Key Vault for secrets with graceful fallback
- NEW: AI Foundry project, Application Insights, Azure AI User RBAC

### Roadmap Evolution (v1.0)

- Phases 1-5 executed (5 partially complete)
- Inserted phases: 4.1 (deployment), 4.2 (swipe-delete), 4.3 (agent-user UX)
- 28 plans completed across all phases

### Pending Todos

None.

### Blockers/Concerns

- [Open]: Connected Agents + HITL integration — how does request_info / request_misunderstood work with server-managed agents?
- [Open]: AG-UI adapter redesign — current AGUIWorkflowAdapter wraps Workflow stream; Connected Agents may emit different events
- [Open]: Agent lifecycle management — create at deploy time? At startup? How to handle instruction updates?
- [Open]: Thread management — server-managed threads vs Cosmos DB inbox items coexistence
- [Open]: Foundry Agent Service pricing vs Chat Completions pricing

## Session Continuity

Last session: 2026-02-25
Stopped at: Milestone v2.0 started, defining requirements
Resume file: .planning/fas-rearchitect.md
