---
phase: 24-foundry-ga-migration
audit_scope: TG 23.3 (Classifier surface + warmup + main lifespan + eval cleanup)
patch_subject: .planning/phases/24-foundry-ga-migration/FIDELITY-23.3.patch
verdict: PASS-WITH-WARNINGS
in_scope_failures: 0
out_of_scope_failures: 0
warnings: 3
passes: 19
audited_at: 2026-05-11
---

# Framework Fidelity Audit — Task Group 23.3

**Date:** 2026-05-11
**Scope:** task-group-23.3 (Classifier surface — `agents/classifier.py`, `agents/instructions/classifier.md`, `tools/classification.py`, `tools/transcription.py`, `streaming/adapter.py`, `api/capture.py` follow-up path, `cosmos/inbox_conversation_history.py`, `models/documents.py` InboxDocument.conversationHistory + ConversationTurn, `warmup.py`, `main.py` Classifier lifespan slice + foundry probe deletion + final config orphan cleanup, `eval/dry_run_tools.py`, `eval/invoker.py` final GA-only state, `eval/runner.py`, `processing/admin_handoff.py` docstring sweep, `tools/investigation.py` docstring sweep, `agents/middleware.py` deletion, `observability/kql_templates.py` FORCED_TOOL_FAILURE addition, `config.py` orphan field removal)

**Diff command:** `git diff c4d2e51..HEAD -- backend/`
**Files changed:** 24 (20 src + 4 tests). Patch: 3935 lines.
**Design reference:** `docs/superpowers/specs/2026-05-05-foundry-ga-migration-design.md`
**Calibration baseline:** `.planning/phases/24-foundry-ga-migration/FRAMEWORK-FIDELITY-calibration.md`
**Prior-task-group audit:** `.planning/phases/24-foundry-ga-migration/FRAMEWORK-FIDELITY-23.2.md`

## Verdict

**PASS-WITH-WARNINGS**

The Classifier surface, warmup, and final lifespan cleanup are cleanly GA-compliant. Every remaining in-scope finding from the calibration baseline (F-01 Classifier slice, F-02 warmup, F-04 classifier streaming, F-08 Classifier+transcription+dry_run, F-09 safety net, F-10 RC tool_choice dict, F-11 voice tool registration, F-12 Classifier agent_id, F-13 classifier follow-up conversation_id, F-14 classifier streaming custom spans, F-17 legacy middleware deletion, F-19 Classifier instructions promotion) is resolved against the framework-first checklist. The codebase under `backend/src/second_brain/` is now RC-clean: `grep -rE "AzureAIAgentClient|agent_framework\.azure" backend/src/second_brain/` returns empty, and `tests/test_no_rc_imports_after_cleanup.py` is permanently GREEN as a regression guard.

Three warnings carry forward or are tracked as justified deviations: W-01 (calibration-anticipated `CaptureTraceSpanProcessor` narrowing — landed in 23.1, justified retention per D-07a), W-02-23.3 (decorative tool-call content-type vocabulary; carried from 23.1 + 23.2 — applies to the Classifier streaming path now that it consumes `streaming_shape.json`; risk LOW because the load-bearing answer text flows through `update.text` which IS probe-validated), and W-03-23.3 (final cleanup state for the Settings model — `extra='ignore'` retained until 24-23 post-UAT removes the orphan env vars).

Cross-task-group regression check vs 23.2 and 23.1: all closures stand. No reintroduction of `tracer.start_as_current_span(...)` against framework calls. No new `AzureAIAgentClient` runtime construction sites added. The 23.1 `CaptureTraceSpanProcessor` narrowing remains in place; the `agents/agent_middleware/` path remains the active GA middleware module. Plan 24-18 successfully deleted the legacy `agents/middleware.py` and the `RCEvalAgentInvoker` + `_MigrationHybridInvoker`; plan 24-19 cleared the last RC import from `main.py` (the legacy `foundry_client = AzureAIAgentClient(...)` connectivity probe block). Plan 24-21 deleted the three orphan `azure_ai_*_agent_id` Settings fields and added `extra='ignore'` to tolerate the still-set Container App env vars (CONFIG-DELTAS Step C asymmetric cleanup pattern).

## Summary

| Counter | Value |
|---|---:|
| Pass findings (in-scope GA-compliant) | 19 |
| Warnings (justified or near-violation) | 3 |
| In-scope failures (blocking) | 0 |
| Out-of-scope failures (deferred) | 0 |
| Prerequisite failures | 0 |

