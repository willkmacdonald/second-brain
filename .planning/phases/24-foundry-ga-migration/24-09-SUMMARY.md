---
phase: 24-foundry-ga-migration
plan: 09
subsystem: backend/agents
tags: [foundry-ga, admin-agent, lifespan, middleware, p1-3, p1-5]
requires:
  - admin_instructions_in_repo                # promoted from candidate this plan
  - capture_trace_middleware_package          # 24-03 deliverable
  - foundry_chat_client_singleton             # 24-04 deliverable (shared)
  - sync_managed_identity_credential          # P1-5 lock (verified, not re-imported)
  - load_instructions_helper                  # 24-04 deliverable (reused)
provides:
  - build_admin_agent_factory
  - admin_instructions_md
  - admin_agent_ga_lifespan
  - admin_agent_state_singleton
affects:
  - classifier_lifespan_unchanged_until_24_14
  - warmup_skips_admin_until_24_19
  - spine_foundry_adapter_skips_admin_segment_mid_migration
  - investigation_tools_admin_client_param_now_None_during_migration
tech-stack:
  added: []
  patterns:
    - factory_function_mirrors_investigation
    - tool_list_built_pre_construction_for_recipe_conditional
    - shared_foundry_chat_client_singleton
key-files:
  created:
    - backend/src/second_brain/agents/instructions/admin.md
  modified:
    - backend/src/second_brain/agents/admin.py
    - backend/src/second_brain/main.py
decisions:
  - "Admin slice mirrors Investigation factory pattern from 24-04"
  - "Recipe tool wiring moved BEFORE build_admin_agent so fetch_recipe_url is in tools= at construction (replaces post-hoc admin_agent_tools.append)"
  - "Explicit app.state.admin_client = None on success branch — keeps warmup loop's direct attr access (line 793) safe during migration window (Rule 2 deviation)"
  - "AdminTools tool names verified from source: 6 admin (add_errand_items, add_task_items, get_routing_context, manage_destination, manage_affinity_rule, query_rules) + 1 recipe (fetch_recipe_url) = 7 total when Playwright succeeds, 6 when Playwright fails"
  - "P1-5 invariant verified — no new credential import, sync azure.identity.ManagedIdentityCredential from 24-04 still in place"
  - "P1-3 invariant verified — CaptureTrace middleware imports already from agent_middleware/ path (24-04), reused here"
metrics:
  duration_minutes: 5
  completed: 2026-05-11
  tasks: 3
  files_created: 1
  files_modified: 2
---

# Phase 24 Plan 09: Migrate Admin Agent to GA Foundry — Summary

**One-liner:** Replaced Admin's RC `AzureAIAgentClient` + `ensure_admin_agent` portal-shell pattern with GA `Agent(client=FoundryChatClient(...))` constructed via `build_admin_agent` factory; promoted admin instructions to repo; wired capture-trace middleware; preserved the 7-tool surface (6 admin + 1 recipe) with conditional recipe tool inclusion based on Playwright availability.

## Scope

- `backend/src/second_brain/agents/instructions/admin.md` — NEW. Promoted verbatim from `.planning/phases/23-foundry-ga-prep/CANDIDATE-instructions/admin.md` (4882 bytes). D-02 source of truth shifts from Foundry portal to repo.
- `backend/src/second_brain/agents/admin.py` — Rewrite. `ensure_admin_agent` portal-shell creator deleted; replaced with `build_admin_agent(chat_client, tools, middleware) -> Agent` factory. Reuses `load_instructions` from `agents/investigation` (DRY).
- `backend/src/second_brain/main.py` — Admin lifespan slice migrated. Imports `build_admin_agent`. Admin slice now builds `admin_agent` via the GA factory using the shared `chat_client` from 24-04. Classifier slice still uses `AzureAIAgentClient` (24-14 migrates it).

## What Changed

### 1. `agents/instructions/admin.md` (NEW, promoted from candidate)

- 4882 bytes, byte-for-byte identical to `.planning/phases/23-foundry-ga-prep/CANDIDATE-instructions/admin.md` (verified via `diff`).
- D-02: code reads this at startup via `load_instructions("admin")`. Portal instructions field becomes display-only / unused.
- `classifier.md` correctly absent — 24-14 promotes Classifier instructions.

