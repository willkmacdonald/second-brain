---
phase: 24-foundry-ga-migration
audit_scope: TG 23.1 (Investigation surface)
patch_subject: .planning/phases/24-foundry-ga-migration/FIDELITY-23.1.patch
verdict: PASS-WITH-WARNINGS
in_scope_failures: 0
out_of_scope_failures: 14
warnings: 3
passes: 14
audited_at: 2026-05-10
---

# Framework Fidelity Audit — Task Group 23.1

## Verdict

**PASS-WITH-WARNINGS**

Investigation surface is cleanly GA-compliant. Every in-scope finding from the
calibration baseline (F-01 Investigation slice, F-05, F-08 Investigation slice,
F-13 Investigation slice, F-15, F-17 Investigation usage, F-18 fixtures, F-19
Investigation slice) is resolved against the framework-first checklist. Three
warnings are tracked: W-01 narrowing now landed (was an explicit anticipated
warning at calibration time), an observability-only spine adapter no-op for
Investigation, and a soft probe-fidelity warning on tool-call content typing
which is a non-load-bearing decorative path.

Out-of-scope findings (Admin + Classifier slices, warmup, eval, processing,
classifier streaming) remain RC-shaped and are deferred to TG 23.2 and TG 23.3
per the scope-constraint contract. This checkpoint does not block on those.

## Summary

| Counter | Value |
|---|---:|
| ✓ Pass findings (in-scope GA-compliant) | 14 |
| ⚠️ Warnings (justified or near-violation) | 3 |
| ❌ In-scope failures (blocking) | 0 |
| ❌ Out-of-scope failures (deferred) | 14 |
| Prerequisite failures | 0 |

## Resolution Of Calibration Findings (F-01..F-19)

### F-01 main.py: 10 RC client construction sites
- **Status:** ⚠️ partial — Investigation slice CLEARED; Admin + Classifier slices remain
- **Evidence cleared (Investigation):** `backend/src/second_brain/main.py:493-508` now constructs `FoundryChatClient(project_endpoint=..., model=..., credential=ManagedIdentityCredential())`. Lines 720-755 construct the Investigation `Agent` via `build_investigation_agent(chat_client=chat_client, tools=[...], middleware=[CaptureTraceAgentMiddleware(), CaptureTraceFunctionMiddleware()])`. The portal-managed `ensure_investigation_agent` path is removed. `app.state.investigation_agent` replaces `app.state.investigation_client`.
- **Evidence remaining (out-of-scope):** lines 520, 598, 639, 800, 818, 833 still construct `AzureAIAgentClient`. The patch explicitly documents `# KEPT for Admin/Classifier slices that still use AzureAIAgentClient. Removed in plans 24-09 (Admin) and 24-14 (Classifier).` These sites are out-of-scope per scope_constraint; deferred to TG 23.2 and TG 23.3.

### F-02 RC framework client in warmup.py
- **Status:** ❌ out-of-scope (target plan 24-19 — warmup is in TG 23.3)
- **Evidence:** `backend/src/second_brain/warmup.py:8-19` still imports and types against `AzureAIAgentClient`. No change in this patch.
- **Side effect of TG 23.1:** `app.state.investigation_client` and `app.state.investigation_agent_id` are no longer set, so the warmup branches at `main.py:795-796, 830-844` that reference them become silent no-ops (the `getattr(..., None)` returns None and the `if` guard prevents adapter wiring). This is benign downgrade — the warmup loop continues to operate for Admin + Classifier — but represents stale code that should be cleaned in plan 24-19.

### F-03 RC framework client in processing/admin_handoff.py
- **Status:** ❌ out-of-scope (target plan 24-11 — Admin is in TG 23.2)
- **Evidence:** unchanged in this patch; `backend/src/second_brain/processing/admin_handoff.py:15` still imports `AzureAIAgentClient`.

### F-04 RC framework client in streaming/adapter.py (Classifier streaming)
- **Status:** ❌ out-of-scope (target plan 24-16 — Classifier streaming is in TG 23.3)
- **Evidence:** unchanged; `backend/src/second_brain/streaming/adapter.py:18` still imports `AzureAIAgentClient`.