## Resolution Of Calibration Findings (F-01..F-19) — Remaining Classifier slices

### F-01 main.py: 10 RC client construction sites
- **Status:** CLEARED (all 3 slices now resolved across 23.1+23.2+23.3)
- **Evidence cleared (Classifier + final cleanup):**
  - `backend/src/second_brain/main.py:494-501` constructs `FoundryChatClient(project_endpoint=..., model=..., credential=ManagedIdentityCredential())` — the single chat client shared by all three agents.
  - `main.py:570-606` (Phase 24-14 + 24-19): Classifier Agent built via `build_classifier_agent(chat_client=chat_client, tools=classifier_agent_tools, middleware=[CaptureTraceAgentMiddleware(), CaptureTraceFunctionMiddleware()])`. `app.state.classifier_agent` replaces `app.state.classifier_client`.
  - `main.py` (24-19 sweep): the legacy `foundry_client = AzureAIAgentClient(...)` connectivity probe block was deleted entirely; `app.state.foundry_client = None` documents the deliberate downgrade. Health endpoint's existing `getattr(..., None)` short-circuit returns "not_configured" for the Foundry probe channel.
  - `_make_classifier_client` / `_make_admin_client` / `_make_investigation_client` RC factories deleted (24-19); replaced by GA `build_*_agent` factory invocations that read tool instances from `app.state` and close over the shared `chat_client`.
- **Verification:** `grep -rE 'AzureAIAgentClient|agent_framework\.azure' backend/src/second_brain/main.py` returns empty. `grep -rE 'AzureAIAgentClient|agent_framework\.azure' backend/src/second_brain/` returns empty across the entire src tree.

### F-02 RC framework client in warmup.py
- **Status:** CLEARED (24-19)
- **Evidence:** `backend/src/second_brain/warmup.py` is GA-shaped end-to-end:
  - Imports: `from agent_framework.azure import AzureAIAgentClient` + `from agent_framework import Message` REPLACED by `from agent_framework import Agent`.
  - Signature: `agent_warmup_loop(agents: list[tuple[str, Agent]], interval_seconds: int, agent_factories: dict[str, Callable[[], Agent]] | None = None, on_recreate: Callable[[str, Agent], None] | None = None) -> None`. Parameter renames: `clients` → `agents`, `client_factories` → `agent_factories`.
  - Ping body: `messages = [Message(role="user", text="ping")]` + `await client.get_response(messages=messages)` REPLACED by single-line `await agent.run("ping")`.
- **Regression guard:** `tests/test_no_rc_imports_after_cleanup.py` flipped RED → GREEN at 24-19 commit.

### F-03 RC framework client in processing/admin_handoff.py
- **Status:** CLEARED (23.2 — closure stands; 23.3 only touched docstrings)
- **Evidence:** `admin_handoff.py` was migrated to GA Agent in 23.2 (`process_admin_capture(admin_agent: Agent, ...)`). 24-19 reworded docstring narrative occurrences of `AzureAIAgentClient` to "legacy RC client" to clear the codebase-wide `grep -rE` gate. No code-shape change.

### F-04 RC framework client in streaming/adapter.py (Classifier streaming)
- **Status:** CLEARED (24-16)
- **Evidence:** `backend/src/second_brain/streaming/adapter.py` is GA-shaped end-to-end:
  - Imports: `from agent_framework.azure import AzureAIAgentClient` + `from agent_framework import ChatOptions, Message` REPLACED by `from agent_framework import Agent, ChatOptions` (Message is now built explicitly per turn from history).
  - All 3 streaming entry points (text capture, voice capture, follow-up) now take an `Agent` parameter and invoke `agent.run(messages=msg_list, stream=True, options=ChatOptions(tool_choice="required"))` — stateless invocation per P0-1 Option A.

### F-05 RC framework client in streaming/investigation_adapter.py
- **Status:** CLEARED (23.1 — closure stands; no change in 23.3)

### F-06 RC-shaped eval invocation in eval/runner.py
- **Status:** FULLY CLEARED (23.2 routed through invoker; 24-18 promoted `RCEvalAgentInvoker` → deletion; only `GAEvalAgentInvoker` remains)
- **Evidence:** `eval/invoker.py:GAEvalAgentInvoker` is the sole implementation. `_MigrationHybridInvoker` deleted in 24-18. `api/eval.py` constructs only `GAEvalAgentInvoker`. The Classifier evaluation path is GA end-to-end.

