---
phase: 25-admin-inbox-soft-delete-30-day-retention-inserted
plan: 02
status: complete
completed: 2026-05-17
requirements:
  - REQ-SD-05
  - REQ-SD-09
key-files:
  created:
    - backend/tests/test_config.py
  modified:
    - backend/src/second_brain/config.py
---

# Plan 25-02 Summary

## What was built

1. **Settings field added:** `inbox_filed_retention_days: int = Field(default=30, ge=1, description="Days to retain filed admin inbox docs; minimum 1.")` in `backend/src/second_brain/config.py`. Also added `from pydantic import Field` import.

2. **Validation tests created:** `backend/tests/test_config.py` with 4 tests covering default, positive int accept, zero-reject, negative-reject.

3. **Cosmos infrastructure enabled:** Operator-authorized `az cosmosdb sql container update --account-name shared-services-cosmosdb --resource-group shared-services-rg --database-name second-brain --name Inbox --ttl -1` confirmed `defaultTtl=-1` on the Inbox container. Idempotency verified by re-running the same command.

## Verification

**Task 1 (code):**
- `uv run pytest tests/test_config.py -v --noconftest` → 4 passed:
  - `test_inbox_filed_retention_days_default_is_30`
  - `test_inbox_filed_retention_days_accepts_positive_int`
  - `test_inbox_filed_retention_days_min_validation_rejects_zero`
  - `test_inbox_filed_retention_days_min_validation_rejects_negative`
- `grep -n "inbox_filed_retention_days" backend/src/second_brain/config.py` → 1 match (the new field block)
- `grep -n "from pydantic import Field" backend/src/second_brain/config.py` → 1 match

**Task 2 (infra — operator confirmed):**
- Step 3 first run output: `-1` (confirmed by operator)
- Step 3 after idempotency re-run: still `-1` (confirmed by operator)
- TTL machinery enabled in production; per-doc `ttl` values from Plan 01 will now be honored

## Plan 01 unblocked

- Settings field exists: `get_settings().inbox_filed_retention_days` is now a valid call site
- Cosmos container `defaultTtl=-1` (TTL machinery on) — per-doc `ttl` writes will take effect
- Landmines #7 (ge=1 prevents immediate-purge), #8 (deploy ordering infra-before-code), #9 (must use -1) all addressed

## Self-Check: PASSED

All acceptance criteria met. Plan 01 (Wave 2) can proceed.
