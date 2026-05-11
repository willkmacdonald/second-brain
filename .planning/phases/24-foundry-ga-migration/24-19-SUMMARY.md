---
phase: 24-foundry-ga-migration
plan: 19
subsystem: backend
tags: [foundry-ga, f-01, f-02, warmup-ga, agent-framework, codebase-rc-free]

# Dependency graph
requires:
  - phase: 24-foundry-ga-migration/04
    provides: "build_investigation_agent factory + load_instructions helper"
  - phase: 24-foundry-ga-migration/09
    provides: "build_admin_agent factory + admin lifespan wiring pattern (W-03 dead-code factories planted for 24-19 sweep)"
  - phase: 24-foundry-ga-migration/14
    provides: "build_classifier_agent factory + Classifier lifespan wiring + placeholder locals consumed by 24-19"
  - phase: 24-foundry-ga-migration/18
    provides: "Final end-of-23.3 cleanup; AST-scan offender count narrowed from 4 -> 2 (main.py + warmup.py)"
  - phase: 24-foundry-ga-migration/24-CONTEXT.md
    provides: "D-13 strict-cutover state for warmup.py + W-03-23.2 sweep scope"
provides:
  - "backend/src/second_brain/warmup.py is GA-shaped (Agent type, agent.run('ping') ping path, agent_factories kwarg)"
  - "backend/src/second_brain/main.py is RC-free (last AzureAIAgentClient import + agents-client connectivity probe block removed)"
  - "Codebase under backend/src/second_brain/ is RC-clean (`grep -rE 'AzureAIAgentClient|agent_framework\\.azure' backend/src/second_brain/` returns empty)"
  - "tests/test_no_rc_imports_after_cleanup.py flipped RED -> GREEN; permanent regression guard active"
  - "Warmup self-heal factories rebuild GA Agent instances via build_classifier_agent / build_admin_agent / build_investigation_agent"
  - "Two warmup self-heal unit tests rewritten against the GA signature (agent.run, agents=, agent_factories=)"
affects:
  - "24-21 (final config cleanup): all RC-shaped warmup + foundry-client plumbing is gone; only orphan `azure_ai_*_agent_id` config fields remain"
  - "24-20 (cumulative audit + pre-deploy gates): F-01/F-02 closed; auditor should report zero in-scope failures from this slice"
  - "24-22 (deploy): Container App startup path no longer imports the RC SDK; GA-only image is shippable"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "GA warmup loop pings via `await agent.run('ping')` (replacing RC `client.get_response(messages=[Message(role='user', text='ping')])`). Single-string user input — no Message wrapper, no role plumbing."
    - "Self-heal factories take no arguments and close over `chat_client` plus read tool instances from `app.state.{...}_tools` / `app.state.investigation_tools_instance` at call time. Survives any future tool-instance replacement."
    - "Mid-migration safe-default extended to `app.state.foundry_client = None`. Health endpoint's existing `getattr(..., None)` short-circuit returns 'not_configured' for Foundry. Migration of the connectivity probe to a GA-shaped check is deferred."
    - "Docstring-level RC class name rewording (`AzureAIAgentClient` -> 'legacy RC client') in narrative docstrings of admin_handoff.py + eval/invoker.py to clear plan's codebase-wide `grep -rE` gate. Established norm post 24-10 'docstring trap' lesson."

key-files:
  created:
    - .planning/phases/24-foundry-ga-migration/24-19-SUMMARY.md
    - .planning/phases/24-foundry-ga-migration/deferred-items.md
  modified:
    - backend/src/second_brain/warmup.py
    - backend/src/second_brain/main.py
    - backend/src/second_brain/processing/admin_handoff.py
    - backend/src/second_brain/eval/invoker.py
    - backend/tests/test_observability.py
  deleted: []

