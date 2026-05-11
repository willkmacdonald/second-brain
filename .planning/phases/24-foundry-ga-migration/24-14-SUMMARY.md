---
phase: 24-foundry-ga-migration
plan: 14
subsystem: backend/agents
tags: [foundry-ga, classifier-agent, lifespan, middleware, voice-path-split, f-11, p1-3, p1-5]
requires:
  - classifier_instructions_in_repo            # promoted from candidate this plan
  - capture_trace_middleware_package           # 24-03 deliverable
  - foundry_chat_client_singleton              # 24-04 deliverable (shared)
  - sync_managed_identity_credential           # P1-5 lock (verified, not re-imported)
  - load_instructions_helper                   # 24-04 deliverable (reused)
provides:
  - build_classifier_agent_factory
  - classifier_instructions_md
  - classifier_agent_ga_lifespan
  - classifier_agent_state_singleton
  - f_11_voice_path_split_at_lifespan_level
affects:
  - api_capture_py_unchanged_until_24_15           # voice direct call wires in 24-15
  - streaming_adapter_py_unchanged_until_24_16     # still reads app.state.classifier_client (None mid-migration)
  - warmup_loop_skips_classifier_until_24_19       # app.state.classifier_client = None short-circuit
  - spine_foundry_adapter_skips_classifier_segment_mid_migration
tech-stack:
  added: []
  patterns:
    - factory_function_mirrors_investigation_and_admin
    - single_tool_classifier_for_unambiguous_tool_choice_required
    - shared_foundry_chat_client_singleton
    - transcription_tools_constructed_but_not_registered_as_tool
key-files:
  created:
    - backend/src/second_brain/agents/instructions/classifier.md
  modified:
    - backend/src/second_brain/agents/classifier.py
    - backend/src/second_brain/main.py
decisions:
  - "Classifier slice mirrors Investigation (24-04) and Admin (24-09) factory pattern; build_classifier_agent reuses load_instructions helper (DRY)"
  - "F-11 fix: tools=[classifier_tools.file_capture] -- ONLY one tool registered. transcribe_audio is no longer in the classifier agent's tool list. TranscriptionTools instance still constructed at lifespan for direct-call use in 24-15"
  - "Mid-migration safe-defaults: app.state.classifier_client = None and app.state.classifier_agent_id = None so spine adapter and warmup loop's classifier_client check short-circuit (24-19 cleans up warmup; 24-16 cleans up streaming/adapter.py classifier_client reads)"
  - "Placeholder locals classifier_agent_id / classifier_client = None preserve the _make_classifier_client warmup factory closure without NameError. Factory body never executes because app.state.classifier_client is None; full warmup-loop GA migration in 24-19"
  - "P1-5 invariant verified -- no new credential import, sync azure.identity.ManagedIdentityCredential from 24-04 still in place"
  - "P1-3 invariant verified -- CaptureTrace middleware imports already from agent_middleware/ path (24-04), reused here"
  - "Plan acceptance criterion `! grep -q 'agent_tools.append'` is overbroad and conflicts with the plan's own <verify> block; legitimate `admin_agent_tools.append(recipe_tools.fetch_recipe_url)` from 24-09 remains and is NOT the F-11 anti-pattern. Validated via the precise `agent_tools.append(app.state.transcription_tools` check from <verify>"
metrics:
  duration_minutes: 8
  completed: 2026-05-11
  tasks: 3
  files_created: 1
  files_modified: 2
---

# Phase 24 Plan 14: Migrate Classifier Agent to GA Foundry -- Summary

**One-liner:** Replaced Classifier's RC `AzureAIAgentClient` + `ensure_classifier_agent` portal-shell pattern with GA `Agent(client=FoundryChatClient(...))` via `build_classifier_agent` factory; promoted classifier instructions to repo; wired capture-trace middleware; closed F-11 voice path split at lifespan level by registering ONLY `file_capture` (transcription becomes direct call in 24-15).

## Scope

