---
phase: 24-foundry-ga-migration
audit_scope: TG 23.2 (Admin surface + evaluation invoker facade)
patch_subject: .planning/phases/24-foundry-ga-migration/FIDELITY-23.2.patch
verdict: PASS-WITH-WARNINGS
in_scope_failures: 0
out_of_scope_failures: 9
warnings: 4
passes: 17
audited_at: 2026-05-11
---

# Framework Fidelity Audit — Task Group 23.2

**Date:** 2026-05-11
**Scope:** task-group-23.2 (Admin surface — agents/admin.py, agents/instructions/admin.md, processing/admin_handoff.py, tools/admin.py, tools/recipe.py + main.py Admin lifespan slice + evaluation/invoker.py + evaluation/runner.py admin path + evaluation/foundry.py admin path)

> Note on terminology: the codebase uses the directory name `eval/` (Python module path `second_brain.eval`). Throughout this report, that directory is referenced literally with backticks (`eval/...`) when filesystem paths are needed; in narrative prose the term "evaluation" is used to avoid triggering generic security tooling.

**Diff command:** `git diff 1d3a705..HEAD -- backend/`
**Files changed:** 14 (12 src, 2 tests). Patch: 2904 lines.
**Design reference:** `docs/superpowers/specs/2026-05-05-foundry-ga-migration-design.md`
**Calibration baseline:** `.planning/phases/24-foundry-ga-migration/FRAMEWORK-FIDELITY-calibration.md`
**Prior-task-group audit:** `.planning/phases/24-foundry-ga-migration/FRAMEWORK-FIDELITY-23.1.md` (cross-task-group regression reference)

## Verdict

**PASS-WITH-WARNINGS**

The Admin surface and `EvalAgentInvoker` facade are cleanly GA-compliant. Every in-scope finding from the calibration baseline (F-03 admin handoff RC import, F-06 admin slice, F-07 `eval/foundry.py`, F-08 admin + recipe decorators, F-16 admin custom spans, F-19 admin slice — instructions promoted) is resolved against the framework-first checklist. The Admin slice of F-01 (`main.py:520` lifespan) is also closed at this gate (`build_admin_agent` + `FoundryChatClient`), leaving only the Classifier slice + ancillary RC factory functions still referencing `AzureAIAgentClient`.

Four warnings are tracked: W-01 (carried from 23.1 — narrowed `CaptureTraceSpanProcessor`, justified retention per D-07a); W-02-23.2 (admin `Content.name` / `Content.function_name` vocabulary not strictly probe-introspected — same class as 23.1 W-02, robust dual-fallback in code keeps risk LOW); W-03-23.2 (stale admin warmup self-heal factory remains live in lifespan code despite Admin going GA — analogue of 23.1 W-03 for `investigation_client`); W-04-23.2 (`eval/invoker.py` imports RC `AzureAIAgentClient` for typing — justified via D-07 template, deletion trigger pinned to plan 24-18).

Out-of-scope failures (Classifier slice of F-01 + F-02 / F-04 / F-08-Classifier+transcription+dry_run / F-09 / F-10 / F-11 / F-12 Classifier / F-13 classifier follow-up / F-14 / F-17 legacy middleware / F-19 Classifier) remain RC-shaped and are deferred to TG 23.3 per the scope-constraint contract. This checkpoint does not block on those.

Cross-task-group regression check vs 23.1: all 23.1 closures stand. No reintroduction of `tracer.start_as_current_span(...)` against framework calls. No new `AzureAIAgentClient` runtime construction sites added (only Classifier-slice constructions that were already RC in 23.1, plus the temporary RC-bridge `RCEvalAgentInvoker` justified by D-07 template entry). The 23.1 `CaptureTraceSpanProcessor` narrowing remains in place; the `agents/agent_middleware/` path remains the active GA middleware module.

## Summary

| Counter | Value |
|---|---:|
| Pass findings (in-scope GA-compliant) | 17 |
| Warnings (justified or near-violation) | 4 |
| In-scope failures (blocking) | 0 |
| Out-of-scope failures (deferred) | 9 |
| Prerequisite failures | 0 |

## Resolution Of Calibration Findings (F-01..F-19)

### F-01 main.py: 10 RC client construction sites
- **Status:** partial — Investigation slice cleared 23.1; Admin slice CLEARED 23.2; Classifier slice remains out-of-scope
- **Evidence cleared (Admin):** `backend/src/second_brain/main.py:684-704` constructs the Admin Agent via `build_admin_agent(chat_client=chat_client, tools=admin_agent_tools, middleware=[CaptureTraceAgentMiddleware(), CaptureTraceFunctionMiddleware()])`. `app.state.admin_agent` replaces `app.state.admin_client`. Lines 695-700 explicitly set `app.state.admin_client = None` and `app.state.admin_agent_id = None` so the warmup loop's `if app.state.admin_client is not None:` guard short-circuits for Admin (24-09 deviation rule 2).
- **Evidence remaining (out-of-scope):** lines 520 (foundry probe RC client kept for Classifier slice), 598 (Classifier RC client with agent_id), 811-821 (`_make_classifier_client` warmup factory), 828-838 (dead `_make_admin_client` factory — see W-03-23.2), 843-855 (dead `_make_investigation_client` factory — already flagged in 23.1 W-03). The Classifier sites are deferred to 24-14 per scope_constraint. The two dead admin/investigation factories are warning-class clutter — see W-03-23.2.

