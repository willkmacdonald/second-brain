---
phase: 24-foundry-ga-migration
plan: 17
subsystem: backend
tags: [foundry-ga, inbox-document, conversation-history, p0-1-outcome, option-a, f-08, f-13, d-07b]

# Dependency graph
requires:
  - phase: 24-foundry-ga-migration
    provides: ConversationTurn model + resolve_inbox_conversation_history helper (24-15)
  - phase: 24-foundry-ga-migration
    provides: streaming adapter consumes resolve_inbox_conversation_history (24-16)
  - phase: 24-foundry-ga-migration
    provides: P0-1 OUTCOME fixture session_rehydration_fresh_process.json (24-06.5)
provides:
  - inbox_document_conversationhistory_field
  - inbox_document_foundrythreadid_retained_for_rollback
  - eval_dry_run_tools_decorator_free
affects:
  - 24-18 (delete agents/middleware.py + RCEvalAgentInvoker — InboxDocument schema now supports Option A persistence end-to-end)
  - 24-19 (warmup + main.py GA migration)
  - 24-22 (UAT — end-to-end follow-up replay verifies conversationHistory persists across turns)
  - 24-24 (post-UAT cleanup — DELETES foundryThreadId from InboxDocument)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Additive schema migration: conversationHistory ADDED alongside foundryThreadId (NOT a rename) for rollback safety during deploy window"
    - "ConversationTurn imported from cosmos/inbox_conversation_history (single canonical type source — no duplication)"
    - "No backfill script — RC docs lack client-side message list to reconstruct from; graceful continuity loss per P0-1 OUTCOME Option A trade-off"
    - "Single Write per file decorator strip pattern (continues 24-05/24-10/24-14/24-15 norm)"

key-files:
  created: []
  modified:
    - backend/src/second_brain/models/documents.py
    - backend/src/second_brain/eval/dry_run_tools.py

key-decisions:
  - "ConversationTurn IMPORTED from second_brain.cosmos.inbox_conversation_history (not relocated to models/documents.py) — 24-15 already established that module as the canonical type source; no circular-import risk because inbox_conversation_history.py only imports stdlib + pydantic"
  - "foundryThreadId field RETAINED verbatim — explicit rollback safety per P0-2 amendment. Plan 24-24 deletes it after UAT confirms GA stable. NO field deletion in this plan."
  - "NO sessionId field added — P0-1 OUTCOME (session_rehydration_fresh_process.json, recalled_pineapple=false) proved cross-process AgentSession rehydration FAILS on GA Foundry SDK 1.3.0. Field is permanently absent from the model; conversationHistory replaces its role under Option A."
  - "All 4 @tool decorators stripped from dry_run_tools.py (not just the 3 admin-side ones the executor brief mentioned) — F-08 is class-wide. EvalClassifierTools.file_capture (1) + DryRunAdminTools.{add_errand_items, add_task_items, get_routing_context} (3) = 4 total."
  - "Doc comment on conversationHistory field cites the P0-1 OUTCOME fixture by name (session_rehydration_fresh_process.json, recalled_pineapple=false) so the design driver is discoverable from the field declaration itself."
  - "Class docstring updates avoid the literal '@tool(approval_mode=' substring to satisfy grep-guard lesson from 24-09/24-10/24-14/24-15 — reworded to 'RC tool-registration decorator pattern'."

requirements-completed: [F-08, F-13, D-07b, P0-1, P0-2]

# Metrics
duration: 2min
completed: 2026-05-11
---

# Phase 24 Plan 17: InboxDocument conversationHistory + eval/dry_run_tools decorator strip — Summary

**Added `conversationHistory: list[ConversationTurn] | None = None` field to `InboxDocument` (P0-1 OUTCOME Option A), KEPT `foundryThreadId` for rollback safety, and stripped all 4 RC `@tool` decorators from `eval/dry_run_tools.py` (F-08).**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-05-11T05:38:34Z
- **Completed:** 2026-05-11T05:41:09Z
- **Tasks:** 2
- **Files modified:** 2
- **Files created:** 0

## Accomplishments

