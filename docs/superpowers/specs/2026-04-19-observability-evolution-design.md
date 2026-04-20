# Observability Evolution: 19.3 → 22

**Date:** 2026-04-19
**Status:** Draft for approval
**Predecessors:** Phase 19.2 (transaction-first spine, shipped 2026-04-19)
**Related memos:**
- `memory/project_native_foundry_correlation_gap.md`
- `memory/project_deferred_19.2_spine_gaps.md`
- `docs/codex-agent-observability-plan.md`

## Purpose

Phase 19.2 shipped the transaction-first spine — the ledger backbone that replaces native telemetry as the first-look operator view for capture lifecycle questions. Two gap classes remain:

1. **Infrastructure drill-down is still blind at step 4.** Native OpenTelemetry spans and Azure diagnostics are not tagged with `capture_trace_id`, so segment pages show "runs (0)" for captures that demonstrably ran.
2. **Agent behavior is not observable.** The stack today answers infrastructure questions (did it arrive, which segment failed, how long). It cannot answer behavior questions: what prompt did the agent see, what did it output, what rules drove the decision, which agent configuration was active.

This spec sequences the work to close both gaps, reconciling them with the existing Phase 20/21/22 roadmap entries (Feedback / Evals / Self-Monitoring) so the same data substrate serves both operator root-cause analysis and automated evaluation.

## Taxonomy

The four distinct observability concerns — kept separate so phases don't conflate them:

| Concern | Answers | Cardinality | Audience | Maps to |
|---|---|---|---|---|
| Infrastructure drill-down | "Which segment failed, when, with what latency" | One capture | Operator (RCA) | 19.3 + 19.4 |
| Root-cause analysis (RCA) | "What prompt, what output, what rules, what release, for this one run" | One capture | Operator (RCA) | 19.5 |
| Labels | "Was this decision right or wrong, per the user" | Per signal | User + operator (curation) | 20 |
| Evaluation | "Is the system working well enough right now" | Aggregate | System (automated) | 21 + 22 |

RCA and Eval share substrate (the decision record) but are distinct phases with distinct read paths.

## Design Rule: Built-In First

Every phase below must, before writing code, cite Phase 19.3's Native Capability Inventory. If a capability is already provided by App Insights, Sentry, Azure services, Azure AI Foundry, OpenTelemetry, Azure Monitor, Cosmos DB, Container Apps, GitHub Actions, or Expo/EAS, we adopt it. We do not rebuild platform features.

The codex plan's core rule — "Foundry First, App Summary Second" — is the specific instance of this design rule that governs RCA: raw prompts, outputs, and tool transcripts live in Foundry; the app stores references, small previews, and product-decision fields only. We do not build a second transcript store.

## Phase Sequence

```
[housekeeping: mobile EAS rebuild to close 19.2 baseline]
  ↓
Phase 19.3 — Native Capability Inventory  [investigation only, 1 plan]
  ↓
Phase 19.4 — Native Span Correlation Tagging  [memo + 3-4 impl plans]
  ↓
Phase 19.5 — Agent Decision Record & RCA View  [8-10 plans incl. mobile segment-view restructure]
  ↓ [integration check: 19.5 → 20]
Phase 20 — Labels: Feedback Signals  [5 plans]
  ↓
Phase 21 — Eval: Automated Scoring  [memo + 3-4 impl plans]
  ↓ [integration check: 21 → 22]
Phase 22 — Self-Monitoring  [thin, 3 plans]

[housekeeping: Key Vault cleanup whenever]
```

## Phase 19.3 — Native Capability Inventory

**Goal:** A single source-of-truth inventory of what the nine native surfaces we depend on already do, so subsequent phases never build what a platform provides.

**Form:** Investigation + deliverable document. Zero production code changes.

**Native surfaces in scope (9):**

