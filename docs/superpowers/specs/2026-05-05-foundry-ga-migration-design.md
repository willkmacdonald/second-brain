# Foundry GA Migration — Design

**Date:** 2026-05-05
**Status:** Approved — pending implementation via GSD
**Supersedes / extends:** [docs/crossroad.md](../../crossroad.md) (assessed 2026-05-01)
**Related:** [docs/foundry/investigation-agent-instructions.md](../../foundry/investigation-agent-instructions.md), `.planning/phases/21.1-migrate-eval-to-foundry-native-platform/`

> **Phase numbering reconciliation (round-3 PLAN-CHECK, 2026-05-08).** This doc was originally drafted with placeholder phase identifiers per the design's own caveat that "Phase numbering placeholder — final integers picked at `/gsd-add-phase` time." When GSD created the artifact-only prep phase, it was assigned **Phase 23** with directory `.planning/phases/23-foundry-ga-prep/` (not `.planning/phases/23.0/` as drafted here). The migration phase that follows is **Phase 24** (directory `.planning/phases/24-foundry-ga-migration/`). All artifact path references in this doc have been mass-renamed from `.planning/phases/23.0/` → `.planning/phases/23-foundry-ga-prep/`. The textual labels "Phase 23.0" (artifact-only) and "Phase 23" (migration with task groups 23.1/23.2/23.3) are retained throughout the prose because they map cleanly to the design's narrative; readers should treat them as synonyms for "Phase 23 (prep)" and "Phase 24 (migration)" respectively. Plans, PLAN-CHECK.md, STATE.md, and the calibration report (`.planning/phases/24-foundry-ga-migration/FRAMEWORK-FIDELITY-calibration.md`) all use the GSD-assigned integer naming; this doc's textual labels are the only remaining placeholder reference.

## Executive summary

Migrate the Second Brain backend off the pre-GA `agent-framework-azure-ai==1.0.0rc2` (RC) onto the GA `agent-framework` + `agent-framework-foundry` packages. All three production agents (Investigation, Admin, Classifier) stay app-hosted code agents; instructions move from the Foundry portal into versioned repo markdown.

**Cutover shape:** RC and GA SDK packages are mutually incompatible at the dependency level (verified — see D-05), and there is no staging environment. The deployed workflow is **`push origin main` → GitHub Actions (OIDC) → ACR → Container Apps**, so any push of `main` is a production deploy. The migration is therefore a **single big-bang production deploy**, organized as **two GSD phases**: Phase 23.0 (artifact-only setup; commits stay local) and Phase 23 (single-deploy migration with internal task groups 23.1 / 23.2 / 23.3 done as sequential commit clusters on the local `main` branch — never pushed until gates pass). The final `git push origin main` is the production cutover event. A local **Foundry probe harness** that exercises the GA SDK against the real Foundry endpoint substitutes for staged production.

The migration is governed by a **framework-first principle**: every cross-cutting concern (observability, capture-trace propagation, tool registration, required tool calls, conversation continuity, token metering, eval) defaults to the Microsoft Agent Framework or Foundry primitive. Custom Python is a fallback that requires explicit justification, never the path of least resistance. This principle is enforced by a dedicated `gsd-framework-fidelity-auditor` subagent run as a gate at end of each task group.

Estimated total effort: **~9-10 engineering days** across the two phases (~2 days Phase 23.0, ~7 days Phase 23 done as sequential commits on local `main` before the single push).

## Why now

1. **SDK risk.** Running RC packages in production is operationally fragile. Microsoft has GA'd Agent Framework 1.0; staying pre-GA means living with a deprecation clock and no LTS. The previously-documented attempt to upgrade to `agent-framework==1.2.0` was reverted (commit `bddd216`, 2026-04-24) because `AzureAIAgentClient` was removed and replaced by `DurableAIAgentClient` with an incompatible constructor — the wrong target. This design uses the correct target: `agent-framework-foundry` with `FoundryChatClient`.
2. **Learn the GA-era patterns.** This is a personal hobby project; mastering RC patterns that are about to disappear has no value. The migration is the moment to adopt the matured GA shape (explicit ownership of agent definitions, middleware-based cross-cutting concerns, framework-emitted OTel spans).
3. **Eval unblock.** `agent-framework-azure-ai==1.0.0rc2` hard-pins `azure-ai-projects==2.0.0b3`, which lacks the Foundry eval APIs (those need `>=2.1.0`). This pin is what stalled Phase 21.1. The GA SDK breaks the pin; the Foundry-native eval cutover is then unblocked as a follow-up phase (D-04).

## Decisions

### D-01 — Migration driver

**Primary:** Reduce SDK risk (RC → GA) for production hygiene.
**Secondary:** Learn the matured GA-era patterns. Hobby/learning project — no value mastering RC.

**Implication:** Prefer the GA-recommended pattern over a porting shortcut, even when the shortcut would ship faster. Approach 1 (lift-and-shift behind a facade) and Approach 3 (strangler with feature flags) were rejected because they hide GA from the codebase or keep RC alive; Approach 2 (idiomatic GA rewrite of the agent layer) was selected.

### D-02 — Where agent instructions live

**Repo markdown is the only source of truth.** One file per agent under `backend/src/second_brain/agents/instructions/`. Code reads them at startup and passes the content to `FoundryChatClient`/`Agent`. The Foundry portal becomes display/trace-only for these three agents — its agent-definition surface is unused.

**Implication:** Every instruction change is a code change. Git diffs, history, rollback via revert. No portal-textarea hot edits.

### D-03 — Where rules + destinations live

**Cosmos stays the runtime store.** The voice-editing flow (`manage_destination`, `manage_affinity_rule` tools) keeps working at ~1s latency. Repo gets a `rules.seed.yaml` (or similar) defining the canonical default state for fresh deploy / reset; on startup, if Cosmos is empty for a userId, seed from the file.

**Implication:** Repo describes how routing works by default; Cosmos holds the live, voice-edited reality. Rules are "agent memory of user preferences", not agent definition — appropriate that they live separately from instructions.

### D-04 — Eval scope

**SDK migration only in this milestone.** The custom eval framework currently in the repo (`eval/runner.py`, `dry_run_tools.py`, `metrics.py`, `foundry.py`, `api/eval.py`) is the gate during migration — the framework was reverted back into place at commit `bddd216` (2026-04-24) after the failed 21.1 SDK upgrade attempt, so no restoration is needed. The Phase 21.1 vision (Foundry-native eval cutover) becomes a separate follow-up phase once the GA SDK is live and stable.

**Implication:** Smaller blast radius for the migration. Phase 21.1-01 work (Foundry eval module, registered evaluators, rewired investigation tools) waits dormant as deferred local work / planning artifacts until the resumption phase.

### D-05 — Cutover strategy: single big-bang deploy with internal task ordering

**Original draft assumed staged-by-agent reverse-risk cutover. Two later findings made this structurally impossible:**

1. RC and GA SDK packages cannot coexist in a single Python environment. `agent-framework-azure-ai==1.0.0rc2` requires `azure-ai-projects==2.0.0b3`; `agent-framework-foundry` GA requires `azure-ai-projects>=2.1.0` and pins `agent-framework-core[all]==1.2.x`. The dependency sets are mutually incompatible. There is no "Investigation on GA, Classifier still on RC" runtime state.
2. There is no staging environment. Per project operating principles: testing happens against the deployed production endpoint after `git push origin main` triggers CI/CD. Trying to invent staging-shaped intermediate phases inside that workflow would be fighting the system.

**The honest cutover shape:**

- **One push, one CI run, one deploy.** All three agents migrate in a single `git push origin main`. Production goes from RC to GA in one event.
- **All Phase 23 work is on local `main`.** No feature branches. Commits accumulate on local `main` in task-group order: 23.1 (Investigation) → 23.2 (Admin) → 23.3 (Classifier). Each task group is a sequential commit cluster on local `main` followed by a framework-fidelity audit. Investigation goes first because it's the simplest surface for hardening shared patterns (instruction loading, capture-trace middleware, tool registration idiom). Admin and Classifier inherit those patterns. The reverse-risk *learning order* is preserved at the code level even though deploy is unified.
- **Local `main` is intentionally not buildable for Admin/Classifier until end of task group 23.3.** Because pushing `main` is the deploy trigger, this broken-mid-state must NOT be pushed — do NOT `git push origin main` until local `main` builds cleanly and all pre-deploy gates pass.
- **Pre-deploy verification is the substitute for staged production.** Golden-trace replay tests, eval gates, probe-fixture replays, and the framework-fidelity auditor all run on local `main` **before any `git push origin main`**. The bar is materially higher than under a staged-cutover model — see Phase 23 validation contract.
- **Phase 23.0 stays separate** as pure artifact work (fixtures, baselines, instructions export, candidate dependency files, span-name mapping, the probe harness script). Phase 23.0 commits also accumulate on local `main` and stay unpushed; they're consumed by Phase 23 directly from local `main`. (Pushing them mid-stream would be safe — they touch only `.planning/`, `tests/fixtures/`, and `backend/scripts/foundry_probe.py`, so the rebuilt image is identical — but it's not required.)

