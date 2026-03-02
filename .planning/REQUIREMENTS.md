# Requirements: The Active Second Brain

**Defined:** 2026-03-01
**Core Value:** One-tap capture from a phone instantly routes through an agent that classifies, files, and clarifies — with zero organizational effort from the user.

## v3.0 Requirements

Requirements for v3.0 Admin Agent & Shopping Lists. Each maps to roadmap phases.

### Agent Infrastructure

- [ ] **AGNT-01**: Admin Agent registered as persistent Foundry agent on startup (mirrors Classifier pattern)
- [x] **AGNT-02**: Admin Agent has separate AzureAIAgentClient instance with own agent_id and tool list
- [ ] **AGNT-03**: Admin Agent processes Inbox items classified as Admin, running silently after Classifier files to Inbox
- [x] **AGNT-04**: Inbox items get a "processed" flag after Admin Agent handles them

### Shopping Lists

- [x] **SHOP-01**: Shopping list items stored in Cosmos DB, grouped by store
- [x] **SHOP-02**: Admin Agent routes items to correct store based on agent instructions (Jewel, CVS, pet store, etc.)
- [ ] **SHOP-03**: User can capture ad hoc items ("need cat litter") that flow through Classifier → Admin Agent → correct store list
- [ ] **SHOP-04**: Admin Agent splits multi-item captures across multiple stores from a single capture
- [ ] **SHOP-05**: User can swipe-to-remove items from shopping lists

### Recipe Extraction

- [ ] **RCPE-01**: User can paste a YouTube URL that gets classified as Admin, and Admin Agent extracts recipe ingredients
- [ ] **RCPE-02**: Extracted ingredients are added to the appropriate grocery store shopping list
- [ ] **RCPE-03**: Shopping list items from recipes show source attribution (recipe name/URL)

### Mobile UI

- [ ] **MOBL-01**: Status & Priorities screen exists as a new tab in the app
- [ ] **MOBL-02**: Status screen displays shopping lists grouped by store with item counts
- [ ] **MOBL-03**: User can expand a store to see its items and tap to check off / swipe to remove

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
| AGNT-01 | Phase 11 | Pending |
| AGNT-02 | Phase 10 | Complete |
| AGNT-03 | Phase 11 | Pending |
| AGNT-04 | Phase 11 | Complete |
| SHOP-01 | Phase 10 | Complete |
| SHOP-02 | Phase 10 | Complete |
| SHOP-03 | Phase 11 | Pending |
| SHOP-04 | Phase 11 | Pending |
| SHOP-05 | Phase 12 | Pending |
| RCPE-01 | Phase 13 | Pending |
| RCPE-02 | Phase 13 | Pending |
| RCPE-03 | Phase 13 | Pending |
| MOBL-01 | Phase 12 | Pending |
| MOBL-02 | Phase 12 | Pending |
| MOBL-03 | Phase 12 | Pending |

**Coverage:**
- v3.0 requirements: 15 total
- Mapped to phases: 15/15
- Unmapped: 0

---
*Requirements defined: 2026-03-01*
*Last updated: 2026-03-01 after roadmap creation (Phases 10-13)*