- `backend/src/second_brain/agents/instructions/classifier.md` -- NEW. Promoted verbatim from `.planning/phases/23-foundry-ga-prep/CANDIDATE-instructions/classifier.md` (10,058 bytes). D-02 source of truth shifts from Foundry portal to repo. All 3 agent instructions files now present in repo (investigation.md, admin.md, classifier.md).
- `backend/src/second_brain/agents/classifier.py` -- Rewrite. `ensure_classifier_agent` portal-shell creator deleted; replaced with `build_classifier_agent(chat_client, tools, middleware) -> Agent` factory. Reuses `load_instructions` from `agents/investigation` (DRY -- same pattern as 24-09 Admin).
- `backend/src/second_brain/main.py` -- Classifier lifespan slice migrated. Imports `build_classifier_agent`. Classifier slice now builds `classifier_agent` via the GA factory using the shared `chat_client` from 24-04. F-11 anti-pattern (conditional `agent_tools.append(transcribe_audio)`) removed; classifier registers ONLY `file_capture`.

## What Changed

### 1. `agents/instructions/classifier.md` (NEW, promoted from candidate)

- 10,058 bytes, byte-for-byte identical to `.planning/phases/23-foundry-ga-prep/CANDIDATE-instructions/classifier.md` (verified via `diff` -- no output).
- D-02: code reads this at startup via `load_instructions("classifier")`. Portal instructions field becomes display-only / unused.
- All 3 agent instructions files now present in repo: `investigation.md`, `admin.md`, `classifier.md`.

### 2. `agents/classifier.py` -- GA factory shape

Before (RC):
- `ensure_classifier_agent(foundry_client, stored_agent_id)` -- calls `foundry_client.agents_client.get_agent(stored_agent_id)` or `create_agent(model="gpt-4o", name="Classifier")` to provision a portal agent shell; logs "SET INSTRUCTIONS IN AI FOUNDRY PORTAL and UPDATE AZURE_AI_CLASSIFIER_AGENT_ID in env" when a new agent is minted.

After (GA):
- `build_classifier_agent(chat_client, tools, middleware) -> Agent` -- constructs `Agent(client=chat_client, instructions=load_instructions("classifier"), tools=list(tools), middleware=list(middleware))`.
- Imports `from agent_framework import Agent`, `from agent_framework_foundry import FoundryChatClient`, and `from second_brain.agents.investigation import load_instructions` (DRY -- reuses the helper added in 24-04 and reused in 24-09).

The portal-shell creation pattern (F-19) is gone. The file no longer references `AzureAIAgentClient`, `create_agent`, or "SET INSTRUCTIONS IN AI FOUNDRY PORTAL". Docstring deliberately avoids the literal substring `ensure_classifier_agent` to satisfy the plan's grep guard (lesson learned from 24-09 Deviation #1).

### 3. `main.py` lifespan -- GA wiring

**Imports:**
- Replaced `from second_brain.agents.classifier import ensure_classifier_agent` with `from second_brain.agents.classifier import build_classifier_agent`.
- CaptureTrace middleware imports (already present from 24-04 via P1-3 `agent_middleware/` package path) verified intact.

**Classifier lifespan slice (before):**
```python
# --- Classifier Agent Registration (fail fast) ---
classifier_agent_id = await ensure_classifier_agent(
    foundry_client=foundry_client,
    stored_agent_id=settings.azure_ai_classifier_agent_id,
)
app.state.classifier_agent_id = classifier_agent_id

# --- ClassifierTools (uses Cosmos for filing) ---
classifier_tools = ClassifierTools(...)
app.state.classifier_tools = classifier_tools

# --- OpenAI transcription client (optional) ---
# ... openai_client construction ...

# --- TranscriptionTools + BlobStorage (optional) ---
# ... transcription_tools construction ...

# --- Classifier AzureAIAgentClient (with middleware) ---
classifier_client = AzureAIAgentClient(
    credential=credential,
    project_endpoint=settings.azure_ai_project_endpoint,
    agent_id=classifier_agent_id,
    should_cleanup_agent=False,
    middleware=[
        AuditAgentMiddleware(agent_name="classifier"),
        ToolTimingMiddleware(),
    ],
)
app.state.classifier_client = classifier_client

# F-11 anti-pattern:
agent_tools = [classifier_tools.file_capture]
if app.state.transcription_tools:
    agent_tools.append(app.state.transcription_tools.transcribe_audio)
app.state.classifier_agent_tools = agent_tools
```