**Implication:** the migration milestone is structured as **Phase 23.0** (artifact-only setup) followed by **Phase 23** (single-deploy migration with internal task groups 23.1/23.2/23.3 organized as sequential commits on local `main` before the deploy push). Two separate phases at the GSD level — not four. Manual UAT day-after on real captures is the only post-deploy gate; everything else gates pre-deploy locally.

### D-06 — Validation contract

**Combined: golden-trace + eval-comparable.**

- **Golden-trace** — pre-migration baseline captures end-to-end traces (App Insights span tree + SSE event sequence + tool-call payloads) for each agent. Post-migration replays must match the contract with documented allowed deltas. Catches wire-shape drift.
- **Eval-comparable** — pre-migration baseline runs the existing custom eval suite. Post-migration scores must stay within ±2 percentage points absolute, with no class-specific drops greater than 5 pp. Catches model-behavior drift.

Both gates must pass before Phase 23 push to `origin/main`.

### D-07 — Framework-first principle

**Default: use what Microsoft Agent Framework or Foundry provides.** Custom Python is a fallback that requires explicit justification, never the path of least resistance. This principle overrides every later decision and applies to every cross-cutting concern in the migration.

**Explicit justification template** (required in the deployment-checklist artifact for Phase 23 and as inline code comment when custom Python is chosen over a framework primitive):

1. Which framework primitive was the candidate?
2. What capability does the custom code provide that the primitive does not?
3. Why can't this be solved by middleware / context provider / tool / configuration?
4. Is this a permanent answer or a temporary bridge with a deletion trigger?

Without this, the choice is rejected by the fidelity auditor.

### D-07a — Capture-trace propagation: layered tagging strategy

The current `CaptureTraceSpanProcessor` covers Sites 1 (AppRequests), 2 (Foundry agent spans), and 4 (investigation custom spans) by hooking *every* span — including auto-instrumented Azure SDK / Cosmos / HTTP dependency spans. `query_capture_trace` in [observability/kql_templates.py](../../../backend/src/second_brain/observability/kql_templates.py) unions over `AppRequests`, `AppDependencies`, `AppTraces`, `AppExceptions` filtered on `Properties.capture_trace_id`. **Removing the span processor outright would silently break Azure SDK / AppDependency correlation.**

The migrated architecture is layered:

1. **Source-level tagging on framework spans (NEW)** — `AgentMiddleware` + `FunctionMiddleware` read `capture_trace_id` from the existing `ContextVar` and call `span.set_attribute("capture.trace_id", ...)` directly on agent and tool spans. This is the GA-idiomatic location for framework-emitted spans and gives clearer attribution.
2. **HTTP request span tagging — retained as-is** — the existing direct `set_attribute` on the active AppRequests span at `api/capture.py:228` stays. Agent middleware doesn't reach the FastAPI request span.
3. **`CaptureTraceSpanProcessor` — RETAINED with narrowed responsibility** — kept for non-framework, non-route spans (Azure SDK auto-instrumented spans, Cosmos `AppDependencies`, raw `AppExceptions` from libraries, custom non-framework spans). Without this, `query_capture_trace`'s `AppDependencies` union loses correlation.

**Why this is framework-first:** the framework gives us source-level tagging for spans it emits; the span processor keeps catching spans the framework doesn't emit (third-party SDKs, custom non-framework instrumentation). The fidelity auditor's checklist treats this hybrid as **justified** — the span processor is doing work the framework isn't designed to do, not duplicating it.

**KQL impact:** queries continue to work because the attribute name (`capture.trace_id`) is preserved across all three sources.

### D-07b — Forced tool calls replace the Python safety net (with voice path split)

The classifier's Python safety net ("if the model didn't call `file_capture`, fire it ourselves as Misunderstood") is **deleted**. Replaced by `tool_choice='required'` — but only after restructuring the classifier so this is safe.

**The voice problem.** Today the classifier registers both `file_capture` and `transcribe_audio`. Voice flow: `transcribe_audio` runs first, its result text is fed back to the model, then `file_capture` runs. Naively setting `tool_choice='required'` doesn't enforce sequence — it forces the model to call *some* tool, which could be either tool out of order.

**The fix (Phase 23.3 architectural split).** Voice and text classification become two operations with different agent topology:

- **Voice path (new shape):** transcription becomes a non-agent operation (a direct call to the transcription model, OR a separate single-tool sub-agent registered with only `transcribe_audio` and `tool_choice='required'`). The transcription result becomes plain text. The classifier agent itself then only ever sees text input.
- **Classifier agent:** registers ONLY `file_capture`. With one tool registered, `tool_choice='required'` is unambiguous — the model must call `file_capture`. No provider-dict-pinning gymnastics needed.

Provider-dict pinning by name is no longer load-bearing under this design — it becomes a fallback if `tool_choice='required'` doesn't behave as documented.

A new SSE error sub-code `forced_tool_failure` is introduced for the case where forced tool choice still fails (model returns malformed call, tool raises). Mobile already handles `ERROR`; the sub-code is for monitoring/dashboards to distinguish from generic errors.

**Behavior change:** `MISUNDERSTOOD` now narrows to "model deliberately filed it that way." The previously-conflated "model called nothing, we caught it" case becomes `ERROR` with `forced_tool_failure`. Better separation of intent vs. failure; failures become loud where they were previously silent.

### D-08 — Execution path

This brainstorming session ends with this design doc. Implementation runs through GSD as **two phases**: Phase 23.0 (artifact-only setup; commits stay local) and Phase 23 (single-deploy migration with internal task groups 23.1 / 23.2 / 23.3 done as sequential commits on local `main`, never pushed until all pre-deploy gates pass). No feature branches — work directly on local `main`, hold all commits back from `origin/main` until ready, then push once. Auto mode means `/gsd-execute-phase` proceeds without manual prompts between plans within a phase. The Phase 23 deploy is gated by pre-deploy verification (unit tests, golden-trace fixture replay, eval gates, framework-fidelity audit on cumulative diff) — all run locally before `git push origin main`. Manual UAT day-after on real captures is the only post-deploy gate.

The framework-fidelity auditor is a real durable subagent type at `~/.claude/agents/gsd-framework-fidelity-auditor.md`, not a one-off described inline. It is brainstormed-built-calibrated as a separate piece of work *between* design doc approval and Phase 23.0 start, so it is real and tested before any phase relies on it.

## Architecture & boundary

### In scope (changes)

```
backend/src/second_brain/
├── agents/
│   ├── classifier.py             # Agent(client=FoundryChatClient(...))
│   ├── admin.py
│   ├── investigation.py
│   ├── instructions/             # NEW: per-agent .md files (D-02)
│   └── middleware/               # NEW: capture-trace middleware (D-07a)
├── streaming/
│   ├── adapter.py                # AgentRunResponseUpdate → SSE
│   └── investigation_adapter.py
├── tools/                        # drop approval_mode; keep @tool/Annotated
├── processing/admin_handoff.py   # agent.run() not get_response()
├── warmup.py                     # pings new clients
├── main.py                       # lifespan wires FoundryChatClient
└── observability/
    └── (CaptureTraceSpanProcessor RETAINED with narrowed scope per D-07a — still tags Azure SDK / AppDependencies / non-framework spans)

backend/pyproject.toml             # agent-framework + agent-framework-foundry
backend/uv.lock                    # regenerated
backend/Dockerfile                 # ENABLE_INSTRUMENTATION=true env
backend/tests/                     # updated mocks; new fixture-based contract tests
```

### Out of scope (does NOT change)

- `api/` routes & SSE wire contract
- `models/documents.py` (Cosmos schemas)
- `observability/queries.py` (KQL queries — but span Names referenced will be updated per Phase 0 mapping)
- `cosmos/` manager
- `auth/` middleware
- `mobile/`, `web/`, `mcp/`
- `infra/` (Container Apps deployment)
- `eval/` — current local files are the gate per D-04 (already on disk after revert `bddd216`); custom framework continues during migration

**New work that does NOT live under `backend/src/`:**

- `backend/scripts/foundry_probe.py` — standalone module (NOT imported by the running app) used by Phase 23.0 and pre-deploy gates of Phase 23 to exercise the GA SDK against the real Foundry endpoint. See "Foundry probe harness" section.
- `backend/tests/fixtures/foundry-probe/` — captured probe outputs that drive mock construction in unit tests and fixture replay in integration tests.

