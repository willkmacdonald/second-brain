---
phase: 25-admin-inbox-soft-delete-30-day-retention-inserted
plan: 01
type: execute
status: complete
completed: 2026-05-16
subsystem: backend-admin-handoff
tags:
  - soft-delete
  - cosmos-ttl
  - admin-agent-lifecycle
  - context-var
requires:
  - 25-02-PLAN.md  # Settings field + Cosmos defaultTtl=-1
provides:
  - admin-inbox-soft-delete-branch-b
  - admin-inbox-item-id-contextvar-shell
affects:
  - 25-03-PLAN.md  # dismiss_admin_notification will follow same pattern
  - 25-04-PLAN.md  # add_errand_items / add_task_items read admin_inbox_item_id_var
tech-stack:
  added: []
  patterns:
    - read -> mutate -> upsert with **th=trace_headers (canonical idiom from Branch A)
    - module-level ContextVar pattern (mirrors tools/classification.py)
    - atomic multi-field upsert body (status + adminProcessingStatus + ttl)
key-files:
  created: []
  modified:
    - backend/src/second_brain/processing/admin_handoff.py
    - backend/src/second_brain/tools/admin.py
    - backend/tests/test_admin_handoff.py
decisions:
  - "Used a `_PHASE25_REFS` module-level sentinel during multi-step edit to defeat auto-format import stripping (removed once usages landed) — Landmine #5 mitigation."
  - "Renamed test_delete_not_found_is_non_fatal / test_delete_failure_is_non_fatal to test_filing_not_found_is_non_fatal / test_filing_failure_is_non_fatal — the failure points now sit on read_item (filing read) and upsert_item (filing write), not delete_item."
metrics:
  duration: "approx 25 minutes"
  tasks: 2
  files-modified: 3
requirements:
  - REQ-SD-01  # status='filed' + ttl on inbox doc via upsert
  - REQ-SD-02  # (already addressed in Plan 02 infra step; Plan 01 consumes it)
  - REQ-SD-03  # ttl = settings.inbox_filed_retention_days * 86400
  - REQ-SD-04  # phone inbox excludes filed (Plan 03; Plan 01 stamps the marker)
commits:
  - 1f434ce  # test(25-01): RED tests
  - 01cc699  # feat(25-01): GREEN soft-delete swap
---

# Phase 25 Plan 01: Admin Inbox Soft-Delete (Branch B) Summary

Replaced the hard `delete_item` call in `processing/admin_handoff.py` Branch B (the simple-confirmation success path) with a `read -> mutate -> upsert` that atomically sets `status="filed"` + `adminProcessingStatus="completed"` + `ttl` in one body. Wired the `admin_inbox_item_id_var` ContextVar shell into `tools/admin.py` and set it from `admin_handoff.py` before `agent.run` so Plan 04 read sites can stamp backlinks. Test file modernized — 5 new tests + 5 renames + 1 extension keep the failed-path orthogonality intact.

## What changed

### 1. `backend/src/second_brain/processing/admin_handoff.py`

- **Imports (lines 24-32)** — added `from second_brain.config import get_settings` and merged `admin_inbox_item_id_var` into the existing `from second_brain.tools.admin import ...` line.
- **ContextVar set (line 220)** — `admin_inbox_item_id_var.set(inbox_item_id)` lands alongside `capture_trace_id_var.set(...)` before `agent.run`. Set unconditionally (no `if inbox_item_id` guard) because `inbox_item_id` is a required parameter of `process_admin_capture`.
- **Branch B swap (lines 400-437)** — the `else:` arm that previously called `inbox_container.delete_item(...)` now does:
  ```python
  settings = get_settings()
  ttl_seconds = settings.inbox_filed_retention_days * 86400
  doc = await inbox_container.read_item(item=inbox_item_id, partition_key="will", **th)
  doc["status"] = "filed"
  doc["adminProcessingStatus"] = "completed"
  doc["ttl"] = ttl_seconds
  await inbox_container.upsert_item(body=doc, **th)
  logger.info("Filed processed inbox item %s. outcome=filed", inbox_item_id, extra=log_extra)
  ```
  Plus a `CosmosResourceNotFoundError` branch (logs "already deleted") and a generic exception branch (logs "Failed to file ...") — both non-fatal because errand items are the durable output. **Branch A unchanged.** `_mark_inbox_failed` unchanged (preserves Phase 24 backlog orthogonality).

### 2. `backend/src/second_brain/tools/admin.py`

- **`import contextvars`** added to the imports block (line 16).
- **ContextVar definition (lines 33-41)** — `admin_inbox_item_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("admin_inbox_item_id_var", default=None)`. Defined at module level after the logger but before `build_routing_context`. Plan 04 will add the read sites in `add_errand_items` / `add_task_items`.

### 3. `backend/tests/test_admin_handoff.py`

10 total test changes (5 renamed/rewritten + 5 new):