### F-07 RC-shaped eval in eval/foundry.py (app-mediated dataset generator)
- **Status:** CLEARED (23.2 — closure stands)

### F-08 RC `@tool(approval_mode="never_require")` decorators
- **Status:** CLEARED (all 16 tools across 4 files now decorator-free)
- **Evidence cleared (Classifier + transcription + dry_run):**
  - `backend/src/second_brain/tools/classification.py` — `file_capture` decorator stripped (24-15).
  - `backend/src/second_brain/tools/transcription.py` — `transcribe_audio` decorator stripped AND `Annotated` parameter shape removed (24-15) because transcription is now invoked as a direct Python call from the voice handler, not registered as a tool on any agent.
  - `backend/src/second_brain/eval/dry_run_tools.py` — RC `@tool` decorators stripped (24-17).
- **Verification:** `grep -rE "@tool|approval_mode" backend/src/second_brain/` returns empty across the entire src tree.

### F-09 Python "safety net" in classifier streaming
- **Status:** CLEARED (24-16)
- **Evidence:** the `_safety_net_file_as_misunderstood` function and its 3 call sites are deleted from `streaming/adapter.py`. `tool_choice="required"` (probe-validated string form per `tool_choice_required.json`) is now the only forcing mechanism. Failures route to the new `forced_tool_failure` SSE sub-code (24-18 D-04 KQL template added) rather than silent fabrication.

### F-10 RC-shaped tool_choice provider-dict in classifier streaming
- **Status:** CLEARED (24-16)
- **Evidence:** `grep -rE "required_function_name|tool_choice.*mode.*required" backend/src/second_brain/` returns empty. All `tool_choice` references use the probe-validated string form `tool_choice="required"`.

### F-11 Voice tool registered on classifier agent
- **Status:** CLEARED (24-15)
- **Evidence:** `main.py:548-577` documents the voice path split: "Phase 24 plan 24-14: transcribe_audio is NO LONGER a registered tool — direct call". The classifier agent registers ONLY `file_capture`. The voice handler (`api/capture.py`) calls `transcribe_audio` directly as a Python helper before invoking the classifier agent. This unblocks `tool_choice='required'` as unambiguous.

### F-12 Constructor-level `agent_id`-pinned RC clients
- **Status:** CLEARED (all 3 slices closed; no remaining `AzureAIAgentClient(agent_id=...)` constructors)
- **Evidence:** `grep -rE "AzureAIAgentClient\(agent_id=" backend/src/second_brain/` returns empty. All three agents are now GA singletons built via `build_*_agent` factories.

### F-13 RC `conversation_id` round-trip (bypasses framework session API)
- **Status:** CLEARED (24-16 + 24-17 via P0-1 OUTCOME Option A)
- **Evidence:** the per-call rehydration via `AgentSession.session_id` design is locked off because the calibrated probe (`session_rehydration_fresh_process.json`, `recalled_pineapple=false`) disproved cross-process recall. Replaced by Option A: explicit conversationHistory persisted on InboxDocument.
  - `InboxDocument.conversationHistory: list[ConversationTurn] | None = None` (24-17, `models/documents.py:64`).
  - `cosmos/inbox_conversation_history.py:resolve_inbox_conversation_history()` reconstructs the message list from the Inbox doc; returns empty list with a warning for legacy `foundryThreadId`-only docs.
  - `streaming/adapter.py` builds `msg_list = [Message(role=..., text=...) for turn in history] + [new_turn]` per request and invokes `agent.run(messages=msg_list, stream=True, options=ChatOptions(tool_choice="required"))` stateless.
  - `api/capture.py` follow-up path no longer round-trips `foundryThreadId` via `ChatOptions["conversation_id"]`; the field is RETAINED on InboxDocument for rollback safety, deleted in 24-24 post-UAT (P0-2 amendment).
- **Verification:** `grep -rE 'ChatOptions\["conversation_id"\]|conversation_id=foundry_thread' backend/src/second_brain/` returns empty.