### The GA pipeline shape we are targeting

The GA `Agent` wraps two layered components:

- **Agent layer** (outer): `AgentMiddlewareLayer` + `AgentTelemetryLayer` + `RawAgent` + context providers
- **ChatClient layer** (inner, swappable): `FunctionInvocation` + `ChatMiddleware` + telemetry + `FoundryChatClient`

Every cross-cutting concern slots into one of those layers — no parallel custom plumbing.

## Per-agent migration anatomy

### Common shape (all three agents)

1. **Construction** — `Agent(client=FoundryChatClient(...), instructions=load_instructions(...), tools=[...], middleware=[...])` wired in `main.py` lifespan.
2. **Instructions** — markdown file under `backend/src/second_brain/agents/instructions/<agent>.md`, loaded at startup.
3. **Tools** — plain Python functions (sync or async) with `Annotated[type, "desc"]` + docstring. Optional `@tool` decorator for name/description override. `approval_mode` parameter is removed (RC concept).
4. **Middleware** — capture-trace middleware (D-07a) for agent + function spans. Token metering is handled by the framework's built-in observability (already activated by `enable_instrumentation()` in `main.py` import-time) — no per-agent decorator. Per-agent custom middleware added as needed.
5. **Streaming** — adapter consumes `AsyncIterable[AgentRunResponseUpdate]` from `agent.run_stream()`; emits the existing SSE wire contract unchanged.
6. **Threading** — Per-call rehydration only. The `Agent` is a singleton (one instance per agent type, constructed at lifespan start). For low-confidence follow-ups (only relevant to Classifier today), a session/thread identifier is stored on the Inbox doc and passed back into `agent.run_stream(messages, thread=AgentThread(...))` — or reconstituted via `agent.get_session(stored_id)` if the GA API exposes that — on the next turn. **NOT** a constructor-level `conversation_id` (would conflate captures into one global thread).
7. **Tests** — unit tests with mocked `FoundryChatClient`; contract test that replays a captured input against the live agent and asserts SSE event sequence + span tree match the golden fixture.

### Task group 23.1 — Investigation (first commit cluster on local `main`)

The simplest surface for hardening shared patterns (instruction loading, capture-trace middleware, tool registration idiom) before Admin and Classifier inherit them. Note: this is a **task group of commits on local `main`**, not an independent phase that ships separately. Local `main` is intentionally not buildable for Admin/Classifier at the end of this commit cluster — they're fixed in the next two task groups, and **a temporary push guard installed as Phase 23 task 0 prevents accidental push during this broken-mid-state window** (see Phase 23 GSD section for the guard mechanism).

**File-level changes:**

- `agents/investigation.py` — Agent construction
- `streaming/investigation_adapter.py` — consume `run_stream()`, map to SSE
- `tools/investigation.py` — 9 tools migrated (drop `approval_mode`, GA `@tool`, `Annotated[..., Field(description=...)]`): `trace_lifecycle`, `recent_errors`, `system_health`, `usage_patterns`, `query_feedback_signals`, `promote_to_golden_dataset`, `run_classifier_eval`, `run_admin_eval`, `get_eval_results`. The three eval tools talk to the local Foundry eval module (`eval/foundry.py`) — Phase 23.1 explicitly verifies they still function after the SDK swap because the eval surface they call may interact with the new client
- `agents/instructions/investigation.md` — promoted/moved from `docs/foundry/investigation-agent-instructions.md`

**Behavior contract preserved (verified post-deploy):** `/investigate` CLI slash command, mobile investigation chat, SSE event sequence, capture-trace ID propagation on spans when invoked from a capture context.

**Per-task-group gate (fidelity-only, not build/test):** framework-fidelity auditor runs on the partial diff at end of this task group. Zero ❌. **No build/test gate at task-group boundaries** — local `main` isn't expected to compile cleanly until end of task group 23.3. Build/test gates fire as part of Phase 23 pre-deploy verification.

**Risk contribution:** task group 23.1 is the simplest surface. If it produces patterns that don't transfer cleanly to Admin/Classifier, that's discovered before they're built — limiting rework.

### Task group 23.2 — Admin (commits build on 23.1's commits on local `main`)

Stress-tests the framework-first patterns under side-effect load (Cosmos writes, output-tool detection, retry). Like 23.1, this is a commit cluster on local `main` — not an independent phase. Local `main` is still not buildable for Classifier at the end of this commit cluster; the push guard installed at Phase 23 task 0 still blocks accidental push.

**Deltas vs. task group 23.1:**

- Non-streaming path (`agent.run()` not `run_stream()`) since admin runs in background processing
- Output-tool detection from `AgentRunResponse` — but the *exact* extraction path is unknown. The official `AgentRunResponse` doc shape is `messages` + `metadata` + content; tool calls live inside message content blocks, not as a guaranteed top-level `tool_calls` field. **The probe harness `tool_call_extraction` (run during Phase 23.0 — see "Foundry probe harness" section) captures the raw `AgentRunResponse` against the real Foundry endpoint and documents the exact extraction path.** The committed probe fixture under `tests/fixtures/foundry-probe/tool_call_extraction.json` is the source of truth that Admin's `processing/admin_handoff.py` rewrite codes against. No "deployed test admin run" required — the probe runs locally before any migration code commits.
- Retry semantics — Phase 23.2 planner verifies whether `tool_choice` provider-dict can pin "either `add_errand_items` OR `add_task_items` required". If yes, retry collapses to one bounded extra run; if no, justified Python loop with explicit-justification template
- Routing context (Cosmos rules + destinations via `get_routing_context`) — D-03 preserved

**Behavior contract preserved:** errands-screen-triggered processing (NOT auto-fired), affinity rule routing, recipe URL extraction, inbox status transitions.

**Validation gates:** unit tests, golden-trace contract tests (5 fixtures), custom admin routing accuracy eval within ±2pp, framework-fidelity audit zero ❌ with extra scrutiny on retry logic.

**Risk:** Medium. Wrong destination, dropped item, stuck-in-pending. Bounded — errands screen is the only trigger.

### Phase 23.3 — Classifier agent

The capture path. Highest risk; patterns are battle-tested by then.

**Deltas vs. Phases 23.1 and 23.2:**

- **Voice path split.** Voice and text classification become two operations. Transcription becomes either (a) a direct call to the transcription model outside any agent, or (b) a single-tool sub-agent that registers ONLY `transcribe_audio` and uses `tool_choice='required'`. Either way, the transcription result becomes plain text fed to the classifier agent.
- **Classifier agent registers ONLY `file_capture`.** With one tool registered, `tool_choice='required'` is unambiguous — the model must call `file_capture`. No provider-dict-pinning gymnastics needed.
- **Python safety net deleted** — no longer needed because the architectural split + single-tool registration makes `tool_choice='required'` correct.
- New SSE error sub-code `forced_tool_failure`
- **Follow-up continuity preserves the durable per-Inbox-item session.** Today `_stream_with_thread_id_persistence` in `api/capture.py` writes `foundryThreadId` (the Foundry conversation ID) onto the Inbox doc when a capture lands as MISUNDERSTOOD; subsequent follow-up turns re-use it. This durable persistence is **kept**. The only change is *what* gets stored and *how* it is rehydrated: the framework's session/thread identifier (`service_session_id` in GA terms, or whatever the GA `Agent.get_session()` API returns) replaces the RC-era opaque thread ID. The `Agent` object stays singleton; per-call rehydration via `agent.get_session(stored_id)` (or `thread=AgentThread(...)` per-call) is what threads continuity through. **NOT** constructor-level `conversation_id` on the singleton — that would conflate all users/captures into one thread.
- 6 SSE event types preserved (`CLASSIFIED`, `LOW_CONFIDENCE`, `MISUNDERSTOOD`, `UNRESOLVED`, `ERROR`, `COMPLETE`)
- `tools/classification.py` keeps both tools as functions; they're registered with *different agents* (transcribe with the transcription sub-agent if used, `file_capture` with the classifier agent), not bundled on the same agent.

**Validation gates:** unit tests, golden-trace contract tests (8 fixtures), custom classifier accuracy eval within ±2pp, framework-fidelity audit zero ❌ with extra scrutiny on `tool_choice='required'` and `AgentThread` usage, manual UAT day-after on 10+ representative captures, 7-day post-deploy `forced_tool_failure` rate < 1% of captures and < 5/day.

**Risk:** High but bounded. Capture path = silent capture loss possible. Mitigations: prior phases harden patterns, golden traces catch wire drift, eval gate catches model drift, `forced_tool_failure` sub-code makes previously-silent failures loud.