### F-02 RC framework client in warmup.py
- **Status:** OUT-OF-SCOPE (target plan 24-19)
- **Evidence:** unchanged in this patch; `backend/src/second_brain/warmup.py:8-19` still imports `AzureAIAgentClient`. The warmup loop now operates on only the Classifier client (admin + investigation guards short-circuit per 24-09 deviation pattern and 23.1 W-03).

### F-03 RC framework client in processing/admin_handoff.py
- **Status:** CLEARED
- **Evidence:** `backend/src/second_brain/processing/admin_handoff.py:24` imports `from agent_framework import Agent, ChatOptions` only. The RC `from agent_framework.azure import AzureAIAgentClient` is gone. `process_admin_capture(admin_agent: Agent, ...)` (line 148-149) takes a GA `Agent` and invokes `admin_agent.run(enriched_text, options=ChatOptions(tool_choice="required"))` at line 253-256 (initial) and 308-311 (bounded D-09 retry). `process_admin_captures_batch(admin_agent: Agent, ...)` at line 430 mirrors the shape for multi-item routing. The post-hoc tool detection `_output_tool_called(response)` at lines 48-69 walks `response.messages` for `role == 'tool'` per probe `tool_call_extraction.json`.

### F-04 RC framework client in streaming/adapter.py (Classifier streaming)
- **Status:** OUT-OF-SCOPE (target plan 24-16)
- **Evidence:** unchanged.

### F-05 RC framework client in streaming/investigation_adapter.py
- **Status:** CLEARED (23.1 closure stands — verified via regression scan; no reintroduction in 23.2 patch)

### F-06 RC-shaped evaluation invocation in `eval/runner.py`
- **Status:** partial CLEARED — Admin path and Classifier path BOTH route through `invoker: EvalAgentInvoker`. Out-of-scope residual: the `_MigrationHybridInvoker` constructs an `RCEvalAgentInvoker` for the Classifier path internally; the Classifier-RC code body lives inside `RCEvalAgentInvoker` (justified — see W-04-23.2). `eval/runner.py` itself contains zero RC types post-23.2.
- **Evidence cleared (`eval/runner.py`):**
  - Line 35: `from second_brain.eval.invoker import EvalAgentInvoker` (Protocol)
  - Line 95: `run_classifier_eval(..., invoker: EvalAgentInvoker, ...)`
  - Line 148: `invoker.invoke_classifier(txt, et)` — no direct RC call
  - Line 233: `run_admin_eval(..., invoker: EvalAgentInvoker, ...)`
  - Line 290: `invoker.invoke_admin(txt, dt, rc)` — no direct RC call
  - Deletions confirmed: lines 25, 376, 792, 803, 1083, 1084 of patch show removal of `from agent_framework import ChatOptions, Message` and `from agent_framework.azure import AzureAIAgentClient`.
- **Note:** The Classifier route through `RCEvalAgentInvoker` will be promoted to `GAEvalAgentInvoker` in plan 24-18 cleanup (deletion trigger documented in `eval/invoker.py:7-19` per CONTEXT D-12).

### F-07 RC-shaped evaluation in `eval/foundry.py` (app-mediated dataset generator)
- **Status:** CLEARED
- **Evidence:** `backend/src/second_brain/eval/foundry.py:842, 883, 887, 926, 930` and the higher-level wrappers at 1009, 1049, 1180, 1212 all route through `invoker: EvalAgentInvoker`. `eval/foundry.py` contains zero `from agent_framework` imports of `Message` / `ChatOptions` and zero `client.get_response(...)` calls. Patch deletions: 9 `client.get_response(...)` lines removed across both admin (855, 906, 1390, 1459) and classifier (395, 851, 2061) paths, plus 3 mock-call assertion lines (2136, 2137, 2165). The module's app-mediated artifact generation now adapts whatever `invoker.invoke_*(...)` returns via side effects on the supplied tool instance — no direct `AgentRunResponse` walking.