### F-14 Custom tracer.start_as_current_span in streaming/adapter.py
- **Status:** CLEARED (24-16)
- **Evidence:** all 3 custom spans (`capture_text`, `capture_voice`, `capture_follow_up`) are deleted. Capture-shape attributes (`capture.trace_id`, `capture.type`, `capture.thread_id`) now ride either the framework-emitted `invoke_agent` span via `CaptureTraceAgentMiddleware` or the auto-instrumented AppRequests span via `trace.get_current_span().set_attribute(...)`.
- **Verification:** `grep -rE "tracer.start_as_current_span" backend/src/second_brain/streaming/` returns empty.

### F-15 Custom tracer.start_as_current_span in streaming/investigation_adapter.py
- **Status:** CLEARED (23.1 — closure stands)

### F-16 Custom tracer.start_as_current_span in processing/admin_handoff.py
- **Status:** CLEARED (23.2 — closure stands)

### F-17 Existing AgentMiddleware uses tracer.start_as_current_span anti-pattern
- **Status:** CLEARED (24-18 deleted the legacy `agents/middleware.py` file)
- **Evidence:**
  - `agents/middleware.py` (the module containing `AuditAgentMiddleware` + `ToolTimingMiddleware`) is DELETED in plan 24-18 commit `1b93734`.
  - The new GA-compliant `CaptureTraceAgentMiddleware` + `CaptureTraceFunctionMiddleware` at `agents/agent_middleware/capture_trace.py` operate on `trace.get_current_span().set_attribute(...)` exclusively.
  - `tests/test_legacy_middleware_imports_survive.py` was updated in 24-18 to assert the deletion (legacy file gone, new path live).

### F-18 Probe-fixture-shaped extraction code missing
- **Status:** CLEARED (all 6 fixtures present + consumed)
- **Evidence:** `backend/tests/fixtures/foundry-probe/` contains all six fixtures: `auth_probe.json`, `streaming_shape.json`, `tool_call_extraction.json`, `tool_choice_required.json`, `session_rehydration.json`, `session_rehydration_fresh_process.json`. Each is consumed by the appropriate code path (cross-references documented in the calibration baseline). The new normalize-and-diff helper at `backend/scripts/foundry_probe_compare.py` provides automated replay diffing.

### F-19 Portal-managed agent shell pattern (D-02 violation)
- **Status:** CLEARED (all 3 agents now built via repo-resident instructions)
- **Evidence cleared (Classifier):**
  - `backend/src/second_brain/agents/classifier.py` is now a pure factory: `build_classifier_agent(chat_client, tools, middleware) -> Agent` reads `agents/instructions/classifier.md` via `load_instructions("classifier")` and constructs `Agent(client=chat_client, instructions=instructions, tools=list(tools), middleware=list(middleware))`. The `ensure_classifier_agent` portal-shell + "SET INSTRUCTIONS IN AI FOUNDRY PORTAL" log line is removed.
  - `agents/instructions/classifier.md` exists (promoted from portal in 24-14).
  - Final config cleanup (24-21) deleted the three orphan `azure_ai_*_agent_id` Settings fields. `Settings.model_config['extra'] = 'ignore'` tolerates the still-set Container App env vars until 24-23 post-UAT removal.
- **Verification:** `grep -rE "ensure_classifier_agent|ensure_admin_agent|ensure_investigation_agent" backend/src/second_brain/` returns empty.

## Pass — Framework Primitives Correctly Used (in-scope, new in 23.3)