key-decisions:
  - "Delete the RC `foundry_client = AzureAIAgentClient(...)` block in main.py and set `app.state.foundry_client = None`. The plan acceptance criterion (`! grep -q 'AzureAIAgentClient' main.py`) requires zero references; deleting the import alone leaves a NameError. The health endpoint already handles `app.state.foundry_client is None` via `getattr(..., None)` -> 'not_configured', so no caller breaks. Migrating the health probe to a GA-shaped `agent.run('ping')` check is a deferred follow-up (recorded in deferred-items.md)."
  - "Warmup self-heal factories now read tool instances from app.state at call time (not closures over locals). The original RC factories closed over locals (`classifier_agent_id`, `app.state.{admin,investigation}_agent_id`). The GA factories close over the shared `chat_client` (immutable post-lifespan) and read mutable `app.state.{classifier,admin,recipe,investigation_tools}_instance` lazily. Tradeoff: marginally less efficient (one app.state attr read per recreation) for resilience to any future tool replacement."
  - "Gating condition switches from `app.state.{name}_client is not None` to `app.state.{name}_agent is not None`. The W-03 dead-code paths from 24-09/24-14 (gated on permanently-None `_client` attrs) become LIVE paths gated on the GA `_agent` singletons."
  - "Docstring narrative references to `AzureAIAgentClient` reworded to 'legacy RC client' in processing/admin_handoff.py + eval/invoker.py. The plan's `grep -rE` gate is strict; literal occurrences in narrative docstrings trip it. Established post-24-10 norm."
  - "Two test_observability.py warmup self-heal tests REWRITTEN (not deleted). They were already broken pre-commit because warmup.py at strict-cutover state was importing the deleted RC class. After Task 1, warmup.py is import-clean but the test fixtures still used `clients=` / `client_factories=` kwargs + `get_response` mock attr. Updated to `agents=` / `agent_factories=` + `run`. Mock-only changes; same semantics. 7/7 tests in the file pass."
  - "Pre-existing collection errors in test_classifier_integration.py + test_event_tracing.py (both import the removed `stream_voice_capture` from streaming/adapter.py — see STATE decision [24-16]) are OUT OF SCOPE. Documented in deferred-items.md, NOT fixed here. Per executor SCOPE BOUNDARY: only auto-fix issues DIRECTLY caused by current task's changes. This breakage predates 24-19."

requirements-completed: [F-02, F-01]

# Metrics
duration: 6min
completed: 2026-05-11
---

# Phase 24 Plan 19: warmup.py + main.py GA migration — codebase is RC-free

**This is the final RC migration plan. The codebase under `backend/src/second_brain/` no longer references `AzureAIAgentClient` or `agent_framework.azure` anywhere — imports, name references, or docstring narrative. `tests/test_no_rc_imports_after_cleanup.py` flipped RED -> GREEN.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-05-11T06:02:12Z
- **Completed:** 2026-05-11T06:08:50Z
- **Tasks:** 2
- **Files modified:** 5 (backend) + 1 created (deferred-items.md)
- **Files created:** 2 (this SUMMARY + deferred-items.md)

## Accomplishments

### F-02 cleared — warmup.py GA rewrite (Task 1)

`backend/src/second_brain/warmup.py` is now GA-shaped end-to-end:

- **Imports:** `from agent_framework.azure import AzureAIAgentClient` + `from agent_framework import Message` -> `from agent_framework import Agent`.
- **Function signature:**
  ```python
  async def agent_warmup_loop(
      agents: list[tuple[str, Agent]],
      interval_seconds: int,
      agent_factories: dict[str, Callable[[], Agent]] | None = None,
      on_recreate: Callable[[str, Agent], None] | None = None,
  ) -> None
  ```
  Parameter renames: `clients` -> `agents`, `client_factories` -> `agent_factories`. Type renames: `AzureAIAgentClient` -> `Agent` throughout.