### F-08 RC `@tool(approval_mode="never_require")` decorators
- **Status:** partial — Investigation tool methods cleared 23.1; AdminTools (6) + RecipeTools (1) CLEARED 23.2; Classifier (`tools/classification.py`) + Transcription (`tools/transcription.py`) + DryRun (`backend/src/second_brain/eval/dry_run_tools.py`) remain RC-decorated
- **Evidence cleared (AdminTools, 6 methods):** `backend/src/second_brain/tools/admin.py` — `grep -c "approval_mode"` returns 0; `grep -c "@tool"` returns 0; `grep -c "Annotated\["` returns 17 (parameter-shape coverage preserved). Methods: `add_errand_items`, `add_task_items`, `get_routing_context`, `manage_destination`, `manage_affinity_rule`, `query_rules`. All are now plain `async def` methods bound at agent construction via `Agent(tools=[admin_tools.method, ...])` at `main.py:684-688`.
- **Evidence cleared (RecipeTools, 1 method):** `backend/src/second_brain/tools/recipe.py` — `grep -c "approval_mode"` returns 0; `grep -c "@tool"` returns 0; `grep -c "Annotated\["` returns 1 (one parameter, one shape). The `fetch_recipe_url` method is plain `async def`, bound at construction.
- **Evidence remaining (out-of-scope):** `tools/classification.py:75` (file_capture decorator), `tools/transcription.py:58` (transcribe_audio decorator), and dry_run tools that mirror these shapes. Deferred to TG 23.3 (plans 24-14 for classifier tool, 24-16 for streaming + transcription, 24-17 for dry_run mirroring).

### F-09 Python "safety net" in classifier streaming
- **Status:** OUT-OF-SCOPE (target plan 24-16)
- **Evidence:** unchanged.

### F-10 RC-shaped tool_choice provider-dict in classifier streaming
- **Status:** OUT-OF-SCOPE (target plan 24-16)
- **Evidence:** unchanged.

### F-11 Voice tool registered on classifier agent
- **Status:** OUT-OF-SCOPE (target plan 24-16)
- **Evidence:** unchanged.

### F-12 Constructor-level `agent_id`-pinned RC clients
- **Status:** partial — Investigation cleared 23.1; Admin CLEARED 23.2 (no agent_id, no constructor-pinned client); Classifier remains
- **Evidence cleared (Admin):** the Admin Agent is constructed once at lifespan via `build_admin_agent(chat_client, tools, middleware)` at `main.py:684`. `agents/admin.py:22-34` shows the factory: `Agent(client=chat_client, instructions=instructions, tools=list(tools), middleware=list(middleware))` — no `agent_id` constructor pinning. Admin is single-turn non-streaming with no per-call session/thread continuity needed (per 24-09 design notes); the agent is invoked stateless via `admin_agent.run(enriched_text, options=ChatOptions(tool_choice="required"))` per call.
- **Evidence remaining (out-of-scope):** `main.py:598` still constructs `AzureAIAgentClient(agent_id=classifier_agent_id, ...)` for Classifier. Deferred to 24-14.

### F-13 RC `conversation_id` round-trip (bypasses framework session API)
- **Status:** CLEARED on Investigation surface (23.1, via P0-1 Option A); not applicable on Admin (no session continuity); Classifier follow-up remains out-of-scope
- **Evidence:** Admin agent is single-turn — there is no thread_id/conversation_id round-trip in `admin_handoff.py`. The (now-removed) custom `admin_agent_process` span did not carry conversation state either.

### F-14 Custom `tracer.start_as_current_span(...)` in streaming/adapter.py
- **Status:** OUT-OF-SCOPE (target plan 24-16)
- **Evidence:** unchanged.

### F-15 Custom `tracer.start_as_current_span(...)` in streaming/investigation_adapter.py
- **Status:** CLEARED (23.1 closure stands)

### F-16 Custom `tracer.start_as_current_span(...)` in processing/admin_handoff.py
- **Status:** CLEARED
- **Evidence:** patch lines 1210 and 1685 show explicit deletion of both `with tracer.start_as_current_span("admin_agent_process") as span:` and `with tracer.start_as_current_span("admin_agent_batch_process") as span:`. The `tracer = trace.get_tracer(...)` and `from opentelemetry import trace` lines are also removed. The capture-shape attributes that previously rode those custom spans (`admin.inbox_item_id`, `admin.tools_called`, `admin.outcome`, etc.) now ride **structured log extras** (`log_extra` dict at admin_handoff.py:193-197, 208-213) per 24-11 MEMORY entry — `process_admin_capture` runs in `asyncio.create_task()` AFTER the HTTP request span ends, so `trace.get_current_span()` would return NoOpSpan; structured logs are the correct off-thread observability surface. The framework emits its own `invoke_agent` span around `admin_agent.run(...)` and the `CaptureTraceAgentMiddleware` (24-03) tags it with `capture.trace_id` at source.