### Phase 23.0 — Artifact-only setup (zero deployed change)

Prerequisite for Phase 23. Deliberately scoped so **the only files that change are under `.planning/phases/23-foundry-ga-prep/`, `backend/tests/fixtures/`, and the single new file `backend/scripts/foundry_probe.py`** (the standalone probe harness, not imported by the running app). **No deploy happens** during Phase 23.0. All artifacts produced here feed Phase 23. See "Boundary check" below for the enumerated allow-list.

**Phase 23.0 deliverables (artifact-only, no runtime touch):**

- Capture golden-trace fixtures: 5 investigation queries, 5 admin captures, 8 classifier captures (text + voice + low-confidence + deliberate misunderstood) = 18 fixtures total. Captured against deployed RC system. Land at `backend/tests/fixtures/<agent>/`.
- **Inventory the current custom eval gate.** The eval module already exists locally (`eval/runner.py`, `dry_run_tools.py`, `metrics.py`, `foundry.py`, `api/eval.py`). Run end-to-end against deployed RC; save scores to `tests/fixtures/eval-baseline-pre-migration.json`. Document for Phase 23: the eval runner currently calls `client.get_response(...)` with RC `Message` + `ChatOptions` types (`eval/runner.py:133-143, 278-288`) — won't work against a GA `Agent`. Phase 23 internal task group 23.2 introduces an `EvalAgentInvoker` facade to bridge this.
- Export current Foundry portal instructions for Classifier and Admin into `.planning/phases/23-foundry-ga-prep/CANDIDATE-instructions/`. Investigation already has `docs/foundry/investigation-agent-instructions.md` (canonicalized in Phase 17.1) — diff against the portal text and reconcile any drift.
- **Local-only dependency-resolution spike.** In a throwaway local venv (NOT in repo `pyproject.toml`, NOT in any deployed image), produce a candidate `pyproject.toml` + `uv.lock` that pins `agent-framework` + `agent-framework-foundry` and removes `agent-framework-azure-ai`. Verify it resolves cleanly and the GA imports work in a Python REPL. Commit the candidate files as `.planning/phases/23-foundry-ga-prep/CANDIDATE-pyproject.toml` and `CANDIDATE-uv.lock` for Phase 23 to consume.
- **Write the Foundry probe harness** at `backend/scripts/foundry_probe.py` — see "Foundry probe harness" section below. **Run all 5 probes** (`streaming_shape`, `tool_call_extraction`, `tool_choice_required`, `session_rehydration`, `auth_probe`) against the real Foundry endpoint from the laptop using `az login` credentials. Commit captured outputs as fixtures under `backend/tests/fixtures/foundry-probe/<probe>.json` and a written summary at `.planning/phases/23-foundry-ga-prep/FOUNDRY-PROBE-FINDINGS.md`. These probe fixtures are the source of truth for SDK behavior — Phase 23 mocks and tests are constructed from them, NOT from documentation alone.
- Document the candidate config + env-var changes for Phase 23 to apply: `foundry_model` setting added to `config.py`; `FOUNDRY_MODEL=<deployment>` env var added to Container App. Existing `azure_ai_project_endpoint` setting is reused. The three `azure_ai_*_agent_id` settings become orphaned under D-02 — kept for backward compat at first; deletion bundled into Phase 23's cleanup commit.
- Verify `~/.claude/agents/gsd-framework-fidelity-auditor.md` subagent exists (created in the detour between design approval and Phase 23.0).
- Produce RC→GA span-name mapping at `.planning/phases/23-foundry-ga-prep/SPAN-NAME-MAPPING.md`.

**Boundary check (what Phase 23.0 IS allowed to add):**

- Files under `.planning/phases/23-foundry-ga-prep/` — fixtures, candidate dep files, findings docs, span-name mapping
- Files under `backend/tests/fixtures/` — golden-trace fixtures, probe-output fixtures, eval baseline JSON
- `backend/scripts/foundry_probe.py` — the probe harness, NOT imported by the running app, deletion has no runtime effect
- `~/.claude/agents/gsd-framework-fidelity-auditor.md` — verified to exist (created in the detour)

**Boundary check (what Phase 23.0 does NOT touch):**

- `backend/pyproject.toml`, `backend/uv.lock`, `backend/Dockerfile`
- Anything under `backend/src/second_brain/`
- Container App env vars
- Anything that would trigger CI/CD on push

**Push policy for Phase 23.0:** Phase 23.0 commits land on local `main` and stay unpushed until Phase 23 also completes locally. Phase 23 consumes the artifacts directly from local `main`. **Pushing 23.0 commits to `main` mid-stream would be safe** because they touch only `tests/fixtures/`, `backend/scripts/foundry_probe.py`, and `.planning/` — auto-deploy would rebuild an effectively-identical image (no `backend/src/` change, no dependency change). But pushing isn't required and isn't recommended; the cleanest workflow is to keep all migration commits on local `main` until the single Phase 23 cutover push.

Rollback for Phase 23.0: `rm -rf .planning/phases/23-foundry-ga-prep/` + delete the fixtures + delete `backend/scripts/foundry_probe.py` — purely a documentation rollback. If 23.0 commits were pushed to `main`, follow with `git revert` of those commits and a re-push.

## Foundry probe harness

The probe harness is the **substitute for staged production**. Because RC and GA dependency sets cannot coexist (D-05) and there is no staging environment, the high-uncertainty SDK questions (streaming shape, tool-call extraction, `tool_choice='required'`, session rehydration, RBAC/token acquisition) cannot be empirically verified inside a deployed test environment. The probe harness verifies them locally against the real Foundry endpoint instead.

### What it is

`backend/scripts/foundry_probe.py` is a standalone Python module that:

- Lives outside `backend/src/second_brain/` and is **NOT imported by the running app**. Removing it has no runtime effect.
- Uses the local dev environment's `agent-framework-foundry` install (the candidate dependency set produced by Phase 23.0's resolution spike).
- Authenticates via `AzureCliCredential` (laptop's `az login` session) — note this is NOT the same credential type the deployed Container App uses (`ManagedIdentityCredential`). The `auth_probe` specifically tests whether the credential acquisition surface shape is the same.
- Hits the **real production Foundry project endpoint** (the only one that exists). Probe runs have **no app-side effects** — no Cosmos writes, no SSE emission to mobile, no Inbox-doc mutations, no spine-event emission. They DO, however, create Foundry-side artifacts: agent runs, threads/sessions, OTel traces, and token-usage rows. Mitigations and optional cleanup below.
- Tags every probe-emitted span with `probe.run_id=<uuid>` and `probe.name=<probe_name>` so they're filterable in App Insights and don't pollute production-capture queries.
- Emits no `capture.trace_id` (probe runs are not captures), so KQL queries that union on `Properties.capture_trace_id` exclude them automatically.
- **Optional cleanup:** if the GA SDK exposes thread/session deletion (`Agent.delete_session(...)` or equivalent), each probe deletes its own thread/session at end-of-run. If the SDK doesn't expose deletion, probe-created threads accumulate as Foundry-side dust — filterable but not removable via SDK. Phase 23.0 planner verifies which is the case and documents in `FOUNDRY-PROBE-FINDINGS.md`.

### What it is NOT

- Not a deployment. Nothing reaches Container Apps or any production service the app uses at runtime.
- Not a "staging" environment. There's no staging-shaped concept of revisions, traffic splits, or non-prod resources.
- Not part of the running backend. It can be deleted any time without affecting the deployed app.

### The 5 probes

Each probe is a function in `foundry_probe.py` that can be run individually via `uv run python -m scripts.foundry_probe <probe_name>`. Each writes a JSON fixture to `backend/tests/fixtures/foundry-probe/<probe_name>.json` capturing the raw SDK output it observed.

| Probe | What it verifies | Output fixture |
|---|---|---|
| `streaming_shape` | The exact field/type/order of `AgentRunResponseUpdate` events emitted by `agent.run_stream(...)`. Includes a 1-tool stub agent producing 1 forced tool call so the fixture covers text deltas + tool-call updates + final-response shape. | `streaming_shape.json` — JSON-serialized list of every update yielded |
| `tool_call_extraction` | The exact path inside `AgentRunResponse` where tool calls appear after `agent.run(...)`. Resolves whether tool calls are top-level, in `messages[].content[]`, or elsewhere. | `tool_call_extraction.json` — full `AgentRunResponse` JSON dump for a 1-tool call |
| `tool_choice_required` | Whether `tool_choice='required'` enforces single-tool selection on the Foundry Responses endpoint. Single-tool agent so the result is unambiguous. | `tool_choice_required.json` — observed behavior + whether the model called the tool |
| `session_rehydration` | Round-trips an `AgentThread` (or `conversation_id`, or `service_session_id` — whichever the GA API exposes) across two `run_stream` calls. Captures the stored identifier shape and confirms continuity. | `session_rehydration.json` — both turn outputs + the identifier shape that was stored and replayed |
| `auth_probe` | Constructs `FoundryChatClient(credential=AzureCliCredential())` and runs a minimal agent invocation. Verifies (a) the GA `FoundryChatClient` accepts an Azure-credential object and successfully acquires a Foundry-scoped token, (b) the laptop's `az login` identity has the RBAC roles needed (Cognitive Services User on the Foundry resource, or whatever roles the GA path requires), (c) the request reaches Foundry and returns a successful response. **Does NOT simulate `ManagedIdentityCredential`** — only the deployed Container App can exercise that, since managed identity acquisition is environment-dependent. The probe confirms the credential class shape and RBAC assignment shape; the actual managed identity acquisition is verified post-deploy. | `auth_probe.json` — credential class used, token-acquisition outcome, RBAC role names confirmed, sample agent response |

### Findings document

`.planning/phases/23-foundry-ga-prep/FOUNDRY-PROBE-FINDINGS.md` is the human-readable summary of all 5 probe outputs. For each probe it answers:

1. What was the question?
2. What did the probe show?
3. What does Phase 23 migration code need to do differently from what docs alone would suggest?
4. Which open question (Section "Open questions resolved by each phase's gsd-planner") does this resolve?

This document is consumed by the gsd-planner that plans Phase 23 — it constrains the planner's choices to what the SDK actually does, not what docs claim.

### Pre-deploy consumption in Phase 23

- **Mocks** for `FoundryChatClient` in unit tests are constructed by reading the probe fixtures and shaping the mock to match. If a test asserts on `AgentRunResponseUpdate` field names, those names came from `streaming_shape.json` — not from imagination.
- **Replay tests** for the migration code re-run the probe scenarios against the local GA build. The committed probe fixtures are the expected output. If the migration code produces different SDK call sequences, the replay test catches it.
- **Eval suite** (admin + classifier accuracy) runs against the real Foundry endpoint via the same probe-style harness — the eval runner's GA-side `EvalAgentInvoker` implementation is conceptually a probe shape pinned to the eval input/output protocol.

### Trace pollution containment

Probe runs emit OTel spans against the same App Insights workspace as production captures. Mitigations:

- Every probe span has `probe.run_id=<uuid>` + `probe.name=<probe>` attributes.
- KQL queries used for production observability filter on `Properties.capture_trace_id`, which probe runs never set — so production queries naturally exclude probes.
- A new investigation tool helper `query_probe_runs` (built incidentally in Phase 23.0 if useful, optional) lets you find probe runs by `probe.run_id`.
- Probe runs are time-boxed — each probe takes seconds to minutes; you don't leave them running.
- **Cost:** negligible. ~5-20 probe API calls per probe; a few dozen total over Phase 23.0. Foundry token spend is rounding error against monthly capture volume.

## Observability, eval, and tools under the framework-first principle

### Observability

**Configure (Phase 0):**

- `ENABLE_INSTRUMENTATION=true`, `ENABLE_SENSITIVE_DATA=false` in Container App env.
- Existing `configure_azure_monitor()` + `azure-monitor-opentelemetry` exporter wiring stays — framework spans flow into the existing App Insights resource (`second-brain-insights`).

**Add (per agent phase):**

- `agents/middleware/capture_trace.py` — `AgentMiddleware` + `FunctionMiddleware` setting `capture.trace_id` span attribute on agent and tool spans.
- Token metering: nothing per-agent. The framework's existing `enable_instrumentation()` call (already invoked at import-time in `main.py:31`) emits token-usage metrics following the GenAI semantic conventions. Phase 23.0 verifies these metrics aren't double-counted alongside any existing custom counters.

**Delete:**

- Custom token counters in `streaming/adapter.py` (if any) — framework emits via `enable_instrumentation()`.
- Hand-rolled span emitters around agent calls (if any) — framework emits `invoke_agent` / `execute_tool` spans.

**Retained but narrowed (D-07a):**

- `observability/CaptureTraceSpanProcessor` — kept for non-framework spans (Azure SDK auto-instrumented `AppDependencies`, third-party library `AppExceptions`, custom non-framework spans). Without it, `query_capture_trace`'s union over `AppDependencies` loses correlation. The framework's middleware tags agent + tool spans at the source; the span processor still catches everything else.

**Survives unchanged:**

- `observability/queries.py` (KQL) — span attribute names preserved; span Names updated per Phase 0 mapping document.
- Investigation tools (`recent_errors`, `system_health`, etc.) — they query App Insights, not the framework.
- Spine workload events — separate system, out of scope.

### Eval

**Phase 23.0 inventory and preserve:** the eval module already exists locally (`eval/runner.py`, `dry_run_tools.py`, `metrics.py`, `foundry.py`, `api/eval.py`, and corresponding tests). No restoration needed. Phase 23.0 verifies the eval still runs end-to-end against deployed RC; commits baseline JSON.

**Per-phase gates:** Phase 23.2 re-runs admin eval; Phase 23.3 re-runs classifier eval. Pass: ±2pp absolute; no class-specific drop > 5pp.

**Eval invocation facade (REQUIRED scope for Phases 23.2 and 23.3).** The current eval runner calls `client.get_response(messages=..., options=ChatOptions(...))` with RC `Message` + `ChatOptions` types directly (`eval/runner.py:133-143, 278-288`). Once Admin or Classifier becomes a GA `Agent`, those direct calls fail — `Agent` exposes `run(...)` / `run_stream(...)` with `AgentRunResponse`, not `get_response()` with RC types. Each agent-migration phase that touches an agent with an eval gate must therefore:

1. Introduce a small `EvalAgentInvoker` interface (one method per relevant invocation pattern) inside `eval/`. The interface hides whether the underlying agent is RC or GA.
2. Update `eval/runner.py` to call `EvalAgentInvoker` instead of the agent client directly. RC-shaped `Message` / `ChatOptions` constructions stay in the RC implementation of the invoker; the GA implementation uses `agent.run(messages)` and adapts the response shape.
3. The fidelity auditor checks that the GA implementation uses the framework's API directly (no parallel custom Python re-implementing what `Agent.run()` does).

This facade is justified by D-07's explicit-justification template: it's not a portability layer hiding the framework — it's a minimal seam isolating RC vs. GA invocation differences during the migration window. It is deleted at end of Phase 23.3 once all agents are on GA and the RC implementation has no callers.

**Foundry-native eval follow-up phase (NOT in this scope but checklist enforced when run):**

- Custom evaluators registered with Foundry via `azure-ai-projects>=2.1.0`, NOT a standalone `metrics.py`
- Built-in evaluators (`IntentResolutionEvaluator`, `ToolCallAccuracyEvaluator`, `TaskAdherenceEvaluator`) NOT hand-rolled equivalents
- Run records in Foundry's eval results store, NOT custom Cosmos `EvalResults`
- Triggering via investigation tools calling Foundry SDK directly, NOT custom HTTP endpoint
- Foundry portal Tracing/Evaluation pages show real data

### Tools

**Pattern (RC → GA):**

```python
# Before (RC)
from agent_framework.azure import tool

class ClassifierTools:
    @tool(approval_mode="never_require")
    async def file_capture(self, bucket: str, ...) -> str:
        """File a capture into a bucket."""
        ...

# After (GA)
from typing import Annotated
from agent_framework import tool  # optional decorator
from pydantic import Field

@tool  # optional — only needed to override name/description
async def file_capture(
    bucket: Annotated[str, Field(description="Bucket name")],
    ...
) -> str:
    """File a capture into a bucket."""
    ...
```

**Mechanical changes per tool:** drop `approval_mode`; convert class methods to plain async functions OR keep as bound methods on a tools class (`tools=[instance.method, ...]` preserves Cosmos manager DI without globals); verify `Annotated[..., Field(description=...)]` coverage; verify docstring is the tool description.

**Per-file:** `tools/classification.py` (2 tools, Phase 23.3 — but registered with *separate* agents per D-07b voice path split), `tools/admin.py` (6 tools, Phase 23.2), `tools/investigation.py` (9 tools, Phase 23.1).

### `tool_choice='required'` for classifier (D-07b mechanics)

Per D-07b, the classifier agent registers ONLY `file_capture`. Voice transcription is handled by a separate code path (direct transcription model call, or a single-tool sub-agent). With one tool registered on the classifier, `tool_choice='required'` is unambiguous: the model must call `file_capture`.

Implementation form:

- **Preferred:** `tool_choice='required'` — clean and minimal.
- **Fallback:** `tool_choice={"type": "function", "function": {"name": "file_capture"}}` — provider-dict shape pinning by name. Used only if `'required'` doesn't behave as documented on the Foundry Responses endpoint.

**Endpoint behavior is verified by the probe harness `tool_choice_required` (run during Phase 23.0 against the real Foundry endpoint — see "Foundry probe harness" section).** The committed probe fixture under `tests/fixtures/foundry-probe/tool_choice_required.json` records whether `'required'` enforced single-tool selection. If the probe shows it works, the migration uses the preferred form. If not, the migration uses the fallback. No "deployed test call" required — the probe runs locally before any push to `main`. Either way, the Python safety net is deleted because the architectural split + single-tool registration makes the safety net redundant.

### Framework-fidelity auditor checklist

| Concern | Pass | Fail (= ❌) |
|---|---|---|
| Tracing | `configure_otel_providers`, `get_tracer()`, framework spans | Custom `tracer.start_as_current_span(...)` wrapping agent calls |
| Capture-trace propagation (framework spans) | `AgentMiddleware` / `FunctionMiddleware` setting span attribute on agent + tool spans | Custom span processor wrapping framework-emitted spans |
| Capture-trace propagation (non-framework spans) | `CaptureTraceSpanProcessor` retained for Azure SDK / third-party / custom spans | Removing the span processor outright (breaks `AppDependencies` correlation) |
| Tool registration | `@tool` / plain function + `Annotated[..., Field(...)]` | Manual JSON schema dicts, custom registries, custom validators |
| Required-tool semantics | `tool_choice='required'` or provider-dict | Python loop re-firing the tool after no-tool-call detected |
| Conversation continuity | Per-call rehydration via framework `Agent.get_session(stored_id)` / `thread=AgentThread(...)`; durable `foundryThreadId` (or its GA equivalent `service_session_id`) persisted on the Inbox doc | Constructor-level `conversation_id` on a singleton agent (conflates users/captures); custom thread-id round-trip that bypasses the framework session API |
| Token metering | Framework's `enable_instrumentation()` (auto-emits GenAI usage metrics) | Manual token counter in adapter or stream consumer |
| Eval (follow-up phase) | Foundry SDK `client.evals.runs.create()` | Custom `eval/runner.py` + `metrics.py` as long-term answer |
| App Insights export | `azure-monitor-opentelemetry` + framework's standard wiring | Custom span exporter or duplicate pipeline |

## Phase breakdown for GSD execution

**Two GSD phases**, not four. Phase 23.0 is artifact-only setup (no deployed change). Phase 23 is the single-deploy migration with internal task groups 23.1 / 23.2 / 23.3 done as **sequential commits on local `main`** (no feature branches), with all commits held back from `origin/main` until pre-deploy gates pass. Phase numbering placeholder — final integers picked at `/gsd-add-phase` time.

**Workflow note:** the deployed pipeline is `push origin main → GitHub Actions (OIDC) → ACR → Container Apps`. There is no PR / merge gate; pushing `main` is itself the deploy event. Phase 23 commits therefore must NOT be pushed until local `main` builds cleanly AND all pre-deploy gates pass — pushing an intentionally-broken intermediate state would deploy a broken backend. The commit cadence is: each task group's commits land on local `main`, the framework-fidelity auditor runs against the cumulative local-main diff, then the next task group's commits land. The final action of Phase 23 is a single `git push origin main` after task group 23.3 completes; this push IS the production cutover event.

### Phase 23.0 — Artifact-only setup

**Goal:** All artifacts ready. Zero deployed change. Zero CI run that affects production.

**Scope:** capture 18 golden-trace fixtures (`tests/fixtures/<agent>/`), run pre-migration eval baseline, export portal instructions to `.planning/phases/23-foundry-ga-prep/CANDIDATE-instructions/`, produce `.planning/phases/23-foundry-ga-prep/CANDIDATE-pyproject.toml` + `CANDIDATE-uv.lock` from a local-only dep-resolution spike, document config + env-var deltas for Phase 23 to apply, produce `.planning/phases/23-foundry-ga-prep/SPAN-NAME-MAPPING.md`. Verify the fidelity-auditor subagent (built in the detour) runs successfully on a no-op diff.

**Boundary:** files allowed to change in Phase 23.0 are limited to `.planning/phases/23-foundry-ga-prep/`, `backend/tests/fixtures/`, and the single new file `backend/scripts/foundry_probe.py` (the probe harness — standalone, not imported by the running app, deletion has no runtime effect). No other file under `backend/src/` or in repo root changes.

**Effort:** ~2 days. **Risk:** Very low.

### Phase 23 — Migration (single deploy, internal task groups 23.1 → 23.2 → 23.3)

**Goal:** All 3 agents working on GA SDK, deployed atomically. Production goes from RC to GA in one push.

**Task 0 — Install push guard (FIRST action of Phase 23, before any task-group work):**

Local `main` is intentionally broken from the moment task group 23.1 starts until task group 23.3 completes (~7 days). A discipline-only "don't push" rule is avoidable risk over a window that long. Phase 23 therefore opens by installing a mechanical guard. Pick one (gsd-planner decides at Phase 23 plan time):

- **Option A (preferred): local `pre-push` hook.** Add an executable `.git/hooks/pre-push` that exits non-zero if it detects the migration-in-progress sentinel file (e.g. `.planning/phases/23/PUSH-GUARD-ACTIVE`). Sentinel is created by Task 0 and deleted by Task N (the unguard step) only after pre-deploy gates pass. The hook prints a loud message: "Phase 23 migration in progress — local main is intentionally broken. Run /gsd-execute-phase 23 to completion before pushing."
- **Option B: rename remote.** `git remote rename origin origin-paused` for the duration. Push attempts fail with "remote not found." Restored by `git remote rename origin-paused origin` at the unguard step.

Option A is preferred because it's surgical (one file, can't accidentally push to other remotes if any get added later) and fails loudly with a useful message. Option B is the absolute hammer fallback if hook installation runs into machine-specific friction.