| Test                                              | Type      | Purpose                                                                                                |
| ------------------------------------------------- | --------- | ------------------------------------------------------------------------------------------------------ |
| `test_simple_confirmation_files_inbox_item`       | renamed   | TWO upserts (pending + filing); filing body has status=filed, adminProcessingStatus=completed, ttl>0; delete_item NOT called |
| `test_filed_doc_ttl_matches_settings`             | new       | ttl == `get_settings().inbox_filed_retention_days * 86400` == 30 * 86400 (2592000) default             |
| `test_filing_writes_all_fields_atomically`        | new       | All three keys (status, adminProcessingStatus, ttl) present in the SAME upsert body — Landmine #4      |
| `test_agent_error_sets_status_to_failed`          | extended  | Added `assert last_body.get("status") != "filed"` orthogonality assertion                              |
| `test_agent_error_does_not_file_inbox_item`       | new       | Every upsert body in the failed path MUST NOT have status="filed" (REQ-SD-04)                          |
| `test_admin_handoff_sets_inbox_item_id_contextvar`| new       | Captures `admin_inbox_item_id_var.get()` inside the agent.run side_effect; asserts it equals the inbox_item_id arg |
| `test_filing_not_found_is_non_fatal`              | renamed   | Was `test_delete_not_found_is_non_fatal` — failure point moved from delete_item to filing read_item    |
| `test_filing_failure_is_non_fatal`                | renamed   | Was `test_delete_failure_is_non_fatal` — failure point moved to filing upsert_item                     |
| `test_output_tool_called_files_inbox_item`        | renamed   | Was `..._deletes_inbox_item` — asserts filing upsert instead of delete_item.assert_called_once         |
| `test_tool_call_still_files`                      | renamed   | Was `test_tool_call_still_deletes` — asserts filing upsert + delete_item.assert_not_called             |
| `test_intermediate_tool_retry_succeeds`           | edited    | Replaced delete_item assertion with filing upsert assertion                                            |
| `test_batch_one_failure_does_not_block_second`    | edited    | Replaced `delete_item.call_count >= 1` with filing-body-present assertion + `delete_item.assert_not_called()` |

## Acceptance criteria check

| Criterion                                                                                          | Status  |
| -------------------------------------------------------------------------------------------------- | ------- |
| Branch B of admin_handoff.py now soft-deletes (status="filed" + adminProcessingStatus="completed" + ttl) | PASS    |
| All three fields land in the SAME upsert body                                                       | PASS    |
| Failed path (agent.run exception + `_mark_inbox_failed`) does NOT touch status="filed"             | PASS    |
| `admin_inbox_item_id_var` ContextVar shell exists in tools/admin.py                                | PASS    |
| `admin_handoff` sets `admin_inbox_item_id_var` before `agent.run`                                  | PASS    |
| ttl = `settings.inbox_filed_retention_days * 86400` (default 2592000)                              | PASS    |
| `outcome=filed` log key exists exactly once                                                        | PASS    |
| `outcome=processed` log key gone                                                                   | PASS    |
| `delete_item` references gone from admin_handoff.py                                                | PASS    |
| `pytest tests/test_admin_handoff.py` exits 0 — 23/23 GREEN                                         | PASS    |
| `pytest tests/test_config.py` (Plan 02 still green)                                                | PASS    |

## Verification commands run

```bash
cd backend && uv run pytest tests/test_admin_handoff.py --tb=short -q
# 23 passed
cd backend && uv run pytest tests/test_admin_handoff.py tests/test_config.py --tb=short -q
# 27 passed
```

Broader test suite (excluding Plans 03/04 files): 460 passed, 2 unrelated pre-existing failures in `test_health.py` (Foundry connectivity health assertions — touched last in commit `e0eba5b` for Phase 6, not regressed by Plan 25-01), and 2 import errors in `test_classifier_integration.py` + `test_event_tracing.py` (missing `AzureAIAgentClient` from `agent_framework.azure` and `stream_voice_capture` from `streaming.adapter` — both pre-existing environmental gaps in the worktree dependency snapshot, not caused by this plan).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Auto-format stripped unused imports during multi-step edit**

- **Found during:** Task 2 sub-step 2.2 (admin_handoff.py imports + usages).
- **Issue:** When the imports-only edit landed first (before the usage edits), ruff/auto-format hook stripped both `from second_brain.config import get_settings` and the new `admin_inbox_item_id_var` import alias because they were temporarily unused. Confirmed by the PostToolUse hook output and a subsequent grep that returned empty.
- **Fix:** Re-added the imports in the same Edit that added a `_PHASE25_REFS = (get_settings, admin_inbox_item_id_var)` module-level tuple — a single-line "usage" anchor that defeats the unused-import strip. Once the real usages (ContextVar `.set()` call and Branch B `get_settings()` call) landed in subsequent edits, removed the sentinel.
- **Files modified:** `backend/src/second_brain/processing/admin_handoff.py` (only).
- **Commit:** Folded into `01cc699` (Task 2 GREEN commit).

**2. [Rule 1 - Bug] Two delete-error tests were obsolete after Branch B swap**