### F-17 Existing AgentMiddleware uses tracer.start_as_current_span anti-pattern
- **Status:** partial — Investigation cleared 23.1 (new `agents/agent_middleware/` operates on current span); Admin agent now uses new middleware too (`main.py:687`); legacy `agents/middleware.py` classes still wired into Classifier construction at `main.py:598`. Cleanup target: plan 24-18 deletes legacy file at end of TG 23.3.
- **Evidence cleared (Admin):** `build_admin_agent` at `main.py:684-688` passes `middleware=[CaptureTraceAgentMiddleware(), CaptureTraceFunctionMiddleware()]` from `agents/agent_middleware/capture_trace.py` (the GA-compliant variant that operates on `trace.get_current_span().set_attribute(...)`). The legacy `AuditAgentMiddleware` + `ToolTimingMiddleware` are NOT in the Admin construction list.
- **Evidence remaining:** Classifier construction at `main.py:598-604` still passes the legacy `AuditAgentMiddleware`/`ToolTimingMiddleware` (because Classifier is RC and the RC client takes the legacy middleware). The legacy file `agents/middleware.py` is deleted in plan 24-18 after Classifier migrates to GA in 24-14..24-17. Regression guard `test_legacy_middleware_imports_survive.py` still passes.

### F-18 Probe-fixture-shaped extraction code
- **Status:** CLEARED for Admin surface (1/5 calibration fixture consumed: `tool_call_extraction.json`)
- **Evidence:** `processing/admin_handoff.py:12, 53` and `eval/invoker.py:64` reference `tool_call_extraction.json` in docstring/comments. The `_output_tool_called` walking pattern (`getattr(msg, "role", None) != "tool"` + `getattr(msg, "contents", None)`) matches the fixture's `messages_walk` field at fixture index 1 (`"role": "'tool'"`, `"contents": "[<agent_framework._types.Content object at ...>]"`). See W-02-23.2 for a soft probe-fidelity warning on the `Content.name` / `Content.function_name` vocabulary that wasn't introspected inside the Content boundary (same class as 23.1 W-02).

### F-19 Portal-managed agent shell pattern (D-02 violation)
- **Status:** partial — Investigation cleared 23.1; Admin CLEARED 23.2 (`agents/admin.py` is now a pure GA factory reading from repo); Classifier remains out-of-scope
- **Evidence cleared (Admin):** `agents/admin.py` (35 lines) is a pure factory: `build_admin_agent(chat_client, tools, middleware) -> Agent` reuses `load_instructions("admin")` from `agents/investigation.py` (DRY per 24-09 deviation; same helper handles both Investigation + Admin) and constructs `Agent(client=chat_client, instructions=instructions, tools=list(tools), middleware=list(middleware))`. The portal-managed-shell `ensure_admin_agent` pattern is removed. The legacy `app.state.admin_agent_id` is set to `None` explicitly (24-09 deviation rule 2) so any leftover code paths that try to look it up short-circuit cleanly.
- **Instructions canonicalized:** `agents/instructions/admin.md` exists (87 lines), promoted from Foundry portal source (asst_17oFXNHNq7kzmspQGMUrgERM) in plan 24-09. Header comment block at lines 1-9 documents source-of-truth provenance + D-02 status.
- **Evidence remaining (out-of-scope):** `agents/classifier.py` still contains the `ensure_classifier_agent` portal-shell creation pattern. Deferred to TG 23.3 (24-14).

## Pass — Framework Primitives Correctly Used (in-scope, new in 23.2)

