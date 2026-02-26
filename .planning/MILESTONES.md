# Milestones: The Active Second Brain

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