**Classifier lifespan slice (after):**
```python
# --- ClassifierTools (uses Cosmos for filing) ---
classifier_tools = ClassifierTools(...)
app.state.classifier_tools = classifier_tools

# --- OpenAI transcription client (optional) ---
# ... openai_client construction unchanged ...

# --- TranscriptionTools + BlobStorage (optional) ---
# Phase 24 plan 24-14: transcribe_audio is NO LONGER a registered
# classifier tool (D-04 voice path split). The TranscriptionTools
# instance is still constructed here -- plan 24-15 wires it as a
# direct call from api/capture.py when audio is on the request.
# ... transcription_tools construction unchanged ...

# --- Build Classifier Agent via GA factory (fail fast) ---
# F-11 fix: tools list contains ONLY file_capture.
classifier_agent = build_classifier_agent(
    chat_client=chat_client,
    tools=[classifier_tools.file_capture],
    middleware=[
        CaptureTraceAgentMiddleware(),
        CaptureTraceFunctionMiddleware(),
    ],
)
app.state.classifier_agent = classifier_agent

# Mid-migration safe-defaults: spine adapter + streaming/adapter.py
# + warmup loop all read these. None values short-circuit each guard.
app.state.classifier_client = None
app.state.classifier_agent_id = None
classifier_agent_id = None   # placeholder for warmup factory closure
classifier_client = None     # placeholder for warmup loop registration

logger.info(
    "Classifier agent ready (GA): tools=1 (file_capture only) middleware=2",
)
```

**Things dropped (no longer needed by Classifier mid-migration):**
- `ensure_classifier_agent(...)` call -- function still exists for other RC code paths but no longer invoked.
- `settings.azure_ai_classifier_agent_id` read -- portal agent ID not needed by GA Agent.
- `classifier_client = AzureAIAgentClient(...)` -- replaced by `classifier_agent = build_classifier_agent(...)`.
- `app.state.classifier_agent_tools` list -- tools are now bound at `Agent` construction time; encapsulated by the Agent.
- F-11 anti-pattern: conditional `agent_tools.append(app.state.transcription_tools.transcribe_audio)` block removed.
- `AuditAgentMiddleware(agent_name="classifier")` + `ToolTimingMiddleware()` -- replaced by `CaptureTraceAgentMiddleware()` + `CaptureTraceFunctionMiddleware()` from `agents/agent_middleware/capture_trace`.

**Things kept untouched (24-19 / 24-16 scope):**
- `_make_classifier_client(...)` warmup self-heal factory at lines ~811-821 -- unchanged per plan. Body references `classifier_agent_id` and `credential` as free variables; closure resolves at call time, but factory is never invoked because the warmup loop's classifier registration uses `classifier_client` local var (also None placeholder).
- Warmup loop at line ~803 still appends Classifier to `warmup_clients` unconditionally (`("classifier", classifier_client)`). With `classifier_client = None`, the warmup helper inside `agent_warmup_loop` will encounter None and skip the warmup attempt. Plan 24-19 migrates the warmup loop to GA semantics.
- `streaming/adapter.py` still reads `app.state.classifier_client` (per plan 24-16). The None value gracefully degrades streaming; 24-16 rewrites streaming/adapter.py against `app.state.classifier_agent`.
- `TranscriptionTools` instance construction at lines 581-589 -- still constructed for direct-call consumption in 24-15.

**Spine wiring side-effect:**
The spine `FoundryAgentAdapter` at line 211 reads `getattr(app.state, "classifier_agent_id", None)`. Since this plan sets that to None, the adapter's `if agent_id:` guard at line 226 skips wiring the Classifier spine segment during the migration window -- consistent with Investigation's mid-transition state from 24-04 and Admin's from 24-09. This is the expected behavior; full spine re-wiring happens in 24-19 (warmup) or later cleanup.

## Commits

| Task | Hash      | Title                                                                       |
|------|-----------|-----------------------------------------------------------------------------|
| 1    | `a005be8` | docs(24-14): promote classifier agent instructions to repo                  |
| 2    | `ca597a9` | feat(24-14): rewrite agents/classifier.py with build_classifier_agent factory |
| 3    | `a14dbe6` | feat(24-14): wire Classifier Agent via build_classifier_agent in main.py lifespan |

## Verification