### 2. `agents/admin.py` — GA factory shape

Before (RC):
- `ensure_admin_agent(foundry_client, stored_agent_id)` — calls `foundry_client.agents_client.get_agent(stored_agent_id)` or `create_agent(model="gpt-4o", name="AdminAgent")` to provision a portal agent shell; logs "SET INSTRUCTIONS IN AI FOUNDRY PORTAL and UPDATE AZURE_AI_ADMIN_AGENT_ID in env" when a new agent is minted.

After (GA):
- `build_admin_agent(chat_client, tools, middleware) -> Agent` — constructs `Agent(client=chat_client, instructions=load_instructions("admin"), tools=list(tools), middleware=list(middleware))`.
- Imports `from agent_framework import Agent`, `from agent_framework_foundry import FoundryChatClient`, and `from second_brain.agents.investigation import load_instructions` (DRY — reuses the helper added in 24-04).

The portal-shell creation pattern (F-19) is gone. The file no longer references `AzureAIAgentClient`, `create_agent`, or "SET INSTRUCTIONS IN AI FOUNDRY PORTAL".

### 3. `main.py` lifespan — GA wiring

**Imports:**
- Replaced `from second_brain.agents.admin import ensure_admin_agent` with `from second_brain.agents.admin import build_admin_agent`.
- CaptureTrace middleware imports (already present from 24-04 via P1-3 `agent_middleware/` package path) verified intact.

**Admin lifespan slice (before):**
```python
try:
    admin_agent_id = await ensure_admin_agent(foundry_client=foundry_client, stored_agent_id=settings.azure_ai_admin_agent_id)
    app.state.admin_agent_id = admin_agent_id
    admin_tools = AdminTools(cosmos_manager=cosmos_mgr)
    app.state.admin_tools = admin_tools
    admin_client = AzureAIAgentClient(credential=credential, project_endpoint=..., agent_id=admin_agent_id, middleware=[Audit, ToolTiming])
    app.state.admin_client = admin_client
    app.state.admin_agent_tools = [admin_tools.add_errand_items, ..., admin_tools.query_rules]  # 6
    # nested try: Playwright launch -> recipe_tools -> app.state.admin_agent_tools.append(recipe_tools.fetch_recipe_url)
```

**Admin lifespan slice (after):**
```python
try:
    admin_tools = AdminTools(cosmos_manager=cosmos_mgr)
    app.state.admin_tools = admin_tools

    # Playwright/RecipeTools FIRST so fetch_recipe_url goes into tools= at construction
    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True, args=[...])
        app.state.playwright = pw
        app.state.browser = browser
        recipe_tools = RecipeTools(browser=browser, spine_repo=getattr(app.state, "spine_repo", None))
        app.state.recipe_tools = recipe_tools
    except Exception:
        # Playwright failure -> recipe_tools = None -> agent built with 6 tools
        app.state.playwright = None
        app.state.browser = None
        app.state.recipe_tools = None
        recipe_tools = None

    admin_agent_tools = [
        admin_tools.add_errand_items,
        admin_tools.add_task_items,
        admin_tools.get_routing_context,
        admin_tools.manage_destination,
        admin_tools.manage_affinity_rule,
        admin_tools.query_rules,
    ]
    if recipe_tools is not None:
        admin_agent_tools.append(recipe_tools.fetch_recipe_url)

    admin_agent = build_admin_agent(
        chat_client=chat_client,
        tools=admin_agent_tools,
        middleware=[CaptureTraceAgentMiddleware(), CaptureTraceFunctionMiddleware()],
    )
    app.state.admin_agent = admin_agent
    app.state.admin_client = None   # migration-window safe-default (see Deviations)
    app.state.admin_agent_id = None # migration-window safe-default (see Deviations)
```

**Things dropped (no longer needed by Admin during migration):**
- `ensure_admin_agent(...)` call — function no longer exists.
- `settings.azure_ai_admin_agent_id` read — portal agent ID not needed by GA Agent.
- `admin_client = AzureAIAgentClient(...)` — replaced by `admin_agent = build_admin_agent(...)`.
- `app.state.admin_agent_tools = [...]` list — tools are now bound at `Agent` construction time; encapsulated by the Agent.
- `app.state.admin_agent_tools.append(recipe_tools.fetch_recipe_url)` (line 685) — recipe tool now in `tools=` at construction.
- `AuditAgentMiddleware(agent_name="admin")` + `ToolTimingMiddleware()` — replaced by CaptureTrace{Agent,Function}Middleware from `agent_middleware/`.