### F-05 RC framework client in streaming/investigation_adapter.py
- **Status:** ✅ CLEARED
- **Evidence:** `backend/src/second_brain/streaming/investigation_adapter.py:44` now imports `from agent_framework import Agent, Message`. The old `from agent_framework.azure import AzureAIAgentClient` is gone. `stream_investigation(...)` takes `agent: Agent` and invokes `agent.run(msg_list, stream=True)` at line 142. No more `client.get_response(messages=..., stream=True, options=options)`.

### F-06 RC-shaped eval invocation in eval/runner.py
- **Status:** ❌ out-of-scope (target plan 24-15 — eval is in TG 23.3)
- **Evidence:** unchanged; `backend/src/second_brain/eval/runner.py:32` still imports `AzureAIAgentClient` for typing.

### F-07 RC-shaped eval in eval/foundry.py
- **Status:** ❌ out-of-scope (target plan 24-15 — eval is in TG 23.3)
- **Evidence:** unchanged in this patch.

### F-08 RC `@tool(approval_mode="never_require")` decorators
- **Status:** ⚠️ partial — Investigation tool methods CLEARED; Admin + Classifier + recipe + transcription remain RC-decorated
- **Evidence cleared (Investigation):** `backend/src/second_brain/tools/investigation.py` strips all 9 `@tool(approval_mode="never_require")` decorators. `from agent_framework import tool` import is removed. Tool methods are now plain `async def` with `Annotated[..., Field(description=...)]` parameter shapes and docstrings; the GA `Agent(tools=[instance.method, ...])` registration in `main.py:734-744` binds them as tools at construction.
- **Evidence remaining (out-of-scope):** `backend/src/second_brain/tools/admin.py`, `tools/classification.py`, `tools/recipe.py`, `tools/transcription.py` still carry RC decorators. Deferred to TG 23.2 (admin/recipe) and TG 23.3 (classifier/transcription).

### F-09 Python "safety net" in classifier streaming
- **Status:** ❌ out-of-scope (target plan 24-16 — classifier streaming is in TG 23.3)
- **Evidence:** unchanged in this patch; `streaming/adapter.py:92-152` retains `_safety_net_file_as_misunderstood`.

### F-10 RC-shaped tool_choice provider-dict in classifier streaming
- **Status:** ❌ out-of-scope (target plan 24-16 — classifier streaming is in TG 23.3)
- **Evidence:** unchanged in this patch.

### F-11 Voice tool registered on classifier agent
- **Status:** ❌ out-of-scope (target plan 24-16 — classifier is in TG 23.3)
- **Evidence:** unchanged in this patch.

### F-12 Constructor-level agent_id-pinned RC clients
- **Status:** ⚠️ partial — Investigation CLEARED; Admin + Classifier remain
- **Evidence cleared (Investigation):** the Investigation Agent is constructed once at lifespan via `build_investigation_agent(chat_client, tools, middleware)` (a true GA singleton; no `agent_id` constructor pinning). Per-call conversation continuity is supplied by the mobile-side history payload per P0-1 OUTCOME (see F-13 disposition).
- **Evidence remaining (out-of-scope):** `main.py:598, 639` still construct `AzureAIAgentClient(agent_id=..., should_cleanup_agent=False)` for Admin + Classifier. Deferred.

### F-13 RC `conversation_id` round-trip (bypasses framework session API)
- **Status:** ✅ CLEARED on Investigation surface (via P0-1 OUTCOME Option A, not via `AgentThread`/`get_session`)
- **Evidence:** the calibrated probe `backend/tests/fixtures/foundry-probe/session_rehydration_fresh_process.json` PROVED that cross-process session-handle rehydration via `session_id` alone FAILS on GA Foundry SDK 1.3.0 (`recalled_pineapple: false`, magic word "PINEAPPLE" not recalled in fresh subprocess). The operator locked **Option A**: stateless agent invocation with explicit conversation context. For Investigation specifically:
  - `api/investigate.py:42-55` accepts `history: list[ConversationTurn] | None` on the request body. Mobile holds the visible chat history client-side.
  - `streaming/investigation_adapter.py:130-133` builds an explicit `list[Message]` from the mobile-supplied history + new question.
  - `agent.run(msg_list, stream=True)` is invoked stateless per turn — no `conversation_id`, no `thread=AgentThread(...)`, no `session=`.
  - The `thread_id` echoed on the `done` SSE event is a fresh `uuid.uuid4()` per turn for mobile backward compat only; it has no server-side meaning.
