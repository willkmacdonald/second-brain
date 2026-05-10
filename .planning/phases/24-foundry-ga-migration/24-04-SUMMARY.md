---
phase: 24-foundry-ga-migration
plan: 04
subsystem: backend/agents
tags: [foundry-ga, investigation-agent, lifespan, middleware, p1-3, p1-5]
requires:
  - foundry_chat_client_constructor_shape  # CONFIG-DELTAS Probe 5
  - capture_trace_middleware_package       # 24-03 deliverable
  - investigation_instructions_in_repo     # 24-03 deliverable
  - foundry_model_setting                  # 24-02 deliverable
  - sync_managed_identity_credential       # P1-5 lock
provides:
  - build_investigation_agent_factory
  - load_instructions_helper
  - investigation_agent_ga_lifespan
  - foundry_chat_client_singleton
  - p1_5_red_test_green
affects:
  - admin_lifespan_unchanged_until_24_09
  - classifier_lifespan_unchanged_until_24_14
  - warmup_will_skip_investigation_until_24_19
  - spine_foundry_adapter_skips_investigation_segment_mid_migration
tech-stack:
  added:
    - agent_framework.Agent
    - agent_framework_foundry.FoundryChatClient
    - azure.identity.ManagedIdentityCredential (sync)
  patterns:
    - lifespan_singleton_chat_client
    - factory_function_for_agent_construction
    - middleware_via_constructor_kwarg
    - instructions_loaded_from_repo_md
key-files:
  created:
    - backend/tests/test_foundry_credential_shape.py
  modified:
    - backend/src/second_brain/agents/investigation.py
    - backend/src/second_brain/main.py
decisions:
  - "P1-5: sync azure.identity.ManagedIdentityCredential (NOT azure.identity.aio variant) per CONFIG-DELTAS verbatim and operator lock"
  - "P1-3: middleware imports use second_brain.agents.agent_middleware.capture_trace (distinct from legacy agents/middleware.py)"
  - "Investigation lifespan no longer sets app.state.investigation_agent_id; FoundryAgentAdapter for Investigation skips wiring during migration window"
  - "warmup _make_investigation_client factory left in place (24-19 scope); warmup will skip Investigation until then because app.state.investigation_client is no longer set"
metrics:
  duration_minutes: ~30
  completed: 2026-05-10
  tasks: 3
  files_created: 1
  files_modified: 2
  ast_offender_files_dropped: 1
---

# Phase 24 Plan 04: Migrate Investigation Agent to GA Foundry — Summary

**One-liner:** Replaced Investigation's RC `AzureAIAgentClient` with GA `Agent(client=FoundryChatClient(...))` constructed via a `build_investigation_agent` factory; wired capture-trace middleware; landed a sync `ManagedIdentityCredential` AST guard.

## Scope

- `backend/src/second_brain/agents/investigation.py`: replaced `ensure_investigation_agent` (portal-shell creator) with `build_investigation_agent` factory + `load_instructions` helper. RC import dropped.
- `backend/src/second_brain/main.py`: added a single shared `FoundryChatClient` (sync `ManagedIdentityCredential`); replaced the Investigation lifespan slice with the GA factory call wired to capture-trace middleware. Admin and Classifier slices still use `AzureAIAgentClient` — that's expected and migrates in 24-09 / 24-14.
- `backend/tests/test_foundry_credential_shape.py`: NEW — P1-5 invariant guard (AST-scans `main.py` for sync credential class).

## What Changed

### 1. `agents/investigation.py` — GA factory shape

Before (RC):
- `ensure_investigation_agent(foundry_client, stored_agent_id)` — talks to Foundry portal, creates a portal agent shell, expected the operator to set instructions in the portal.

After (GA):
- `load_instructions(name)` — reads `agents/instructions/{name}.md` from repo (D-02). Length 18,005 chars for Investigation.
- `build_investigation_agent(chat_client, tools, middleware) -> Agent` — constructs `Agent(client=chat_client, instructions=..., tools=..., middleware=...)`.

The portal-shell creation pattern (F-19) is gone. The file no longer references `AzureAIAgentClient`, `create_agent`, or "SET INSTRUCTIONS IN AI FOUNDRY PORTAL".

