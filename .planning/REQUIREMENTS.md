# Requirements: The Active Second Brain

**Defined:** 2026-04-05
**Core Value:** One-tap capture from a phone instantly routes through an agent that classifies, files, and clarifies -- with zero organizational effort.

## v3.1 Requirements

Requirements for v3.1 Observability & Evals milestone. Each maps to roadmap phases.

### Investigation Agent

- [ ] **INV-01**: User can ask natural language questions about captures and get human-readable answers (e.g., "what happened to my last capture?")
- [ ] **INV-02**: User can trace a specific capture's full lifecycle by providing a trace ID
- [ ] **INV-03**: User can view recent failures and errors with trace IDs and component attribution
- [ ] **INV-04**: User can query system health (error rates, capture volume, latency trends)
- [ ] **INV-05**: User can query usage insights (capture counts by period, destination usage, bucket distribution)

### Mobile Experience

- [ ] **MOBL-01**: User can open a chat screen from the Status screen to ask investigation questions
- [ ] **MOBL-02**: Investigation agent streams responses via SSE with "Thinking..." indicator
- [ ] **MOBL-03**: User can ask follow-up questions in the same conversation thread
- [ ] **MOBL-04**: User can tap quick-action chips for common queries (recent errors, today's captures, system health, last eval results)
- [ ] **MOBL-05**: User can see at-a-glance health dashboard cards (capture count, success rate, eval scores, last error)
- [ ] **MOBL-06**: User can tap a dashboard error card to jump to investigation chat with pre-filled query

### Claude Code Integration

- [ ] **MCP-01**: User can query App Insights from Claude Code via MCP tool (trace lookups, failures, health)

### Eval Framework

- [ ] **EVAL-01**: Golden dataset of 50+ test captures with known-correct bucket labels evaluates Classifier accuracy
- [ ] **EVAL-02**: Classifier eval reports per-bucket precision/recall, overall accuracy, and confidence calibration
- [ ] **EVAL-03**: Admin Agent eval measures routing accuracy by destination and tool usage correctness
- [ ] **EVAL-04**: Eval results are stored with timestamps for trend tracking (Cosmos + App Insights)
- [ ] **EVAL-05**: User can trigger an eval run on-demand from mobile or Claude Code

### Feedback & Signals

- [ ] **FEED-01**: Implicit quality signals are captured automatically (recategorize = misclassification, HITL bucket pick, errand re-routing)
- [ ] **FEED-02**: User can provide explicit feedback on classifications (thumbs up/down)
- [ ] **FEED-03**: Quality signals can be promoted to golden dataset entries after user confirmation
- [ ] **FEED-04**: Investigation agent can answer "what are the most common misclassifications?" from signal data

### Self-Monitoring

- [ ] **MON-01**: Eval pipeline runs on a weekly automated schedule
- [ ] **MON-02**: Alert fires when Classifier accuracy drops below threshold (e.g., <85%)
- [ ] **MON-03**: Alert fires when Admin Agent task adherence drops below threshold (e.g., <80%)
- [ ] **MON-04**: User receives push notification via Azure Monitor when eval scores degrade

## v3.2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Specialist Agents

- **AGNT-01**: Projects Agent -- action item tracking, progress follow-ups
- **AGNT-02**: Ideas Agent -- weekly idea check-ins, keeps captured ideas alive
- **AGNT-03**: People Agent -- relationship tracking, interaction nudges

### Proactive Features

- **PROA-01**: Push notifications for agent-processed output
- **PROA-02**: Location-aware reminders (notify near store with items on list)
- **PROA-03**: Daily digest delivered at 6:30 AM CT
- **PROA-04**: Full-text search across all buckets

## Out of Scope

| Feature | Reason |
|---------|--------|
| Full Grafana/dashboard visualization | Over-scoped for single-user; simple cards + NL investigation sufficient |
| Real-time streaming metrics | Polling on screen open is sufficient for single user |
| Automated instruction tuning | Dangerous for production; surface signals, let user decide |
| Third-party eval platforms (Langfuse, etc.) | External dependency; Azure AI Foundry has native eval support |
| A/B testing of agent configurations | Single-user system; no statistical significance possible |
| Custom KQL query builder UI | NL agent generates KQL; query builder is a product in itself |
| Fine-tuning / model retraining | GPT-4o doesn't support fine-tuning for agent use |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INV-01 | Phase 17 | Pending |
| INV-02 | Phase 17 | Pending |
| INV-03 | Phase 17 | Pending |
| INV-04 | Phase 17 | Pending |
| INV-05 | Phase 17 | Pending |
| MOBL-01 | Phase 18 | Pending |
| MOBL-02 | Phase 18 | Pending |
| MOBL-03 | Phase 18 | Pending |
| MOBL-04 | Phase 18 | Pending |
| MOBL-05 | Phase 18 | Pending |
| MOBL-06 | Phase 18 | Pending |
| MCP-01 | Phase 19 | Pending |
| FEED-01 | Phase 20 | Pending |
| FEED-02 | Phase 20 | Pending |
| FEED-03 | Phase 20 | Pending |
| FEED-04 | Phase 20 | Pending |
| EVAL-01 | Phase 21 | Pending |
| EVAL-02 | Phase 21 | Pending |
| EVAL-03 | Phase 21 | Pending |
| EVAL-04 | Phase 21 | Pending |
| EVAL-05 | Phase 21 | Pending |
| MON-01 | Phase 22 | Pending |
| MON-02 | Phase 22 | Pending |
| MON-03 | Phase 22 | Pending |
| MON-04 | Phase 22 | Pending |

**Coverage:**
- v3.1 requirements: 25 total
- Mapped to phases: 25
- Unmapped: 0

**Note:** Phase 16 (Query Foundation) has no direct requirements -- it is infrastructure enabling Phases 17-22.

---
*Requirements defined: 2026-04-05*
*Last updated: 2026-04-05 after roadmap creation*