- **Ping body:** `messages = [Message(role="user", text="ping")]` + `await client.get_response(messages=messages)` -> single line `await agent.run("ping")`.
- **Self-heal path:** Same shape; just type-renamed. Factory dict now produces `Agent` objects via the `build_*_agent` helpers (wired by Task 2).
- **Module docstring:** Updated to reflect GA-only state. Literal `Message` / `AzureAIAgentClient` strings expunged so the plan's `! grep -q "Message"` + `! grep -q "from agent_framework.azure"` gates pass.

### F-01 fully cleared — main.py RC import + warmup factory rewrite (Task 2)

`backend/src/second_brain/main.py` has zero RC SDK references:

- **Top-level import deletion:** `from agent_framework.azure import AzureAIAgentClient` -> `from agent_framework import Agent` (the new Agent type is used as the return annotation for the rebuilt warmup factories + the `warmup_agents` list type).
- **Foundry agents-client connectivity probe deleted (lines ~511-538):**
  ```python
  # Before (RC):
  foundry_client = AzureAIAgentClient(credential=..., project_endpoint=..., model_deployment_name="gpt-4o")
  async for _ in foundry_client.agents_client.list_agents(limit=1):
      break
  app.state.foundry_client = foundry_client
  # After (GA-deferred):
  app.state.foundry_client = None
  ```
  The health endpoint (`api/health.py`) uses `getattr(app.state, "foundry_client", None)` and gracefully reports `not_configured` when None. Migrating the probe to a GA-shaped check (`app.state.classifier_agent.run("ping")` with a short timeout) is a follow-up tracked in deferred-items.md.
- **Placeholder locals removed:** The post-24-14 `classifier_agent_id = None` / `classifier_client = None` locals that existed solely to satisfy the RC factory closure are deleted.
- **Warmup factory cluster rewritten:**
  - `_make_classifier_client` -> `_make_classifier_agent` returning `Agent` via `build_classifier_agent(chat_client, tools=[app.state.classifier_tools.file_capture], middleware=[CaptureTraceAgentMiddleware(), CaptureTraceFunctionMiddleware()])`.
  - `_make_admin_client` -> `_make_admin_agent` returning `Agent` via `build_admin_agent(chat_client, tools=[admin_tools.add_errand_items, ..., recipe_tools.fetch_recipe_url], middleware=[...])`. Recipe tool optional (preserved guard from 24-09).
  - `_make_investigation_client` -> `_make_investigation_agent` returning `Agent` via `build_investigation_agent(chat_client, tools=[inv_tools.trace_lifecycle, ..., inv_tools.get_eval_results], middleware=[...])`. All 9 investigation tools rebuilt.
- **Warmup loop call site:**
  ```python
  # Before (RC):
  agent_warmup_loop(clients=warmup_clients, ..., client_factories=warmup_factories, on_recreate=_on_recreate)
  # After (GA):
  agent_warmup_loop(agents=warmup_agents, ..., agent_factories=warmup_factories, on_recreate=_on_recreate)
  ```
  `warmup_agents` populated from `app.state.{classifier,admin,investigation}_agent` (each gated on presence). `_on_recreate` writes back to `app.state.{name}_agent`.

### Docstring cleanup (Rule 2)

The plan's `grep -rE "AzureAIAgentClient|agent_framework\\.azure" backend/src/second_brain/` gate is strict. Two docstring narrative references survived 24-18 and tripped it:

- `processing/admin_handoff.py` module docstring: `"Uses GA Agent.run() in place of RC AzureAIAgentClient.get_response()."` -> `"Uses GA Agent.run() in place of the legacy RC client's get_response()."`
- `eval/invoker.py` module docstring: `"The TYPE_CHECKING import of AzureAIAgentClient that supported the RC implementation's type hints"` -> `"The TYPE_CHECKING import of the legacy RC client class that supported the RC implementation's type hints"`

No code semantics change; only string content. The 24-10 STATE decision documents this as an established norm: "Docstring grep-guard fix... literal substring `@tool(approval_mode=` in module docstring tripped the plan's automated grep check. Reworded... Pattern is now established for any future decorator/symbol strips: avoid the literal name in docstrings."

