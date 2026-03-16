# Roadmap: The Active Second Brain

## Milestones

- [x] **v1.0 Text & Voice Capture Loop** - Phases 1-5 plus 4.1, 4.2, 4.3 (shipped 2026-02-25, partial)
- [x] **v2.0 Foundry Migration & HITL Parity** - Phases 6-9 plus 9.1 (shipped 2026-03-01)
- [ ] **v3.0 Admin Agent & Shopping Lists** - Phases 10-13 (in progress)

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

<details>
<summary>v1.0 Text & Voice Capture Loop (Phases 1-5) - SHIPPED 2026-02-25</summary>

- [x] **Phase 1: Backend Foundation** - FastAPI server with AG-UI endpoint, Cosmos DB, API auth, and OpenTelemetry tracing
- [x] **Phase 2: Expo App Shell** - Mobile app with text input, main capture screen, and cross-platform support
- [x] **Phase 3: Text Classification Pipeline** - Orchestrator and Classifier agents that route text input to the correct bucket in Cosmos DB
- [x] **Phase 4: HITL Clarification and AG-UI Streaming** - Real-time agent chain visibility and clarification conversation for low-confidence classifications
- [x] **Phase 4.1: Backend Deployment to Azure Container Apps** (INSERTED) - Containerized deployment with CI/CD
- [x] **Phase 4.2: Swipe-to-delete inbox items** (INSERTED) - Inbox management UX
- [x] **Phase 4.3: Agent-User UX with unclear item** (INSERTED) - Three distinct classification failure flows
- [x] **Phase 5: Voice Capture** - Voice recording with Whisper transcription routed through the Perception Agent

</details>

<details>
<summary>v2.0 Foundry Migration & HITL Parity (Phases 6-9.1) - SHIPPED 2026-03-01</summary>

- [x] **Phase 6: Foundry Infrastructure** - Foundry project connectivity, RBAC, Application Insights, old code deletion, async credential migration (completed 2026-02-27)
- [x] **Phase 7: Classifier Agent Baseline** - Persistent Classifier agent registered in Foundry with local @tool execution (completed 2026-02-27)
- [x] **Phase 8: FoundrySSEAdapter and Streaming** - New SSE adapter replacing AGUIWorkflowAdapter, text and voice capture end-to-end on Foundry (completed 2026-02-27)
- [x] **Phase 9: HITL Parity and Observability** - All three HITL flows verified on Foundry, Application Insights traces and token metrics (completed 2026-02-28)
- [x] **Phase 9.1: Mobile UX Review and Refinements** (INSERTED) - Unified capture screen with Voice/Text toggle, inline text capture, processing stages (completed 2026-03-01)

</details>

### v3.0 Admin Agent & Shopping Lists (Phases 10-13)

**Milestone Goal:** Add the first specialist agent (Admin Agent) that enriches Admin-classified captures with store-based shopping list management, including YouTube recipe ingredient extraction. Admin Agent works silently in the background -- results appear on a new Status & Priorities screen.

- [x] **Phase 10: Data Foundation and Admin Tools** - Pydantic models, Cosmos container, and AdminTools @tool class for shopping list writes (completed 2026-03-02)
- [x] **Phase 11: Admin Agent and Capture Handoff** - Persistent Admin Agent in Foundry with silent background processing after Classifier files to Inbox (completed 2026-03-02)
- [x] **Phase 12: Shopping List API and Status Screen** - REST endpoints and mobile tab for viewing, expanding, and removing shopping list items (completed 2026-03-03)
- [ ] **Phase 12.2: Rename Admin infrastructure from shopping lists to errands** (INSERTED) - Rename data model, API, tools, and UI from shopping-specific to generic errands system
- [ ] **Phase 13: Recipe URL Extraction** - Paste any recipe webpage URL, LLM extracts ingredients and adds them to shopping list with source attribution

## Phase Details

<details>
<summary>v1.0 Phase Details (Phases 1-5)</summary>

See: .planning/milestones/v1.0-ROADMAP.md (if exists) or git history

</details>

<details>
<summary>v2.0 Phase Details (Phases 6-9.1)</summary>