| # | Concern | Evidence |
|---|---|---|
| Pass-1 | GA Agent construction (Classifier singleton) | `agents/classifier.py:build_classifier_agent` → `Agent(client=chat_client, instructions=load_instructions("classifier"), tools=list(tools), middleware=list(middleware))` |
| Pass-2 | Instructions live in repo (D-02 Classifier) | `agents/instructions/classifier.md` exists; `load_instructions("classifier")` reads it at lifespan startup |
| Pass-3 | `agent.run(...)` stream invocation (Classifier streaming) | `streaming/adapter.py:288` `options = ChatOptions(tool_choice="required")` + downstream `agent.run(messages=msg_list, stream=True, options=options)` |
| Pass-4 | `tool_choice="required"` (string form, probe-verified) | `streaming/adapter.py:288` — string form per `tool_choice_required.json` probe; provider-dict explicitly rejected (D-10); D-04 `forced_tool_failure` SSE sub-code emitted when forcing fails (24-18 KQL template `FORCED_TOOL_FAILURE_COUNT` added for monitoring) |
| Pass-5 | Explicit message list per turn (P0-1 OUTCOME Option A) | `streaming/adapter.py` builds `msg_list = [Message(role=..., text=...) for turn in conversation_history] + [Message(role="user", text=current_text)]` and invokes stateless |
| Pass-6 | P0-1 OUTCOME conversation-history schema | `models/documents.py:64` `conversationHistory: list[ConversationTurn] | None = None`; `cosmos/inbox_conversation_history.py:resolve_inbox_conversation_history` resolver handles legacy docs gracefully |
| Pass-7 | No custom spans wrapping framework calls (Classifier streaming) | `grep -rE "tracer.start_as_current_span" backend/src/second_brain/streaming/` returns empty |
| Pass-8 | New `CaptureTraceAgentMiddleware` wired into Classifier Agent | `main.py:570-606` passes `middleware=[CaptureTraceAgentMiddleware(), CaptureTraceFunctionMiddleware()]` to `build_classifier_agent` |
| Pass-9 | Voice path split (D-07b) | `main.py:548-577` registers ONLY `file_capture` on classifier agent; voice handler `api/capture.py` direct-calls `transcribe_audio` before classifier run |
| Pass-10 | Plain Python tool methods on ClassifierTools (no `@tool(approval_mode=...)`) | `tools/classification.py:file_capture` is plain `async def` with `Annotated[..., Field(description=...)]`; bound at construction via `Agent(tools=[classifier_tools.file_capture, ...])` |
| Pass-11 | Transcription is a plain Python helper, not a registered tool | `tools/transcription.py:transcribe_audio` decorator-stripped AND `Annotated` parameters removed (direct-call shape) |
| Pass-12 | DryRun tools mirror GA pattern | `eval/dry_run_tools.py` — all RC decorators stripped (24-17); mirrors production tools' plain-method shape |
| Pass-13 | `GAEvalAgentInvoker` is the sole eval invoker (24-18 cleanup) | `eval/invoker.py` no longer contains `RCEvalAgentInvoker` or `_MigrationHybridInvoker`; `api/eval.py` constructs only `GAEvalAgentInvoker` |
| Pass-14 | GA warmup loop pings via `agent.run("ping")` | `warmup.py` GA-shaped end-to-end (24-19): `Agent` type throughout, single-line `await agent.run("ping")` ping body, `agent_factories=` self-heal kwarg |
| Pass-15 | Codebase under `backend/src/second_brain/` is RC-free | `grep -rE "AzureAIAgentClient|agent_framework\.azure" backend/src/second_brain/` returns empty; `tests/test_no_rc_imports_after_cleanup.py` is permanently GREEN |
| Pass-16 | Token metering unchanged | `main.py:31` `enable_instrumentation()` unchanged. No manual `tokens_used`/`prompt_tokens`/`completion_tokens` counters anywhere in `streaming/`, `agents/`, or `processing/` |
| Pass-17 | App Insights export wiring unchanged | `main.py:14, 21` unchanged; `configure_azure_monitor(...)` is the single export pipeline |
| Pass-18 | Settings is GA-only after 24-21 cleanup | `config.py` has only `azure_ai_project_endpoint` + `foundry_model` (Foundry-related); orphan `azure_ai_*_agent_id` fields deleted; `extra='ignore'` tolerates still-set Container App env vars per CONFIG-DELTAS Step C |
| Pass-19 | `FORCED_TOOL_FAILURE_COUNT` KQL template added (24-18) | `observability/kql_templates.py` — D-04 monitoring template emits a count over `customDimensions["error.subcode"] == "forced_tool_failure"` for production dashboards |

## Warnings

### W-01 (calibration anticipated, carried from 23.1+23.2): `CaptureTraceSpanProcessor` narrowing — RETAINED

- **File:** `backend/src/second_brain/observability/span_processor.py` (no change in 23.3)
- **Concern:** Capture-trace propagation (non-framework spans).
- **Status:** narrowed-responsibility docstring landed in 23.1; processor RETAINED per design D-07a as the bulk-tagger for non-framework spans (Cosmos `AppDependencies`, third-party library `AppExceptions`, custom non-framework spans). The on_start overlap with framework-tagged spans on the same attribute name is idempotent and benign.
- **Justification (D-07a, verbatim from docstring):** "Without this processor, `query_capture_trace`'s union over `AppDependencies` loses correlation."
- **Verdict:** justified retention. No action needed. Sticks at warning class until W-01 is closed by removal of the processor (target: never — design D-07a is permanent retention).

