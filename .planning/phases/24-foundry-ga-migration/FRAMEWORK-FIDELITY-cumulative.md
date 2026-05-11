---
phase: 24-foundry-ga-migration
audit_scope: cumulative (Phase 24 — 24-01..24-21, all task groups)
patch_subject: .planning/phases/24-foundry-ga-migration/FIDELITY-cumulative.patch
verdict: PASS-WITH-WARNINGS
in_scope_failures: 0
out_of_scope_failures: 0
warnings: 3
passes: 22
audited_at: 2026-05-11
---

# Framework Fidelity Audit — Cumulative (Phase 24, 24-01..24-21)

**Date:** 2026-05-11
**Scope:** cumulative (entire Phase 24 diff including all three task groups + push guard + final config orphan cleanup)
**Diff command:** `git diff 92926b4..HEAD -- backend/ .planning/phases/24-foundry-ga-migration/`
**Files changed:** 89 (mix of src + tests + planning artifacts). Patch: 27876 lines.
**Design reference:** `docs/superpowers/specs/2026-05-05-foundry-ga-migration-design.md`
**Calibration baseline:** `.planning/phases/24-foundry-ga-migration/FRAMEWORK-FIDELITY-calibration.md` (19 ❌ findings F-01..F-19 + 1 ⚠️ W-01 + 3 ✓)
**Task-group audits:**
- `.planning/phases/24-foundry-ga-migration/FRAMEWORK-FIDELITY-23.1.md` (TG 23.1: 14 ✓ / 3 ⚠️ / 0 in-scope ❌ / 14 out-of-scope ❌)
- `.planning/phases/24-foundry-ga-migration/FRAMEWORK-FIDELITY-23.2.md` (TG 23.2: 17 ✓ / 4 ⚠️ / 0 in-scope ❌ / 9 out-of-scope ❌)
- `.planning/phases/24-foundry-ga-migration/FRAMEWORK-FIDELITY-23.3.md` (TG 23.3: 19 ✓ / 3 ⚠️ / 0 in-scope ❌ / 0 out-of-scope ❌)

## Verdict

**PASS-WITH-WARNINGS**

The cumulative Phase 24 diff fully discharges every calibration-baseline finding. All 19 F-## ❌ items (F-01..F-19) from `FRAMEWORK-FIDELITY-calibration.md` are CLEARED. Zero in-scope ❌ findings remain. The codebase under `backend/src/second_brain/` is end-to-end GA-shaped:

- Every `agent_framework.azure.AzureAIAgentClient` import is gone.
- All three production agents (Investigation, Admin, Classifier) are GA `Agent` singletons constructed via `build_*_agent` factories reading repo-resident instructions (D-02 honored).
- All 16 production tools have `@tool(approval_mode="never_require")` decorators stripped.
- Voice path is split (D-07b): classifier registers only `file_capture`; voice handler direct-calls `transcribe_audio` before agent invocation.
- `tool_choice="required"` (probe-validated string form) is the sole forcing mechanism for classifier + admin.
- Python safety net (`_safety_net_file_as_misunderstood`) is deleted; `forced_tool_failure` SSE sub-code + `FORCED_TOOL_FAILURE_COUNT` KQL template added for D-04 monitoring.
- Capture-trace propagation goes through GA `CaptureTraceAgentMiddleware`/`CaptureTraceFunctionMiddleware` (operates on `trace.get_current_span().set_attribute(...)`, never starts a new span). `CaptureTraceSpanProcessor` retained per D-07a for non-framework spans (Azure SDK `AppDependencies`, third-party `AppExceptions`).
- P0-1 OUTCOME locked to Option A: cross-process session rehydration via `AgentSession.session_id` was probe-disproven (`recalled_pineapple == false` in two independent live runs). Replaced by explicit `conversationHistory` persistence on `InboxDocument` + stateless `agent.run(messages=msg_list, stream=True)` per turn.
- `EvalAgentInvoker` facade introduced in 23.2 and PROMOTED in 24-18: `RCEvalAgentInvoker` + `_MigrationHybridInvoker` deleted; `GAEvalAgentInvoker` is the sole implementation.
- All 6 probe fixtures present and consumed at the correct code sites (added `session_rehydration_fresh_process.json` from P0-1 OUTCOME closure).