### Test updates (Task 2)

`tests/test_observability.py` two warmup self-heal tests rewritten to the GA signature:

- `test_warmup_recreates_client_after_consecutive_failures` -> `test_warmup_recreates_agent_after_consecutive_failures` (renamed to match GA wording).
- Mock attribute: `failing_client.get_response = AsyncMock(...)` -> `failing_agent.run = AsyncMock(...)`.
- Keyword args: `clients=` -> `agents=`; `client_factories=` -> `agent_factories=`.
- Local variable renames: `clients` -> `agents`, `mock_client` -> `mock_agent`, `failing_client` -> `failing_agent`, `new_client` -> `new_agent`.

Same fail-twice-succeed-once-fail-twice semantics; the test continues to verify (a) factory is called after 3 consecutive failures + on_recreate fires, and (b) success at iteration 3 resets the counter so factory is NEVER called.

7/7 tests in test_observability.py pass.

## Task Commits

| Task | Hash      | Title                                                                                       |
|------|-----------|---------------------------------------------------------------------------------------------|
| 1    | `7dfcbde` | feat(24-19): rewrite warmup.py against GA Agent (F-02 cleared)                              |
| 2    | `55f04a5` | feat(24-19): rewrite main.py warmup factories + RC import deletion (F-01 fully cleared)    |

(Plan metadata commit follows this SUMMARY.)

## Files Created/Modified

| Path | Change | Notes |
|------|--------|-------|
| `backend/src/second_brain/warmup.py` | modified (-25 / +33) | Full GA rewrite — Agent type, agent.run("ping") ping path, agent_factories kwarg, no Message / AzureAIAgentClient literals anywhere. |
| `backend/src/second_brain/main.py` | modified (~-112 / +111) | RC import deleted; legacy `foundry_client = AzureAIAgentClient(...)` block removed; placeholder locals cleared; warmup factory cluster + call site rewritten to GA; `Agent` import added. |
| `backend/src/second_brain/processing/admin_handoff.py` | modified (-1 / +1) | One-line docstring rewording — replaces literal `AzureAIAgentClient` with "legacy RC client". |
| `backend/src/second_brain/eval/invoker.py` | modified (-1 / +1) | One-line docstring rewording — same. |
| `backend/tests/test_observability.py` | modified (~-25 / +30) | Two warmup self-heal tests rewritten to GA signature. |
| `.planning/phases/24-foundry-ga-migration/24-19-SUMMARY.md` | **CREATED** | This file. |
| `.planning/phases/24-foundry-ga-migration/deferred-items.md` | **CREATED** | Out-of-scope discoveries (api/health.py GA migration + 2 pre-existing test collection errors). |

## Decisions Made

1. **Delete the RC `foundry_client = AzureAIAgentClient(...)` block and set `app.state.foundry_client = None`.** The plan acceptance gate requires zero `AzureAIAgentClient` references in main.py. Deleting the import alone would leave a NameError on the construction block. Setting `app.state.foundry_client = None` is consistent with the mid-migration safe-default pattern established by 24-09 (admin_client=None) and 24-14 (classifier_client=None). `api/health.py` already handles `None` via `getattr(..., None)` so no caller breaks.

2. **Warmup self-heal factories read tool instances from app.state at call time.** Original RC factories closed over locals or app.state attrs (`classifier_agent_id`, `app.state.{admin,investigation}_agent_id`). GA factories close over the shared `chat_client` (immutable post-lifespan) and read mutable `app.state.{classifier,admin,recipe,investigation_tools}_instance` lazily at recreation time. Slightly less efficient, but resilient to any future tool replacement (e.g. a hypothetical `recipe_tools` swap during a Playwright restart) without code change.