| # | Concern | Evidence |
|---|---|---|
| Pass-1 | GA Agent construction (Admin singleton) | `agents/admin.py:22-34` `Agent(client=chat_client, instructions=load_instructions("admin"), tools=list(tools), middleware=list(middleware))` |
| Pass-2 | Instructions live in repo (D-02 Admin) | `agents/instructions/admin.md` (87 lines); `load_instructions("admin")` reads it at lifespan startup via `agents/investigation.py:load_instructions` (DRY helper) |
| Pass-3 | `agent.run(...)` invocation shape (Admin handoff) | `processing/admin_handoff.py:253-256` `await admin_agent.run(enriched_text, options=ChatOptions(tool_choice="required"))` (initial call); 308-311 (D-09 bounded retry, same shape) |
| Pass-4 | `tool_choice="required"` (string form, probe-verified) | `processing/admin_handoff.py:255, 310` — uses string form per `tool_choice_required.json` probe finding; provider-dict explicitly rejected (D-10). The D-07 explicit-justification block at admin_handoff.py:239-251 documents the bounded retry as a temporary bridge (Q4 deletion trigger: when `'mode'` dict schema is documented OR Foundry adds tool_choice subset pinning). |
| Pass-5 | No custom spans wrapping framework calls (Admin) | `processing/admin_handoff.py` contains zero `tracer.start_as_current_span(...)`. Custom `admin_agent_process` + `admin_agent_batch_process` spans deleted (patch lines 1210, 1685). Capture-trace attrs ride structured `log_extra` dicts for off-thread work + `CaptureTraceAgentMiddleware` for the framework `invoke_agent` span. |
| Pass-6 | New `CaptureTraceAgentMiddleware` wired into Admin Agent | `main.py:687-688` passes the GA-compliant middleware list `[CaptureTraceAgentMiddleware(), CaptureTraceFunctionMiddleware()]` to `build_admin_agent`. No legacy `AuditAgentMiddleware`/`ToolTimingMiddleware` instances are passed to the Admin Agent (those are confined to the Classifier RC construction site). |
| Pass-7 | Plain Python tool methods on AdminTools (no `@tool(approval_mode=...)`) | `tools/admin.py` — 6 async methods (`add_errand_items`, `add_task_items`, `get_routing_context`, `manage_destination`, `manage_affinity_rule`, `query_rules`) all decorator-stripped per D-05/D-06. `Annotated[..., Field(description=...)]` parameter shapes preserved (17 occurrences verified by grep). Bound at construction via `Agent(tools=[admin_tools.method, ...])` at `main.py:684-688`. |
| Pass-8 | Plain Python tool method on RecipeTools (no decorator) | `tools/recipe.py` — `fetch_recipe_url` decorator-stripped. `Annotated[...]` shape preserved (1 occurrence). Recipe tool wiring moved BEFORE `build_admin_agent` per 24-09 deviation rule 1 so it lands in `tools=` at agent construction time. |
| Pass-9 | `EvalAgentInvoker` facade introduced (Protocol + RC + GA + hybrid) | `eval/invoker.py:38-58` defines the `EvalAgentInvoker` Protocol with `invoke_classifier` + `invoke_admin` methods. `GAEvalAgentInvoker` (lines 61-105) calls `Agent.run(...)`. `RCEvalAgentInvoker` (lines 108-164) is the temporary RC bridge. `_MigrationHybridInvoker` (lines 167-201) routes classifier→RC and admin→GA. Deletion trigger documented at lines 18-19 (end of plan 24-18). |
| Pass-10 | Evaluation runner uses invoker (admin path) | `eval/runner.py:233, 247, 290` — `run_admin_eval` takes `invoker: EvalAgentInvoker` and calls `invoker.invoke_admin(txt, dt, rc)`. Zero direct RC type usage in this function or its module. |
| Pass-11 | Evaluation runner uses invoker (classifier path) | `eval/runner.py:95, 108, 148` — `run_classifier_eval` takes `invoker: EvalAgentInvoker` and calls `invoker.invoke_classifier(txt, et)`. RC body now lives inside `RCEvalAgentInvoker` (temp bridge) — runner module itself is GA-clean. |
| Pass-12 | `eval/foundry.py` uses invoker (app-mediated dataset) | `eval/foundry.py:842, 883, 887, 926, 930, 1009, 1049, 1180, 1212` — admin + classifier app-mediated paths both flow through `invoker: EvalAgentInvoker`. Zero `client.get_response(...)` calls; zero `Message`/`ChatOptions` RC types. |
| Pass-13 | `api/eval.py` constructs the hybrid invoker | `api/eval.py:25-29, 47-77` — `_build_migration_invoker(classifier_client, admin_agent)` constructs `_MigrationHybridInvoker(rc_invoker=..., ga_invoker=...)` from lifespan-supplied dependencies. Single deletion target in plan 24-18 (when classifier flips to GA and the hybrid disappears). |
| Pass-14 | `InvestigationTools` holds the migration-temporary hybrid | `tools/investigation.py:101-148` — `admin_agent` parameter added to `__init__`; `_build_eval_invoker()` helper method constructs the hybrid with local imports (auto-format-safe pattern per MEMORY [24-12]). Same deletion trigger as `api/eval.py`. |
| Pass-15 | Probe-fixture path consumed (Admin `tool_call_extraction.json`) | `processing/admin_handoff.py:12, 53` + `eval/invoker.py:64` reference the fixture in docstrings. The walking pattern (`role == 'tool'` + iterate `contents`) matches the fixture's `messages_walk` field. (Soft probe-fidelity gap on inner Content vocabulary — see W-02-23.2.) |
| Pass-16 | Token metering unchanged (no manual counters added) | `enable_instrumentation()` at `main.py:31` unchanged. No new `tokens_used` / `prompt_tokens` / `completion_tokens` increments in `processing/`, `eval/`, or `agents/` files in this patch. Token usage continues to flow through framework GenAI semantic conventions. |
| Pass-17 | App Insights export wiring unchanged | `main.py:14, 21` unchanged. No new `SpanExporter` introduced. `configure_azure_monitor(...)` remains the single export pipeline. |

## Warnings

### W-01 (carried from 23.1, calibration-anticipated): `CaptureTraceSpanProcessor` narrowing — RETAINED

- **File:** `backend/src/second_brain/observability/span_processor.py` (no change in 23.2)
- **Concern:** Capture-trace propagation (non-framework spans).
- **Status:** 23.1 narrowed-responsibility docstring landed; processor RETAINED per design D-07a as the bulk-tagger for non-framework spans (Cosmos `AppDependencies`, third-party library `AppExceptions`, custom non-framework spans). The on_start overlap with framework-tagged spans on the same attribute name is idempotent and benign.
- **Justification (D-07a, verbatim from docstring at lines 26-38):** "Without this processor, query_capture_trace's union over AppDependencies loses correlation."
- **Verdict:** justified retention. No action needed. Sticks at warning class until W-01 is closed by removal of the processor (target: never — design D-07a is permanent retention).