The guard installation + sentinel commit is the first task of the Phase 23 plan. The matching unguard step is the LAST task of task group 23.3, gated on all pre-deploy verification passing. Only after the unguard step completes can `git push origin main` execute the deploy.

**Internal structure (commit ordering on local `main`, all unpushed until end, push guard active throughout):**

**Task group 23.1 — Investigation (commits land first on local `main`, push guard active):**
- Apply candidate `pyproject.toml` + `uv.lock` from Phase 23.0 (removes `agent-framework-azure-ai`, adds `agent-framework` + `agent-framework-foundry`).
- Add `foundry_model` setting to `config.py`. Plan to add `FOUNDRY_MODEL=<deployment>` env var to Container App as part of the deploy step. Keep `azure_ai_*_agent_id` settings for now (cleaned up in 23.3 task group).
- Rewrite `agents/investigation.py` using `Agent(client=FoundryChatClient(...))`.
- Load instructions from `agents/instructions/investigation.md` (promoted from `docs/foundry/investigation-agent-instructions.md`).
- Migrate 9 investigation tools (6 telemetry + 3 eval — explicitly verify the eval tools still function after the SDK swap since their backing `eval/foundry.py` may interact with the new client).
- Rewrite `streaming/investigation_adapter.py`.
- Populate `agents/middleware/capture_trace.py` against real GA middleware contracts; wire on Investigation. Token metering inherited from existing `enable_instrumentation()` — no per-agent decorator.
- Update `main.py` lifespan + `warmup.py` for Investigation. Admin and Classifier still constructed with RC-style code at this point — but the RC SDK is no longer importable, so this commit cluster intentionally leaves the build broken for Admin/Classifier (the next task groups fix them; the Task 0 push guard prevents accidental push of this broken state).
- Update KQL queries targeting investigation spans.
- Run framework-fidelity audit on this commit cluster's diff. Zero ❌ before moving to next task group.