See: .planning/milestones/v2.0-ROADMAP.md

</details>

### Phase 10: Data Foundation and Admin Tools
**Goal**: Shopping list data model and tool functions exist so downstream phases can write and read shopping list items
**Depends on**: Phase 9.1 (v2.0 complete)
**Requirements**: AGNT-02, SHOP-01, SHOP-02
**Success Criteria** (what must be TRUE):
  1. ShoppingLists container exists in Cosmos DB and individual shopping list item documents can be created, queried by store, and deleted
  2. AdminTools class with `add_shopping_list_items` @tool writes items to Cosmos with store field, and the tool is callable from a test harness independent of any agent
  3. Admin Agent has a separate AzureAIAgentClient instance configuration with its own tool list (no tool leakage to Classifier)
**Plans**: 2 plans

Plans:
- [x] 10-01-PLAN.md -- Data models, CosmosManager extension, AdminTools @tool, unit tests
- [x] 10-02-PLAN.md -- Admin Agent registration, config, lifespan wiring, integration tests

### Phase 11: Admin Agent and Capture Handoff
**Goal**: Admin-classified captures are silently enriched by the Admin Agent in the background, with items routed to the correct store shopping list
**Depends on**: Phase 10
**Requirements**: AGNT-01, AGNT-03, AGNT-04, SHOP-03, SHOP-04
**Success Criteria** (what must be TRUE):
  1. Admin Agent is visible as a persistent agent in the AI Foundry portal with a stable agent_id that survives backend restarts
  2. When a user captures "need cat litter and milk", the Classifier files it to Inbox as Admin, then the Admin Agent silently processes it and items appear on the correct store lists (pet store and Jewel)
  3. Inbox items classified as Admin have a "processed" flag set to true after the Admin Agent completes its work
  4. The capture flow completes and returns to the user without streaming Admin Agent work -- no SSE events from the Admin Agent reach the mobile app during capture
  5. Multi-item captures referencing different stores result in items split across the correct store lists from a single capture
**Plans**: 2 plans

Plans:
- [ ] 11-01-PLAN.md -- InboxDocument adminProcessingStatus field, process_admin_capture background function, unit tests
- [ ] 11-02-PLAN.md -- Wire fire-and-forget trigger into adapter/capture/main, Foundry instructions, end-to-end verification

### Phase 11.1: Classifier Multi-Bucket Splitting (INSERTED)

**Goal:** When a user captures mixed-content text containing multiple distinct intents targeting different buckets, the Classifier splits it into separate inbox items per bucket. Single-intent captures remain unaffected.
**Requirements**: SPLIT-01, SPLIT-02, SPLIT-03, SPLIT-04, SPLIT-05
**Depends on:** Phase 11
**Success Criteria** (what must be TRUE):
  1. Capturing "need milk and remind me to call the vet" produces two inbox items: one Admin, one in the appropriate bucket for the vet reminder
  2. The mobile toast shows "Filed to Admin, People" (multi-bucket format) for multi-split and "Filed -> Admin (0.85)" (existing format) for single-intent
  3. Multiple Admin-classified split items trigger a single batched Admin Agent background task
  4. Single-intent captures behave identically to pre-11.1 behavior
  5. Voice captures support multi-split identically to text captures
**Plans**: 4 plans

Plans:
- [x] 11.1-01-PLAN.md -- Backend adapter multi-result collection, SSE event extension, batch admin handoff, unit tests
- [x] 11.1-02-PLAN.md -- Mobile client multi-bucket toast, Classifier Foundry instruction update
- [x] 11.1-03-PLAN.md -- (GAP CLOSURE) Fix adapter batched tool call handling with call_id-based pairing
- [x] 11.1-04-PLAN.md -- (GAP CLOSURE) Revise Classifier Foundry instructions for conversational phrasing tolerance