1. Azure AI Foundry — Tracing depth, Conversation UI, Evaluations SDK, Prompt-agent versioning
2. OpenTelemetry — span attributes, baggage propagation, log correlation
3. Application Insights / Log Analytics — auto-instrumentation surface, table schema, retention
4. Azure Monitor — Workbooks, Alerts, Action Groups (existing `SecondBrainAlerts`)
5. Sentry.IO — Python SDK, RN SDK, tags/breadcrumbs
6. Azure Cosmos DB — diagnostic logs (`AzureDiagnostics` + `activityId_g`), Change Feed
7. Azure Container Apps — revision metadata, built-in logs
8. GitHub Actions — cron schedules, artifact storage, workflow summaries
9. Expo / EAS — crash reports, update diagnostics

**Highest-leverage rows (most likely to collapse downstream phase scope):**
- Foundry Evaluations SDK (Phase 21)
- Azure Monitor Workbooks (Phase 19.5)
- Cosmos Change Feed (Phase 20)

**Deliverable:** `docs/superpowers/specs/native-observability-inventory.md` — table-first document with columns *Capability | Native surface we use today | What we'd still need to build*. Each row cited by at least one downstream phase or it does not belong in the doc. Includes a "phase impact" addendum that may revise the scope of 19.4 / 19.5 / 20 / 21 / 22.

**Confirmation checkpoints:**

- **Checkpoint A — Foundry trace depth.** Pull a real recent capture's Foundry trace; inspect prompt, output, tool args, confidence. Determines whether Phase 19.5's decision record is small-reference (cheap) or needs to copy fields (medium).
- **Checkpoint B — Foundry evals applicability.** Live test against one agent if SDK allows. Determines Phase 21 scope.
- **Checkpoint C — Sentry RN status on deployed phone.** Confirm mobile Sentry is capturing what it should post-18-03.

**Success criteria (what must be TRUE):**
1. Inventory document exists at `docs/superpowers/specs/native-observability-inventory.md` with ≥15 rows covering all 9 surfaces.
2. Every row cites at least one downstream phase that depends on its finding.
3. Phase impact addendum exists with concrete scope deltas (e.g., "Phase 21 Plan 02 replaced by Foundry eval configuration" or "no change").
4. Three checkpoint findings (A/B/C) are documented with evidence (screenshots, query results, or trace links).

**Plan count:** 1.

**Approx size:** 1–2 days of investigation + 1 day of writing + 1 round of review.

## Phase 19.4 — Native Span Correlation Tagging

**Goal:** Every native telemetry row produced during a capture is filterable by `capture_trace_id`. The drill-down from spine to native telemetry (step 4) stops being blind.

**Problem:** The 19.2 spine ledger works. The web segment page still shows "runs (0)" for captures that ran, because the native renderer filters native spans by `capture_trace_id` and those spans aren't tagged.

**Four emit sites (collapsed into one phase per the gap memo):**

1. `backend_api` AppRequests — FastAPI middleware layer.
2. Azure AI Foundry agent spans — runs/steps/tool calls from the Foundry SDK.
3. Cosmos diagnostic logs — `AzureDiagnostics.activityId_g` needs a pivot to `capture_trace_id`.
4. Investigation custom spans — thread-kind spans emitted during investigation runs.

