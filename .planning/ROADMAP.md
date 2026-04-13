# Roadmap: The Active Second Brain

## Milestones

- [x] **v1.0 Text & Voice Capture Loop** — Phases 1-5 plus 4.1, 4.2, 4.3 (shipped 2026-02-25, partial)
- [x] **v2.0 Foundry Migration & HITL Parity** — Phases 6-9 plus 9.1 (shipped 2026-03-01)
- [x] **v3.0 Admin Agent & Shopping Lists** — Phases 10-15 plus 11.1, 12.1, 12.2, 12.3, 12.3.1, 12.5 (shipped 2026-03-23)
- [ ] **v3.1 Observability & Evals** — Phases 16-22 (in progress)

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

### v3.1 Observability & Evals (In Progress)

**Milestone Goal:** The system watches itself -- an investigation agent answers questions about captures and system health, an eval pipeline measures agent quality, and alerts fire when things degrade.

- [x] **Phase 16: Query Foundation** - LogsQueryClient, workspace-compatible KQL templates, Cosmos containers for eval data (completed 2026-04-05)
- [x] **Phase 17: Investigation Agent** - Third Foundry agent with parameterized KQL tools and SSE streaming endpoint (completed 2026-04-06)
- [x] **Phase 17.3: Address Critical Observability Gaps** (INSERTED) - Sentry crash reporting, React error boundaries, ErrorFallback recovery UI (completed 2026-04-11)
- [x] **Phase 18: Mobile Investigation Chat** - Chat screen, dashboard cards, quick action chips, and error deep-linking (completed 2026-04-12)
- [ ] **Phase 19: Claude Code MCP Tool** - Standalone MCP server for App Insights queries from Claude Code
- [ ] **Phase 20: Feedback Collection** - Implicit quality signals, explicit thumbs up/down, golden dataset promotion
- [ ] **Phase 21: Eval Framework** - Golden datasets, deterministic evaluators, score storage, on-demand trigger
- [ ] **Phase 22: Self-Monitoring Loop** - Automated weekly evals, threshold alerts, push notifications on degradation

## Phase Details

### Phase 16: Query Foundation
**Goal**: App Insights telemetry is queryable programmatically and eval data has a home in Cosmos
**Depends on**: Nothing (first phase of v3.1)
**Requirements**: (infrastructure -- no direct requirements; enables Phases 17-22)
**Success Criteria** (what must be TRUE):
  1. LogsQueryClient can execute a KQL query against the Log Analytics workspace and return structured results
  2. All existing portal KQL templates (.kql files from Phase 14) have workspace-compatible equivalents using `traces`/`requests` tables (not `AppTraces`/`AppRequests`)
  3. Partial query results are detected and flagged (not silently treated as complete)
  4. Feedback, EvalResults, and GoldenDataset Cosmos containers exist with Pydantic document models
**Plans**: 3 (Wave 1: observability module + Cosmos containers in parallel, Wave 2: infrastructure setup + deploy)

### Phase 16.1: Improve Deployment Process (INSERTED)

**Goal:** Harden the deploy-backend workflow with dependency safety, commit-correlated revision naming, post-deploy health verification, revision cleanup, and structured deploy summary
**Requirements**: (infrastructure -- no direct requirements; prevents deployment failures)
**Depends on:** Phase 16
**Success Criteria** (what must be TRUE):
  1. `uv lock --check` fails the workflow if pyproject.toml and uv.lock are out of sync
  2. Every deployed revision name contains the git SHA for commit correlation
  3. Health endpoint is verified post-deploy (JSON body check, not just HTTP 200)
  4. Deployed image SHA matches the expected build SHA
  5. Old revisions are deactivated after successful verification
  6. Structured deploy summary appears on the workflow run page
**Plans:** 2/2 plans complete

Plans:
- [ ] 16.1-01-PLAN.md -- Pre-build dependency validation and commit-correlated revision naming
- [ ] 16.1-02-PLAN.md -- Post-deploy health verification, revision cleanup, and deploy summary

