# Milestones: The Active Second Brain

## v2.0 — Foundry Migration & HITL Parity (Shipped: 2026-03-01)

**Goal:** Migrate the capture pipeline from local HandoffBuilder orchestration to Azure AI Foundry Agent Service with persistent agents, and achieve full HITL parity on the new foundation.

**Shipped:** 2026-03-01

**Phases:** 6–9 (plus inserted 9.1)

| Phase | Name | Status |
|-------|------|--------|
| 6 | Foundry Infrastructure | Complete |
| 7 | Classifier Agent Baseline | Complete |
| 8 | FoundrySSEAdapter and Streaming | Complete |
| 9 | HITL Parity and Observability | Complete |
| 9.1 | Mobile UX Review and Refinements | Complete |

**Last phase number:** 9.1

**Key accomplishments:**
- Foundry Agent Service migration — persistent Classifier agent with `AzureAIAgentClient`, stable agent ID across restarts
- FoundrySSEAdapter — async generator SSE adapter replacing 540-line AGUIWorkflowAdapter with ~170-line streaming functions
- HITL parity — low-confidence bucket selection, misunderstood follow-up (text + voice), and recategorize all working on Foundry
- Application Insights observability — OTel spans on agent runs, tool calls, and streaming endpoints with token usage tracking
- Unified capture screen — Voice/Text toggle replacing separate text capture route, granular processing stages
- ContextVar-based in-place follow-up updates — eliminated fragile orphan reconciliation pattern

**Architecture:** `AzureAIAgentClient` + FastAPI code-based routing (no Orchestrator agent). Persistent Foundry agent with local `@tool` functions. Connected Agents not used (local @tool constraint).

**Scope note:** Originally defined as "Proactive Second Brain" (Phases 6-12 including specialist agents, push notifications, and scheduling). Redefined at milestone audit to ship what's built. Specialist agents, push, and scheduling move to v3.0.

**16 plans completed** across 5 phases. 19/19 requirements satisfied (redefined scope). 59 commits.

**Known gaps (accepted as tech debt):**
- `conversation/[threadId].tsx` is dead code (unreachable after unified screen refactor)
- AGNT-02 requirement text references obsolete tool names (functional intent met via `file_capture`)
- Pre-existing E501 ruff line-length errors in classifier.py/classification.py

---

## v1.0 — Text & Voice Capture Loop (Archived)

**Goal:** Prove the core capture-classify loop works with real daily use — text and voice input, automatic classification, HITL clarification, and mobile inbox.

**Shipped:** 2026-02-25 (partial — voice UAT incomplete, rearchitecture pivot)

**Phases:** 1–5 (plus inserted 4.1, 4.2, 4.3)

| Phase | Name | Status |
|-------|------|--------|
| 1 | Backend Foundation | Complete |
| 2 | Expo App Shell | Complete |
| 3 | Text Classification Pipeline | Complete |
| 4 | HITL Clarification and AG-UI Streaming | Complete |
| 4.1 | Backend Deployment to Azure Container Apps | Complete |
| 4.2 | Swipe-to-delete inbox items | Complete |
| 4.3 | Agent-User UX with unclear item | Complete (8/10 plans, 2 gap fixes executed untracked) |
| 5 | Voice Capture | Partial (backend + mobile done, UAT paused at test 3/7) |

**Last phase number:** 5 (plus 4.1, 4.2, 4.3 inserted)

**Key outcomes:**
- Text capture → Orchestrator → Classifier → filed to Cosmos DB (working)
- Voice capture → Perception → Orchestrator → Classifier (working, UAT incomplete)
- HITL flows: misunderstood (conversation), low-confidence (silent pending), recategorize (inbox)
- Deployed to Azure Container Apps with CI/CD
- AG-UI streaming with step dots and classification result

**Architecture:** `AzureOpenAIChatClient` + `HandoffBuilder` (local orchestration). Pivoting away from this in v2.0.

**28 plans completed** across all phases.

---
*Archived: 2026-02-25 — pivoting to Foundry Agent Service*
