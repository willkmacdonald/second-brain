# Requirements: The Active Second Brain

**Defined:** 2026-03-01
**Core Value:** One-tap capture from a phone instantly routes through an agent that classifies, files, and clarifies — with zero organizational effort from the user.

## v3.0 Requirements

Requirements for v3.0 Admin Agent & Shopping Lists. Each maps to roadmap phases.

### Agent Infrastructure

- [x] **AGNT-01**: Admin Agent registered as persistent Foundry agent on startup (mirrors Classifier pattern)
- [x] **AGNT-02**: Admin Agent has separate AzureAIAgentClient instance with own agent_id and tool list
- [x] **AGNT-03**: Admin Agent processes Inbox items classified as Admin, running silently after Classifier files to Inbox
- [x] **AGNT-04**: Inbox items get a "processed" flag after Admin Agent handles them

### Shopping Lists

- [x] **SHOP-01**: Shopping list items stored in Cosmos DB, grouped by store
- [x] **SHOP-02**: Admin Agent routes items to correct store based on agent instructions (Jewel, CVS, pet store, etc.)
- [x] **SHOP-03**: User can capture ad hoc items ("need cat litter") that flow through Classifier → Admin Agent → correct store list
- [x] **SHOP-04**: Admin Agent splits multi-item captures across multiple stores from a single capture
- [x] **SHOP-05**: User can swipe-to-remove items from shopping lists

### Inbox Cleanup

- [x] **CLEAN-01**: Admin Agent deletes successfully processed inbox items instead of flagging them, keeping the Inbox free of stale processed entries

### Classifier Multi-Bucket Splitting

- [x] **SPLIT-01**: Mixed-content captures with intents targeting different buckets produce separate inbox items per bucket
- [x] **SPLIT-02**: Single SSE event confirms all filed buckets to the user with multi-bucket toast format
- [x] **SPLIT-03**: Admin-classified split items trigger Admin Agent background processing in a single batched task
- [x] **SPLIT-04**: Single-intent captures are unaffected -- behavior identical to pre-split flow
- [x] **SPLIT-05**: Voice captures support multi-split identically to text captures

### Recipe Extraction

- [x] **RCPE-01**: User can paste any recipe webpage URL that gets classified as Admin, and Admin Agent extracts recipe ingredients from the page
- [x] **RCPE-02**: Extracted ingredients are added to the appropriate grocery store shopping list
- [x] **RCPE-03**: Shopping list items from recipes show source attribution (recipe name/URL)

### Mobile UI

- [x] **MOBL-01**: Status & Priorities screen exists as a new tab in the app
- [x] **MOBL-02**: Status screen displays shopping lists grouped by store with item counts
- [x] **MOBL-03**: User can expand a store to see its items and tap to check off / swipe to remove

### Observability

- [x] **OBS-01**: configure_azure_monitor scoped to application loggers (logger_name="second_brain") to prevent SDK noise
- [x] **OBS-02**: Logger.info traces visible in App Insights AppTraces table (not just WARNING+)
- [x] **OBS-03**: Consistent log level policy enforced across all backend source files (ERROR/WARNING/INFO/DEBUG)
- [x] **OBS-04**: Per-capture trace ID (capture_trace_id) propagated end-to-end from mobile through classification, admin processing, and errand writes
- [x] **OBS-05**: Mobile app generates trace ID per capture, sends as X-Trace-Id header, and displays it for copy-paste debugging
- [x] **OBS-06**: Mobile client-side errors reported to backend telemetry proxy endpoint and logged to App Insights
- [x] **OBS-07**: Four version-controlled KQL query files: capture trace, recent failures, system health, admin agent audit
- [x] **OBS-08**: Azure Monitor alert rules configured for API errors, capture failures, and health check with push notification delivery

## Future Requirements (v3.1+)

### Push Notifications

- **PUSH-01**: Push notification when agent-processed output is ready
- **PUSH-02**: Location-aware reminders when near a store with items on its list

### Additional Specialist Agents

- **SPEC-01**: Projects Agent — action item tracking, progress follow-ups
- **SPEC-02**: Ideas Agent — weekly idea check-ins, keeps captured ideas alive
- **SPEC-03**: People Agent — relationship tracking, interaction nudges

### Admin Agent Enhancements

- **ADMN-01**: "I've got free hours" → Admin Agent surfaces fitting tasks
- **ADMN-02**: Recurring item auto-ordering (computer use for Chewy.com, etc.)
- **ADMN-03**: Weekend meal prep planning pipeline
- **ADMN-04**: Agent-to-agent feedback (Admin Agent pushes back misclassified items to Classifier)

### Content & Search

- **SRCH-01**: Full-text search across all buckets
- **SRCH-02**: Cross-references extracted (people mentioned in projects, etc.)
- **DIGT-01**: Daily digest at 6:30 AM CT
- **DIGT-02**: Weekly review digest on Sunday 9 AM CT

## Out of Scope

| Feature | Reason |
|---------|--------|
| Push notifications | Deferred to v3.1+ — pull-based UI sufficient for v3.0 |
| Location-aware reminders | Expo managed workflow limitations; deferred to v3.1+ |
| Real-time streaming of Admin Agent work | Specialist agents work in background; results appear on Status screen |
| Other specialist agents (Projects, Ideas, People) | Prove pattern with Admin Agent first |
| Connected Agents pattern (Foundry) | Cannot call local @tool functions; code-based routing used instead |
| Recipe website scraping (non-YouTube) | Start with YouTube only; consider recipe-scrapers later |
| Item deduplication/merge | Accept duplicates for now; user can manually delete |
| Shared/collaborative lists | Single-user system |
| Pantry/inventory tracking | Shopping lists are capture-based, not inventory |
| Aisle/store layout sorting | Sort by addition order; defer optimization |
| Offline support | Requires connectivity (existing constraint) |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| AGNT-01 | Phase 11 | Complete |
| AGNT-02 | Phase 10 | Complete |
| AGNT-03 | Phase 11 | Complete |
| AGNT-04 | Phase 11 | Complete |
| SHOP-01 | Phase 10 | Complete |
| SHOP-02 | Phase 10 | Complete |
| SHOP-03 | Phase 11 | Complete |
| SHOP-04 | Phase 11 | Complete |
| SHOP-05 | Phase 12 | Complete |
| RCPE-01 | Phase 13 | Complete |
| RCPE-02 | Phase 13 | Complete |
| RCPE-03 | Phase 13 | Complete |
| MOBL-01 | Phase 12 | Complete |
| MOBL-02 | Phase 12 | Complete |
| MOBL-03 | Phase 12 | Complete |
| SPLIT-01 | Phase 11.1 | Complete |
| SPLIT-02 | Phase 11.1 | Complete |
| SPLIT-03 | Phase 11.1 | Complete |
| SPLIT-04 | Phase 11.1 | Complete |
| SPLIT-05 | Phase 11.1 | Complete |
| CLEAN-01 | Phase 12.1 | Complete |
| OBS-01 | Phase 14 | Not started |
| OBS-02 | Phase 14 | Not started |
| OBS-03 | Phase 14 | Not started |
| OBS-04 | Phase 14 | Not started |
| OBS-05 | Phase 14 | Not started |
| OBS-06 | Phase 14 | Not started |
| OBS-07 | Phase 14 | Not started |
| OBS-08 | Phase 14 | Not started |

**Coverage:**
- v3.0 requirements: 29 total
- Mapped to phases: 29/29
- Unmapped: 0

---
*Requirements defined: 2026-03-01*
*Last updated: 2026-03-22 after Phase 14 planning*