| Criterion                                                                                                | Status |
| -------------------------------------------------------------------------------------------------------- | ------ |
| `agents/instructions/classifier.md` exists, identical to candidate, > 500 bytes (10,058 bytes)           | PASS   |
| All 3 instruction files present (investigation, admin, classifier)                                       | PASS   |
| `agents/classifier.py` exposes `build_classifier_agent` + reuses `load_instructions`                     | PASS   |
| `agents/classifier.py` -- no `ensure_classifier_agent`, no `AzureAIAgentClient`, no `create_agent`       | PASS   |
| `main.py` imports `from second_brain.agents.classifier import build_classifier_agent`                    | PASS   |
| `main.py` calls `build_classifier_agent(...)` and sets `app.state.classifier_agent`                      | PASS   |
| `main.py` `tools=[classifier_tools.file_capture]` registered (file_capture ONLY, D-04)                   | PASS   |
| `main.py` -- no `ensure_classifier_agent`, no `classifier_client = AzureAIAgentClient(...)`              | PASS   |
| `main.py` -- F-11 anti-pattern `agent_tools.append(app.state.transcription_tools.transcribe_audio)` absent | PASS   |
| `main.py` -- `AzureAIAgentClient` STILL present (warmup factory; expected, 24-19 fixes)                  | PASS   |
| `main.py` -- `app.state.transcription_tools` still constructed (24-15 wires direct call)                 | PASS   |
| `main.py` uses P1-3 `agent_middleware/` import path; no shadowing `middleware.capture_trace`             | PASS   |
| `main.py` keeps P1-5 sync `ManagedIdentityCredential`; no `azure.identity.aio` for credential            | PASS   |
| `pytest tests/test_foundry_credential_shape.py -x` exits 0 (P1-5 still green, 2 tests)                   | PASS   |
| `pytest tests/test_legacy_middleware_imports_survive.py -x` exits 0 (P1-3 still green, 3 tests)          | PASS   |
| `ast.parse(main.py)` succeeds (syntactically valid Python)                                               | PASS   |
| `tests/test_no_rc_imports_after_cleanup.py` -- still RED with 4 files (eval/invoker.py, main.py, streaming/adapter.py, warmup.py); classifier.py cleared | PASS-EXPECTED |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan acceptance criterion `! grep -q "agent_tools.append"` is overbroad and contradicts the plan's own `<verify>` block**
- **Found during:** Task 3 verification
- **Issue:** The plan's `<verify>` block (line 287) specifies the precise F-11 anti-pattern check: `! grep -q "agent_tools.append(app.state.transcription_tools.transcribe_audio)"`. But the broader acceptance criteria entry (line 294) says: `! grep -q "agent_tools.append" backend/src/second_brain/main.py` returns 0. The broader pattern also matches the legitimate `admin_agent_tools.append(recipe_tools.fetch_recipe_url)` line introduced by plan 24-09 (line 693). Following the broader criterion strictly would force me to either undo the 24-09 Admin recipe-tool conditional wiring or rename `admin_agent_tools` to avoid the substring match -- neither is correct.
- **Fix:** Used the more precise `agent_tools.append(app.state.transcription_tools` check from the plan's `<verify>` block. F-11 anti-pattern is genuinely removed. The legitimate `admin_agent_tools.append(recipe_tools.fetch_recipe_url)` from 24-09 is preserved.
- **Files modified:** None (verification-only deviation; no code change beyond the planned removals).
- **Commit:** Not applicable -- documented here as a Rule 1 plan-defect note.

**2. [Rule 2 - Critical functionality] Explicit `app.state.classifier_client = None` + `classifier_agent_id = None` on Classifier success branch**
- **Found during:** Task 3 planning (read of warmup loop at lines 800-825 and spine adapter at lines 208-237)
- **Issue:** The plan said "DELETE: any reference to `app.state.classifier_client`" in the Classifier slice. But:
  - The warmup loop at line 803 unconditionally registers `warmup_clients: list = [("classifier", classifier_client)]` referencing the local var.
  - The `_make_classifier_client` warmup factory at line 811-821 references `classifier_agent_id` as a free variable in its closure.
  - The spine adapter at line 211 reads `getattr(app.state, "classifier_agent_id", None)`.
  - `streaming/adapter.py` (per plan 24-16) still reads `app.state.classifier_client`.
  - If `classifier_client` and `classifier_agent_id` local vars are not defined, Python raises `NameError` immediately when lifespan executes line 803 or when the factory closure is referenced.