### 2. `main.py` lifespan — GA wiring

Imports added:
```python
from agent_framework_foundry import FoundryChatClient
from azure.identity import ManagedIdentityCredential   # SYNC (P1-5)
from second_brain.agents.agent_middleware.capture_trace import (
    CaptureTraceAgentMiddleware,
    CaptureTraceFunctionMiddleware,
)
from second_brain.agents.investigation import build_investigation_agent
```

Imports kept (Admin/Classifier still use them):
- `from agent_framework.azure import AzureAIAgentClient` (24-09 / 24-14 remove these slices)
- `from second_brain.agents.middleware import AuditAgentMiddleware, ToolTimingMiddleware` (24-09 / 24-14 remove these wrappings; 24-18 deletes legacy middleware.py)

Imports removed:
- `from second_brain.agents.investigation import ensure_investigation_agent` (function no longer exists)

Lifespan body:

**Foundry probe block** — wrapped in fail-fast try/except. Constructs and stores the single shared chat client at `app.state.foundry_chat_client`. RC `AzureAIAgentClient` probe block KEPT alongside (used by Admin/Classifier through 24-09/24-14).

```python
chat_client = FoundryChatClient(
    project_endpoint=settings.azure_ai_project_endpoint,
    model=settings.foundry_model,
    credential=ManagedIdentityCredential(),  # SYNC
)
app.state.foundry_chat_client = chat_client
```

**Investigation slice** — replaced. Before: `investigation_client = AzureAIAgentClient(agent_id=..., middleware=[Audit, ToolTiming])` + `app.state.investigation_tools = [...9 methods]`. After: `investigation_agent = build_investigation_agent(chat_client, tools=[...9 methods], middleware=[CaptureTraceAgentMiddleware(), CaptureTraceFunctionMiddleware()])` stored at `app.state.investigation_agent`. Non-fatal try/except preserved.

Also dropped (no longer needed by Investigation):
- `app.state.investigation_agent_id` — Foundry no longer needs a portal agent ID since the agent is constructed in-process.
- `app.state.investigation_client` — replaced by `app.state.investigation_agent`.
- `app.state.investigation_tools` (the list-of-method-references shape) — tools are now bound at Agent construction time.

Kept untouched (24-19 scope):
- `_make_investigation_client(...)` warmup factory at lines ~810-822 — leave alone per plan instruction.
- Warmup loop registration of Investigation will skip naturally because the `if getattr(app.state, "investigation_client", None) is not None` guard now sees None.

**Spine wiring** — the spine `FoundryAgentAdapter` for Investigation reads `getattr(app.state, "investigation_agent_id", None)` at line 212. Since this plan no longer sets that attribute, the adapter's `if agent_id:` guard skips wiring the Investigation segment during the migration window. Admin and Classifier adapters still wire correctly (they keep their `_agent_id`).

### 3. P1-5 red test — `test_foundry_credential_shape.py`

Two sub-tests, both green after Task 3:
- `test_foundry_chat_client_uses_sync_managed_identity` — instantiates the sync class and asserts it's not the `aio` variant.
- `test_main_py_imports_sync_managed_identity` — AST-scans `main.py` for `ManagedIdentityCredential` imports; asserts the import comes from `azure.identity` (sync), not `azure.identity.aio`.

The test was committed in Task 1 with sub-test 2 failing (no main.py import yet); Task 3 turned it green.

## Commits

| Task | Hash       | Title                                                            |
| ---- | ---------- | ---------------------------------------------------------------- |
| 1    | `d4bf6d6`  | test(24-04): land foundry credential shape red test              |
| 2    | `90166ec`  | feat(24-04): migrate Investigation Agent to GA Foundry           |
| 3    | `2678305`  | feat(24-04): wire Investigation lifespan with FoundryChatClient  |

## Verification

All success criteria pass:

| Criterion                                                                 | Status |
| ------------------------------------------------------------------------- | ------ |
| `agents/investigation.py` uses `Agent(client=FoundryChatClient(...))`     | PASS   |
| `agents/investigation.py` has NO `AzureAIAgentClient` import              | PASS   |
| `main.py` Investigation lifespan uses GA pattern                          | PASS   |
| `main.py` Admin + Classifier slices STILL use `AzureAIAgentClient`        | PASS (expected mid-migration) |
| `main.py` imports sync `azure.identity.ManagedIdentityCredential`        | PASS   |
| `main.py` does NOT import `azure.identity.aio.ManagedIdentityCredential` | PASS   |
| Capture-trace middleware wired into Agent                                 | PASS   |
| `test_foundry_credential_shape.py` exists; both sub-tests PASS            | PASS   |
| `test_legacy_middleware_imports_survive.py` still PASSES                  | PASS   |

### AST scan offender count delta

`tests/test_no_rc_imports_after_cleanup.py` is still expected RED at this point (the plan only clears Investigation slices). Offender file count drop:
- Before this plan: 9 files (`admin.py`, `classifier.py`, `eval/runner.py`, `investigation.py`, `main.py`, `processing/admin_handoff.py`, `streaming/adapter.py`, `streaming/investigation_adapter.py`, `tools/investigation.py`, `warmup.py`).

Wait — that's actually 10 files. Let me recount from the actual test output:

Before (baseline at f3c2081):
- `agents/admin.py`, `agents/classifier.py`, `agents/investigation.py`, `eval/runner.py`, `main.py`, `processing/admin_handoff.py`, `streaming/adapter.py`, `streaming/investigation_adapter.py`, `tools/investigation.py`, `warmup.py` = 10 files (30 entries: 3 per file).

Wait the earlier output showed 9 files because it stopped at first failure. Let me note what actually changed:

After 24-04:
- `agents/investigation.py` — **CLEARED** (was emitting `AzureAIAgentClient` via `TYPE_CHECKING` import; now imports `FoundryChatClient` only).
- `main.py` — **STILL FLAGGED** because Admin/Classifier slices keep `AzureAIAgentClient`.

So the plan's effect: `agents/investigation.py` cleared from offender list. The remaining 9 files are migrated by:
- `agents/admin.py`, `processing/admin_handoff.py`, `streaming/adapter.py` — 24-09 (Admin)
- `agents/classifier.py`, `eval/runner.py`, `streaming/adapter.py` — 24-14 (Classifier; eval invoker introduced 24-12 then deleted by 24-14)
- `streaming/investigation_adapter.py`, `tools/investigation.py` — 24-05 + 24-06 (Investigation streaming adapter rewrite + tool decorator strip)
- `warmup.py` — 24-19 (warmup migration)
- `main.py` — naturally clears as Admin/Classifier slices migrate

The "21 -> ~15" approximation in the executor prompt is loose; the actual effect of 24-04 is to clear `agents/investigation.py` from the offender file list (a single-file drop). The cumulative drop happens incrementally across the rest of the wave.

## Deviations from Plan

None — plan executed exactly as written. Auto-format trap was anticipated by the plan instruction; managed by ordering Edit operations so usages exist before imports.

## Authentication Gates

None encountered. The local main.py is intentionally not buildable (Azure Monitor needs an instrumentation key); plan validation is via AST parse + grep + `test_foundry_credential_shape.py` which works without Azure connectivity.

## Known Stubs

None — all data sources are wired. Investigation Agent has 9 tools bound; the FoundryChatClient is constructed with sync credential and shared across the lifespan; the streaming adapter rewrite (which actually consumes `app.state.investigation_agent`) lands in 24-05.

## Threat Flags

None — this plan does not introduce new network endpoints, auth paths, or trust-boundary changes. The credential class swap (RC `AsyncDefaultAzureCredential` → GA `ManagedIdentityCredential`) is documented in CONFIG-DELTAS as the expected production posture; Container App managed identity already has `Azure AI User` role.

## Self-Check: PASSED

- `backend/tests/test_foundry_credential_shape.py` — FOUND
- `backend/src/second_brain/agents/investigation.py` — FOUND (modified)
- `backend/src/second_brain/main.py` — FOUND (modified)
- Commit `d4bf6d6` — FOUND
- Commit `90166ec` — FOUND
- Commit `2678305` — FOUND