- **Note on framework primitive:** Option A is documented in the design D-07 explicit-justification template as the correct response when `AgentSession`-based rehydration fails its probe. This is a valid framework-first answer: the GA SDK's `agent.run(messages=[...])` IS the framework primitive for explicit-history invocation, and the calibrated probe disproved the alternative primitive.
- **Evidence remaining (out-of-scope, classifier follow-up):** classifier-follow-up code in `streaming/adapter.py:596` and `api/capture.py` still RC-stores `foundryThreadId`. Deferred to TG 23.3.

### F-14 Custom tracer.start_as_current_span in streaming/adapter.py
- **Status:** ❌ out-of-scope (target plan 24-16 — classifier streaming is in TG 23.3)
- **Evidence:** unchanged; `streaming/adapter.py:175, 372, 582` still wrap framework calls with custom spans.

### F-15 Custom tracer.start_as_current_span in streaming/investigation_adapter.py
- **Status:** ✅ CLEARED
- **Evidence:** the entire `with tracer.start_as_current_span("investigate") as span: ...` block is deleted. `tracer = trace.get_tracer("second_brain.investigation")` import is removed. The capture-shape attributes that previously lived on that span (`investigate.question_length`, `investigate.thread_id`, `investigate.history_length`) now ride on the auto-instrumented AppRequests span via `api/investigate.py:99-107` using `trace.get_current_span().set_attribute(...)`, mirroring the established `api/capture.py:228` pattern. The framework emits its own `invoke_agent` span around `agent.run(...)` and capture-trace tagging happens there via `CaptureTraceAgentMiddleware`.

### F-16 Custom tracer.start_as_current_span in processing/admin_handoff.py
- **Status:** ❌ out-of-scope (target plan 24-11 — admin processing is in TG 23.2)
- **Evidence:** unchanged.

### F-17 Existing AgentMiddleware uses tracer.start_as_current_span anti-pattern
- **Status:** ⚠️ partial — Investigation surface CLEARED (new `CaptureTraceAgentMiddleware` + `CaptureTraceFunctionMiddleware` operate on the current span); legacy classes preserved for Admin + Classifier
- **Evidence cleared:** `backend/src/second_brain/agents/agent_middleware/capture_trace.py:56, 78-80, 106-115, 118` operate exclusively via `trace.get_current_span().set_attribute(...)`. The new middleware classes never start a new span — they read context and add attributes to the framework-emitted span. Per F-17 prescription verbatim.
- **Per P1-3:** the new middleware lives at `agents/agent_middleware/` (NOT `agents/middleware/`) to avoid Python import-system shadowing of the legacy module `agents/middleware.py`. The legacy module continues to export `AuditAgentMiddleware` + `ToolTimingMiddleware` and is still wired into Admin + Classifier construction sites at `main.py:598, 639`. Plan 24-18 deletes the legacy file at end of TG 23.3.
- **Regression test in place:** `backend/tests/test_legacy_middleware_imports_survive.py` AST-asserts that `agents/middleware/` is NOT a package (would shadow the module) and that both legacy and new middleware are importable during the migration window.

### F-18 Probe-fixture-shaped extraction code missing
- **Status:** ✅ CLEARED for Investigation surface (5/5 calibration fixtures + new fresh-process probe present)
- **Evidence:** `backend/tests/fixtures/foundry-probe/` now contains all six fixtures:
  - `auth_probe.json` (consumed by `main.py:496-501` FoundryChatClient construction)
  - `streaming_shape.json` (consumed by `streaming/investigation_adapter.py:148, 159`)
  - `tool_call_extraction.json` (will be consumed by TG 23.2 `processing/admin_handoff.py` — not yet in scope)
  - `tool_choice_required.json` (will be consumed by TG 23.3 `streaming/adapter.py` — not yet in scope)
  - `session_rehydration.json` (same-process probe — disproved as not-load-bearing by P0-1)
  - `session_rehydration_fresh_process.json` (NEW — P0-1 OUTCOME locks Option A)