### Task 1 — InboxDocument.conversationHistory ADDITION (F-13 + D-07b + P0-1 + P0-2)

**Pre-flight verified:** `backend/tests/fixtures/foundry-probe/session_rehydration_fresh_process.json` → `recalled_pineapple: false` (P0-1 OUTCOME design driver confirmed).

- ADDED `conversationHistory: list[ConversationTurn] | None = None` field directly below `foundryThreadId` in `InboxDocument`.
- ADDED `from second_brain.cosmos.inbox_conversation_history import ConversationTurn` import at module top — uses 24-15's canonical type definition (no circular-import risk; helper module only imports stdlib + pydantic).
- ADDED 9-line doc comment above the new field citing CONTEXT D-07b, probe 4, P0-1 OUTCOME, and Option A. Names the fixture explicitly (`session_rehydration_fresh_process.json, recalled_pineapple=false`) so the design driver is discoverable from the field declaration itself.
- **KEPT** `foundryThreadId: str | None = None` verbatim — rollback safety during the migration window; plan 24-24 deletes it after UAT.
- **NO** `sessionId` field added — P0-1 OUTCOME made it permanently obsolete.
- All other InboxDocument fields preserved byte-for-byte (source, filedRecordId, status, title, clarificationText, adminProcessingStatus).
- Pydantic accepts all 4 doc shapes:
  - foundryThreadId-only (legacy RC doc)
  - conversationHistory-only (post-24-24 clean state)
  - both (transitional / post-24-17 new captures during rollback-safety window)
  - neither (brand-new capture before classifier writes thread state)

### Task 2 — eval/dry_run_tools.py decorator strip (F-08)

- Removed all **4** `@tool(approval_mode="never_require")` decorator lines:
  - `EvalClassifierTools.file_capture` (was line 30)
  - `DryRunAdminTools.add_errand_items` (was line 90)
  - `DryRunAdminTools.add_task_items` (was line 120)
  - `DryRunAdminTools.get_routing_context` (was line 143)
- Removed `from agent_framework import tool` import (unused after strip).
- **Preserved** all `Annotated[..., Field(description=...)]` parameter shapes byte-for-byte (8 Annotated invocations, 4 Field(description=...) blocks total across both classes).
- **Preserved** `__init__(self) -> None` and `__init__(self, routing_context: str) -> None` signatures (DI invariant per D-06).
- **Preserved** the entire `reset()` helper on `EvalClassifierTools` and the side-effect-capture mechanism (`last_bucket`, `last_confidence`, `last_status`, `captured_destinations`, `captured_items`, `captured_tasks`).
- Module docstring + both class docstrings updated to mention GA tool registration via `Agent(tools=[instance.method, ...])` and reference 24-12's GAEvalAgentInvoker call site. Reworded to avoid the literal `@tool(approval_mode=` substring per grep-guard lesson (24-09/24-10/24-14/24-15).
- All 4 method docstrings unchanged (they continue to serve as GA tool descriptions).

## Task Commits

| Task | Hash | Title |
|------|------|-------|
| 1 | `110d75d` | feat(24-17): add conversationHistory to InboxDocument (P0-1 OUTCOME Option A) |
| 2 | `c015058` | feat(24-17): strip RC @tool decorators from eval/dry_run_tools.py (F-08) |

(Plan metadata commit follows this summary.)

## Files Created/Modified

| Path | Change | Notes |
|------|--------|-------|
| `backend/src/second_brain/models/documents.py` | modified (+12 / -0) | ConversationTurn import + conversationHistory field + 9-line doc comment |
| `backend/src/second_brain/eval/dry_run_tools.py` | modified (+16 / -5) | 4 decorator strips + unused import removal + 3 docstring touch-ups |

## Decisions Made

1. **ConversationTurn imported (not relocated)** — 24-15 placed the model in `cosmos/inbox_conversation_history.py` and the 24-15 SUMMARY explicitly documents 24-17 as the consumer that imports from there. Inspected the helper module's imports: stdlib + pydantic only, no circular-import risk. Kept the established layout; documented in the import line.