### Phase 12: Shopping List API and Status Screen
**Goal**: Users can view their shopping lists grouped by store and remove items they have purchased
**Depends on**: Phase 11 (data written by Admin Agent)
**Requirements**: MOBL-01, MOBL-02, MOBL-03, SHOP-05
**Success Criteria** (what must be TRUE):
  1. A "Status & Priorities" tab exists in the mobile app as the third tab, and tapping it shows shopping lists grouped by store with item counts
  2. User can expand a store section to see individual items and swipe to remove an item (optimistic UI with rollback on failure)
  3. Shopping list data refreshes when the Status screen gains focus, so newly added items from captures appear without manual pull-to-refresh
  4. REST API endpoints exist for fetching shopping lists (`GET /api/shopping-lists`), and deleting items (`DELETE /api/shopping-lists/items/{id}`)
**Plans**: 2 plans

Plans:
- [ ] 12-01-PLAN.md -- Shopping List API endpoints (GET + DELETE), Pydantic models, unit tests, router registration
- [ ] 12-02-PLAN.md -- Mobile Status tab, SectionList with expand/collapse, ShoppingListRow with swipe-to-delete, focus-based refresh

### Phase 12.1: Admin agent deletes processed inbox items (INSERTED)

**Goal:** Admin Agent deletes inbox items after successful processing instead of flagging them, keeping the Inbox clean
**Requirements**: CLEAN-01
**Depends on:** Phase 12
**Plans:** 2/2 plans complete

Plans:
- [x] 12.1-01-PLAN.md -- Replace processed-upsert with delete in admin_handoff.py, update tests
- [x] 12.1-02-PLAN.md -- (GAP CLOSURE) Fix delete failure leaving 'pending' limbo, add stale pending retry

### Phase 12.2: Rename Admin infrastructure from shopping lists to errands (INSERTED)

**Goal:** Rename the Admin Agent's data model, API, tools, and UI from "shopping list" to a generic "errands/tasks" system. The Admin function handles any errand (appointments, reminders, purchases), not just shopping. Shopping items were the first use case but the naming shouldn't constrain future Admin capabilities.
**Depends on:** Phase 12.1
**Plans:** 3 plans

Plans:
- [ ] 12.2-01-PLAN.md -- Backend data layer rename (documents.py, admin.py tool, cosmos.py, tests)
- [ ] 12.2-02-PLAN.md -- Backend API layer rename (shopping_lists.py -> errands.py, main.py, tests)
- [ ] 12.2-03-PLAN.md -- Mobile UI rename (ErrandRow, status.tsx, StatusSectionRenderer) + Cosmos migration script

### Phase 13: Recipe URL Extraction
**Goal**: Users can paste any recipe webpage URL, the Admin Agent fetches the page, the LLM extracts ingredients, and adds them to the shopping list with source attribution
**Depends on**: Phase 11 (Admin Agent pipeline)
**Requirements**: RCPE-01, RCPE-02, RCPE-03
**Success Criteria** (what must be TRUE):
  1. User pastes a recipe webpage URL as a text capture, it gets classified as Admin, and the Admin Agent extracts ingredients from the page content
  2. Extracted ingredients appear on the appropriate store shopping lists as individual items
  3. Shopping list items originating from a recipe show source attribution (recipe name and/or URL) so the user knows where the item came from
  4. When a URL cannot be fetched or contains no recognizable recipe, the system fails gracefully with a clear message rather than silently dropping the capture
**Plans**: TBD

Plans:
- [ ] 13-01: TBD
- [ ] 13-02: TBD

## Progress