- **Found during:** Task 1 sub-step 1.7 (the 5 other delete-assertion sites).
- **Issue:** `test_delete_not_found_is_non_fatal` and `test_delete_failure_is_non_fatal` (lines 296-328 of the old file) configured `container.delete_item = AsyncMock(side_effect=...)` to verify error swallowing. After the Branch B swap, `delete_item` is never called — these tests would pass trivially but for the wrong reason. The error-swallowing contract moved to the filing read_item / upsert_item calls.
- **Fix:** Renamed to `test_filing_not_found_is_non_fatal` (configures the SECOND `read_item` call to raise `CosmosResourceNotFoundError`) and `test_filing_failure_is_non_fatal` (configures the SECOND `upsert_item` call to raise generic Exception). Both still assert no propagation. This preserves the original test intent while exercising the new code path.
- **Files modified:** `backend/tests/test_admin_handoff.py`.
- **Commit:** Folded into `1f434ce` (Task 1 RED commit).

**3. [Rule 3 - Blocking] Test environment setup required dev-dependencies install + uv.lock revert**

- **Found during:** First pytest invocation in Task 1.
- **Issue:** Worktree's backend venv had no `pytest`, `pytest-asyncio`, or `mcp[cli]` installed. The instructions explicitly authorized installing these via `uv add --dev` but required reverting `pyproject.toml` and `uv.lock` before commit.
- **Fix:** Ran `uv sync` then `uv add --dev pytest pytest-asyncio "mcp[cli]"`. After all production commits landed, ran `git checkout backend/pyproject.toml backend/uv.lock` to remove those changes from the final tree. Final `git status --short` is clean.
- **Files modified:** none (changes reverted before final commit).
- **Commit:** n/a.

No architectural changes (Rule 4) needed.

## Known Stubs

None. The `admin_inbox_item_id_var` ContextVar is a shell — but Plan 04's responsibility is to wire the READ sites (in `add_errand_items` and `add_task_items`) and add the `sourceInboxItemId` / `sourceCaptureTraceId` Pydantic fields. Plan 01's contract was the DEFINITION + SET, which is fully wired and proven by `test_admin_handoff_sets_inbox_item_id_contextvar`.

## Threat Flags

None. The Phase 25 threat model in 25-01-PLAN.md is fully addressed:

| Threat ID    | Status   | Evidence                                                                                       |
| ------------ | -------- | ---------------------------------------------------------------------------------------------- |
| T-25-01-01   | mitigated | `test_filing_writes_all_fields_atomically` + `test_simple_confirmation_files_inbox_item` enforce atomicity |
| T-25-01-02   | mitigated | `test_agent_error_does_not_file_inbox_item` + extended `test_agent_error_sets_status_to_failed` |
| T-25-01-03   | mitigated | Plan 02's `Field(ge=1)` on `inbox_filed_retention_days` is in place — startup fails on 0       |
| T-25-01-04   | accept    | ContextVar lifecycle scoped to asyncio task — no cross-request leak risk                       |
| T-25-01-05   | mitigated | `logger.info("Filed processed inbox item %s. outcome=filed", ...)` exists at line 419          |
| T-25-01-06   | n/a       | No new external integration points                                                             |

## TDD Gate Compliance

| Gate     | Commit       | Marker                                                                                |
| -------- | ------------ | ------------------------------------------------------------------------------------- |
| RED      | `1f434ce`    | `test(25-01): RED — Phase 25 soft-delete + ContextVar tests for admin_handoff`        |
| GREEN    | `01cc699`    | `feat(25-01): GREEN — soft-delete admin inbox via status=filed + ttl upsert`          |
| REFACTOR | (skipped)    | No refactor needed — the new Branch B mirrors Branch A's idiom exactly (read-mutate-upsert with `**th`); no duplicated state to extract. |

## Plan 04 unblocked

- `admin_inbox_item_id_var` ContextVar exists in `tools/admin.py` (lines 33-41).
- `admin_handoff.process_admin_capture` sets it before `agent.run` (line 220), unconditional and proven by test.
- Plan 04 only needs to: (a) import `admin_inbox_item_id_var` in the tool methods, (b) call `.get()` plus `capture_trace_id_var.get() or None` to read both, (c) pass them as new optional fields when constructing `ErrandItem` / `TaskItem`. The plumbing for the SET side is fully landed.

## Self-Check

- [x] `backend/src/second_brain/processing/admin_handoff.py` exists with `status="filed"` + `adminProcessingStatus="completed"` + `ttl` upsert in Branch B
- [x] `backend/src/second_brain/tools/admin.py` exists with `admin_inbox_item_id_var` ContextVar definition
- [x] `backend/tests/test_admin_handoff.py` contains all 5 new test names + 5 renamed/extended sites
- [x] Commits `1f434ce` and `01cc699` exist in git log
- [x] `pytest tests/test_admin_handoff.py` exits 0
- [x] No modifications to STATE.md, ROADMAP.md, pyproject.toml, or uv.lock in the final tree

## Self-Check: PASSED