Three warnings track justified deviations/retentions:
- **W-01** (calibration-anticipated): `CaptureTraceSpanProcessor` narrowed per D-07a — justified permanent retention.
- **W-02-cumulative** (carried from all three task groups): tool-call `Content.type` / `Content.name` / `Content.function_name` vocabulary not introspected inside the probe Content boundary — decorative-path-only, load-bearing answer text IS probe-validated, defensive `or` chains keep risk LOW.
- **W-03-cumulative** (24-21): `Settings.model_config['extra'] = 'ignore'` is a justified tolerance window for CONFIG-DELTAS Step C asymmetric cleanup; deletion trigger documented and pinned to 24-23 post-UAT.

Five Phase 24 plan defects were closed via amendment + red tests before execution (per `24-PLAN-DEFECTS.md` resolution_notes): P0-1 (session rehydration unproven → probed + Option A locked), P0-2 (backfill deletes RC field pre-deploy → three-phase additive migration), P1-3 (middleware package shadowing → renamed to `agents/agent_middleware/`), P1-4 (RC dep removed before RC imports gone → ADDed GA deps first; retracted under packaging-infeasibility detour to direct-pin variant), P1-5 (credential class disagreement → locked sync `ManagedIdentityCredential`), P1-6 (probe replay unstable + /tmp redirect bug → normalize-and-diff helper), P1-7 (admin baseline empty → seeded N=11 from real production captures), P2-8 (gates run before final cleanup → reordered so 24-21 ships BEFORE 24-20). All 8 red-test artifacts are committed and green.

## Summary

| Counter | Value |
|---|---:|
| Pass findings | 22 |
| Warnings (justified or near-violation) | 3 |
| In-scope failures (blocking) | 0 |
| Out-of-scope failures (deferred) | 0 |
| Prerequisite failures | 0 |

## Resolution Of All 19 Calibration Findings (F-01..F-19)

Every F-## row from `FRAMEWORK-FIDELITY-calibration.md` is closed. Detailed evidence is provided in each task-group audit; this section summarises which task group cleared each finding.