- **Strict fidelity check for Investigation surface:**
  - `streaming_shape.json` → `update.text` and `update.contents[]` field names present in fixture; adapter reads exactly those at lines 148 and 159 ✅
  - `session_rehydration_fresh_process.json` → `recalled_pineapple: false` proves fresh-process session rehydration fails; adapter responds by NOT using sessions (Option A) ✅
  - `auth_probe.json` → FoundryChatClient + sync credential validated; main.py constructs `FoundryChatClient(credential=ManagedIdentityCredential())` ✅
- **Soft probe-fidelity warning:** see W-02 below — the streaming_shape probe didn't introspect `Content.type` string vocabulary; the adapter relies on `content.type == "function_call"` / `"function_result"` for the decorative tool-call rendering path, which is non-load-bearing.

### F-19 Portal-managed agent shell pattern (D-02 violation)
- **Status:** ⚠️ partial — Investigation CLEARED; Admin + Classifier remain
- **Evidence cleared (Investigation):** `agents/investigation.py` is now a pure factory: `build_investigation_agent(chat_client, tools, middleware) -> Agent` reads `agents/instructions/investigation.md` via `load_instructions("investigation")` and constructs `Agent(client=chat_client, instructions=instructions, tools=list(tools), middleware=list(middleware))`. The portal-managed shell pattern (`foundry_client.agents_client.create_agent(model="gpt-4o", name="InvestigationAgent")` + "SET INSTRUCTIONS IN AI FOUNDRY PORTAL" log line) is fully removed.
- **Instructions canonicalized:** `agents/instructions/investigation.md` exists (290 lines), seeded from the Phase 17.1-canonicalized `docs/foundry/investigation-agent-instructions.md`.
- **Evidence remaining (out-of-scope):** `agents/admin.py` and `agents/classifier.py` still contain the `ensure_*_agent` portal-shell creation pattern. Deferred to TG 23.2 + TG 23.3.

## ✓ Pass — Framework Primitives Correctly Used (in-scope)

| # | Concern | Evidence |
|---|---|---|
| ✓1 | GA chat client construction | `main.py:498-501` `FoundryChatClient(project_endpoint=..., model=..., credential=ManagedIdentityCredential())` |
| ✓2 | GA Agent construction (singleton) | `agents/investigation.py:38-43` `Agent(client=chat_client, instructions=..., tools=[...], middleware=[...])` |
| ✓3 | Instructions live in repo (D-02) | `agents/instructions/investigation.md` (290 lines); `load_instructions("investigation")` reads it at startup |
| ✓4 | `agent.run(...)` invocation shape | `streaming/investigation_adapter.py:142` `stream = agent.run(msg_list, stream=True)` |
| ✓5 | Explicit message list per turn (P0-1 Option A) | `streaming/investigation_adapter.py:130-133` builds `list[Message]` from mobile-supplied history + new turn |
| ✓6 | No custom spans wrapping framework calls | `streaming/investigation_adapter.py` and `api/investigate.py` contain zero `tracer.start_as_current_span(...)`. Capture-shape attrs ride on auto-instrumented AppRequests span via `trace.get_current_span().set_attribute(...)` |
| ✓7 | GA AgentMiddleware operates on current span | `agents/agent_middleware/capture_trace.py:56` `trace.get_current_span().set_attribute("capture.trace_id", ...)` — never starts a new span |
| ✓8 | GA FunctionMiddleware lifts tool attrs onto framework span | `agents/agent_middleware/capture_trace.py:80, 106-115, 118` |
| ✓9 | Plain Python tool methods (no `@tool(approval_mode=...)`) | `tools/investigation.py` — 9 async methods with `Annotated[..., Field(description=...)]` shapes and docstrings; bound at construction via `Agent(tools=[instance.method, ...])` |
| ✓10 | `Annotated` parameter coverage preserved | Every `tools/investigation.py` tool method retains `Annotated[type, Field(description=...)]` per GA pattern |
| ✓11 | Tool-choice defaults to `auto` (correct for Investigation) | `streaming/investigation_adapter.py` deliberately omits `tool_choice` — Investigation can respond without tool calls (e.g., "thanks"). Per design D-07b voice-split discussion, only the classifier needs `'required'`. |
| ✓12 | App Insights export wiring unchanged | `main.py:14, 21` still uses `azure-monitor-opentelemetry`'s `configure_azure_monitor(...)`. No custom SpanExporter introduced. |
| ✓13 | Token metering via `enable_instrumentation()` | `main.py:31` unchanged. No manual `tokens_used` / `prompt_tokens` / `completion_tokens` increments in any in-scope file. |
| ✓14 | Direct-pin agent-framework-core (P1-4 retraction) | `pyproject.toml:16` `"agent-framework-core>=1.3.0,<2"` + `"agent-framework-foundry"` (NOT the `agent-framework` meta-package, which would transitively pull `agent-framework-azure-ai-search==0.0.0a1` whose 0-byte `__init__.py` would overwrite the real one) |