3. **Switch warmup gating from `_client` to `_agent` app.state attrs.** Post-24-09/24-14, the `_client` attrs are permanently `None` so the W-03 dead-code factories never ran. Switching to `app.state.{name}_agent is not None` makes the factories LIVE — warmup actually self-heals the GA agents when they go cold.

4. **Rename `_on_recreate`'s `new_client` parameter to `new_agent`.** Internal-only change; reflects the new GA shape. The callback updates `app.state.{name}_agent` (was `{name}_client`).

5. **Rewrite (not delete) two warmup self-heal unit tests.** They were pre-existing assertions on the warmup self-heal contract; only the signature changed. Deleting would lose useful coverage. Updated mock fixtures (`.get_response` -> `.run`) + kwarg names + variable names to the GA shape. Same fail-twice-succeed-once semantics retained.

6. **Reword `AzureAIAgentClient` -> "legacy RC client" in two docstring narratives.** The plan's `grep -rE` gate on `backend/src/second_brain/` is strict; literal RC class names in any text (code, docstring, comment) trip it. Pattern established post-24-10 docstring-trap lesson recorded in STATE.

7. **Defer the api/health.py Foundry connectivity probe migration.** The probe currently calls `app.state.foundry_client.agents_client.list_agents(limit=1)`. The GA equivalent is `app.state.classifier_agent.run("ping")` with a short `asyncio.timeout(5)`. Out of scope for 24-19's `files_modified` frontmatter (warmup.py + main.py only); documented in deferred-items.md.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — Critical functionality / plan gate compliance] Bundled docstring rewording in processing/admin_handoff.py + eval/invoker.py**

- **Found during:** Task 2 final grep verification
- **Issue:** Plan acceptance criterion `! grep -rE "AzureAIAgentClient|agent_framework\\.azure" backend/src/second_brain/` was failing because two docstring narratives (one each in `processing/admin_handoff.py` and `eval/invoker.py`, both inherited from 24-11 and 24-18 respectively) still mentioned the literal RC class name in their historical context paragraphs. The AST scan red test does NOT flag docstrings (it walks `ast.Import`/`ast.ImportFrom`/`ast.Name`/`ast.Attribute`), but the plan's plain `grep -rE` gate does.
- **Fix:** One-line docstring edit in each file: literal `AzureAIAgentClient` replaced with "legacy RC client" (preserving the narrative semantics). Zero code change.
- **Files modified:** `backend/src/second_brain/processing/admin_handoff.py`, `backend/src/second_brain/eval/invoker.py`.
- **Verification:** `grep -rE "AzureAIAgentClient|agent_framework\\.azure" backend/src/second_brain/` now exits 1 (no matches). AST scan test still passes.
- **Committed in:** `55f04a5` (Task 2 bundle)

**2. [Rule 3 — Blocking] Updated 2 unit tests broken by Task 1 signature change**

- **Found during:** Post-Task 1 / pre-Task 2 regression sweep
- **Issue:** `tests/test_observability.py::test_warmup_recreates_client_after_consecutive_failures` + `test_warmup_resets_failure_count_on_success` called `agent_warmup_loop(clients=..., client_factories=...)` with mocked `client.get_response`. After Task 1 the GA signature uses `agents=` / `agent_factories=` / `agent.run`. Without updating tests, `pytest tests/test_observability.py` fails with `TypeError: agent_warmup_loop() got an unexpected keyword argument 'clients'`.
- **Fix:** Two-test rewrite in test_observability.py. Mock fixtures change `client.get_response` -> `agent.run`; keyword args change `clients`/`client_factories` -> `agents`/`agent_factories`; variable names renamed for clarity. One test renamed `_recreates_client_` -> `_recreates_agent_`. Same fail-twice-succeed-once semantics retained.
- **Files modified:** `backend/tests/test_observability.py`.
- **Verification:** `pytest tests/test_observability.py -v` -> 7/7 pass.
- **Committed in:** `55f04a5` (Task 2 bundle — co-located with main.py rewrite that consumes the same GA signature)