2. **foundryThreadId field RETAINED verbatim** — P0-2 amendment makes this explicit: the field stays during the migration window for rollback safety. Plan 24-24 deletes it after UAT confirms GA stable. NO field deletion in this plan, no rename, no migration script.

3. **NO sessionId field added** — P0-1 OUTCOME's `recalled_pineapple=false` proved cross-process `AgentSession.session_id` rehydration fails on GA SDK 1.3.0. The original 24-17 plan rename, then the first amendment's additive-sessionId design, are both dead. Option A — `conversationHistory: list[ConversationTurn]` — is the locked design.

4. **All 4 dry_run_tools.py decorators stripped (not 3)** — the executor brief mentioned "3 methods (add_errand_items, add_task_items, get_routing_context)" but `EvalClassifierTools.file_capture` also carries a `@tool` decorator and is mechanically equivalent. F-08 is class-wide ("strip RC @tool from tool classes"), and the plan's acceptance criterion `! grep -q "@tool(approval_mode=" backend/src/second_brain/eval/dry_run_tools.py` requires ZERO matches across the file. Stripped all 4; documented here for traceability.

5. **Doc comment cites the fixture by name** — the field declaration's comment names `session_rehydration_fresh_process.json` and `recalled_pineapple=false` so a future reader investigating why this field exists can locate the design-driver fixture without leaving the source file. Mirrors the 24-15 pattern (helper docstring also references the fixture).

6. **Class docstring rewording to avoid `@tool(approval_mode=`** — the established grep-guard lesson from 24-09/24-10/24-14/24-15: any literal occurrence of `@tool(approval_mode=` in a module satisfies the "decorator present" grep check. Rewrote both class docstrings to say "RC tool-registration decorator pattern" instead, keeping the substring out of the file entirely.

7. **Single Write per file pattern preserved** — Tasks 1 and 2 used `Write` (full-file rewrite) to land import additions/removals atomically with field/decorator changes, avoiding the ruff auto-format trap (MEMORY.md Phase 17.1 lesson; established norm 24-05/24-10/24-14/24-15). For Task 1, adding the `ConversationTurn` import in a separate `Edit` before the field reference landed would have caused ruff to strip the import. Single Write puts both the import and the usage on disk together.

## Deviations from Plan

### Auto-fixed Issues

**None.** Both tasks executed exactly as the plan specifies. No bugs, no missing critical functionality, no blockers, no architectural changes.

### Documentation note

The executor brief said "3 methods" for the decorator strip, but the plan's acceptance criterion is class-wide (`! grep -q "@tool(approval_mode="`). Stripped all 4 decorators (the classifier's `file_capture` plus the 3 admin-side methods). Not a deviation from the plan itself — the plan's verify check is the authoritative gate, and the executor brief was a slightly truncated paraphrase. Documented here for traceability.

### Out-of-scope discoveries

`mcp/uv.lock` shows uncommitted modification (pre-existing on `main`, not touched by this plan). Per SCOPE BOUNDARY, not investigated. Same state as 24-15 / 24-16 SUMMARYs documented.

## Authentication Gates

None encountered. All verification ran locally:
- `uv run python -c "..."` smoke tests for InboxDocument 4-shape acceptance
- `uv run pytest tests/test_inbox_dual_read.py tests/test_legacy_middleware_imports_survive.py tests/test_foundry_credential_shape.py -x` → 12 passed
- `uv run pytest tests/test_eval.py tests/test_eval_dry_run.py tests/test_eval_metrics.py -x` → 37 passed
- `uv run python -c "from second_brain.eval.dry_run_tools import ...; asyncio.run(ec.file_capture(...))"` → coroutines confirmed; side-effect capture works

## Known Stubs

None. The `conversationHistory` field is consumed end-to-end:
- READ via `resolve_inbox_conversation_history()` (24-15) — wired into `streaming/adapter.py` follow-up flow (24-16).
- WRITE via the streaming adapter's race-safe upsert (24-16) — re-reads doc before writing to coexist with `file_capture`'s classification field writes.

The 24-15 SUMMARY's note about `app.state.classifier_client = None` being mid-migration state per CONTEXT D-13 still applies (cleared in 24-19); not a stub of this plan.