### Phase 17: Investigation Agent
**Goal**: User can ask natural language questions about their captures and system health and get human-readable answers
**Depends on**: Phase 16
**Requirements**: INV-01, INV-02, INV-03, INV-04, INV-05
**Success Criteria** (what must be TRUE):
  1. User can ask "what happened to my last capture?" and get a plain-English answer derived from App Insights telemetry
  2. User can provide a trace ID and see the full capture lifecycle (classification, filing, admin processing) with timing
  3. User can ask about recent errors and get a list with trace IDs, timestamps, and which component failed
  4. User can ask about system health and see error rates, capture volume, and latency trends for a given time window
  5. User can ask about usage patterns (captures per day, bucket distribution, destination usage) and get summarized results
**Plans**: 2 (Wave 1: enhanced KQL + query functions, Wave 2: agent tools + streaming + API endpoint)

Plans:
- [ ] 17-01-PLAN.md -- Enhanced KQL templates, result models, and query functions for investigation tools
- [ ] 17-02-PLAN.md -- InvestigationTools, agent registration, SSE adapter, API endpoint, lifespan wiring

### Phase 17.3: Address Critical Observability Gaps (INSERTED)

**Goal:** Mobile app crashes and rendering errors are visible via Sentry crash reporting and caught by React error boundaries with graceful recovery UI
**Requirements**: OBS-01, OBS-02
**Depends on:** Phase 17
**Success Criteria** (what must be TRUE):
  1. Unhandled JS exceptions are captured and reported to Sentry (not silently lost)
  2. Native crashes (OOM, Obj-C exceptions) are captured and reported to Sentry
  3. React rendering errors are caught by an error boundary with a recovery UI instead of crashing the screen
  4. Existing reportError() pipeline to /api/telemetry continues to work unchanged
**Plans:** 1/1 plans complete

Plans:
- [x] 17.3-01-PLAN.md -- Sentry SDK integration, ErrorFallback component, root layout wrapping