### W-02-23.3 (carried from 23.1 + 23.2): Tool-call content-type vocabulary not strictly probe-introspected — now applies to Classifier streaming too

- **File:** `backend/src/second_brain/streaming/adapter.py` (Classifier streaming consumes `streaming_shape.json` for `update.text` + `update.contents[]`)
- **Concern:** Strict probe fidelity (Q2 in the auditor contract). Same class as 23.1 W-02 and 23.2 W-02-23.2.
- **Detail:** the load-bearing path (`update.text` for streamed answer text) IS probe-validated. The decorative path (`content.type == "function_call"` / `"function_result"` for tool-call rendering) is not introspected — the probe captured `contents: [<agent_framework._types.Content object at ...>]` but stopped at the Content boundary without walking `.type` to capture the string vocabulary.
- **Risk classification:** LOW. The load-bearing answer streaming works correctly. The only risk is missing pretty-printing of tool-call descriptions if the GA SDK uses different type strings than what the code defensively checks for. Empirically verifiable on first deployed Classifier run.
- **Recommended response:** non-blocking. Either (a) accept the risk and verify empirically on first deployed Classifier processing run, or (b) extend `scripts/foundry_probe.py` probe 1 to walk `Content.__dict__` and pin the captured vocabulary into the fixture. Same recommendation as 23.1 W-02 / 23.2 W-02-23.2.

### W-03-23.3 (NEW): Settings `extra='ignore'` is a temporary tolerance window

- **File:** `backend/src/second_brain/config.py` (24-21 final cleanup)
- **Concern:** Configuration hygiene — `model_config = {"extra": "ignore"}` was added (Rule 2 deviation in 24-21) so the GA image boots cleanly against the Container App's still-set `AZURE_AI_*_AGENT_ID` env vars.
- **Detail:** Pydantic Settings v2 defaults to `extra='forbid'`. With the three orphan field declarations deleted in 24-21 but the env vars still set in the Container App, instantiation would `ValidationError` on startup. The `extra='ignore'` guard is the only honourable way to satisfy CONFIG-DELTAS Step C asymmetric cleanup (code now, env later). 24-23 (post-UAT) removes the env vars and 24-23 also has the OPTION to revert `extra='ignore'` if the operator wants strict env validation back.
- **Verdict:** justified deviation; pinned deletion trigger documented in `config.py` docstring (24-23). NOT a violation — this is the canonical pattern for cross-deploy config cleanup. Sticks at warning class until 24-23 closes it.

## ❌ Out-of-Scope Failures (deferred)

**None.** TG 23.3 is the final task group. All 19 calibration-baseline F-## findings are now CLEARED. No findings remain deferred to a future task group within Phase 24.

The only remaining work in Phase 24 is operational:
- 24-20 (this plan): pre-deploy gate runner
- 24-22: deploy push
- 24-23: post-deploy UAT + Container App env var cleanup
- 24-24: post-UAT InboxDocument.foundryThreadId field deletion (P0-2 rollback-safety field retired)

## New Findings (not in calibration)