**Things kept untouched (24-19 scope):**
- `_make_admin_client(...)` warmup self-heal factory at lines ~817-829.
- Warmup loop registration of Admin will skip naturally because `if app.state.admin_client is not None` (line 793) now sees None (explicit `= None` set in success branch ensures the check is safe).

**Spine wiring side-effect:**
The spine `FoundryAgentAdapter` at line 216 reads `getattr(app.state, "admin_agent_id", None)`. Since this plan sets that to None, the adapter's `if agent_id:` guard at line 226 skips wiring the Admin spine segment during the migration window — same as Investigation's mid-transition state from 24-04. This is the expected behavior; full spine re-wiring happens in 24-19 (warmup) or later cleanup.

**InvestigationTools side-effect:**
InvestigationTools at line 728 reads `admin_client=getattr(app.state, "admin_client", None)`. With the new explicit `= None` value, `run_admin_eval` flows through with `admin_client=None` (graceful degradation — eval surface for Admin is exercised via EvalAgentInvoker introduced in 24-12, which decouples from `admin_client`).

## Commits

| Task | Hash      | Title                                                                  |
|------|-----------|------------------------------------------------------------------------|
| 1    | `a95dbc8` | docs(24-09): promote admin agent instructions to repo                  |
| 2    | `7b0de54` | feat(24-09): rewrite agents/admin.py with build_admin_agent factory    |
| 3    | `e89f8f3` | feat(24-09): wire Admin Agent via build_admin_agent in main.py lifespan |

## Verification

| Criterion                                                                                          | Status |
| -------------------------------------------------------------------------------------------------- | ------ |
| `agents/instructions/admin.md` exists, identical to candidate, > 500 bytes                          | PASS   |
| `! test -f agents/instructions/classifier.md`                                                       | PASS   |
| `agents/admin.py` exposes `build_admin_agent` + reuses `load_instructions`                          | PASS   |
| `agents/admin.py` — no `ensure_admin_agent`, no `AzureAIAgentClient`, no `create_agent`             | PASS   |
| `main.py` imports `from second_brain.agents.admin import build_admin_agent`                         | PASS   |
| `main.py` calls `build_admin_agent(...)` and sets `app.state.admin_agent`                           | PASS   |
| `main.py` — no `admin_client = AzureAIAgentClient(...)`, no `ensure_admin_agent(...)` call          | PASS   |
| `main.py` — `AzureAIAgentClient` STILL present (Classifier slice, expected; 24-14 fixes)            | PASS   |
| `main.py` uses P1-3 `agent_middleware/` import path; no shadowing `middleware.capture_trace`       | PASS   |
| `main.py` keeps P1-5 sync `ManagedIdentityCredential`; no `azure.identity.aio` for credential       | PASS   |
| 7 tool methods (6 admin + 1 recipe) appear at `build_admin_agent(tools=...)` call site              | PASS   |
| `pytest tests/test_foundry_credential_shape.py -x` exits 0 (P1-5 still green)                       | PASS   |
| `pytest tests/test_legacy_middleware_imports_survive.py -x` exits 0 (P1-3 still green)              | PASS   |
| `ast.parse(main.py)` succeeds (syntactically valid Python)                                          | PASS   |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Docstring containing literal `ensure_admin_agent` violated grep guard**
- **Found during:** Task 2 verification
- **Issue:** The new `agents/admin.py` docstring originally read "Replaces RC ensure_admin_agent portal-shell creation pattern (F-19)." That substring made the acceptance check `! grep -q "ensure_admin_agent"` fail because the grep doesn't distinguish comments from code.
- **Fix:** Reworded to "Replaces the RC portal-shell creation pattern (F-19)." Preserves intent; satisfies grep guard.
- **Files modified:** `backend/src/second_brain/agents/admin.py`
- **Commit:** Folded into Task 2 commit `7b0de54`.