### Phase 18: Mobile Investigation Chat
**Goal**: Investigation agent is accessible from the phone with a conversational chat interface and at-a-glance health dashboard
**Depends on**: Phase 17
**Requirements**: MOBL-01, MOBL-02, MOBL-03, MOBL-04, MOBL-05, MOBL-06
**Success Criteria** (what must be TRUE):
  1. User can open a chat screen from the Status screen and type a question to the investigation agent
  2. Agent responses stream in real-time via SSE with a visible "Thinking..." indicator while the agent works
  3. User can ask follow-up questions in the same conversation thread without losing context
  4. Quick action chips (recent errors, today's captures, system health, last eval results) send pre-filled queries with one tap
  5. Dashboard cards on the Status screen show capture count, success rate, eval scores, and last error at a glance
**Plans:** 4/4 plans complete

Plans:
- [x] 18-01-PLAN.md -- Investigation chat screen with SSE streaming, markdown bubbles, quick action chips, and voice input
- [x] 18-02-PLAN.md -- Dashboard health cards on Status screen with investigate icon and error deep-link
- [x] 18-03-PLAN.md -- Gap closure: fix cross-screen voice event leak, MIME types, and Sentry instrumentation
- [ ] 18-04-PLAN.md -- Gap closure: fix dashboard-to-investigation error inconsistency (UAT blocker 9)

### Phase 19: Claude Code MCP Tool
**Goal**: App Insights telemetry is queryable directly from Claude Code during development sessions
**Depends on**: Phase 16
**Requirements**: MCP-01
**Success Criteria** (what must be TRUE):
  1. User can query App Insights from Claude Code via MCP tool (trace lookups, recent failures, system health) and get structured results
  2. MCP server runs as a standalone process with stdio transport (not inside the Docker image)
**Plans**: TBD

### Phase 20: Feedback Collection
**Goal**: Quality signals flow into the system automatically from user behavior and explicitly from user feedback
**Depends on**: Phase 17 (FEED-04 needs investigation agent), Phase 16 (Cosmos containers)
**Requirements**: FEED-01, FEED-02, FEED-03, FEED-04
**Success Criteria** (what must be TRUE):
  1. Recategorizing an inbox item, picking a HITL bucket, or re-routing an errand automatically records a quality signal in Cosmos (zero extra effort from user)
  2. User can tap thumbs up/down on inbox items to record explicit classification feedback
  3. User can promote a quality signal to a golden dataset entry after confirming the correct label
  4. Investigation agent can answer "what are the most common misclassifications?" by querying feedback signal data
**Plans**: TBD

### Phase 21: Eval Framework
**Goal**: Classifier and Admin Agent quality are measured with deterministic metrics against golden datasets
**Depends on**: Phase 20 (feedback data for signals), Phase 16 (Cosmos containers)
**Requirements**: EVAL-01, EVAL-02, EVAL-03, EVAL-04, EVAL-05
**Success Criteria** (what must be TRUE):
  1. A golden dataset of 50+ curated test captures with known-correct labels exists and can be run against the Classifier
  2. Classifier eval produces per-bucket precision/recall, overall accuracy, and confidence calibration metrics
  3. Admin Agent eval measures routing accuracy by destination and tool usage correctness
  4. Eval results are stored with timestamps in Cosmos and logged to App Insights for trend tracking
  5. User can trigger an eval run on-demand from mobile or Claude Code and see results
**Plans**: TBD

### Phase 22: Self-Monitoring Loop
**Goal**: The system detects its own quality degradation and alerts the user before captures go wrong
**Depends on**: Phase 21
**Requirements**: MON-01, MON-02, MON-03, MON-04
**Success Criteria** (what must be TRUE):
  1. Eval pipeline runs automatically on a weekly schedule via GitHub Actions
  2. Azure Monitor alert fires when Classifier accuracy drops below the configured threshold
  3. Azure Monitor alert fires when Admin Agent task adherence drops below the configured threshold
  4. User receives a push notification via Azure Monitor when eval scores degrade
**Plans**: TBD

## Backlog

Items not yet scheduled into a milestone or phase.

### YouTube Recipe Extraction
**Context:** Extract ingredients from YouTube recipe videos via captions/transcript. Originally Phase 13 scope, replaced by general recipe URL extraction which covers more use cases. YouTube support could be added later as an enhancement to Phase 13's URL extraction pipeline (fetch captions instead of page HTML).

## Progress

**Execution Order:**
- v1.0: 1 -> 2 -> 3 -> 4 -> 4.1 -> 4.2 -> 4.3 -> 5 (complete)
- v2.0: 6 -> 7 -> 8 -> 9 -> 9.1 (complete)
- v3.0: 10 -> 11 -> 11.1 -> 12 -> 12.1 -> 12.2 -> 12.3 -> 12.3.1 -> 12.5 -> 13 -> 14 -> 15 (complete)
- v3.1: 16 -> 16.1 -> 17 -> 17.3 -> 18 -> 19 -> 20 -> 21 -> 22

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 16. Query Foundation | 3/3 | Complete    | 2026-04-06 | - |
| 16.1. Improve Deployment Process | 2/2 | Complete    | 2026-04-06 | - |
| 17. Investigation Agent | 2/2 | Complete    | 2026-04-06 | - |
| 17.3. Address Critical Observability Gaps | 1/1 | Complete    | 2026-04-12 | - |
| 18. Mobile Investigation Chat | 4/4 | Complete   | 2026-04-13 | - |
| 19. Claude Code MCP Tool | v3.1 | 0/TBD | Not started | - |
| 20. Feedback Collection | v3.1 | 0/TBD | Not started | - |
| 21. Eval Framework | v3.1 | 0/TBD | Not started | - |
| 22. Self-Monitoring Loop | v3.1 | 0/TBD | Not started | - |