## Threat Flags

None — this plan does not introduce new network endpoints, auth paths, file access patterns, or trust-boundary changes.

- `models/documents.py` is a Pydantic schema file. Adding an optional list field changes no I/O surface.
- `eval/dry_run_tools.py` is a test/eval helper class that captures predictions in memory; no Cosmos writes, no network calls, no new code paths.
- The added doc comment names a fixture file in the test corpus — no PII.
- The `conversationHistory` field stores user/assistant message text on the Inbox doc. This is the same trust boundary as `rawText` (already on `BaseDocument`) — no new sensitivity tier introduced.

## TDD Gate Compliance

Plan type is `execute` (not `tdd`). No RED/GREEN commits required. The Pydantic field acceptance test (4-shape smoke test from the plan's `<action>` step 8) was executed inline as part of the verify gate, not committed as a separate test file. Existing regression suite (`test_inbox_dual_read.py` 7 tests) already pins the schema contract from the helper side — those tests stay GREEN with the new field.

## Verification

### Task 1 (models/documents.py)

| Criterion | Status |
|-----------|--------|
| `grep -q "conversationHistory" backend/src/second_brain/models/documents.py` | PASS (1 field declaration) |
| `grep -q "from second_brain.cosmos.inbox_conversation_history import ConversationTurn"` | PASS |
| `! grep -q "sessionId" backend/src/second_brain/models/documents.py` | PASS (0 matches, P0-1 OUTCOME) |
| `grep -q "foundryThreadId" backend/src/second_brain/models/documents.py` | PASS (3 mentions: field + doc comment x2) |
| `grep -E "P0-1 OUTCOME\|Option A" backend/src/second_brain/models/documents.py` | PASS (2 lines) |
| InboxDocument accepts foundryThreadId-only | PASS (m1.foundryThreadId=='legacy', m1.conversationHistory is None) |
| InboxDocument accepts conversationHistory-only | PASS (m2.conversationHistory[0].content=='hi') |
| InboxDocument accepts both | PASS (m3.foundryThreadId=='legacy' AND len(m3.conversationHistory)==1) |
| InboxDocument accepts neither | PASS (m4.foundryThreadId is None AND m4.conversationHistory is None) |
| `from second_brain.models.documents import InboxDocument` succeeds | PASS |
| `InboxDocument.model_fields` includes `conversationHistory` | PASS |

### Task 2 (eval/dry_run_tools.py)

| Criterion | Status |
|-----------|--------|
| `! grep -q "@tool(approval_mode=" backend/src/second_brain/eval/dry_run_tools.py` | PASS (0 matches, was 4) |
| `! grep -q "from agent_framework import tool" backend/src/second_brain/eval/dry_run_tools.py` | PASS (0 matches) |
| `grep -q "class EvalClassifierTools"` | PASS (1) |
| `grep -q "class DryRunAdminTools"` | PASS (1) |
| `grep -c "Annotated\["` | PASS (8 — all parameter shapes preserved) |
| `grep -c "Field(description="` | PASS (4 — 1 in classifier, 3 in admin tools) |
| `from second_brain.eval.dry_run_tools import EvalClassifierTools, DryRunAdminTools` succeeds | PASS |
| All 4 methods are async coroutines (verified via `inspect.iscoroutinefunction`) | PASS |
| `EvalClassifierTools.file_capture()` runtime callable + captures state | PASS |
| Eval regression suite (37 tests across test_eval.py / test_eval_dry_run.py / test_eval_metrics.py) | PASS (37/37) |
| Phase 24 dual-read suite still GREEN (test_inbox_dual_read.py 7 tests) | PASS (7/7) |

### Phase 24 AST-scan red test (test_no_rc_imports_after_cleanup.py)

```
$ uv run pytest tests/test_no_rc_imports_after_cleanup.py
1 failed (expected RED until 24-19). Remaining offender files (3):
  - second_brain/eval/invoker.py    (cleared in 24-19)
  - second_brain/main.py            (cleared in 24-19)
  - second_brain/warmup.py          (cleared in 24-19)
```

**Net offender count: 4 → 3.** 24-16 cleared `streaming/adapter.py` between 24-15 and now. `dry_run_tools.py` was never in the offender list because the AST scan tracks `AzureAIAgentClient` identifier references, not `agent_framework.tool` imports — so this plan didn't move the count, but it ALSO didn't add to it (no new offenders introduced).

## Next Phase Readiness

**Plan 24-18 (delete agents/middleware.py + RCEvalAgentInvoker):**
- Inbox schema now supports Option A persistence end-to-end (this plan).
- 24-16 already wired the streaming adapter to read/write conversationHistory.
- 24-18 can proceed with deleting the RC eval invoker and switching the classifier eval call to the GA invoker.

**Plan 24-22 (UAT):**
- Will verify end-to-end follow-up replay: capture #1 writes conversationHistory; capture #2 (follow-up with foundryThreadId reference) reads via `resolve_inbox_conversation_history()` and passes message list to `agent.run(messages=[...])`. Counter-factual: a turn-2 "what did I just tell you?" should now succeed (vs P0-1 OUTCOME baseline `recalled_pineapple=false`).
- The 4 doc shapes Pydantic-accepts here are the same 4 shapes the helper handles per 24-15's 7 RED tests; behaviorally consistent.

**Plan 24-24 (post-UAT cleanup):**
- DELETES `foundryThreadId` field from InboxDocument. The doc comment on `conversationHistory` instructs this explicitly.
- Plan 24-24 also runs a Cosmos cleanup to drop the column from existing docs (if any retain it post-UAT).

## Self-Check: PASSED

**Files claimed modified:**
- [x] FOUND: `backend/src/second_brain/models/documents.py` (modified, +12/-0)
- [x] FOUND: `backend/src/second_brain/eval/dry_run_tools.py` (modified, +16/-5)

**Commits claimed:**
- [x] FOUND: `110d75d` (Task 1: InboxDocument conversationHistory)
- [x] FOUND: `c015058` (Task 2: dry_run_tools.py decorator strip)

**Acceptance grep claims:**
- [x] FOUND: `conversationHistory` field in models/documents.py (1 declaration)
- [x] FOUND: `ConversationTurn` import in models/documents.py
- [x] FOUND: 0 occurrences of `sessionId` in models/documents.py
- [x] FOUND: 3 mentions of `foundryThreadId` in models/documents.py (field + doc comment refs)
- [x] FOUND: 0 occurrences of `@tool(approval_mode=` in eval/dry_run_tools.py
- [x] FOUND: 0 occurrences of `from agent_framework import tool` in eval/dry_run_tools.py
- [x] FOUND: 8 `Annotated[` parameter shapes preserved in eval/dry_run_tools.py
- [x] FOUND: 4 `Field(description=` blocks preserved in eval/dry_run_tools.py

**Test claims:**
- [x] 7/7 pass: tests/test_inbox_dual_read.py
- [x] 37/37 pass: tests/test_eval.py + test_eval_dry_run.py + test_eval_metrics.py
- [x] 4-shape Pydantic smoke test (m1/m2/m3/m4) → all asserts hold
- [x] AST-scan offender count 4 → 3 (24-16 cleared streaming/adapter.py; this plan introduced 0 new offenders)

Verification commands executed:
```bash
grep -c "@tool(approval_mode=" backend/src/second_brain/eval/dry_run_tools.py
# 0 (was 4)

cd backend && uv run python -c "from second_brain.models.documents import InboxDocument; from second_brain.cosmos.inbox_conversation_history import ConversationTurn; ..."
# OK

cd backend && uv run pytest tests/test_inbox_dual_read.py tests/test_legacy_middleware_imports_survive.py tests/test_foundry_credential_shape.py -x
# 12 passed

cd backend && uv run pytest tests/test_eval.py tests/test_eval_dry_run.py tests/test_eval_metrics.py -x
# 37 passed

git log --oneline -2
# c015058 110d75d
```

---

*Phase: 24-foundry-ga-migration*
*Plan: 24-17*
*Completed: 2026-05-11*
