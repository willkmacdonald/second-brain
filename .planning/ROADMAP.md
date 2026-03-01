# Roadmap: The Active Second Brain

## Milestones

- [x] **v1.0 Text & Voice Capture Loop** - Phases 1-5 plus 4.1, 4.2, 4.3 (shipped 2026-02-25, partial)
- [x] **v2.0 Foundry Migration & HITL Parity** - Phases 6-9 plus 9.1 (shipped 2026-03-01)
- [ ] **v3.0 Proactive Second Brain** - Phases 10-12 (planned)

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

### v3.0 Proactive Second Brain (Phases 10-12)

**Milestone Goal:** Transform the Second Brain from a filing cabinet into a proactive thinking partner — four specialist agents that follow up over time via push notifications.

- [ ] **Phase 10: Specialist Agents** - Four domain agents (Admin, Ideas, People, Projects) with post-classification routing and Cosmos DB writes
- [ ] **Phase 11: Push Notifications** - Expo push token registration, delivery pipeline, throttling, quiet hours, deep links, action buttons
- [ ] **Phase 12: Proactive Scheduling and Deployment** - APScheduler cron jobs for all agent nudges, deployed to Azure Container Apps with updated CI/CD

## Phase Details

<details>
<summary>v1.0 Phase Details (Phases 1-5)</summary>

See: .planning/milestones/v1.0-ROADMAP.md (if exists) or git history

</details>

<details>
<summary>v2.0 Phase Details (Phases 6-9.1)</summary>

See: .planning/milestones/v2.0-ROADMAP.md

</details>

### Phase 10: Specialist Agents
**Goal**: Four domain-specific agents enrich classified captures with domain intelligence before filing, each writing to its own Cosmos DB container
**Depends on**: Phase 9
**Requirements**: SPEC-01, SPEC-02, SPEC-03, SPEC-04, SPEC-05, SPEC-06
**Success Criteria** (what must be TRUE):
  1. Admin, Ideas, People, and Projects agents are visible as persistent agents in the AI Foundry portal with stable IDs
  2. After classification, the FastAPI endpoint routes the capture to the correct specialist agent based on the classified bucket
  3. Each specialist agent's @tool functions write enriched data to the correct Cosmos DB container (Admin to Admin, People to People, etc.)
  4. People Agent's `log_interaction` tool updates the `last_interaction` timestamp on the Person document
  5. Projects Agent is registered and functional as a stub (accepts captures, files them, but does not extract action items)
**Plans**: TBD

Plans:
- [ ] TBD (run /gsd:plan-phase 10 to break down)

### Phase 11: Push Notifications
**Goal**: The backend can deliver push notifications to Will's phone with frequency throttling, quiet hours, deep links, and action buttons -- proven end-to-end before any scheduler is connected
**Depends on**: Phase 10
**Requirements**: PUSH-01, PUSH-02, PUSH-03, PUSH-04, PUSH-05, PUSH-06, PUSH-07, PUSH-08, DPLY-03
**Success Criteria** (what must be TRUE):
  1. Expo push token is registered on app startup and stored in Cosmos DB via `POST /api/push-token`
  2. A test push notification sent from the backend arrives on Will's device via Expo Push Service
  3. Notification frequency budget (max 3/day) and quiet hours (9pm-8am) reject sends that would violate limits
  4. Tapping a notification deep-links to the relevant capture/person/idea in the app (not home screen)
  5. Notification action buttons ("Done" and "Snooze 1 week") trigger `POST /api/nudge/respond` and update the item in Cosmos DB
**Plans**: TBD

Plans:
- [ ] TBD (run /gsd:plan-phase 11 to break down)

### Phase 12: Proactive Scheduling and Deployment
**Goal**: Specialist agents proactively nudge Will at the right times via scheduled jobs, and the complete v3.0 system is deployed to Azure Container Apps
**Depends on**: Phase 11
**Requirements**: SCHED-01, SCHED-02, SCHED-03, SCHED-04, SCHED-05, SCHED-06, DPLY-01, DPLY-02
**Success Criteria** (what must be TRUE):
  1. APScheduler runs in the FastAPI lifespan with cron triggers for all scheduled agent jobs
  2. Admin Agent sends a Friday 5pm digest summarizing pending Admin captures and a Saturday 9am errand nudge
  3. Ideas Agent sends a weekly check-in (Tue-Thu, 10am) for the stalest un-nudged idea with contextual agent-generated copy
  4. People Agent sends a relationship nudge when the interaction gap exceeds 4 weeks (max 1/day, daily 8am scan)
  5. All scheduled notifications use agent-generated copy referencing actual capture content and the migrated backend is deployed to Azure Container Apps with updated CI/CD
**Plans**: TBD

Plans:
- [ ] TBD (run /gsd:plan-phase 12 to break down)

## Progress

**Execution Order:**
- v1.0: 1 -> 2 -> 3 -> 4 -> 4.1 -> 4.2 -> 4.3 -> 5 (complete)
- v2.0: 6 -> 7 -> 8 -> 9 -> 9.1 (complete)
- v3.0: 10 -> 11 -> 12

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
| 10. Specialist Agents | v3.0 | 0/TBD | Not started | - |
| 11. Push Notifications | v3.0 | 0/TBD | Not started | - |
| 12. Proactive Scheduling | v3.0 | 0/TBD | Not started | - |