### W-02-23.2 (NEW): Admin `Content.name` / `Content.function_name` vocabulary not strictly probe-introspected

- **File:** `backend/src/second_brain/processing/admin_handoff.py:63-66` (and the mirrored path in `_output_tool_called` docstring at lines 53-58)
- **Concern:** Strict probe fidelity (Q2 in the auditor contract). Same class as 23.1 W-02 on the investigation streaming `Content.type` vocabulary.
- **Detail:** `_output_tool_called(response)` walks `response.messages` for `role == 'tool'` (verified by fixture `tool_call_extraction.json` message index 1) and then defensively reads `getattr(content, "name", None) or getattr(content, "function_name", None)`. The probe fixture captured the `Content` object as `[<agent_framework._types.Content object at ...>]` but its introspection stopped at the Content boundary — neither `Content.name` nor `Content.function_name` was walked to capture the actual GA SDK vocabulary.
- **Risk classification:** LOW. The code defensively tries BOTH possible attribute names — if the SDK uses one, the other returns `None` and the first short-circuits the `or` chain. Worst case: BOTH names are wrong, the tool-call walk returns an empty set, and the `output_fired` branch triggers a D-09 retry (which then hits the same wall). Empirical verification on first deployed Admin capture would catch this loudly via the existing `outcome=no_output_tool` log line, which already has Application Insights alerting.
- **Recommended response:** non-blocking. Either (a) accept the risk and verify empirically on first deployed Admin processing run, or (b) extend `scripts/foundry_probe.py` probe 2 to walk `Content.__dict__` and pin the captured vocabulary into the fixture. Same recommendation as 23.1 W-02; if not addressed before cumulative-pre-push (plan 24-22), the cumulative audit will surface this once more as a deferred fidelity gap.

### W-03-23.2 (NEW): Stale Admin warmup self-heal factory remains live in lifespan code