**Execution Order:**
- v1.0: 1 -> 2 -> 3 -> 4 -> 4.1 -> 4.2 -> 4.3 -> 5 (complete)
- v2.0: 6 -> 7 -> 8 -> 9 -> 9.1 (complete)
- v3.0: 10 -> 11 -> 11.1 -> 12 -> 12.1 -> 12.2 -> 13

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Backend Foundation | v1.0 | 3/3 | Complete | 2026-02-21 |
| 2. Expo App Shell | v1.0 | 2/2 | Complete | 2026-02-22 |
| 3. Text Classification Pipeline | v1.0 | 2/2 | Complete | 2026-02-22 |
| 4. HITL Clarification and AG-UI Streaming | v1.0 | 6/6 | Complete | 2026-02-24 |
| 4.1 Backend Deployment | v1.0 | 2/2 | Complete | 2026-02-23 |
| 4.2 Swipe-to-delete | v1.0 | 1/1 | Complete | 2026-02-24 |
| 4.3 Agent-User UX | v1.0 | 10/10 | Complete | 2026-02-25 |
| 5. Voice Capture | v1.0 | 3/3 | Complete | 2026-02-25 |
| 6. Foundry Infrastructure | v2.0 | 3/3 | Complete | 2026-02-27 |
| 7. Classifier Agent Baseline | v2.0 | 2/2 | Complete | 2026-02-27 |
| 8. FoundrySSEAdapter and Streaming | v2.0 | 2/2 | Complete | 2026-02-27 |
| 9. HITL Parity and Observability | v2.0 | 7/7 | Complete | 2026-02-28 |
| 9.1 Mobile UX Review | v2.0 | 2/2 | Complete | 2026-03-01 |
| 10. Data Foundation and Admin Tools | 2/2 | Complete    | 2026-03-02 | - |
| 11. Admin Agent and Capture Handoff | 2/2 | Complete    | 2026-03-02 | - |
| 11.1 Classifier Multi-Bucket Splitting | v3.0 | Complete    | 2026-03-03 | 2026-03-02 |
| 12. Shopping List API and Status Screen | 2/2 | Complete   | 2026-03-03 | - |
| 12.1 Admin Agent Deletes Processed Items | v3.0 | 2/2 | Complete | 2026-03-03 |
| 12.2 Rename Admin to Errands | v3.0 | 0/TBD | Not started | - |
| 13. YouTube Recipe Extraction | v3.0 | 0/TBD | Not started | - |
| 14. App Insights Operational Audit | v3.0 | 0/TBD | Not started | - |
| 15. On-Device Voice Transcription (SpeechAnalyzer) | v3.0 | 0/TBD | Not started | - |

### Phase 14: App Insights Operational Audit

**Goal:** Review and streamline App Insights logging setup to ensure operational effectiveness and efficiency. Audit log levels, query patterns, alert configuration, and cost. Ensure Python logger output is structured and actionable, not noisy.
**Requirements**: TBD
**Depends on:** Phase 13
**Plans:** TBD

Plans:
- [ ] TBD (run /gsd:plan-phase 14 to break down)

### Phase 15: On-Device Voice Transcription (SpeechAnalyzer)

**Goal:** Replace cloud-based Azure OpenAI gpt-4o-transcribe with iOS on-device transcription via `expo-speech-transcriber` and Apple's `SpeechAnalyzer` (iOS 26), eliminating transcription API costs and reducing voice capture latency
**Depends on:** Phase 5 (voice capture infrastructure)
**Requirements**: VOICE-OD-01, VOICE-OD-02, VOICE-OD-03
**Success Criteria** (what must be TRUE):
  1. Voice captures use on-device `SpeechAnalyzer` (iOS 26) via `expo-speech-transcriber` for real-time streaming transcription -- no audio upload to Azure Blob, no gpt-4o-transcribe API call
  2. Transcription accuracy is acceptable for informal voice captures (shopping items, reminders, quick notes) -- validated through manual UAT
  3. Backend transcription infrastructure (Azure Blob upload, OpenAI transcription client) remains available as a fallback but is not used in the default flow
  4. Voice capture UX shows real-time interim transcription results as the user speaks
**Plans**: TBD

Plans:
- [ ] TBD (run /gsd:plan-phase 15 to break down)

## Backlog

Items not yet scheduled into a milestone or phase.

### YouTube Recipe Extraction
**Context:** Extract ingredients from YouTube recipe videos via captions/transcript. Originally Phase 13 scope, replaced by general recipe URL extraction which covers more use cases. YouTube support could be added later as an enhancement to Phase 13's URL extraction pipeline (fetch captions instead of page HTML).
**Blocked on:** Phase 13 (recipe URL extraction foundation)
**When ready:** Add YouTube URL detection to the Admin Agent's URL handler, fetch captions via YouTube API or yt-dlp, extract ingredients using the same LLM pipeline