**2. [Rule 2 - Critical functionality] Explicit `app.state.admin_client = None` on Admin success branch**
- **Found during:** Task 3 planning (read of lines 789-829)
- **Issue:** The plan said "DELETE: any reference to `app.state.admin_client`" in the Admin slice. The warmup loop at line 793 (`if app.state.admin_client is not None:`) uses DIRECT attribute access, not defensive `getattr`. If the Admin success branch never sets `admin_client`, line 793 raises `AttributeError` because the attribute was never created on app.state for that lifespan invocation. Investigation's slice in 24-04 escaped this because warmup uses defensive `getattr(app.state, "investigation_client", None)` for it (line 795).
- **Fix:** Set `app.state.admin_client = None` and `app.state.admin_agent_id = None` in the success branch alongside `app.state.admin_agent = admin_agent`. This preserves the warmup guard's skip semantics and matches the existing except-branch pattern (lines 705-706). Plan 24-19 will migrate the warmup factory to GA and unblock this.
- **Files modified:** `backend/src/second_brain/main.py`
- **Commit:** Folded into Task 3 commit `e89f8f3`.

**3. [Rule 3 - Blocking issue] Recipe tool wiring reordered BEFORE `build_admin_agent`**
- **Found during:** Task 3 planning (read of lines 622-712)
- **Issue:** The plan's tool list says `[admin_tools.add_errand_items, ..., admin_tools.fetch_routing_destinations, recipe_tools.fetch_recipe_url]` as one literal list at the `build_admin_agent` call site. But `recipe_tools` is only assigned inside the nested Playwright try block that runs AFTER the agent registration in the original code. With GA construction-time tool binding, the order must be inverted: Playwright/RecipeTools → tool list assembly → `build_admin_agent(...)`. The plan's tool-name list also references `update_inbox_status`, `delete_inbox_item`, `fetch_routing_destinations` — none of which exist on `AdminTools`. Read of `backend/src/second_brain/tools/admin.py` confirmed the actual 6 tool method names are `add_errand_items`, `add_task_items`, `get_routing_context`, `manage_destination`, `manage_affinity_rule`, `query_rules`. The plan's NOTE warns: "If a method is named slightly differently (e.g., `get_routing_destinations` vs `fetch_routing_destinations`), use the actual method name from the source." — I used the actual names.
- **Fix:** (a) Reordered: AdminTools init → Playwright try (with recipe_tools = None on failure) → `admin_agent_tools = [6 actual admin method names]` → conditional `admin_agent_tools.append(recipe_tools.fetch_recipe_url)` if recipe_tools is not None → `build_admin_agent(tools=admin_agent_tools, ...)`. (b) Used actual AdminTools method names (`manage_destination`, `manage_affinity_rule`, `query_rules`) not the plan's hypothetical names. Total: 7 tools when Playwright succeeds, 6 when it fails (graceful degradation).
- **Files modified:** `backend/src/second_brain/main.py`
- **Commit:** Folded into Task 3 commit `e89f8f3`.

## Authentication Gates

None encountered. The local main.py is intentionally not buildable end-to-end (per CONTEXT D-13 relaxation — Classifier slice still on RC); plan validation is via AST parse + grep + `test_foundry_credential_shape.py` + `test_legacy_middleware_imports_survive.py` which work without Azure connectivity.

## Known Stubs

None — all data sources are wired. The Admin Agent has up to 7 tools bound (6 + conditional recipe); the FoundryChatClient is the shared lifespan singleton from 24-04; mid-migration `app.state.admin_client = None` is intentional graceful state (not a stub — warmup/spine adapter check for it).

## Threat Flags

None — this plan does not introduce new network endpoints, auth paths, file access patterns, or trust-boundary changes. The credential class is unchanged (sync `ManagedIdentityCredential` from 24-04 is reused; no new credential construction in 24-09). Capture-trace middleware is the same package + same classes wired in 24-04 for Investigation, now also for Admin.

## Self-Check: PASSED

- `backend/src/second_brain/agents/instructions/admin.md` — FOUND (4882 bytes)
- `backend/src/second_brain/agents/admin.py` — FOUND (modified, 33 lines)
- `backend/src/second_brain/main.py` — FOUND (modified)
- Commit `a95dbc8` — FOUND
- Commit `7b0de54` — FOUND
- Commit `e89f8f3` — FOUND