**Task group 23.2 — Admin (commits build on 23.1's commits on local `main`):**
- The `AgentRunResponse` extraction path is already known from Phase 23.0's `tool_call_extraction` probe — code against the committed fixture under `tests/fixtures/foundry-probe/tool_call_extraction.json`. No new spike or "deployed test" needed in this task group.
- Rewrite `agents/admin.py` using `Agent(client=FoundryChatClient(...))` and `agents/instructions/admin.md`.
- Migrate 6 admin tools.
- Rewrite `processing/admin_handoff.py` to use `agent.run()` (non-streaming) and the documented extraction path.
- Investigate framework-first retry: `tool_choice` provider-dict pinning either-or required-tool. If supported, retry collapses to one bounded run; if not, justified Python loop with explicit-justification entry.
- Introduce `EvalAgentInvoker` facade in `eval/`. RC implementation kept temporarily for any RC-side callers; GA implementation calls `agent.run(messages)` and adapts. Update `eval/runner.py` admin path to use the facade.
- Wire capture-trace middleware on Admin.
- Update `main.py` lifespan + `warmup.py` for Admin. Classifier still RC-style, still broken at this commit cluster.
- Update KQL queries targeting admin spans.
- Run framework-fidelity audit on cumulative 23.1+23.2 diff. Zero ❌ before moving to 23.3.

**Task group 23.3 — Classifier (commits build on 23.1+23.2's commits on local `main`):**
- Voice path split (per D-07b). Implement transcription as a non-agent direct Azure OpenAI call OR a single-tool transcription sub-agent. Classifier agent registers ONLY `file_capture`.
- Rewrite `agents/classifier.py` using `Agent(client=FoundryChatClient(...))` and `agents/instructions/classifier.md`.
- Apply `tool_choice='required'` (or fallback to provider-dict pinning, per Phase 23.0's `tool_choice_required` probe finding).
- Rewrite `streaming/adapter.py` to consume `AsyncIterable[AgentRunResponseUpdate]` (shape known from Phase 23.0's `streaming_shape` probe); preserve all 6 SSE event types.
- Delete the Python safety net.
- Add `forced_tool_failure` SSE sub-code path + KQL query for the new metric.
- Replace constructor-level conversation handling with per-call rehydration using whatever the `session_rehydration` probe revealed as the GA pattern: store the identifier returned by the SDK on the Inbox doc, replay it via the documented mechanism on follow-up turns.
- Wire capture-trace middleware on Classifier.
- Extend `EvalAgentInvoker` facade for classifier accuracy eval.
- **Final cleanup commit:** remove orphaned `azure_ai_*_agent_id` settings from `config.py`; remove RC-shaped helpers no longer in use; remove RC implementation of `EvalAgentInvoker` (no callers left).
- Update `main.py` lifespan + `warmup.py` for Classifier. **Local `main` now compiles cleanly.**
- Run framework-fidelity audit on cumulative 23.1+23.2+23.3 diff. Zero ❌ before pushing.

**Pre-deploy gates (all must pass locally before `git push` to `main`):**
- All unit tests green. Mocks for `FoundryChatClient` are constructed from probe-captured shapes (the probe fixtures captured in Phase 23.0 against the real Foundry endpoint), NOT from documentation alone.
- All 18 RC-side golden-trace fixture replay tests green against the locally dependency-resolved environment on local `main` using mocks shaped by Phase 23.0 probe output.
- All 5 Phase 23.0 probe fixtures (`streaming_shape`, `tool_call_extraction`, `tool_choice_required`, `session_rehydration`, `auth_probe`) replay green against the local GA build — i.e. the migration code reproduces the exact behavior the probe captured.
- Custom admin + classifier eval suites run via `EvalAgentInvoker` GA implementation against the local GA build (which talks to the real Foundry endpoint via the probe-style harness, not via staging), scores within ±2pp of pre-migration baseline; no class-specific drops > 5pp.
- Framework-fidelity auditor zero ❌ on cumulative diff.
- `auth_probe` succeeds locally: confirms the GA `FoundryChatClient` accepts an Azure-credential object, the `az login` identity has the necessary RBAC roles on the Foundry resource, and the agent invocation returns a successful response. Note: this validates the **credential class shape and RBAC assignment shape only** — it does NOT validate Container App managed identity acquisition (only the deployed environment can verify that, see post-deploy gate).

**Deploy sequence (deterministic, env vars before image):**

1. **Update Container App env vars FIRST** via `az containerapp update --set-env-vars FOUNDRY_MODEL=<deployment> ENABLE_INSTRUMENTATION=true ENABLE_SENSITIVE_DATA=false ...`. This is a pre-push action, run from the laptop. The env-var update creates a new revision with the existing (RC) image plus the new env vars; that revision still works because the GA env vars are simply ignored by the RC code.
2. **Verify the env-var-only revision is healthy** (existing `health` endpoint passes; system still on RC and functional with extra env vars present).
3. **`git push origin main`** → GitHub Actions (OIDC) → ACR builds GA image → Container Apps creates a new revision with the GA image. The new revision starts up with the env vars already in place — no startup race where the GA code looks for `FOUNDRY_MODEL` before it's set.
4. **Verify the GA revision is healthy** before promoting traffic to it (Container Apps default behavior promotes automatically; if Phase 23 task-group 23.3 planner picks a "manual promote" mode, that's an explicit pre-promote check).

**Why this order:** missing config can break startup. If env vars and image change in the same push and CI/CD's revision creation order put the image first, the GA container would start without `FOUNDRY_MODEL` and crash-loop. Decoupling makes the env-var change a safe no-op against RC, then the image change is a safe transition with config already in place.

**Post-deploy validation (manual UAT, day-after):**
- 10+ representative captures (text + voice + low-confidence + admin routing + investigation chat) verified working end-to-end.
- **Container App managed identity actually authenticates to Foundry** in the deployed environment. The pre-deploy `auth_probe` validates the credential class + RBAC shape from the laptop, but cannot exercise managed identity acquisition — that only happens in the actual Container App. Health endpoint should pass; first agent invocation should succeed without auth errors. If managed identity auth fails post-deploy, rollback (revision-promote-back) and investigate offline.
- 7-day post-deploy monitoring: `forced_tool_failure` rate < 1% of captures and < 5/day. Spike triggers incident review.

**Effort:** ~7 days locally on `main` (~2-3d Investigation work, ~2d Admin work, ~3d Classifier work — sequential because each task group's commits build on the previous).

**Risk:** High. Single big-bang production cutover. Capture path migrates with everything else. Mitigations are entirely pre-deploy: thorough fixture replay, eval gates, fidelity audit, all 5 probe replays. Once pushed, fix-forward only — there's no canary surface.

### Cross-phase dependencies

- Phase 23.0 unblocks Phase 23 (fixtures, baseline, probe outputs, candidate dep files, instructions, span mapping).
- No internal dependencies between task groups beyond the commit-ordering on local `main`.

## Validation contract details

### Golden-trace fixture format

Per fixture under `backend/tests/fixtures/<agent>/`:

- `<name>.input.json` — request payload
- `<name>.sse.jsonl` — captured SSE stream from deployed RC (one event per line)
- `<name>.spans.json` — App Insights span tree exported via KQL (Name, attributes, parent_id, duration; sensitive content stripped)
- `<name>.expected-deltas.md` — documented allowed differences between RC and GA traces

**Equivalence:**

- **SSE** — same event types, same order; field-level same where field is contract (bucket name, error sub-code), allowed-different where field is implementation detail (run_id, timestamps, server-generated IDs).
- **Span tree** — same attribute set on each tagged span (`capture.trace_id`, agent name, tool name on tool spans). Span Names allowed to differ per Phase 0 mapping. Parent-child structure equivalent.

### Eval gate operational specifics

Pre-migration baseline output JSON includes: classifier overall accuracy, per-bucket precision/recall, admin routing accuracy, per-destination precision/recall, sample size, model name, framework version.

Pass criteria (per phase): overall accuracy ≥ baseline − 2 percentage points; no class-specific precision drop > 5pp; no class-specific recall drop > 5pp.

Investigation has no eval suite — Phase 23.1 uses smoke replay (5 fixture queries each return non-empty text response with at least one tool call) instead.

### Framework-fidelity audit workflow

The auditor runs three times during Phase 23 — once at the end of each local task group — plus once cumulatively before pushing to `main`. Each task-group run is fidelity-only (local `main` isn't buildable until end of 23.3, so build/test gates don't fire mid-task-group).

1. `git diff <task-group-start-sha>..HEAD` captured to `.planning/phases/23/FIDELITY-23.{1,2,3}.patch`
2. Spawn `gsd-framework-fidelity-auditor` subagent with: task-group ID, scope from this design, the diff, and the auditor checklist
3. Auditor produces `.planning/phases/23/FRAMEWORK-FIDELITY-23.{1,2,3}.md` with sections: **Pass** / **Warnings (⚠️)** / **Failures (❌)**
4. For each ❌, choose: fix the code OR rebut with the explicit-justification template entry, then mark addressed in the report
5. Moving to the next task group requires zero ❌ on the current one
6. `git push origin main` (the deploy event) requires the cumulative audit (`FRAMEWORK-FIDELITY-cumulative.md`) at zero ❌
7. The reports are committed alongside the migration as learning artifacts

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| GA streaming event shape differs unexpectedly | High | Phase 23.0 probe `streaming_shape` captures the real shape locally before migration code commits; mocks in pre-deploy tests are shaped from probe output |
| `tool_choice='required'` not honored by Foundry endpoint | High | Phase 23.0 probe `tool_choice_required` verifies endpoint behavior before any classifier code is written; provider-dict fallback path documented if probe shows non-conformance; `forced_tool_failure` sub-code added regardless |
| Session rehydration doesn't preserve continuity | High | Phase 23.0 probe `session_rehydration` round-trips an `AgentThread` across two `run_stream` calls and captures the stored identifier shape; migration code uses whatever the probe reveals, not what docs assume |
| `AgentRunResponse` extraction path differs from docs | High | Phase 23.0 probe `tool_call_extraction` captures the raw `AgentRunResponse` JSON; admin migration codes against the captured shape, not docs |
| Foundry portal instructions drifted from canonicalized docs | High | Phase 23.0 export step explicitly diffs portal text vs. canonicalized doc; reconciled before Phase 23 starts |
| Classifier model behavior drifts under GA SDK | Medium | Eval gate ±2pp via `EvalAgentInvoker` GA implementation talking to real Foundry; 7-day forced-tool-failure rate monitoring; revision-promote-back rollback if eval regresses |
| Span name change breaks existing KQL / dashboards / alerts | Medium | Phase 23.0 produces RC→GA span-name mapping; queries updated in same task group as the agent emitting new spans; existing Azure Monitor alert rules reviewed in 23.0 prep |
| Identity/RBAC behavior on Container App differs | Medium | Pre-deploy `auth_probe` from laptop validates the credential acquisition path; post-deploy day-after UAT confirms managed identity resolution actually works in the Container App. The probe can't fully simulate the Container App's managed identity token shape — this remains a partial post-deploy unknown |
| Auditor false negative (missed a violation) | Low | Auditor checklist is a living document; calibrated against current RC backend (known-bad case) before Phase 23.0 |
| Eval baseline becomes stale because production model changes mid-migration | Low | Model pinned in `config.py` + Foundry portal; if it changes, re-baseline and re-run all gates |
| Mobile/web depends on RC-era SSE field GA adapter accidentally drops | Low | Golden-trace SSE fixtures captured at the wire boundary; replay tests assert field equivalence |

## Open questions resolved by each phase's gsd-planner

### Phase 23.0 planner

- Exact `FoundryChatClient` credential mode for Container App: `ManagedIdentityCredential` vs. `DefaultAzureCredential` (CLAUDE.md prefers managed identity in production)
- Whether `configure_otel_providers()` needs explicit call given existing `configure_azure_monitor()` wiring
- Whether existing `FOUNDRY_PROJECT_ENDPOINT` URL form is right for `FoundryChatClient`
- Confirm via the local-only dependency-resolution spike that `agent-framework` + `agent-framework-foundry` resolve cleanly with `agent-framework-azure-ai` removed (the candidate `pyproject.toml` + `uv.lock` are the deliverable for Phase 23.1)

### Phase 23.1 planner

- Bound methods on `InvestigationTools` as `tools=[instance.method, ...]` vs. plain functions with closure-captured deps
- Specific span-name mapping for investigation tool spans
- Whether the framework's auto-emitted token-usage metrics (from `enable_instrumentation()`) duplicate any existing custom counters the codebase has — and the order in which `enable_instrumentation()` and `configure_azure_monitor()` should be called for clean exporter wiring

### Phase 23.2 planner

- Whether `tool_choice` provider-dict can pin "either `add_errand_items` OR `add_task_items`" required (admin output-tool detection)
- Whether routing-context injection is best as a tool the agent calls (current pattern) or as `FunctionMiddleware` that pre-loads context
- The exact `AgentRunResponse` extraction path for tool calls — **answered by Phase 23.0 probe `tool_call_extraction` fixture; consume the committed fixture under `tests/fixtures/foundry-probe/tool_call_extraction.json` rather than running a new spike**
- The shape of `EvalAgentInvoker`'s GA implementation: how to translate eval cases (input text + expected label) into an `agent.run(...)` call and parse the result back to the eval runner's expected format

### Phase 23 task group 23.3 planner

- Whether `tool_choice='required'` is honored as documented on the Foundry Responses endpoint — **answered by Phase 23.0 probe `tool_choice_required` fixture, NOT by a deployed test**
- The exact GA session/thread API for per-call rehydration — **answered by Phase 23.0 probe `session_rehydration` fixture**
- The GA-equivalent identifier stored on the Inbox doc (replaces the current `foundryThreadId` field) — **answered by Phase 23.0 probe `session_rehydration` fixture**
- Where in the SSE adapter the `forced_tool_failure` sub-code is emitted (agent level / adapter / middleware)
- Voice path implementation: direct transcription model call vs. single-tool transcription sub-agent — picked based on simplicity and how cleanly transcription telemetry slots into the existing capture-trace plumbing

## Rollback

The cutover is a single big-bang deploy. Rollback is correspondingly binary — the entire migration goes back to RC, or stays on GA. No partial rollback is possible because RC and GA dependency sets are mutually incompatible.

- **Phase 23.0 rollback:** trivial (`rm -rf .planning/phases/23-foundry-ga-prep/` + delete fixtures + delete `backend/scripts/foundry_probe.py`). Pure documentation rollback. No deployed state to undo (Phase 23.0 doesn't push to `main`).
- **Phase 23 rollback:** two paths in priority order:

  1. **Fast path — Container Apps revision-promote-back.** Promote the previous revision back to 100% traffic via `az containerapp revision set-mode` / `az containerapp ingress traffic`. No CI/CD rebuild needed. This is the recommended first action if regression is detected within minutes of deploy. **A deployment checklist must include the previous revision name and the exact `az containerapp` command to re-promote it**, captured at push time, so rollback is a known-good copy-paste even at 2am.
  2. **Durable path — `git revert` of the deploy commit on `main` + push.** Re-triggers CI/CD, which rebuilds the previous-revision image from `pyproject.toml` + `uv.lock` as restored by the revert. Container Apps deploys the rebuilt image. All 3 agents return to RC simultaneously. Use this after the fast-path revision-promote to clean up `main`.

**Rollback bar:** invoke rollback if any of:
- Manual UAT day-after reveals broken capture, broken admin routing, or broken investigation chat that cannot be fixed forward in <30 minutes.
- Any of the 6 SSE event types is missing or malformed for any capture path (catches fixture-replay false negatives).
- `forced_tool_failure` rate spikes > 5/day in the first 24h post-deploy.
- Eval scores regress outside the ±2pp pre-deploy gate (would mean the pre-deploy gate gave a false pass).
- Managed identity auth fails post-deploy (the only auth-related unknown that can't be tested pre-deploy).
- App Insights ingestion stops or trace correlation visibly breaks.

## What this design does NOT specify

Intentionally left to gsd-planner per phase to avoid over-prescribing:

- Exact task breakdown within Phase 23.0 (gsd-planner produces 5-10 plans based on the phase scope above)
- Exact task breakdown within Phase 23 (gsd-planner produces task groups 23.1 / 23.2 / 23.3 as commit-cluster plans on local `main`; ~5-10 commits per task group)
- Specific test file names and unit test breakdown
- Exact line-level code shape (Section 3 has examples but not file-by-file)
- Commit message format / atomic commit boundaries within a task group (GSD convention applies)
- UAT script wording (gsd-verify-work generates from phase scope)
- Exact contents of the deployment-checklist file (e.g. format of the previous-revision-name capture, the rollback `az containerapp` command template) — produced by gsd-planner during Phase 23 task-group 23.3 planning

## Next steps

1. **You review this design doc.**
2. **Detour:** brainstorm + build + calibrate the `gsd-framework-fidelity-auditor` subagent. Calibration target: run on the current RC backend (known-bad case) and verify it produces a long ❌ list dominated by `agent_framework.azure` imports, custom span processor, Python safety net findings.
3. **Then GSD:**
   - `/gsd-add-phase` × 2 (Phase 23.0 + Phase 23)
   - Phase 23.0: `/gsd-plan-phase` → `/gsd-execute-phase` (writes probe harness + runs all 5 probes + commits fixtures + produces span-name mapping + dependency-resolution spike + portal instructions export) → `/gsd-verify-work`. Commits land on local `main` and stay unpushed — Phase 23.0 does not deploy.
   - Phase 23: `/gsd-plan-phase` → `/gsd-execute-phase` runs task groups 23.1 → 23.2 → 23.3 sequentially as commit clusters on local `main` (no feature branches). Pre-deploy gates run locally. The deploy sequence is: (1) `az containerapp update --set-env-vars` for `FOUNDRY_MODEL` etc. against the existing RC revision, verify healthy; (2) `git push origin main` to trigger CI/CD → ACR → Container Apps; (3) verify GA revision health post-deploy.