| # | Finding | Status | Closed by |
|---|---|---|---|
| F-01 | `main.py` 10 RC `AzureAIAgentClient` construction sites | CLEARED | 23.1 (Investigation slice), 23.2 (Admin slice), 23.3 (Classifier slice + 24-19 final `foundry_client` probe deletion + 24-21 orphan field cleanup) |
| F-02 | RC client in `warmup.py` | CLEARED | 23.3 (24-19) |
| F-03 | RC client in `processing/admin_handoff.py` | CLEARED | 23.2 (24-11) |
| F-04 | RC client in `streaming/adapter.py` (Classifier streaming) | CLEARED | 23.3 (24-16) |
| F-05 | RC client in `streaming/investigation_adapter.py` | CLEARED | 23.1 (24-04) |
| F-06 | RC-shaped eval invocation in `eval/runner.py` | CLEARED | 23.2 (24-12 — invoker facade); FULLY GA in 24-18 |
| F-07 | RC-shaped eval in `eval/foundry.py` | CLEARED | 23.2 (24-12); FULLY GA in 24-18 |
| F-08 | RC `@tool(approval_mode="never_require")` on all 16 tools | CLEARED | 23.1 (Investigation: 24-05), 23.2 (Admin: 24-10, recipe: 24-10), 23.3 (Classifier: 24-15, transcription: 24-15, dry_run: 24-17) |
| F-09 | Python safety net in classifier streaming | CLEARED | 23.3 (24-16) |
| F-10 | RC-shaped `tool_choice` provider-dict in classifier | CLEARED | 23.3 (24-16) |
| F-11 | Voice tool registered on classifier agent | CLEARED | 23.3 (24-15) — D-07b voice path split |
| F-12 | Constructor-level `agent_id`-pinned RC clients | CLEARED | 23.1 (Investigation: 24-04), 23.2 (Admin: 24-09), 23.3 (Classifier: 24-14) |
| F-13 | RC `conversation_id` round-trip bypassing framework session API | CLEARED | 23.1 (Investigation via P0-1 Option A), 23.3 (Classifier via 24-16 + 24-17 conversationHistory schema) |
| F-14 | Custom `tracer.start_as_current_span` in `streaming/adapter.py` (3 sites) | CLEARED | 23.3 (24-16) |
| F-15 | Custom `tracer.start_as_current_span` in `streaming/investigation_adapter.py` | CLEARED | 23.1 (24-04) |
| F-16 | Custom `tracer.start_as_current_span` in `processing/admin_handoff.py` (2 sites) | CLEARED | 23.2 (24-11) |
| F-17 | Legacy `AuditAgentMiddleware` + `ToolTimingMiddleware` use `tracer.start_as_current_span` | CLEARED | 23.1 (new GA middleware introduced at `agents/agent_middleware/capture_trace.py` in 24-03), 23.3 (legacy file `agents/middleware.py` deleted in 24-18) |
| F-18 | Probe-fixture-shaped extraction code missing | CLEARED | All 6 fixtures present in `backend/tests/fixtures/foundry-probe/`; consumed by appropriate code paths (per F-## row evidence in task-group audits); normalize-and-diff helper added in 24-20 (this plan) for automated replay diffing |
| F-19 | Portal-managed agent shell + "SET INSTRUCTIONS IN AI FOUNDRY PORTAL" (D-02 violation) | CLEARED | 23.1 (Investigation: instructions promoted in 24-03, agent rewrite in 24-04), 23.2 (Admin: instructions in 24-09, agent in 24-09), 23.3 (Classifier: instructions in 24-14, agent in 24-14, orphan config fields deleted in 24-21) |

**Final state verification (run 2026-05-11):**

```
grep -rE "AzureAIAgentClient|from agent_framework.azure" backend/src/second_brain/ → 0 hits
grep -rn "approval_mode" backend/src/second_brain/ → 0 hits
grep -rn "_safety_net_file" backend/src/second_brain/ → 0 hits
grep -rE "AzureAIAgentClient\(.*agent_id=" backend/src/second_brain/ → 0 hits
grep -rE "tracer.start_as_current_span" backend/src/second_brain/streaming/ backend/src/second_brain/processing/ → 0 hits
test -f backend/src/second_brain/agents/middleware.py → DELETED (24-18)
grep -rE "ensure_classifier_agent|ensure_admin_agent|ensure_investigation_agent" backend/src/second_brain/ → 0 hits
```

All seven grep gates pass with zero hits in `backend/src/second_brain/`.

## Resolution Of All 8 Phase 24 Plan Defects (P0-1..P2-8)

| Defect | Status | Closure |
|---|---|---|
| P0-1 (session rehydration unproven) | CLOSED — Option A locked | Plan 24-06.5 ran the fresh-process probe live; `recalled_pineapple=false` in two independent runs; operator locked Option A (persist full conversationHistory on Inbox doc). InboxDocument schema updated in 24-17. Streaming adapters rewritten stateless in 24-07 (Investigation) + 24-16 (Classifier). |
| P0-2 (backfill deletes RC field pre-deploy) | CLOSED — three-phase additive migration | Backfill helper added in 24-15 (cosmos/inbox_conversation_history.py); GA code dual-reads via the resolver; conversationHistory field added in 24-17; foundryThreadId RETAINED through pre-deploy + post-deploy UAT; deletion scoped to 24-24. |
| P1-3 (middleware package shadows legacy module) | CLOSED — package renamed | New GA middleware lives at `agents/agent_middleware/` (NOT `agents/middleware/` which would shadow the legacy module). Legacy file deleted in 24-18 (no shadow ever active). Red test `test_legacy_middleware_imports_survive.py` PASSES. |
| P1-4 (RC dep removed before RC imports gone) | CLOSED — packaging-infeasibility detour | The original additive-deps approach was packaging-infeasible (both RC `agent-framework-core==1.0.0rc2` and GA `agent-framework-core==1.3.0` install to the same `agent_framework/` directory). Retracted in favor of strict cutover (24-02): GA-only deps from the start; D-13 relaxed to allow non-runnable intermediate commits within a task group's window; push guard from 24-01 protects the unbuildable window. |
| P1-5 (credential class disagreement) | CLOSED — sync `ManagedIdentityCredential` locked | 24-04 imports the sync variant per CONFIG-DELTAS verbatim. Regression guard `tests/test_foundry_credential_shape.py` AST-scans `main.py` and PASSES. |
| P1-6 (probe replay unstable + /tmp redirect bug) | CLOSED — normalize-and-diff helper | This plan (24-20) Task 2 created `backend/scripts/foundry_probe_compare.py` with `normalize_fixture()` (scrubs UUIDs, timestamps, repr addresses, session ids). Red tests `test_probe_replay_invariants.py` + `test_probe_replay_normalized_diff.py` PASS. |
| P1-7 (admin baseline empty) | CLOSED — N=11 seeded | 24-13.5 seeded 11 real production captures (8 task + 3 errand) via `backend/scripts/seed_admin_golden_dataset.py`. Pre-migration baseline captured against deployed RC: `routing_accuracy=0.9091`, 10/11 correct. Red test `test_admin_eval_baseline_seeded.py` asserts `admin.total>=10` and PASSES. |
| P2-8 (gates run before final cleanup) | CLOSED — reordered | 24-21 (config orphan cleanup) ships BEFORE 24-20 (this plan). depends_on swapped: 24-21 depends_on [19], 24-20 depends_on [21]. New Gate 10 startup smoke runs against post-24-21 artifact. |

## Pass — Framework Primitives Correctly Used (cumulative)

| # | Concern | Evidence |
|---|---|---|
| 1 | GA FoundryChatClient construction (single shared client) | `main.py:494-501` `FoundryChatClient(project_endpoint=..., model=..., credential=ManagedIdentityCredential())` |
| 2 | GA Agent construction (Investigation singleton) | `agents/investigation.py:build_investigation_agent` → `Agent(client=..., instructions=..., tools=[...], middleware=[...])` |
| 3 | GA Agent construction (Admin singleton) | `agents/admin.py:build_admin_agent` |
| 4 | GA Agent construction (Classifier singleton) | `agents/classifier.py:build_classifier_agent` |
| 5 | Instructions live in repo (D-02) | `agents/instructions/{investigation,admin,classifier}.md` all present; `load_instructions("<name>")` helper reads them at lifespan startup |
| 6 | `agent.run(stream=True)` invocation shape (Investigation) | `streaming/investigation_adapter.py:142` |
| 7 | `agent.run(stream=True, options=ChatOptions(tool_choice="required"))` invocation (Classifier) | `streaming/adapter.py:288` + downstream stream loop |
| 8 | `agent.run(options=ChatOptions(tool_choice="required"))` invocation (Admin, non-streaming) | `processing/admin_handoff.py:253-256, 308-311` |
| 9 | Explicit message list per turn (P0-1 OUTCOME Option A) | Investigation + Classifier both build `list[Message]` from history + new turn; invoke stateless. Admin is single-turn — no history needed. |
| 10 | No custom spans wrapping framework calls | `grep -rE "tracer.start_as_current_span" backend/src/second_brain/streaming/ backend/src/second_brain/processing/` returns empty |
| 11 | GA `CaptureTraceAgentMiddleware` operates on current span | `agents/agent_middleware/capture_trace.py:56` `trace.get_current_span().set_attribute("capture.trace_id", ...)` — never starts a new span |
| 12 | GA `CaptureTraceFunctionMiddleware` lifts tool attrs onto framework span | `agents/agent_middleware/capture_trace.py:80, 106-115, 118` |
| 13 | Plain Python tool methods on all 16 production tools | `grep -rE "@tool|approval_mode" backend/src/second_brain/` returns empty across the entire src tree |
| 14 | `Annotated[type, Field(description=...)]` parameter coverage preserved | All tool methods retain `Annotated` parameter shapes per GA pattern |
| 15 | `tool_choice="required"` (probe-validated string form) | Used by Classifier streaming + Admin processing; provider-dict form explicitly rejected per D-10 |
| 16 | Voice path split (D-07b) | Classifier agent registers ONLY `file_capture`; voice handler direct-calls `transcribe_audio` before agent invocation |
| 17 | `forced_tool_failure` SSE sub-code + KQL template | `streaming/adapter.py` emits new sub-code; `observability/kql_templates.py:FORCED_TOOL_FAILURE_COUNT` template (24-18) for monitoring |
| 18 | P0-1 OUTCOME conversation-history schema | `models/documents.py:64` `conversationHistory: list[ConversationTurn] | None = None`; `cosmos/inbox_conversation_history.py:resolve_inbox_conversation_history` graceful legacy-doc handling |
| 19 | `GAEvalAgentInvoker` is the sole eval invoker (24-18 cleanup) | `eval/invoker.py` GA-only after `RCEvalAgentInvoker`+`_MigrationHybridInvoker` deletion; `api/eval.py` constructs only GA invoker |
| 20 | GA warmup loop pings via `agent.run("ping")` (no RC types) | `warmup.py` end-to-end GA (24-19): `Agent` type throughout, single-line `await agent.run("ping")`, `agent_factories=` self-heal kwarg |
| 21 | Codebase under `backend/src/second_brain/` is RC-free | `grep -rE "AzureAIAgentClient|agent_framework\.azure" backend/src/second_brain/` returns empty; `tests/test_no_rc_imports_after_cleanup.py` is permanently GREEN |
| 22 | App Insights export + token metering unchanged | `main.py:14, 21` `configure_azure_monitor(...)` unchanged; `main.py:31` `enable_instrumentation()` unchanged; no manual `tokens_used`/`prompt_tokens`/`completion_tokens` counters anywhere |

## Warnings

### W-01 (calibration-anticipated): `CaptureTraceSpanProcessor` narrowing — LANDED + RETAINED

- **File:** `backend/src/second_brain/observability/span_processor.py`
- **Concern:** Capture-trace propagation (non-framework spans).
- **Status:** Narrowed-responsibility docstring landed in 23.1 (commit `1ee634e`); processor RETAINED per design D-07a as the bulk-tagger for non-framework spans (Cosmos `AppDependencies`, third-party `AppExceptions`, custom non-framework spans). On_start overlap with framework-tagged spans on the same attribute name is idempotent and benign.
- **Justification (D-07a, verbatim from docstring):** "Without this processor, `query_capture_trace`'s union over `AppDependencies` loses correlation."
- **Verdict:** justified retention. No action needed. Permanent warning class — design D-07a is permanent retention.

### W-02-cumulative (carried from 23.1 + 23.2 + 23.3): Inner Content vocabulary not strictly probe-introspected

- **Files affected:** `streaming/investigation_adapter.py:163, 179` (decorative tool-call render), `processing/admin_handoff.py:63-66` (`_output_tool_called` Content walking), `streaming/adapter.py` Classifier (tool-call render parity with investigation_adapter).
- **Concern:** Strict probe fidelity (Q2 in the auditor contract).
- **Detail:** Top-level field access paths (`update.text`, `response.messages`, `role == "tool"`) are probe-validated by `streaming_shape.json` + `tool_call_extraction.json`. Inner `Content.type` / `Content.name` / `Content.function_name` string vocabulary was NOT introspected by the probes — they captured `[<agent_framework._types.Content object at ...>]` and stopped at the Content boundary.
- **Risk classification:** LOW.
  - Load-bearing answer text (`update.text` streamed to user, `response.text` for admin tool-call adjudication) IS probe-validated and works correctly.
  - Decorative paths (tool-call rendering in SSE, output-tool detection in admin) use defensive `or` chains across both possible attribute names. Worst case: a single tool-call render is missing pretty-print OR an admin output-tool detection returns empty and triggers a D-09 bounded retry.
  - Empirically verifiable on first deployed run via App Insights logs (`outcome=no_output_tool` alert already wired).
- **Recommended response:** non-blocking. Either (a) accept the risk and verify empirically on first deployed run, or (b) extend `scripts/foundry_probe.py` probes 1 + 2 to walk `Content.__dict__` and pin the captured vocabulary into the fixtures. Sticks at warning class for post-deploy follow-up.

### W-03-cumulative (24-21): Settings `extra='ignore'` is a justified tolerance window

- **File:** `backend/src/second_brain/config.py`
- **Concern:** Configuration hygiene — `model_config = {"extra": "ignore"}` was added (Rule 2 deviation in 24-21).
- **Detail:** With the three orphan `azure_ai_*_agent_id` field declarations deleted in 24-21 but the env vars still set on the Container App (per CONFIG-DELTAS NON-NEGOTIABLE: those env vars are removed in 24-23 post-UAT, NOT pre-deploy), `Settings()` instantiation would `ValidationError` on startup under Pydantic v2 default `extra='forbid'`. The `extra='ignore'` guard is the only honourable way to satisfy CONFIG-DELTAS Step C asymmetric cleanup (code now, env later).
- **Verdict:** justified deviation; pinned deletion trigger documented in `config.py` docstring (24-23). NOT a violation — this is the canonical pattern for cross-deploy config cleanup. Sticks at warning class until 24-23 closes it.

## ❌ Out-of-Scope Failures (deferred)

**None.** All 19 calibration-baseline F-## findings are CLEARED. The cumulative diff includes all task groups; there is no "deferred to future task group" residual.

The only remaining work in Phase 24 is operational:
- 24-20 (this plan): pre-deploy gate runner — runs against the artifact this report audits.
- 24-22: deploy push — unblocked if all gates in 24-20 pass.
- 24-23: post-deploy UAT + Container App env var cleanup (removes `AZURE_AI_*_AGENT_ID` env vars; renders `extra='ignore'` guard temporarily unnecessary).
- 24-24: post-UAT `InboxDocument.foundryThreadId` field deletion (P0-2 rollback-safety field retired).

## Probe Fixture Strict-Fidelity Check (cumulative — all 6 fixtures)

| Fixture | Consumed by (cumulative) | Status | Notes |
|---|---|---|---|
| `streaming_shape.json` | `streaming/investigation_adapter.py:148, 159` (23.1); `streaming/adapter.py` Classifier streaming (23.3) | exact | Top-level `update.text` validated. Inner `Content.type` vocabulary W-02 — decorative path. |
| `tool_call_extraction.json` | `processing/admin_handoff.py:48-69` `_output_tool_called` (23.2) | partial | Top-level walk matches; inner `Content.name`/`Content.function_name` vocabulary W-02. |
| `tool_choice_required.json` | `streaming/adapter.py:288` (23.3) Classifier; `processing/admin_handoff.py:255, 310` (23.2) Admin | exact | All callers use probe-validated string form `"required"`. Provider-dict explicitly rejected per D-10. |
| `session_rehydration.json` | not consumed (P0-1 OUTCOME superseded) | n/a | Same-process probe; design abandoned this path. |
| `session_rehydration_fresh_process.json` (NEW from 24-06.5) | `streaming/investigation_adapter.py` (23.1) + `streaming/adapter.py` + `cosmos/inbox_conversation_history.py` (23.3) | exact | `recalled_pineapple: false` fixture drives Option A everywhere. |
| `auth_probe.json` | `main.py:494-501` `FoundryChatClient` construction (23.1) | exact | Sync `ManagedIdentityCredential` confirmed by `test_foundry_credential_shape.py`. |

P1-6 normalize-and-diff helper (`backend/scripts/foundry_probe_compare.py`, added in 24-20 this plan) provides automated replay diffing under volatile-field normalization. The invariant tests `tests/test_probe_replay_invariants.py` PASS (6/6) against committed fixtures.

## Cross-Task-Group Regression Check

The cumulative diff is the union of TG 23.1 + 23.2 + 23.3 + push-guard + final-config-cleanup. Each task-group audit reports its own no-regression-against-earlier finding. The cumulative state holds:

| Earlier closure | Cumulative verification |
|---|---|
| F-01 + F-02 + F-04 + F-05 (RC `AzureAIAgentClient` constructions) | All cleared; `grep -rE "AzureAIAgentClient|agent_framework\.azure" backend/src/second_brain/` returns 0 hits across the entire src tree. |
| F-08 (RC `@tool(approval_mode=...)` on all 16 tools) | All cleared; `grep -rE "@tool|approval_mode" backend/src/second_brain/` returns 0 hits. |
| F-09 (safety net) | Cleared; `grep -rn "_safety_net_file" backend/src/second_brain/` returns 0 hits. |
| F-10 (RC tool_choice provider-dict) | Cleared; `grep -rE "required_function_name|tool_choice.*mode.*required" backend/src/second_brain/` returns 0 hits. |
| F-11 (voice tool on classifier) | Cleared; `transcribe_audio` is direct-called, not registered as a tool. |
| F-12 + F-13 (agent_id constructor pinning + RC conversation_id) | Cleared; zero `AzureAIAgentClient(agent_id=...)` constructors; zero `ChatOptions["conversation_id"]` round-trips. |
| F-14 + F-15 + F-16 (custom `tracer.start_as_current_span` wrapping framework calls) | All cleared; `grep -rE "tracer.start_as_current_span" backend/src/second_brain/streaming/ backend/src/second_brain/processing/` returns 0 hits. |
| F-17 (legacy `AuditAgentMiddleware`/`ToolTimingMiddleware`) | New GA middleware introduced in 23.1; legacy file deleted in 24-18. |
| F-19 (portal-managed shells, D-02 violation) | All cleared; instructions in repo for all 3 agents; orphan config fields deleted in 24-21. |
| W-01 (`CaptureTraceSpanProcessor` narrowed per D-07a) | Narrowing documentation landed in 23.1; processor retained per design. |

No earlier closure is regressed in any later commit. The cumulative state is the strict improvement over calibration: 0 in-scope ❌, all 19 F-## items discharged.

## Files Outside Framework-First Scope (not audited)

Per scope_constraint:
- `mobile/**`, `web/**`, `mcp/**`, `infra/**` (entire surfaces out of scope per design)
- `docs/**`, `.planning/**` outside Phase 24's own artifacts
- `backend/tests/**` outside the regression-guard tests + the new tests added by this plan
- `backend/src/second_brain/spine/**` (separate workload events system, out of scope per design)
- `backend/src/second_brain/cosmos/**` except `cosmos/inbox_conversation_history.py`
- `backend/src/second_brain/auth.py`, `models/**` except `models/documents.py` `InboxDocument.conversationHistory` addition

## Decision

**This gate PASSES.**

All 19 calibration-baseline F-## findings are resolved. All 8 Phase 24 plan defects (P0-1, P0-2, P1-3..P1-7, P2-8) are closed with amendments + red tests committed. The codebase under `backend/src/second_brain/` is end-to-end GA-shaped, RC-clean, and ready for deploy.

The three warnings (W-01 + W-02-cumulative + W-03-cumulative) are justified retentions/deviations with documented rationale and (where applicable) pinned deletion triggers. Zero blocking findings; the cumulative auditor verdict is **PASS-WITH-WARNINGS**.

Plan 24-22 (deploy push) is unblocked from a framework-fidelity standpoint. Remaining 24-20 gates (Gates 3..10) below must also pass before deploy.

---

**FIDELITY AUDIT: 22 pass, 3 warning, 0 in-scope failure (0 out-of-scope failure). Report at `.planning/phases/24-foundry-ga-migration/FRAMEWORK-FIDELITY-cumulative.md`.**