## ⚠️ Warnings

### W-01 (calibration anticipated): `CaptureTraceSpanProcessor` narrowing — LANDED
- **File:** `backend/src/second_brain/observability/span_processor.py:26-38`
- **Status at calibration:** ⚠️ anticipated future warning (auditor expected the narrowing to land in TG 23.1)
- **Status now:** narrowed-responsibility docstring landed; processor RETAINED per design D-07a as the bulk-tagger for non-framework spans. The class-level docstring at lines 26-38 explicitly documents:
  - Framework-emitted `invoke_agent` / `execute_tool` spans are now tagged at source by `CaptureTraceAgentMiddleware` / `CaptureTraceFunctionMiddleware`
  - This processor stays for Azure SDK auto-instrumented AppDependencies (Cosmos, HTTP), AppExceptions from libraries, custom non-framework spans
  - The on_start overlap with framework-tagged spans on the same attribute name is idempotent and benign
- **Justification (verbatim from docstring):** "Without this processor, query_capture_trace's union over AppDependencies loses correlation."
- **Verdict:** ⚠️ justified retention per D-07a, correctly documented. No action needed.

### W-02 (NEW): Tool-call content-type vocabulary not strictly probe-fidelity-checked
- **File:** `backend/src/second_brain/streaming/investigation_adapter.py:163, 179`
- **Concern:** Strict probe fidelity (Q2 in the auditor contract).
- **Detail:** the adapter relies on string-valued content type discriminators `content.type == "function_call"` and `content.type == "function_result"`. The `streaming_shape.json` probe captured `contents: [<agent_framework._types.Content object at ...>]` but its introspection stopped at the `Content` object boundary — the probe did not walk into the Content's `.type` attribute to capture the actual string vocabulary used by the GA SDK.
- **Risk classification:** LOW. This path is decorative (renders `tool_call` and `tool_error` SSE events for UX); the primary user-visible answer flows through `update.text` which the probe DID validate. If the type strings differ in production, the only consequence is missing pretty-printing of tool-call descriptions — the answer text itself is still streamed correctly.
- **Recommended response:** non-blocking. Either (a) accept the risk and verify empirically on first deployed Investigation query, or (b) extend `scripts/foundry_probe.py` probe 1 to walk `Content.__dict__` and add the captured vocabulary to the probe fixture. Either way, this is not a TG 23.1 blocker.