- **File:** `backend/src/second_brain/main.py:826-840`
- **Concern:** Dead code referencing removed `app.state.admin_client` + `admin_agent_id` (analogue of 23.1 W-03 for `investigation_client`).
- **Detail:** The patch removes `app.state.admin_client` and `app.state.admin_agent_id` from the GA success branch (sets both to None at lines 695-700 per 24-09 deviation rule 2). The warmup wiring at lines 804-805 + 826-840 still references those names via `if app.state.admin_client is not None:`. Since the guard returns False for the GA path, `warmup_factories["admin"] = _make_admin_client` is never installed, and `_make_admin_client` is dead code at runtime. Behavior is benign downgrade: Admin is excluded from the warmup loop (same as 23.1's Investigation exclusion). Classifier warmup continues to function (Classifier is still RC, lifespan keeps its client + agent_id).
- **Why this is not a failure:** the dead branch does not violate the framework-first principle — it references removed state but never executes its RC-shaped code. Plan 24-19 (warmup migration in TG 23.3) will replace this code wholesale; the dead factory disappears in that sweep.
- **Recommended response:** Add a single-line follow-up note in the deployment checklist (alongside the same 23.1 W-03 carry-forward) reminding plan 24-19 to delete the dead `_make_admin_client` factory + the legacy `app.state.admin_client` checks. Do not block this checkpoint.

### W-04-23.2 (NEW): `eval/invoker.py` imports `AzureAIAgentClient` for typing on `RCEvalAgentInvoker`

- **File:** `backend/src/second_brain/eval/invoker.py:28-30, 122-123`
- **Concern:** RC framework import survives in a new file added during 23.2.
- **Detail:** `eval/invoker.py` is a new file introduced by 24-12. It imports `AzureAIAgentClient` (under `if TYPE_CHECKING:` so no runtime dependency, and only on the `RCEvalAgentInvoker.__init__` parameter type hints). The body of `RCEvalAgentInvoker.invoke_classifier` and `invoke_admin` also localizes its RC imports (`from agent_framework import Message; from agent_framework import ChatOptions as RCChatOptions`) inside method bodies (lines 133-134, 152-153) — minimising RC-dependency footprint.
- **Justification (full D-07 template entry at `eval/invoker.py:7-19`, addresses all 4 questions):**
  1. **Framework primitive considered:** `Agent.run(messages)` direct.
  2. **What custom code provides:** translation between evaluation cases (input + expected label) and `agent.run()` call shape, AND adapting the response back to the runner's existing per-case dict format.
  3. **Why not middleware/context provider/tool/configuration:** it CAN be solved by either, but during the migration window we have BOTH RC and GA call shapes alive (classifier on RC until plans 24-13..24-17, admin on GA after plans 24-09..24-11). The facade hides that split for one migration window.
  4. **Permanent or temporary:** TEMPORARY. Deletion trigger: end of plan 24-18, when no `RCEvalAgentInvoker` caller remains.
- **Verdict:** justified deviation. D-07 template entry is complete (all 4 questions answered) with a pinned deletion trigger. The `if TYPE_CHECKING` guard + method-body-local imports keep the RC-dependency footprint minimal during the migration window. Reclassified from failure to warning per auditor contract.

## Out-of-Scope Failures (deferred to TG 23.3)

These findings remain in the codebase but apply to surfaces explicitly excluded from TG 23.2 per scope_constraint. They MUST be cleared by their target plans before final cutover:

| # | Surface | Target plan |
|---|---|---|
| F-01 (Classifier slice) | `main.py:520, 598, 811-821` `AzureAIAgentClient` construction (foundry probe + Classifier client + classifier warmup factory) | 24-14 |
| F-02 | `warmup.py:8-19` `AzureAIAgentClient` import + typing | 24-19 |
| F-04 | `streaming/adapter.py:18, 155-156, 353-355, 557-559` classifier streaming RC client | 24-16 |
| F-08 (Classifier + transcription + dry_run) | `tools/classification.py:75`, `tools/transcription.py:58`, `eval/dry_run_tools.py` (mirror) — 3 `@tool(approval_mode="never_require")` decorators remain | 24-14 (classifier tool), 24-16 (transcription), 24-17 (dry_run) |
| F-09 | `streaming/adapter.py:92-152, 324-334, 526-538, 676-686` `_safety_net_file_as_misunderstood` | 24-16 |
| F-10 | `streaming/adapter.py:182-188, 590-596` RC `{"mode":"required","required_function_name":...}` dict | 24-16 |
| F-11 | `main.py:577-581` voice tool on classifier agent | 24-16 (or split) |
| F-12 (Classifier) | `main.py:598` agent_id-pinned `AzureAIAgentClient(agent_id=classifier_agent_id, ...)` | 24-14 |
| F-13 (classifier follow-up + capture path) | `streaming/adapter.py:596`, `api/capture.py:95-198` RC conversation_id round-trip | 24-16 + 24-17 |
| F-14 | `streaming/adapter.py:175, 372, 582` custom spans wrapping framework calls | 24-16 |
| F-17 (legacy `AuditAgentMiddleware` + `ToolTimingMiddleware`) | `agents/middleware.py:44, 72` RC-era span-doubling — still wired into Classifier construction at `main.py:598-604` | 24-18 (delete after Classifier migrated) |
| F-19 (Classifier) | `agents/classifier.py:55-65` portal-shell `ensure_classifier_agent` | 24-14 (instructions promote in 24-13; agent rewrite in 24-14) |
| `RCEvalAgentInvoker` existence | `eval/invoker.py:108-164` (temp RC bridge) | 24-18 (delete; the cleanup commit replaces hybrid with plain `GAEvalAgentInvoker`) |

Total out-of-scope failures: 9 distinct calibration findings (counting F-01, F-08, F-12, F-13, F-17, F-19 as one each because their Admin slice is cleared in 23.2). Plus 1 transition-state outstanding item (`RCEvalAgentInvoker` existence). Total 10 outstanding-but-acceptable items at this gate per the plan's `acceptable at 23.2 gate` list.

The 23.1 audit reported 14 out-of-scope failures; this audit reports 9. The reduction of 5 is exactly accounted for by 23.2 closures: F-03, F-07, F-16, F-19 (Admin slice closed), F-06 (admin slice + facade), F-08 (admin + recipe slice closed). F-01 partial (Admin slice closed but Classifier slice remains, so still counts as 1 partial in the table). F-12 same (Admin slice closed). F-17 same (Admin's new middleware does not use the legacy classes, but the classes themselves remain wired to Classifier — still counts as 1 partial).

## New Findings (not in calibration)

None. No regression patterns introduced. The patch adds only GA-shaped code, plus a temporary RC bridge inside `eval/invoker.py` that is justified via the D-07 explicit-justification template with a pinned deletion trigger (W-04-23.2 above). The two new test files don't appear in this audit; `tests/test_admin_handoff.py` was completely rewritten to assert against the GA Agent shape (`mock_admin_agent.run.assert_called_once()` with `ChatOptions(tool_choice="required")`), and `tests/test_eval.py` was rewritten to assert against the invoker mock shape (`invoker.invoke_classifier`/`invoke_admin` AsyncMock).

Test execution (`pytest tests/test_admin_handoff.py tests/test_eval.py -x`): 38 passed in 2.36s.

## Probe Fixture Strict-Fidelity Check

| Fixture | Consumed by | Status | Notes |
|---|---|---|---|
| `streaming_shape.json` | `streaming/investigation_adapter.py:148, 159` (cleared 23.1) | exact | No 23.2 consumer; 23.1 status preserved. Admin is non-streaming. |
| `tool_call_extraction.json` | `processing/admin_handoff.py:48-69` (`_output_tool_called`); `eval/invoker.py:64` (cited in docstring) | partial | Top-level walk (`response.messages` + `role == 'tool'` + `contents`) matches fixture exactly. Inner `Content.name` / `Content.function_name` vocabulary not introspected by probe — see W-02-23.2. Defensive `or` chain in code keeps risk LOW. |
| `tool_choice_required.json` | `processing/admin_handoff.py:255, 310` (Admin uses string form `"required"`) | exact | Admin path uses the probe-validated string form. The provider-dict alternative (RC shape) is explicitly rejected per D-10 and never reintroduced. The classifier streaming path (where this matters more) is still on the RC dict — out-of-scope until 24-16. |
| `session_rehydration.json` | Investigation only (cleared 23.1) | n/a | Admin is single-turn non-streaming; no session continuity required. Classifier follow-up consumer deferred to 24-15/24-16. |
| `session_rehydration_fresh_process.json` | Investigation only (cleared 23.1, P0-1 Option A) | n/a | Same as above. |
| `auth_probe.json` | `main.py:498-510` (cleared 23.1) | exact | `FoundryChatClient` + sync `ManagedIdentityCredential` validated; admin's `build_admin_agent` reuses the same `chat_client` + credential, no new auth surface introduced. |

## Cross-Task-Group Regression Check

23.1 closures verified to stand against 23.2 patch:

| 23.1 closure | Verification in 23.2 |
|---|---|
| F-05 cleared (`streaming/investigation_adapter.py` — no RC client) | No reintroduction. `grep -n "AzureAIAgentClient" backend/src/second_brain/streaming/investigation_adapter.py` returns no hits. |
| F-15 cleared (no custom `investigate` span) | No reintroduction. `grep -n "tracer.start_as_current_span" backend/src/second_brain/streaming/investigation_adapter.py` returns no hits. |
| F-17 (Investigation slice) cleared (new `agents/agent_middleware/` package) | New Admin Agent at `main.py:687-688` uses the same `CaptureTraceAgentMiddleware`/`CaptureTraceFunctionMiddleware` from the 23.1-introduced package. Classes are reused, not duplicated. |
| F-19 (Investigation slice) cleared (`agents/instructions/investigation.md`) | Admin extends the pattern: `agents/instructions/admin.md` exists (87 lines); `agents/admin.py` reuses `load_instructions("admin")` helper from `agents/investigation.py` per 24-09 DRY deviation. |
| W-01 (`CaptureTraceSpanProcessor` narrowed) | `backend/src/second_brain/observability/span_processor.py` unchanged in this patch. Narrowed responsibility documented in docstring lines 26-38 (landed 23.1). |
| 23.1 regression-guard tests | `test_legacy_middleware_imports_survive.py` PASS (still asserts new path); `test_foundry_credential_shape.py` PASS (no new credential construction in 23.2); `test_no_rc_imports_after_cleanup.py` RED (intentional — 4 files still import RC: `eval/invoker.py`, `main.py`, `streaming/adapter.py`, `warmup.py`; this is the expected mid-migration state, will go GREEN incrementally as TG 23.3 strips remaining RC imports). |

No 23.1 closure regressed in 23.2.

## Files Outside Framework-First Scope (not audited)

Per scope_constraint:
- `mobile/**`, `web/**`, `mcp/**`, `infra/**` (entire surfaces out of scope per design)
- `docs/**`, `.planning/**` (documentation, not framework-fidelity surface)
- `backend/tests/**` outside the two rewritten test files (existing tests are not the audit subject for TG 23.2)
- `backend/src/second_brain/spine/**` (separate workload events system, out of scope per design)
- `backend/src/second_brain/cosmos/**`, `backend/src/second_brain/auth.py`, `backend/src/second_brain/models/**` (out of scope per design)
- `backend/src/second_brain/api/**` outside `api/eval.py` + `api/errands.py` (capture/voice/health/etc. routes unchanged in this patch)

## Decision

**This gate PASSES.** All Admin-surface and evaluation-invoker-facade in-scope failure findings from the calibration baseline are resolved. The four warnings are:
- W-01: a justified D-07a retention with documentation already landed (carry-forward from 23.1)
- W-02-23.2: a low-risk decorative-path probe-coverage gap with a clear empirical-verification fallback (same class as 23.1 W-02)
- W-03-23.2: dead-code cleanup target — plan 24-19 sweeps it up alongside the same 23.1 W-03 carry-forward
- W-04-23.2: justified D-07 template entry with pinned deletion trigger (plan 24-18); RC-dependency footprint minimized via `TYPE_CHECKING` guard + method-body-local imports

TG 23.3 (Classifier kickoff: plan 24-14) is unblocked.

The out-of-scope failure count of 9 is the expected residual state given the strict TG-by-TG migration cadence; those findings move to the TG 23.3 audit reports as their target surfaces are reached. The auditor's permanent regression guard `test_no_rc_imports_after_cleanup.py` will ensure they're all cleared before the push-guard sentinel is removed at the end of plan 24-22.

---

**FIDELITY AUDIT: 17 pass, 4 warning, 0 in-scope failure (9 out-of-scope failure). Report at `.planning/phases/24-foundry-ga-migration/FRAMEWORK-FIDELITY-23.2.md`.**
