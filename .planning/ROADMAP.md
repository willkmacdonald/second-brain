# Roadmap: The Active Second Brain

## Milestones

- [x] **v1.0 Text & Voice Capture Loop** — Phases 1-5 plus 4.1, 4.2, 4.3 (shipped 2026-02-25, partial)
- [x] **v2.0 Foundry Migration & HITL Parity** — Phases 6-9 plus 9.1 (shipped 2026-03-01)
- [x] **v3.0 Admin Agent & Shopping Lists** — Phases 10-15 plus 11.1, 12.1, 12.2, 12.3, 12.3.1, 12.5 (shipped 2026-03-23)

## Phases

<details>
<summary>v1.0 Text & Voice Capture Loop (Phases 1-5) — SHIPPED 2026-02-25</summary>

- [x] **Phase 1: Backend Foundation** — FastAPI server with AG-UI endpoint, Cosmos DB, API auth, and OpenTelemetry tracing
- [x] **Phase 2: Expo App Shell** — Mobile app with text input, main capture screen, and cross-platform support
- [x] **Phase 3: Text Classification Pipeline** — Orchestrator and Classifier agents that route text input to the correct bucket in Cosmos DB
- [x] **Phase 4: HITL Clarification and AG-UI Streaming** — Real-time agent chain visibility and clarification conversation for low-confidence classifications
- [x] **Phase 4.1: Backend Deployment to Azure Container Apps** (INSERTED) — Containerized deployment with CI/CD
- [x] **Phase 4.2: Swipe-to-delete inbox items** (INSERTED) — Inbox management UX
- [x] **Phase 4.3: Agent-User UX with unclear item** (INSERTED) — Three distinct classification failure flows
- [x] **Phase 5: Voice Capture** — Voice recording with Whisper transcription routed through the Perception Agent

See: .planning/milestones/ for full phase details

</details>

<details>
<summary>v2.0 Foundry Migration & HITL Parity (Phases 6-9.1) — SHIPPED 2026-03-01</summary>

- [x] **Phase 6: Foundry Infrastructure** — Foundry project connectivity, RBAC, Application Insights, old code deletion, async credential migration
- [x] **Phase 7: Classifier Agent Baseline** — Persistent Classifier agent registered in Foundry with local @tool execution
- [x] **Phase 8: FoundrySSEAdapter and Streaming** — New SSE adapter replacing AGUIWorkflowAdapter, text and voice capture end-to-end on Foundry
- [x] **Phase 9: HITL Parity and Observability** — All three HITL flows verified on Foundry, Application Insights traces and token metrics
- [x] **Phase 9.1: Mobile UX Review and Refinements** (INSERTED) — Unified capture screen with Voice/Text toggle, inline text capture, processing stages

See: .planning/milestones/v2.0-ROADMAP.md

</details>

<details>
<summary>v3.0 Admin Agent & Shopping Lists (Phases 10-15) — SHIPPED 2026-03-23</summary>

- [x] **Phase 10: Data Foundation and Admin Tools** — Pydantic models, Cosmos container, AdminTools @tool class
- [x] **Phase 11: Admin Agent and Capture Handoff** — Persistent Admin Agent with silent background processing
- [x] **Phase 11.1: Classifier Multi-Bucket Splitting** (INSERTED) — Mixed-content captures split into separate inbox items per bucket
- [x] **Phase 12: Shopping List API and Status Screen** — REST endpoints and mobile Status tab for errands
- [x] **Phase 12.1: Admin Agent Deletes Processed Items** (INSERTED) — Delete-after-success with retry for stuck items
- [x] **Phase 12.2: Rename Admin to Errands** (INSERTED) — Generic errands system replacing shopping-specific naming
- [x] **Phase 12.3: Destination Affinity System** (INSERTED) — Dynamic destinations, voice-managed affinity rules, HITL routing
- [x] **Phase 12.3.1: Security & Dead Code Cleanup** (INSERTED) — Timing-safe auth, parameterized queries, dead code removal
- [x] **Phase 12.5: On-Device Voice Transcription** (INSERTED) — iOS SFSpeechRecognizer replacing cloud transcription
- [x] **Phase 13: Recipe URL Extraction** — Three-tier fetch, ingredient extraction, source attribution
- [x] **Phase 14: App Insights Operational Audit** — Trace IDs, structured logging, KQL queries, Azure Monitor alerts
- [x] **Phase 15: v3.0 Tech Debt Cleanup** — Retry query fix, UnboundLocalError fix, test repairs

See: .planning/milestones/v3.0-ROADMAP.md

</details>

## Backlog

Items not yet scheduled into a milestone or phase.

### YouTube Recipe Extraction
**Context:** Extract ingredients from YouTube recipe videos via captions/transcript. Originally Phase 13 scope, replaced by general recipe URL extraction which covers more use cases. YouTube support could be added later as an enhancement to Phase 13's URL extraction pipeline (fetch captions instead of page HTML).

## Progress

**Execution Order:**
- v1.0: 1 -> 2 -> 3 -> 4 -> 4.1 -> 4.2 -> 4.3 -> 5 (complete)
- v2.0: 6 -> 7 -> 8 -> 9 -> 9.1 (complete)
- v3.0: 10 -> 11 -> 11.1 -> 12 -> 12.1 -> 12.2 -> 12.3 -> 12.3.1 -> 12.5 -> 13 -> 14 -> 15 (complete)