### W-03 (NEW): Stale Investigation references in warmup wiring
- **File:** `backend/src/second_brain/main.py:795-796, 830-844`
- **Concern:** Dead code referencing removed `app.state.investigation_client` and `app.state.investigation_agent_id`.
- **Detail:** the patch removes `app.state.investigation_client` and `app.state.investigation_agent_id` assignments, but the warmup wiring at lines 795-796 + 830-844 still references those names via `getattr(app.state, "investigation_client", None)`. The `getattr` defaults to `None`, so the `if ... is not None` guards prevent any attempt to actually warm a now-non-existent client. Behavior is benign downgrade: Investigation is excluded from the warmup loop. Classifier and Admin warmup continue to function (out-of-scope code paths unchanged).
- **Also:** `main.py:221` references `getattr(app.state, "investigation_agent_id", None)` to wire a spine `FoundryAgentAdapter`. Since the patch no longer sets `investigation_agent_id`, this returns `None`, and the `if agent_id:` guard on line 226 prevents adapter creation. Spine Investigation observability is downgraded (no adapter wiring), but spine still functions for Classifier + Admin.
- **Why this is not ❌:** the dead branches do not violate the framework-first principle — they reference removed state but never execute their RC-shaped code. The TG 23.3 cleanup (plan 24-19 warmup migration) will replace this code wholesale. Tracking as a warning so this regression isn't lost.
- **Recommended response:** add a small follow-up note in the deployment checklist; do not block this checkpoint.

## ❌ Out-of-Scope Failures (deferred to TG 23.2 or TG 23.3)

These findings remain in the codebase but apply to surfaces explicitly excluded from TG 23.1 per scope_constraint. They MUST be cleared by their target plans before final cutover:

| # | Surface | Target plan |
|---|---|---|
| F-01 (Admin + Classifier slices) | `main.py:520, 598, 639, 800, 818, 833` AzureAIAgentClient construction | 24-09 (Admin), 24-14 (Classifier) |
| F-02 | `warmup.py:8-19` AzureAIAgentClient import + typing | 24-19 |
| F-03 | `processing/admin_handoff.py:15, 141, 235, 242-244, 295-302, 418` | 24-11 |
| F-04 | `streaming/adapter.py:18, 155-156, 353-355, 557-559` classifier streaming RC client | 24-16 |
| F-06 | `eval/runner.py:21, 32, 133-145, 278-290` RC-shaped eval | 24-15 |
| F-07 | `eval/foundry.py:856-942` RC-shaped app-mediated dataset generator | 24-15 |
| F-08 (Admin + Classifier + recipe + transcription tools) | `tools/admin.py`, `tools/classification.py`, `tools/recipe.py`, `tools/transcription.py` — 9 `@tool(approval_mode="never_require")` decorators remain | 24-12 (Admin tools), 24-16 (classifier + transcription), 24-13 (recipe) |
| F-09 | `streaming/adapter.py:92-152, 324-334, 526-538, 676-686` `_safety_net_file_as_misunderstood` | 24-16 |
| F-10 | `streaming/adapter.py:182-188, 590-596` RC `{"mode":"required","required_function_name":...}` dict | 24-16 |
| F-11 | `main.py:577-581` voice tool on classifier agent | 24-16 (or split) |
| F-12 (Admin + Classifier) | `main.py:598, 639` agent_id-pinned AzureAIAgentClient | 24-09 (Admin), 24-14 (Classifier) |
| F-13 (classifier follow-up + capture path) | `streaming/adapter.py:596`, `api/capture.py:95-198` RC conversation_id round-trip | 24-16 + 24-17 |
| F-14 | `streaming/adapter.py:175, 372, 582` custom spans wrapping framework calls | 24-16 |
| F-16 | `processing/admin_handoff.py:177, 441` custom spans wrapping admin agent | 24-11 |
| F-17 (legacy AuditAgentMiddleware + ToolTimingMiddleware) | `agents/middleware.py:44, 72` RC-era span-doubling | 24-18 (delete after Admin + Classifier migrated) |
| F-19 (Admin + Classifier) | `agents/admin.py:55-65`, `agents/classifier.py:55-65` portal-shell ensure_*_agent | 24-09 (Admin), 24-14 (Classifier); instructions seed in 24-08, 24-13 |

Total out-of-scope ❌: 14 (counting F-01, F-08, F-12, F-13, F-17, F-19 as one each because their Investigation slice is cleared).

## New Findings (not in calibration)

None. No regression patterns introduced. The patch adds only GA-shaped code, plus three test files that act as regression guards:

- `test_foundry_credential_shape.py` — P1-5 guard: asserts FoundryChatClient credential is SYNC `azure.identity.ManagedIdentityCredential`, not the async `aio` variant.
- `test_legacy_middleware_imports_survive.py` — P1-3 guard: asserts the new GA middleware lives at `agents/agent_middleware/` (NOT `agents/middleware/` which would shadow the legacy module-style file).
- `test_no_rc_imports_after_cleanup.py` — P1-4 guard: AST-walks `backend/src/second_brain/` and fails if any future commit re-introduces `from agent_framework.azure import ...` or `AzureAIAgentClient`. Starts RED (10 source files still import RC) and turns GREEN incrementally as TG 23.2 + TG 23.3 strip RC imports.
- `test_session_rehydration_fresh_process.py` — P0-1 gating test: spawns the fresh-process probe end-to-end. Currently asserts `recalled_pineapple is True`, which is FALSE in the captured fixture — meaning this test is intentionally RED to validate the operator's locked Option A decision. The test will be inverted or retired once Option A is the established baseline (target: TG 23.3 cleanup commit).

## Probe Fixture Strict-Fidelity Check (Investigation surface only)

| Fixture | Consumed by | Status | Notes |
|---|---|---|---|
| `streaming_shape.json` | `streaming/investigation_adapter.py:148, 159` (update.text + update.contents[]) | ✓ exact | Top-level fields match fixture exactly. Inner `Content.type` vocabulary noted as W-02. |
| `tool_call_extraction.json` | (not consumed by 23.1 — admin uses it in 24-11) | — | Fixture present and ready for TG 23.2 consumption. |
| `tool_choice_required.json` | (not consumed by 23.1 — classifier uses it in 24-16) | — | Fixture present and ready for TG 23.3 consumption. |
| `session_rehydration.json` | (disproved as not-load-bearing) | — | Superseded by `session_rehydration_fresh_process.json` which captured P0-1 OUTCOME. |
| `session_rehydration_fresh_process.json` | `streaming/investigation_adapter.py:127-133` (Option A explicit-history pattern) | ✓ exact | `recalled_pineapple: false` in fixture; adapter responds by passing explicit message list per turn. The fixture's documentation of the failure mode is what gates the design choice. |
| `auth_probe.json` | `main.py:498-501` FoundryChatClient construction | ✓ exact | Credential class shape validated; sync ManagedIdentityCredential confirmed by `test_foundry_credential_shape.py`. |

## Cross-Task-Group Regression Check

Not applicable — TG 23.1 is the first task group. No earlier task group exists to regress against. The patch's commits 92926b4..2a5a8a8 are the entire 23.1 work. No prior-task-group cleanup is being reintroduced.

## Files Outside Framework-First Scope (not audited)

Per scope_constraint:
- `mobile/**`, `web/**`, `mcp/**`, `infra/**` (entire surfaces out of scope per design)
- `docs/**`, `.planning/**` (documentation, not framework-fidelity surface)
- `backend/tests/**` outside the four new tests (existing tests are not the audit subject for TG 23.1)
- `backend/src/second_brain/spine/**` (separate workload events system, out of scope per design)
- `backend/src/second_brain/api/**` outside `api/investigate.py` (capture/errands/voice/health/etc. routes unchanged in this patch)
- `backend/src/second_brain/cosmos/**`, `backend/src/second_brain/auth.py`, `backend/src/second_brain/models/**` (out of scope per design)

## Decision

**This gate PASSES.** All Investigation-surface in-scope ❌ findings from the calibration baseline are resolved. The three warnings are:
- W-01: a justified D-07a retention with documentation already landed
- W-02: a low-risk decorative-path probe-coverage gap with a clear empirical-verification fallback
- W-03: dead-code cleanup that plan 24-19 will sweep up

TG 23.2 (Admin) is unblocked.

The out-of-scope ❌ count of 14 is the expected residual state given the strict TG-by-TG migration cadence; those findings move to the TG 23.2 and TG 23.3 audit reports as their target surfaces are reached. The auditor's permanent regression guard `test_no_rc_imports_after_cleanup.py` will ensure they're all cleared before the push-guard sentinel is removed at the end of plan 24-22.

---

**FIDELITY AUDIT: 14 ✓, 3 ⚠️, 0 in-scope ❌ (14 out-of-scope ❌). Report at `.planning/phases/24-foundry-ga-migration/FRAMEWORK-FIDELITY-23.1.md`.**
