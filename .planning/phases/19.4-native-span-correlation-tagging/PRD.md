# Phase 19.4 — Native Span Correlation Tagging (PRD)

**Source:** `docs/superpowers/specs/2026-04-19-observability-evolution-design.md` (Phase 19.4 section)
**Inventory:** `docs/superpowers/specs/native-observability-inventory.md` (Phase Impact Addendum for 19.4)

## Goal

Every native telemetry row produced during a capture is filterable by `capture_trace_id`. The drill-down from spine to native telemetry (step 4) stops being blind.

## Problem

The 19.2 spine ledger works. The web segment page still shows "runs (0)" for captures that ran, because the native renderer filters native spans by `capture_trace_id` and those spans aren't tagged.

## Four Emit Sites

1. `backend_api` AppRequests — FastAPI middleware layer.
2. Azure AI Foundry agent spans — runs/steps/tool calls from the Foundry SDK.
3. Cosmos diagnostic logs — `AzureDiagnostics.activityId_g` needs a pivot to `capture_trace_id`.
4. Investigation custom spans — thread-kind spans emitted during investigation runs.

## Inventory Findings (from Phase 19.3)

- **Surface 2 / Baggage propagation:** OTel baggage propagation through the Foundry SDK is **unverified**. If baggage works, it collapses 3 emit sites (backend_api, Foundry agent spans, investigation) into 1 middleware config. If not, each site needs explicit `span.set_attribute()`.
- **Surface 6 / Per-operation client-request-id:** The `trace_headers()` helper for Cosmos is **proven and tested** (`spine/cosmos_request_id.py`). Phase 19.4 just needs to apply it at remaining capture-correlated Cosmos call sites — no bespoke instrumentation.
- **Surface 1 / Tracing to App Insights:** Foundry SDK auto-instrumented spans carry `operation_Id` but NOT `capture_trace_id`. Gap confirmed by `project_native_foundry_correlation_gap.md`.
- **Surface 2 / Cross-process context propagation:** `httpx` calls in recipe tools are NOT auto-instrumented. Low priority — recipe fetch spans are secondary.

## Scope Delta (from inventory addendum)

`add spike memo` — OTel baggage propagation through the Foundry SDK is the #1 ambiguity. If YES, Plans 02+04 merge (backend_api + investigation handled by one middleware config alongside Foundry). If NO, explicit per-site injection (3 separate plans). Cosmos Plan 03 is unchanged either way.

**Revised plan count estimate:** 3–5. Spike memo (Plan 01) resolves the baggage question and determines whether Plans 02+04 merge.

## Form

Spike-memo + implementation. Memo decides the OTel-baggage-vs-explicit question and the Cosmos mapping strategy.

## Plans (tentative, pending spike memo)

- Plan 01 — Spike memo. Gates Plan 02 scope. Pattern matches 19.2-01.
- Plan 02 — Backend + Foundry: OTel baggage / span attributes for `backend_api` and Foundry agent spans. (May collapse with Plan 04.)
- Plan 03 — Cosmos `activityId_g` mapping: record `(capture_trace_id, activityId_g)` tuples at every Cosmos call site; persistence mechanism chosen by memo (likely extends spine_events or a new correlation-map table).
- Plan 04 — Investigation custom spans: tag thread-kind spans at emit time.
- Plan 05 — Integrated verification.

If OTel baggage covers sites #1, #2, #4 together, plans 02 and 04 merge.

## Success Criteria (what must be TRUE)

1. For any recent `capture_trace_id`, a KQL query against `AppRequests` returns the request span with `capture_trace_id` as a custom dimension.
2. Same for Foundry agent spans in `AppDependencies` (or wherever the Foundry SDK writes).
3. Given a `capture_trace_id`, the spine correlation API returns a list of Cosmos `activityId_g` values that successfully query rows in `AzureDiagnostics`.
4. The web segment page's native `FoundryRunDetail` renderer shows ≥1 run for a capture with an active Foundry run (was showing 0).
5. Investigation custom spans are filterable by correlation ID identically.

## Confirmation Checkpoints

- Checkpoint A (pre-plan 02) — memo approved.
- Checkpoint B (post-plan 02) — live KQL query proves `backend_api` spans carry the tag.
- Checkpoint C (post-plan 03) — live query proves `activityId_g` pivot works.
- Checkpoint D (post-plan 05) — operator performs one fresh capture; drills spine → segment → native; sees real data, not zeros.

## Out of Scope

- Web UI changes beyond "segment page now shows real native runs."
- Agent decision content (prompt / output / confidence). Both are 19.5.

## Native Capability Check (mandatory header for all 19.4+ plans)

Every PLAN.md must cite inventory rows:
- Surface 2 / Baggage propagation → unverified → spike memo
- Surface 6 / Per-operation client-request-id → proven → extend existing
- Surface 1 / Tracing to App Insights → gap confirmed → explicit tagging needed
- Surface 2 / Cross-process context → httpx not auto-instrumented → low priority

## Key References

- `docs/superpowers/specs/native-observability-inventory.md` — the 28-row inventory
- `memory/project_native_foundry_correlation_gap.md` — the gap memo that motivated this phase
- `memory/project_deferred_19.2_spine_gaps.md` — deferred items from 19.2
- `memory/project_followup_audit_first_findings.md` — audit findings (classifier not emitting, mobile_capture not emitting, backend_api untagged)
- `spine/cosmos_request_id.py` — existing Cosmos trace_headers() helper
- `docs/superpowers/specs/2026-04-19-observability-evolution-design.md` — parent spec