None. No regression patterns introduced. The 23.3 patch adds only GA-shaped code, plus four new test artifacts (this plan 24-20's Task 2 deliverables: `backend/scripts/foundry_probe_compare.py`, `backend/tests/test_probe_replay_invariants.py`, `backend/tests/test_probe_replay_normalized_diff.py`, `backend/tests/test_app_startup_smoke.py`) that act as regression guards and gate inputs.

The two new regression guards from 23.2's tail (`test_admin_eval_baseline_seeded.py`, `test_inbox_dual_read.py`) carry forward as permanent guards.

## Probe Fixture Strict-Fidelity Check (full 23.3 surface)

| Fixture | Consumed by | Status | Notes |
|---|---|---|---|
| `streaming_shape.json` | `streaming/investigation_adapter.py:148, 159` (cleared 23.1); `streaming/adapter.py` Classifier streaming (NEW in 23.3) | exact | Top-level `update.text` matches across both adapters. Inner `Content.type` vocabulary remains W-02 — decorative path only. |
| `tool_call_extraction.json` | `processing/admin_handoff.py:48-69` (cleared 23.2) | partial | Top-level walk matches; inner `Content.name`/`Content.function_name` vocabulary remains W-02 — defensive `or` chain in code keeps risk LOW. |
| `tool_choice_required.json` | `streaming/adapter.py:288` Classifier (NEW in 23.3); `processing/admin_handoff.py:255, 310` Admin (cleared 23.2) | exact | All callers use the probe-validated string form `"required"`. Provider-dict form explicitly rejected per D-10. |
| `session_rehydration.json` | not consumed (P0-1 OUTCOME superseded this path) | n/a | Same-process probe; design abandoned this path. |
| `session_rehydration_fresh_process.json` | Investigation `streaming/investigation_adapter.py` (cleared 23.1); Classifier follow-up `streaming/adapter.py` + `cosmos/inbox_conversation_history.py` (NEW in 23.3) | exact | `recalled_pineapple: false` in fixture; both adapters respond by passing explicit message list per turn (P0-1 OUTCOME Option A). |
| `auth_probe.json` | `main.py:498-510` FoundryChatClient construction (cleared 23.1) | exact | Sync `ManagedIdentityCredential` confirmed by `test_foundry_credential_shape.py`. |

## Cross-Task-Group Regression Check

23.1 + 23.2 closures verified to stand against 23.3 patch:

| Earlier closure | Verification in 23.3 |
|---|---|
| F-05 cleared (`streaming/investigation_adapter.py` — no RC client) | No reintroduction. |
| F-15 cleared (no custom `investigate` span) | No reintroduction. |
| F-17 (Investigation+Admin slices) cleared | NOW FULLY CLEARED: 24-18 deleted legacy `agents/middleware.py`. |
| F-19 (Investigation+Admin slices) cleared | NOW FULLY CLEARED: 24-14 promoted classifier instructions; `ensure_classifier_agent` removed. |
| W-01 (`CaptureTraceSpanProcessor` narrowed) | Unchanged in 23.3. |
| 23.1/23.2 regression-guard tests | `test_legacy_middleware_imports_survive.py` — updated in 24-18 for post-deletion state, still PASSES; `test_foundry_credential_shape.py` — still PASSES (no new credential construction in 23.3); `test_no_rc_imports_after_cleanup.py` — flipped RED → GREEN at 24-19 commit; permanent guard active. |
| F-03 cleared (admin_handoff GA) | 24-19 only touched docstrings to clear codebase-wide grep gate. No code-shape regression. |
| F-06+F-07 cleared (eval through invoker) | 24-18 PROMOTED to GA-only via `RCEvalAgentInvoker`+`_MigrationHybridInvoker` deletion. No regression. |

No earlier closure regressed in 23.3.

## Files Outside Framework-First Scope (not audited)

Per scope_constraint:
- `mobile/**`, `web/**`, `mcp/**`, `infra/**` (entire surfaces out of scope per design)
- `docs/**`, `.planning/**` (documentation, not framework-fidelity surface)
- `backend/tests/**` outside the four new tests added by this plan
- `backend/src/second_brain/spine/**` (separate workload events system, out of scope per design)
- `backend/src/second_brain/cosmos/**` except `cosmos/inbox_conversation_history.py` (other modules unchanged in 23.3)
- `backend/src/second_brain/auth.py` (out of scope per design)
- `backend/src/second_brain/api/**` outside `api/capture.py` (capture follow-up path is in scope as F-13 closure)

## Decision

**This gate PASSES.** All Classifier-surface in-scope failure findings from the calibration baseline are resolved, completing the full F-01..F-19 closure across TG 23.1 + 23.2 + 23.3. The three warnings are:
- W-01: justified D-07a retention with documentation already landed (carry-forward from 23.1)
- W-02-23.3: low-risk decorative-path probe-coverage gap with clear empirical-verification fallback (carry-forward from 23.1+23.2)
- W-03-23.3: justified `extra='ignore'` tolerance window for CONFIG-DELTAS Step C asymmetric cleanup; deletion trigger documented

The codebase under `backend/src/second_brain/` is now in its final pre-deploy state: RC-free, GA-only, with all calibration baseline findings discharged. The cumulative audit (Gate 2 of plan 24-20) is unblocked.

---

**FIDELITY AUDIT: 19 pass, 3 warning, 0 in-scope failure (0 out-of-scope failure). Report at `.planning/phases/24-foundry-ga-migration/FRAMEWORK-FIDELITY-23.3.md`.**