**Dependency on 19.3:** The fix shape depends on what is native. If OpenTelemetry baggage/context propagation can carry `capture_trace_id` automatically, the fix is middleware config. If not, explicit span attribute injection at every emit site. Cosmos (#3) is always separate — `activityId_g` comes from the Cosmos SDK, so the fix is a mapper that records `(capture_trace_id, activityId_g)` at SDK call time.

**Form:** Spike-memo + implementation. Memo decides the OTel-baggage-vs-explicit question and the Cosmos mapping strategy.

**Plans (tentative, pending 19.3):**

- Plan 01 — Spike memo. Gates Plan 02 scope. Pattern matches 19.2-01.
- Plan 02 — Backend + Foundry: OTel baggage / span attributes for `backend_api` and Foundry agent spans. (May collapse with Plan 04.)
- Plan 03 — Cosmos `activityId_g` mapping: record `(capture_trace_id, activityId_g)` tuples at every Cosmos call site; persistence mechanism chosen by memo (likely extends spine_events or a new correlation-map table).
- Plan 04 — Investigation custom spans: tag thread-kind spans at emit time.
- Plan 05 — Integrated verification.

If inventory shows OTel baggage covers sites #1, #2, #4 together, plans 02 and 04 merge. Memo decides.

**Success criteria (what must be TRUE):**
1. For any recent `capture_trace_id`, a KQL query against `AppRequests` returns the request span with `capture_trace_id` as a custom dimension.
2. Same for Foundry agent spans in `AppDependencies` (or wherever the Foundry SDK writes).
3. Given a `capture_trace_id`, the spine correlation API returns a list of Cosmos `activityId_g` values that successfully query rows in `AzureDiagnostics`.
4. The web segment page's native `FoundryRunDetail` renderer shows ≥1 run for a capture with an active Foundry run (was showing 0).
5. Investigation custom spans are filterable by correlation ID identically.

**Confirmation checkpoints:**
- Checkpoint A (pre-plan 02) — memo approved.
- Checkpoint B (post-plan 02) — live KQL query proves `backend_api` spans carry the tag.
- Checkpoint C (post-plan 03) — live query proves `activityId_g` pivot works.
- Checkpoint D (post-plan 05) — operator performs one fresh capture; drills spine → segment → native; sees real data, not zeros.

**Out of scope:** Web UI changes beyond "segment page now shows real native runs." Agent decision content (prompt / output / confidence). Both are 19.5.

**Plan count:** 3–5. Memo may collapse plans.

## Phase 19.5 — Agent Decision Record & RCA View

**Goal:** For any capture, the operator can open one page and see — for each agent that touched it — what prompt context was injected, what decision came out, what rules drove it, and which agent configuration was active.

**Design rule:** Foundry First, App Summary Second.
- Raw prompts / raw outputs / full tool transcripts → Foundry native. App stores deep-link references.
- Product semantics (matched rules, threshold policy, safety-net markers, terminal state) → app-owned `AgentDecisionRecord`.
- Agent configuration versioning → `AgentReleaseManifest` only if 19.3 confirms Foundry does not already version prompt-agent instructions.

**Scope — three agents today, extensible:**

1. **Classifier** (`streaming/adapter.py`, `tools/classification.py`) — record terminal state, bucket, confidence, threshold policy version, safety-net-used, retry-used, split-count, Foundry conversation/run IDs, `agent_release_id`.
2. **Admin** (`processing/admin_handoff.py`, `tools/admin.py`) — record routing-context hash, matched `AffinityRuleDocument` IDs + natural-language text, destination, retry/nudge path. This is the codex plan's highest-value field because Foundry cannot know app-owned affinity rules.
3. **Investigation** (`streaming/investigation_adapter.py`, `api/investigate.py`) — record question preview, tools called, answer preview, thread ID. No fabricated confidence.

**Extensibility discipline:** no switch statements on `agent.agentName` in write path or read UI. All branching keyed off `agent.agentType` or explicit decision fields. RCA web page renders agents dynamically. Mobile errors counter groups by `agentName` generically. New agent = one new `emit_decision_record(...)` call site, no schema change, no UI change.

**Data layer:**
- New Cosmos container `AgentDecisionRecords`.
- Partition key: `/captureTraceId` for capture-linked runs; secondary access via `/threadId` for investigation runs (which may lack a capture).
- Schema per codex plan Section "Phase 2" recommended shape.
- Retention: indefinite. Records are small (no transcripts).

**Agent Release Manifest (conditional on 19.3):**
- If Foundry versions prompt-agent instructions natively and the SDK exposes "which version was active at time T" → don't build a manifest. Record `agent_release_id` as the Foundry version identifier.
- Else → build `AgentReleaseManifest` as versioned JSON in repo; snapshot on promotion via GitHub Action.

**Operator RCA view:**

- `GET /api/agent-observability/capture/{trace_id}` — capture summary + per-agent decisions + Foundry deep links.
- `GET /api/agent-observability/thread/{thread_id}` — investigation lookups.
- Web UI: extension of `/correlation/capture/[trace]` with a "Decisions" section per agent showing Prompt ref / Output summary / Confidence / Rule Basis — each with "Open in Foundry" link.

**Mobile treatment — Segment View replaces cramped Status cards:**

- Today the Status screen is overloaded — segment health cards visually crowd admin agent output.
- The magnifying glass icon is rewired to open **Segment View** (new screen or restructured investigation screen).
- Segment View contains: paste-trace-ID input at top (clipboard auto-fill); per-segment error count cards (errors only — successes render nothing); tap a card → flat error list (timestamp, terminal state, input preview, `capture_trace_id`); tap a row → copies `capture_trace_id` to clipboard for pasting into `/investigate` or the web RCA page.
- Segment cards are removed from Status screen. Status reclaims space for admin agent output and errands.
- Investigation chat is reached via a "Chat" action inside Segment View with the currently-pasted trace ID pre-filled as context (Option B from brainstorm).

Mobile is for *noticing*. Web is for *diagnosing*. No Prompt / Output / Rule-Basis rendering on mobile.

**Plans (tentative):**

- Plan 01 — Spike memo (conditional on 19.3 flagging ambiguity). Decides: release manifest yes/no, shape of `injected_context` hash strategy, schema freeze.
- Plan 02 — Cosmos container + Pydantic model + `emit_decision_record(...)` helper.
- Plan 03 — Classifier decision emission + live verification.
- Plan 04 — Admin decision emission including affinity rule capture + live verification.
- Plan 05 — Investigation decision emission + live verification.
- Plan 06 — Backend API endpoints + Pydantic response models.
- Plan 07 — Web UI decisions section + Foundry deep links.
- Plan 08 — Integrated verification.
- (Conditional) Plan 09 — `AgentReleaseManifest` if 19.3 says required.
- Plan 10 — Mobile Segment View + Status screen restructure + magnifying glass rewire.

**Success criteria (what must be TRUE):**
1. Every classifier run writes one `AgentDecisionRecord` with terminal state, bucket, confidence, threshold policy version, safety-net marker.
2. Every admin run writes one record with matched affinity rule IDs + natural-language text + destination.
3. Every investigation answer writes one record with thread ID, tools used, answer preview.
4. `GET /api/agent-observability/capture/{trace_id}` returns classifier + admin (+ investigation if applicable) decisions + Foundry deep links that open the corresponding trace/conversation.
5. The web capture page renders a "Decisions" section with Prompt / Output / Confidence / Rule Basis subsections per agent.
6. For at least one real capture, the operator can answer "why did this go to Admin?" by reading the rule-basis subsection — no code, no KQL.
7. No full prompts or full model outputs are copied into Cosmos — only references, previews (≤200 chars), and product-decision fields.
8. Mobile Segment View exists, is reached via the magnifying glass, contains paste-trace-ID + per-segment error counts + drill-to-error-list + tap-to-copy-trace-ID. Status screen no longer shows segment cards.

**Confirmation checkpoints:**
- Checkpoint A (pre-plan 02) — 19.3 inventory cited; schema decisions traced to specific inventory rows. Release manifest decision made and documented.
- Checkpoint B (post-plan 03) — live classifier capture produces a decision record readable via direct Cosmos query.
- Checkpoint C (post-plan 04) — live admin handoff captures matched affinity rule — the highest-value app-owned field.
- Checkpoint D (post-plan 07) — operator performs real capture → opens web page → reads decision record → clicks through to Foundry trace → sees raw prompt/output in Foundry (not in our UI). Proves the Foundry-First split works.
- Checkpoint E — grep the written decision records; confirm sensitive content (raw prompts/outputs) is not in Cosmos.
- Checkpoint F (post-plan 10) — operator on phone taps magnifying glass → Segment View opens → taps a segment with errors → taps a row → trace ID is in clipboard → pastes into web RCA page and sees detail.

**Out of scope:** Feedback collection (20). Eval scoring (21). Mobile prompt/output/rule-basis rendering. Removing `reasoning_text` logging (defer to later cleanup).

**Plan count:** 8–10. Largest phase in this sequence.

## Phase 20 — Labels: Feedback Signals & Golden Dataset Curation

**Goal:** The system accumulates a stream of labeled examples — implicit (user behavior) and explicit (user feedback) — keyed to decision records, usable as eval golden data.

**Key changes from current roadmap:**
- Label schema references `AgentDecisionRecord.id`. The label says "this decision was wrong, here's what it should have been." Closes the loop for Phase 21.
- Cosmos Change Feed (from 19.3) likely handles implicit signal emission for recategorize/re-route without bespoke instrumentation at N call sites.

**Scope:**
- Implicit signals: recategorization, HITL bucket change, errand re-route. Each emits a label event referencing the `AgentDecisionRecord` it contradicts.
- Explicit signals: thumbs up/down on inbox items and errand rows.
- Golden dataset promotion: operator confirms a label, promotes it to the `GoldenDataset` container (already exists from Phase 16).

**Plans (tentative):**

- Plan 01 — Label schema + Cosmos container (extends existing `FeedbackSignals` from Phase 16).
- Plan 02 — Implicit signal emission: Change Feed listener if 19.3 confirms viability, else explicit emit at write-path call sites.
- Plan 03 — Explicit signal UI (mobile inbox + errands thumbs up/down).
- Plan 04 — Golden dataset promotion flow.
- Plan 05 — Integrated verification.

**Depends on:** 19.5.

**Success criteria (what must be TRUE):**
1. Every label event in Cosmos references an `AgentDecisionRecord.id`.
2. Recategorizing an inbox item produces an implicit label event within ≤1s (or whatever Change Feed latency is confirmed at).
3. Thumbs up/down on an inbox item produces an explicit label event.
4. Operator can promote a label to `GoldenDataset` in one action.
5. Investigation agent can answer "what are the most common misclassifications?" by querying feedback signal data (INV-04 carryover).

**Confirmation checkpoints:**
- Checkpoint A (pre-plan 02) — 19.3 inventory cited on Change Feed viability.
- Checkpoint B (post-plan 05) — live: recategorize an inbox item; a label event appears in Cosmos referencing the original decision record.

**Plan count:** 5.

## Phase 21 — Eval: Automated Scoring Framework

**Goal:** Classifier and admin agent quality are measurable deterministically against golden data.

**Key change from current roadmap — Foundry-native evaluators first.**

19.3 inventory determines whether Foundry Evaluations SDK can score classifier accuracy (label match) and admin routing accuracy (destination match). Three paths:
- **Full Foundry-native:** Plan 02 is Foundry eval configuration + dataset upload. Phase 21 shrinks dramatically.
- **Partial Foundry-native:** Foundry for what it covers, custom scorers for what it doesn't (admin affinity-rule match likely needs custom).
- **Bespoke:** 19.3 finds Foundry evals don't fit; build scorers as originally planned.

**Scope:**
- Evaluator runs score classifier output vs. golden labels — per-bucket precision/recall, accuracy, confidence calibration.
- Evaluator runs score admin routing — per-destination accuracy, tool usage correctness.
- Investigation agent: no automated eval in this phase (no ground truth for open-ended Q&A).
- Results stored in `EvalResults` Cosmos container (already exists). Logged to App Insights with metric names like `eval.classifier.accuracy`.
- Triggerable on-demand via mobile, web, and Claude Code.

**Plans (tentative, assume partial-native path):**

- Plan 01 — Eval spike memo. Foundry evaluator feasibility per agent; bespoke-vs-native split. Gates Plan 02.
- Plan 02 — Classifier eval (Foundry-native if viable, else custom).
- Plan 03 — Admin eval (likely needs custom scorer for affinity rule match).
- Plan 04 — On-demand trigger API + mobile action + Claude Code command.
- Plan 05 — Integrated verification.

**Depends on:** 20, 19.5.

**Success criteria (what must be TRUE):**
1. A golden dataset of 50+ curated test captures with known-correct labels exists (populated via Phase 20 promotion).
2. Classifier eval produces per-bucket precision/recall, overall accuracy, confidence calibration.
3. Admin eval produces per-destination routing accuracy and tool usage correctness.
4. Eval results persist in `EvalResults` with timestamps and log to App Insights as named metrics.
5. Operator can trigger an eval run from mobile, web, or Claude Code and see results.

**Confirmation checkpoints:**
- Checkpoint A (pre-plan 02) — memo approved; Foundry-vs-custom split documented.
- Checkpoint B (post-plan 02/03) — live eval run produces recognizable scores against known-good and known-bad golden entries.
- Checkpoint C (post-plan 05) — operator triggers eval from mobile; score appears within reasonable latency.

**Plan count:** 4–5.

## Phase 22 — Self-Monitoring: Scheduled Evals + Degradation Alerts

**Goal:** Evals run automatically on a schedule. Degradation below thresholds fires push alerts via existing `SecondBrainAlerts` action group.

**Key change from current roadmap — thin.** 19.3 inventory confirms GitHub Actions + Azure Monitor + existing `SecondBrainAlerts` cover the need without new infrastructure. Eval logic was built in Phase 21.

**Scope:**
- GitHub Action cron: weekly eval run invokes Phase 21 pipeline.
- Results logged to App Insights as named metrics (`eval.classifier.accuracy`, `eval.admin.routing_accuracy`).
- Azure Monitor alert rules added to `SecondBrainAlerts`:
  - Classifier accuracy < threshold → alert.
  - Admin routing accuracy < threshold → alert.
- Push notification via existing action group — already wired.

**Plans:**

- Plan 01 — GitHub Actions weekly eval workflow.
- Plan 02 — Alert rules on `SecondBrainAlerts`.
- Plan 03 — Integrated verification (force threshold breach, confirm push arrives).

**Depends on:** 21.

**Success criteria (what must be TRUE):**
1. Eval pipeline runs automatically weekly via GitHub Actions.
2. Azure Monitor alert fires when classifier accuracy drops below configured threshold.
3. Azure Monitor alert fires when admin routing accuracy drops below configured threshold.
4. Push notification arrives on the operator's device via `SecondBrainAlerts` when scores degrade.

**Confirmation checkpoints:**
- Checkpoint A (pre-plan 01) — 19.3 inventory cited: confirm GHA + existing action group cover the need without net-new infrastructure.
- Checkpoint B (post-plan 03) — artificially degrade a score; trigger weekly run; confirm push arrives on phone.

**Plan count:** 3.

## Checkpoint Pattern (applies 19.4 onward)

Every PLAN.md starts with this mandatory header block:

```markdown
## Native Capability Check

**Inventory citations** (from 19.3):
- <capability row> → <finding> → <decision to adopt / bypass / extend>

**Ambiguity flag:** YES / NO
  - If YES → this plan starts with a spike memo (Plan 01 investigation-only).
  - If NO → proceed directly to implementation plans.

**Checkpoints in this phase:**
- Pre-plan X (gate): <what must be true to proceed>
- Post-plan Y (verify): <evidence required>
```

Rules:
- No plan gets written without citing the inventory. If a phase can't cite, the inventory is incomplete — extend 19.3.
- Spike-memo is triggered by a concrete ambiguity flag, not by default. Keeps 19.2-style 3-round memo cycles scoped to where they're load-bearing.
- Post-plan checkpoints are evidentiary, not narrative. "Live KQL query returns correct rows" beats "Verified working."

## Live-Verification Discipline

Each phase ends with one integrated verification plan (the last plan) that gates on:
- Real deployed backend.
- Real trace end-to-end.
- Operator reads real data on a real screen.

No local dev. No mocks for the final gate. Tests pass ≠ feature works.

## Cross-Phase Integration Checks

Two `gsd-integration-checker` passes between phases:
- **19.5 → 20:** A real recategorization produces a label referencing a real decision record.
- **21 → 22:** An actual eval score lands in App Insights with the metric name the alert rule expects.

## Housekeeping (outside phase structure)

Two one-shot items tracked as todos:

**1. Mobile EAS rebuild — close 19.2 baseline.** Trigger before 19.3 starts. Action: `eas build --profile development` → reinstall → one fresh capture → confirm web UI `/correlation/capture/<trace>` shows mobile_capture + backend_api + classifier with no "Missing required segments" warning.

**2. Duplicate Key Vault secret cleanup.** Whenever. Pure housekeeping, zero downstream blocker.

Both captured via `/gsd:add-todo`.

## Out of Scope (all phases)

Explicit non-goals, held firm:

- Building a second transcript store (codex plan rejected, we hold the line).
- Rewriting prompt-agent authoring outside Foundry.
- Full chain-of-thought capture.
- Inventing fake confidence for investigation runs.
- Mobile prompt/output/rule-basis rendering — mobile stays "notice errors" only.
- Evaluation of investigation agent (no ground truth available yet).

## Risks

- **19.3 inventory goes stale.** Mitigation: every phase re-cites (not just references) inventory rows, forcing a read. Rows >6 months old AND load-bearing require spot-check before proceeding.
- **Foundry API surface shifts.** Mitigation: pin SDK versions; 19.3 rows that depend on Foundry SDK record the pinned version.
- **Decision record schema churns when agent 4 is added.** Mitigation: extensibility discipline (no switch on `agentName`, dynamic rendering).
- **The operator doesn't actually use the RCA view.** Mitigation: Checkpoint D in 19.5 is "operator performs real capture and reads the decision record on a real screen." If the UX fails that test, the phase isn't done.

## Ownership Matrix (from codex plan, preserved)

| Operator question | Primary owner | App-owned supplement |
|---|---|---|
| What prompt did the agent see? | Foundry Traces + Conversation results | `agent_release_id`, injected-context hash, capture/inbox linkage |
| What did the agent output? | Foundry Traces + Conversation results | terminal state, tool-result summary, product side-effect summary |
| What was the confidence? | App decision record (classifier) | `confidence_unavailable` for agents that don't emit one |
| What rules drove the behavior? | App decision record | matched rule IDs/text, threshold version, safety-net/retry markers |

## Summary of Roadmap Changes

| Phase | Plans | Status |
|---|---|---|
| 19.3 Native Capability Inventory | 1 | NEW (insert) |
| 19.4 Native Span Correlation Tagging | 3–5 | NEW (insert; absorbs `project_native_foundry_correlation_gap`) |
| 19.5 Agent Decision Record & RCA View | 8–10 | NEW (absorbs codex P1–P5, mobile Segment View restructure) |
| 20 Labels | 5 | Rewritten (references decision records, considers Change Feed) |
| 21 Eval | 4–5 | Rewritten (Foundry-native evaluators first) |
| 22 Self-Monitoring | 3 | Rewritten (thin — uses existing GHA + action group) |

v3.1 milestone grows from 3 remaining phases to 6; phases 21 and 22 get smaller than originally scoped because 19.3 finds native plumbing.

## References

- `memory/project_native_foundry_correlation_gap.md`
- `memory/project_deferred_19.2_spine_gaps.md`
- `memory/project_followup_audit_first_findings.md`
- `docs/codex-agent-observability-plan.md`
- `.planning/phases/19.2-transaction-first-spine/` — predecessor phase artifacts
- `docs/superpowers/specs/2026-04-18-per-segment-correlation-audit-design.md` — 19.2 precursor design
- Foundry tracing setup: https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/trace-agent-setup
- Foundry agent framework tracing: https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/trace-agent-framework
- Foundry threads/runs/messages: https://learn.microsoft.com/en-us/azure/foundry-classic/agents/concepts/threads-runs-messages