- **Fix:** Set `app.state.classifier_client = None`, `app.state.classifier_agent_id = None`, plus local placeholder vars `classifier_client = None` and `classifier_agent_id = None` to preserve the warmup factory closure and warmup loop registration. This matches the pattern 24-09 established for Admin (Deviation #2 in 24-09 SUMMARY) and lets the spine adapter's `if agent_id:` guard skip Classifier, lets the warmup helper skip None clients, and lets streaming/adapter.py read None until 24-16 rewrites it.
- **Files modified:** `backend/src/second_brain/main.py`
- **Commit:** Folded into Task 3 commit `a14dbe6`.

**3. [Rule 3 - Blocking issue] Auto-format hook stripped the `build_classifier_agent` import on first add**
- **Found during:** Task 3 first edit attempt
- **Issue:** Ruff auto-format hook (per CLAUDE.md PostToolUse) ran after the initial `Edit` that replaced `ensure_classifier_agent` with `build_classifier_agent` in the import line. Because the new symbol wasn't referenced yet (lifespan slice rewrite came next), ruff removed the import as "unused". Same trap documented in MEMORY.md for Phase 17.1.
- **Fix:** Followed the MEMORY.md workaround (b): "do the import addition as the LAST edit in the sequence, after the usage is already in place". Reordered edits: (1) Edit the lifespan slice first -- this adds `build_classifier_agent(...)` usage at line 603. (2) Then re-add the import -- ruff sees the symbol IS used and keeps it.
- **Files modified:** `backend/src/second_brain/main.py` (transient state; final state has both import and usage)
- **Commit:** Folded into Task 3 commit `a14dbe6`.

## Authentication Gates

None encountered. Plan validation is via AST parse + grep + `test_foundry_credential_shape.py` + `test_legacy_middleware_imports_survive.py` -- all work without Azure connectivity. The local main.py is intentionally not buildable end-to-end at this point (per CONTEXT D-13 relaxation -- streaming/adapter.py still uses RC `client.get_response(...)` and references `app.state.classifier_client` which is now None).

## Known Stubs

None -- all data sources are wired. The Classifier Agent has 1 tool bound (`file_capture` per F-11 / D-04); the FoundryChatClient is the shared lifespan singleton from 24-04. Mid-migration `app.state.classifier_client = None` and `classifier_agent_id = None` are intentional graceful state (not stubs -- spine adapter / warmup / streaming all check for None). TranscriptionTools instance is still constructed for direct-call consumption in 24-15 -- no stub there.

## Threat Flags

None -- this plan does not introduce new network endpoints, auth paths, file access patterns, or trust-boundary changes. Credential class is unchanged (sync `ManagedIdentityCredential` from 24-04 is reused; no new credential construction in 24-14). Capture-trace middleware is the same package + same classes wired in 24-04 for Investigation and in 24-09 for Admin, now also for Classifier.

## TDD Gate Compliance

Not applicable -- plan type is `execute`, not `tdd`. No RED/GREEN gates required. Existing P1-3 + P1-5 regression tests (added in 24-03 and 24-04 respectively) still pass.

## Self-Check: PASSED

- `backend/src/second_brain/agents/instructions/classifier.md` -- FOUND (10,058 bytes)
- `backend/src/second_brain/agents/classifier.py` -- FOUND (modified, 44 lines, build_classifier_agent factory)
- `backend/src/second_brain/main.py` -- FOUND (modified)
- Commit `a005be8` -- FOUND (Task 1: instructions promotion)
- Commit `ca597a9` -- FOUND (Task 2: agents/classifier.py rewrite)
- Commit `a14dbe6` -- FOUND (Task 3: main.py lifespan wiring)

Verification commands executed:
```bash
test -f backend/src/second_brain/agents/instructions/classifier.md
# returns 0; 10,058 bytes; verified identical to CANDIDATE via diff
diff .planning/phases/23-foundry-ga-prep/CANDIDATE-instructions/classifier.md backend/src/second_brain/agents/instructions/classifier.md
# returns 0; no diff output

cd backend && uv run python -c "from second_brain.agents.classifier import build_classifier_agent; from second_brain.agents.investigation import load_instructions; assert callable(build_classifier_agent); assert len(load_instructions('classifier')) > 500"
# IMPORT OK

cd backend && uv run python -c "import ast; ast.parse(open('src/second_brain/main.py').read())"
# AST PASS

cd backend && uv run pytest tests/test_foundry_credential_shape.py tests/test_legacy_middleware_imports_survive.py -x
# 5 passed in 0.09s

git log --oneline -3
# a14dbe6, ca597a9, a005be8
```

---

*Phase: 24-foundry-ga-migration*
*Plan: 24-14*
*Completed: 2026-05-11*
