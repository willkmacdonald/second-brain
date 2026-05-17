---
phase: 25
slug: admin-inbox-soft-delete-30-day-retention-inserted
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-16
---

# Phase 25 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (existing — `backend/tests/`) |
| **Config file** | `backend/pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `cd backend && pytest tests/test_admin_handoff.py tests/test_admin_tools.py tests/test_inbox_api.py -x` |
| **Full suite command** | `cd backend && pytest tests/ -x --tb=short` |
| **Estimated runtime** | ~3 sec quick / ~30 sec full |

---

## Sampling Rate

- **After every task commit:** Run quick command above (~3 sec)
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds for quick, 30 sec for full

---

## Per-Task Verification Map

Requirements derived from CONTEXT.md decisions + ROADMAP success criteria + RESEARCH.md landmines. Pseudo REQ-IDs follow `REQ-SD-XX` (Soft-Delete) and `REQ-BL-XX` (Backlinks) — Phase ROADMAP requirements field is TBD.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 25-01-XX | 01 | 1 | REQ-SD-01 (admin_handoff Branch B sets status="filed" + ttl + adminProcessingStatus="completed" instead of delete_item) | — | Soft-delete only on success path | unit | `pytest tests/test_admin_handoff.py::test_simple_confirmation_files_inbox_item -x` | ❌ W0 (rename `test_simple_confirmation_deletes_inbox_item`) | ⬜ pending |
| 25-01-XX | 01 | 1 | REQ-SD-02 (per-doc ttl = settings.inbox_filed_retention_days * 86400; default 2592000) | — | TTL durable; no immediate-purge bug | unit | `pytest tests/test_admin_handoff.py::test_filed_doc_ttl_matches_settings -x` | ❌ W0 (new) | ⬜ pending |
| 25-01-XX | 01 | 1 | REQ-SD-03 (filing sets status, adminProcessingStatus, ttl in SAME upsert body — atomicity) | — | No partial-write re-fire bug | unit | `pytest tests/test_admin_handoff.py::test_filing_writes_all_fields_atomically -x` | ❌ W0 (new) | ⬜ pending |
| 25-01-XX | 01 | 1 | REQ-SD-04 (failed path does NOT set status="filed"; orthogonality with adminProcessingStatus="failed") | — | Retry-exhausted items never appear filed | unit | `pytest tests/test_admin_handoff.py::test_agent_error_does_not_file_inbox_item -x` | ❌ W0 (extend `test_agent_error_sets_status_to_failed`) | ⬜ pending |
| 25-02-XX | 02 | 1 | REQ-SD-05 (Settings has inbox_filed_retention_days: int = 30 with Field(ge=1) validation) | — | Misconfig fails fast | unit | `pytest tests/test_config.py::test_inbox_filed_retention_days_min_validation -x` | ❌ W0 (new) | ⬜ pending |
| 25-03-XX | 03 | 1 | REQ-SD-06 (api/inbox.py listing query excludes status="filed" docs) | — | Phone inbox never surfaces filed | integration | `pytest tests/test_inbox_api.py::test_list_inbox_excludes_filed_status -x` | ❌ W0 (new) | ⬜ pending |
| 25-03-XX | 03 | 1 | REQ-SD-07 (api/errands.py:174 unprocessed-admin query continues to work; doesn't pick up filed docs whose adminProcessingStatus is "completed") | — | No re-fire on filed items | integration | `pytest tests/test_errands_api.py::test_unprocessed_admin_query_skips_filed -x` | ❌ W0 (new) | ⬜ pending |
| 25-03-XX | 03 | 1 | REQ-SD-08 (api/errands.py:461 dismiss_admin_notification soft-deletes with status="filed" — lifecycle symmetry) | — | Dismissed notifications retain audit trail | integration | `pytest tests/test_errands_api.py::test_dismiss_admin_notification_files_instead_of_delete -x` | ❌ W0 (new) | ⬜ pending |
| 25-04-XX | 04 | 2 | REQ-BL-01 (ErrandItem + TaskItem Pydantic models gain optional sourceInboxItemId + sourceCaptureTraceId fields with default None) | — | Backward-compat; pre-Phase-25 docs valid | unit | `pytest tests/test_documents_models.py::test_errand_item_optional_backlinks -x` and `test_task_item_optional_backlinks` | ❌ W0 (new) | ⬜ pending |
| 25-04-XX | 04 | 2 | REQ-BL-02 (tools/admin.py admin_inbox_item_id_var ContextVar exists and is set by admin_handoff before agent.run) | — | Trace propagation reliable | unit | `pytest tests/test_admin_handoff.py::test_admin_handoff_sets_inbox_item_id_contextvar -x` | ❌ W0 (new) | ⬜ pending |
| 25-04-XX | 04 | 2 | REQ-BL-03 (add_errand_items reads both ContextVars and carries sourceInboxItemId + sourceCaptureTraceId on every persisted ErrandItem) | — | Backlinks captured at write time | unit | `pytest tests/test_admin_tools.py::test_add_errand_items_carries_backlinks -x` | ❌ W0 (new) | ⬜ pending |
| 25-04-XX | 04 | 2 | REQ-BL-04 (add_task_items reads both ContextVars and carries sourceInboxItemId + sourceCaptureTraceId on every persisted TaskItem) | — | Backlinks captured at write time | unit | `pytest tests/test_admin_tools.py::test_add_task_items_carries_backlinks -x` | ❌ W0 (new) | ⬜ pending |
| 25-04-XX | 04 | 2 | REQ-BL-05 (add_errand_items / add_task_items gracefully no-op the backlink fields when ContextVars are unset — None default) | — | Non-admin code paths unaffected | unit | `pytest tests/test_admin_tools.py::test_add_errand_items_no_contextvars_set -x` | ❌ W0 (new) | ⬜ pending |
| 25-05-XX | 05 | 1 | REQ-SD-09 (Cosmos Inbox container `defaultTtl` = -1 after az CLI update; idempotent) | — | TTL machinery active in prod | manual | Operator runs `az cosmosdb sql container update --account-name shared-services-cosmosdb --database-name second-brain --name Inbox --ttl -1` then `az cosmosdb sql container show ... --query "resource.defaultTtl"` should return `-1` | N/A — operator | ⬜ pending |
| 25-05-XX | 05 | 1 | REQ-SD-10 (Post-deploy UAT: fresh admin capture results in Cosmos Inbox doc with status="filed" + ttl set + adminProcessingStatus="completed") | — | End-to-end works in prod | UAT | Manual: capture an admin item via mobile → wait → Data Explorer query the most recent admin-bucket doc and verify `status`, `ttl`, `adminProcessingStatus` fields | N/A — UAT | ⬜ pending |
| 25-XX | various | — | REQ-SD-11 (investigation.py: no change — no direct Inbox container query exists today) | — | Prevent future regression | guard | `! grep -rn "Inbox" backend/src/second_brain/tools/investigation.py` (CI grep guard or assert in test) | ❌ W0 (new) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_admin_handoff.py` — rename existing `test_simple_confirmation_deletes_inbox_item` (and 5 related fixtures at lines 202, 453, 540, 552, 667 that assert `delete_item.assert_called_once_with(...)`) to assert upsert with `status="filed"` + `ttl` + `adminProcessingStatus="completed"` (NOT delete_item)
- [ ] `backend/tests/test_admin_handoff.py` — add `test_filed_doc_ttl_matches_settings`, `test_filing_writes_all_fields_atomically`, `test_agent_error_does_not_file_inbox_item`, `test_admin_handoff_sets_inbox_item_id_contextvar`
- [ ] `backend/tests/test_admin_tools.py` — add `test_add_errand_items_carries_backlinks`, `test_add_task_items_carries_backlinks`, `test_add_errand_items_no_contextvars_set` (use `capture_trace_id_var.set("trace-X")` + `admin_inbox_item_id_var.set("inbox-Y")` then assert on captured upsert body)
- [ ] `backend/tests/test_inbox_api.py` — add `test_list_inbox_excludes_filed_status` (mock `query_items` to include a filed doc + assert response excludes it)
- [ ] `backend/tests/test_errands_api.py` — add `test_unprocessed_admin_query_skips_filed`, `test_dismiss_admin_notification_files_instead_of_delete`
- [ ] `backend/tests/test_documents_models.py` — add `test_errand_item_optional_backlinks`, `test_task_item_optional_backlinks` (verify Pydantic defaults to None + accepts strings)
- [ ] `backend/tests/test_config.py` — add `test_inbox_filed_retention_days_min_validation` (verify `Field(ge=1)` rejects 0)
- [ ] Investigation.py guard: either a CI grep step or a `test_investigation_has_no_direct_inbox_query` in `backend/tests/test_investigation_queries.py`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cosmos container TTL update | REQ-SD-09 | Production infrastructure change requires operator authorization (same pattern as Phase 24 Step C `az containerapp update`) | Operator: `az cosmosdb sql container update --account-name shared-services-cosmosdb --resource-group shared-services-rg --database-name second-brain --name Inbox --ttl -1` then verify with `az cosmosdb sql container show --account-name shared-services-cosmosdb --resource-group shared-services-rg --database-name second-brain --name Inbox --query "resource.defaultTtl"` → expects `-1`. Re-run the update once to confirm idempotency (second run also returns success). |
| Post-deploy capture-and-file UAT | REQ-SD-10 | End-to-end behavior against live Cosmos cannot be reproduced in unit tests | After deploy: capture an admin-bucket item via mobile (e.g., "add eggs to shopping list"). Wait for Admin agent to process (~10 sec). Open Azure Portal → Cosmos Data Explorer → Inbox container → find the most recent doc with bucket="Admin" and verify: `status: "filed"`, `ttl: 2592000`, `adminProcessingStatus: "completed"`. Verify phone inbox no longer shows the item. |
| Mobile inbox visual regression | ROADMAP SC #3 | Visual confirmation that the filter is invisible to the user | Open the mobile inbox screen before and after deploy; non-filed items render identically. (Server-side filter — no client code change.) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (8 new/modified test files)
- [ ] No watch-mode flags (all commands are one-shot with `-x`)
- [ ] Feedback latency < 5s for quick / < 30s for full
- [ ] `nyquist_compliant: true` set in frontmatter (after Wave 0 lands)

**Approval:** pending