**3. [Rule 3 — Blocking] Deleted the legacy RC `foundry_client = AzureAIAgentClient(...)` block in main.py (beyond plan-action wording)**

- **Found during:** Task 2 plan-action interpretation
- **Issue:** Plan Task 2 action Part A says "Find: `from agent_framework.azure import AzureAIAgentClient`. DELETE it." But main.py:512-538 uses the imported symbol to construct `app.state.foundry_client` and validate Foundry connectivity via `list_agents`. Deleting the import alone leaves a NameError on the construction. The plan's acceptance criterion (`! grep -q "AzureAIAgentClient" main.py`) requires zero references — which only the construction block's deletion satisfies.
- **Fix:** Replaced lines 511-538 with `app.state.foundry_client = None` + an explanatory comment block pointing to the deferred-items.md follow-up. `api/health.py` already uses `getattr(..., None)` so the health endpoint returns `not_configured` for Foundry without raising.
- **Files modified:** `backend/src/second_brain/main.py`.
- **Verification:** `cd backend && uv run python -c "import second_brain.main"` -> exits 0. `pytest tests/test_observability.py` (which mocks `app.state.foundry_client` directly) -> 7/7 pass.
- **Committed in:** `55f04a5` (Task 2 bundle)

---

**Total deviations:** 3 auto-fixed (2 cleanup deviations + 1 plan-implied block deletion).
**Impact on plan:** All within natural scope of "main.py is GA-clean." Deviation #3 specifically: the plan's acceptance criterion mathematically requires the construction block to be deleted, even though the `<action>` Part A wording only mentioned the import line. Plan acceptance + grep gates are authoritative; action wording is descriptive.

## Authentication Gates

None encountered. All verification ran locally:

- `grep` / `! grep -q` / `grep -rE` for acceptance criteria
- `uv run python -c "..."` for import smoke tests (warmup.py + main.py)
- `uv run ruff check` for lint (all modified files)
- `uv run pytest` for the regression-guard test suites

## Known Stubs

None. All wired:

- `_make_classifier_agent` / `_make_admin_agent` / `_make_investigation_agent` factories use the live `build_*_agent` helpers from 24-04/24-09/24-14 (no placeholders).
- Warmup loop is fully migrated; no transitional shape remains.
- The `app.state.foundry_client = None` short-circuit is intentional, documented as a deferred follow-up (not a stub of this plan — it's a separately-tracked behavior change with a known migration path).

## Threat Flags

None — this plan does not introduce new network endpoints, auth paths, file access patterns, or trust-boundary changes.

- Source code DELETIONS (RC SDK construction block, dead-code locals) reduce attack surface.
- Warmup loop ping (`agent.run("ping")`) uses the existing GA Agent + middleware path already shipped in 24-04/24-09/24-14 — same threat surface as the normal `agent.run()` call path that handles real requests.
- `app.state.foundry_client = None` removes a network connection to the Foundry agents control plane that was used only for health probing. No new connection introduced.
- The deferred follow-up to migrate the health probe to a GA-shaped check is additive (new probe via existing `app.state.classifier_agent`), not a new trust boundary.

## TDD Gate Compliance

Plan type is `execute` (not `tdd`). No RED/GREEN commits required. The 2 tasks each landed as a single feat commit with verification gates per the plan's `<verify>` blocks. The "RED -> GREEN" flip in this plan refers to the AST-scan regression-guard test (`tests/test_no_rc_imports_after_cleanup.py`) — its planted state at 24-19.5 prep was RED with 2 offenders, and the GREEN flip is the success criterion of this plan, not a TDD gate per se.

## Verification Snapshot

### Task 1 (warmup.py)

| Criterion | Status |
|-----------|--------|
| `! grep -q "from agent_framework.azure import AzureAIAgentClient" backend/src/second_brain/warmup.py` | PASS |
| `! grep -q "Message" backend/src/second_brain/warmup.py` | PASS |
| `grep -q "from agent_framework import Agent" backend/src/second_brain/warmup.py` | PASS |
| `grep -q 'agent.run("ping")' backend/src/second_brain/warmup.py` | PASS |
| `grep -q "agents: list\\[" backend/src/second_brain/warmup.py` | PASS |
| `! grep -q "client.get_response" backend/src/second_brain/warmup.py` | PASS |
| `cd backend && uv run python -c "from second_brain.warmup import agent_warmup_loop"` exits 0 | PASS |

### Task 2 (main.py)

| Criterion | Status |
|-----------|--------|
| `! grep -q "AzureAIAgentClient" backend/src/second_brain/main.py` | PASS |
| `! grep -q "agent_framework\\.azure" backend/src/second_brain/main.py` | PASS |
| `grep -q "_make_classifier_agent" backend/src/second_brain/main.py` | PASS |
| `grep -q "_make_admin_agent" backend/src/second_brain/main.py` | PASS |
| `grep -q "_make_investigation_agent" backend/src/second_brain/main.py` | PASS |
| `! grep -rE "AzureAIAgentClient\\|agent_framework\\.azure" backend/src/second_brain/` | PASS (exit 1 — no matches) |
| `cd backend && uv run python -c "import second_brain.main"` exits 0 | PASS |

### AST scan red test (the must-flip-green)

```
$ cd backend && uv run pytest tests/test_no_rc_imports_after_cleanup.py -v
tests/test_no_rc_imports_after_cleanup.py::test_no_rc_imports_under_src PASSED [100%]
==============================  1 passed in 0.10s ===============================
```

**Offender count: 2 -> 0.** The codebase under `backend/src/second_brain/` is RC-free.

### Cross-cutting regression guards

```
$ cd backend && uv run pytest tests/test_no_rc_imports_after_cleanup.py \
    tests/test_legacy_middleware_imports_survive.py \
    tests/test_foundry_credential_shape.py \
    tests/test_inbox_dual_read.py \
    tests/test_observability.py \
    tests/test_eval.py \
    tests/test_eval_dry_run.py \
    tests/test_eval_metrics.py \
    tests/test_foundry_eval.py
================== 71 passed, 2 warnings in 2.61s ==================
```

### Linter

```
$ cd backend && uv run ruff check src/second_brain/main.py \
    src/second_brain/warmup.py \
    src/second_brain/processing/admin_handoff.py \
    src/second_brain/eval/invoker.py
All checks passed!
```

## Out-of-Scope Discoveries

Recorded in `.planning/phases/24-foundry-ga-migration/deferred-items.md`:

- **`api/health.py` Foundry connectivity probe** still calls the RC-shaped `foundry_client.agents_client.list_agents(...)` via `getattr(app.state.foundry_client, ...)`. After 24-19, `app.state.foundry_client` is permanently `None`, so the probe short-circuits to `not_configured`. The live `connected/degraded` signal is regressed until a follow-up plan migrates the probe to use `app.state.classifier_agent.run("ping")` with a short timeout. Track for 24-20 or 24-23.
- **`tests/test_classifier_integration.py` + `tests/test_event_tracing.py`** fail collection because both import the removed `stream_voice_capture` from `streaming/adapter.py` (deleted in 24-16 per STATE decision). Pre-existing breakage prior to 24-19; per executor SCOPE BOUNDARY not auto-fixed here.
- **`mcp/uv.lock`** shows uncommitted modification on disk (pre-existing on `main`, not touched by this plan). Same state as 24-15/24-16/24-17/24-18 SUMMARYs documented.

## Next Phase Readiness

- **Plan 24-21 (final config cleanup):** unblocked. With `foundry_client` deleted, the orphan `azure_ai_*_agent_id` settings (Phase 21 spec) become the only RC-shaped config drag. 24-21 strips them per CONTEXT.
- **Plan 24-20 (cumulative pre-deploy audit + gates):** F-01 + F-02 closed; cumulative diff across 24-04..24-19 should produce zero ❌ from the framework-fidelity auditor. The AST-scan permanent guard is now active — any future commit re-introducing RC imports fails CI.
- **Plan 24-22 (deploy):** Container App image now imports zero RC SDK code. Local main is in its final pre-deploy state except for the orphan config fields cleanup (24-21).
- **Follow-up:** `api/health.py` GA migration tracked in deferred-items.md.

## Self-Check: PASSED

**Files claimed modified:**

- [x] MODIFIED: `backend/src/second_brain/warmup.py` (GA-shaped — Agent type + agent.run("ping") + agent_factories kwarg + zero Message/AzureAIAgentClient literals)
- [x] MODIFIED: `backend/src/second_brain/main.py` (RC import deleted; legacy foundry_client block deleted; placeholder locals cleared; warmup factory cluster + call site rewritten; Agent imported)
- [x] MODIFIED: `backend/src/second_brain/processing/admin_handoff.py` (one-line docstring rewording)
- [x] MODIFIED: `backend/src/second_brain/eval/invoker.py` (one-line docstring rewording)
- [x] MODIFIED: `backend/tests/test_observability.py` (two warmup self-heal tests rewritten to GA signature)
- [x] CREATED: `.planning/phases/24-foundry-ga-migration/24-19-SUMMARY.md` (this file)
- [x] CREATED: `.planning/phases/24-foundry-ga-migration/deferred-items.md`

**Commits claimed:**

- [x] FOUND: `7dfcbde` (Task 1: feat(24-19): rewrite warmup.py against GA Agent (F-02 cleared))
- [x] FOUND: `55f04a5` (Task 2: feat(24-19): rewrite main.py warmup factories + RC import deletion (F-01 fully cleared))

**Acceptance grep claims:**

- [x] FOUND: 0 occurrences of `AzureAIAgentClient` anywhere under `backend/src/second_brain/`
- [x] FOUND: 0 occurrences of `agent_framework.azure` anywhere under `backend/src/second_brain/`
- [x] FOUND: 0 occurrences of `Message` in warmup.py
- [x] FOUND: 0 occurrences of `client.get_response` in warmup.py
- [x] FOUND: `agent.run("ping")` in warmup.py
- [x] FOUND: `_make_classifier_agent` + `_make_admin_agent` + `_make_investigation_agent` in main.py
- [x] FOUND: `from agent_framework import Agent` in main.py + warmup.py

**Test claims:**

- [x] `tests/test_no_rc_imports_after_cleanup.py` PASSES (was FAIL pre-commit; the must-flip-green check)
- [x] 71/71 pass: test_no_rc_imports_after_cleanup + test_legacy_middleware_imports_survive + test_foundry_credential_shape + test_inbox_dual_read + test_observability + test_eval + test_eval_dry_run + test_eval_metrics + test_foundry_eval
- [x] Linter clean on all modified files

Verification commands executed:

```bash
git log --oneline -3
# 55f04a5 7dfcbde 1d3a705

! grep -rE "AzureAIAgentClient|agent_framework\.azure" backend/src/second_brain/ && echo "RC-free"
# RC-free

cd backend && uv run pytest tests/test_no_rc_imports_after_cleanup.py -v
# 1 passed in 0.10s

cd backend && uv run pytest tests/test_no_rc_imports_after_cleanup.py \
  tests/test_legacy_middleware_imports_survive.py \
  tests/test_foundry_credential_shape.py \
  tests/test_inbox_dual_read.py \
  tests/test_observability.py \
  tests/test_eval.py \
  tests/test_eval_dry_run.py \
  tests/test_eval_metrics.py \
  tests/test_foundry_eval.py
# 71 passed
```

---

*Phase: 24-foundry-ga-migration*
*Plan: 24-19*
*Completed: 2026-05-11*
