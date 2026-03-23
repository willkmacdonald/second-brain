# Phase 15: v3.0 Tech Debt Cleanup - Research

**Researched:** 2026-03-23
**Domain:** Backend code quality, Cosmos DB queries, Python test infrastructure
**Confidence:** HIGH

## Summary

Phase 15 is a focused cleanup phase that closes all tech debt identified by the v3.0 milestone audit. There are five discrete items: (1) a retry query regression in `errands.py` where `failed` and `pending` conditions were lost during the Phase 12.2 rename, (2) a defensive fix for a potential `UnboundLocalError` in `admin_handoff.py`, (3) four broken recipe tool tests caused by real network calls bypassing mocked Playwright, (4) one stale "shopping list" comment in test_admin_handoff.py, and (5) verifying the REQUIREMENTS.md traceability table is complete (it already appears up to date).

All items are well-understood, with clear root causes and straightforward fixes. No external libraries or architecture changes are needed. This is purely a code hygiene phase.

**Primary recommendation:** Fix all five items in a single plan. Each item is independent and small -- the entire phase can be done in one pass.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CLEAN-01 | Admin Agent deletes successfully processed inbox items instead of flagging them, keeping Inbox free of stale processed entries | The retry query fix in errands.py restores the ability to pick up `failed` and `pending` items for re-processing, completing the CLEAN-01 retry path that was regressed during Phase 12.2 rename |
</phase_requirements>

## Standard Stack

No new libraries or dependencies needed. All fixes use existing project infrastructure:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | existing | Test framework | Already configured in the project |
| httpx | existing | HTTP client (for test recipe mock fixes) | Used in recipe tool fetch tiers |
| unittest.mock | stdlib | Test mocking | Standard Python mocking |

### Supporting
No additional libraries needed.

### Alternatives Considered
None -- this is a cleanup phase, not a feature phase.

## Architecture Patterns

### Pattern 1: Cosmos DB Retry Query (Inclusive Non-Terminal Status Match)

**What:** The retry query in `errands.py` must match ALL non-terminal `adminProcessingStatus` values so that stuck items are recovered when the user opens the Status screen.

**When to use:** Whenever querying for items that need (re)processing.

**Current (broken) query:**
```sql
SELECT c.id, c.rawText FROM c
WHERE c.userId = @userId
AND c.classificationMeta.bucket = 'Admin'
AND (NOT IS_DEFINED(c.adminProcessingStatus)
     OR IS_NULL(c.adminProcessingStatus))
```

**Correct query (must restore):**
```sql
SELECT c.id, c.rawText FROM c
WHERE c.userId = @userId
AND c.classificationMeta.bucket = 'Admin'
AND (NOT IS_DEFINED(c.adminProcessingStatus)
     OR IS_NULL(c.adminProcessingStatus)
     OR c.adminProcessingStatus = 'failed'
     OR c.adminProcessingStatus = 'pending')
```

**Root cause:** Phase 12.1-02 (commit c9f7e57) added the fix to `shopping_lists.py`. Phase 12.2 rewrote the file as `errands.py` and the retry conditions were lost.

**Location:** `backend/src/second_brain/api/errands.py` lines 174-180

### Pattern 2: Defensive Variable Assignment Before Exception Handlers

**What:** Variables used in `except` blocks must be defined before the `try` that the `except` catches.

**Current code analysis:** In `admin_handoff.py`, `inbox_container` is assigned on line 172 and `log_extra` on line 179, both inside the first `try` block (lines 171-193). If that block fails, the function returns early (line 193), so neither variable is referenced in an undefined state. However, the second `try` block's `except` (line 365) uses both `log_extra` (line 373) and `inbox_container` (line 377).

**The risk:** While currently safe due to the early return, a future refactor could remove the early return and cause `UnboundLocalError`. The defensive fix is to initialize these variables before the first `try` block.

**Fix:**
```python
inbox_container = None
log_extra: dict = {"component": "admin_agent"}
```
Defined before the first `try`, then `_mark_inbox_failed` checks for `None`:
```python
if inbox_container is not None:
    await _mark_inbox_failed(inbox_container, inbox_item_id, span)
```

### Pattern 3: Recipe Tool Test Mocking (Network Isolation)

**What:** The `RecipeTools.fetch_recipe_url` method uses a three-tier fetch strategy: Jina Reader -> simple HTTP -> Playwright. The tests only mock Playwright (tier 3) but tiers 1 and 2 make real network calls that bypass the mocks.

**Failure mechanism:**
1. Tests pass a mock browser to `RecipeTools(browser=mock_browser)`
2. But `fetch_recipe_url` tries Jina Reader first (real HTTP call to `r.jina.ai`)
3. SSL verification fails locally: `[SSL: CERTIFICATE_VERIFY_FAILED]`
4. Jina Reader still returns real content from `example.com` (via the Jina proxy, which succeeds despite SSL errors on direct httpx calls)
5. The real Jina content replaces what the mocked browser would have returned
6. Assertions fail because they expect mocked content, not real `example.com` content

**Fix:** Mock `_fetch_jina` and `_fetch_simple` methods (or patch `httpx.AsyncClient`) to prevent real network calls. The cleanest approach is to patch `RecipeTools._fetch_jina` and `RecipeTools._fetch_simple` to return empty strings, forcing the code path to reach Playwright (tier 3) where the mock is set up.

**Alternative (simpler):** Use `unittest.mock.patch.object` on the `RecipeTools` instance or class to intercept `_fetch_jina` and `_fetch_simple`.

### Anti-Patterns to Avoid

- **Patching at the wrong level:** Don't patch `httpx.AsyncClient` globally -- patch the specific methods `_fetch_jina` and `_fetch_simple` on the `RecipeTools` class to keep tests focused.
- **Overly broad query conditions:** The retry query should match non-terminal statuses explicitly. Using `c.adminProcessingStatus != 'completed'` would also match `'processing'` or other future statuses, which might not be correct.
- **Ignoring the existing test for pending items:** The test `test_get_errands_skips_pending_items` has a misleading name and docstring that says pending/failed items should NOT be re-triggered. This test actually just verifies that an empty query result means no processing is triggered. After the query fix, this test's name/docstring should be updated or the test rewritten to match the new behavior.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Network isolation in tests | Custom HTTP interceptor | `unittest.mock.patch.object` on `_fetch_jina` / `_fetch_simple` | Standard Python mocking, no new dependencies |
| Variable safety | Complex try/except restructuring | Initialize variables before try blocks with sentinel values | Simple, idiomatic Python defensive pattern |

**Key insight:** All fixes are mechanical code changes with well-understood patterns. No custom solutions needed.

## Common Pitfalls

### Pitfall 1: Test Name/Docstring Mismatch After Retry Query Fix
**What goes wrong:** The test `test_get_errands_skips_pending_items` says pending items should NOT be re-processed. But the fix makes the query INCLUDE pending items.
**Why it happens:** The test was written when the query excluded pending/failed items. The test passes an empty list to the mock, so it still passes mechanically, but the name and docstring are now misleading.
**How to avoid:** Update the test name and docstring to accurately describe behavior, or rewrite the test to verify that failed/pending items ARE included in processing.
**Warning signs:** Test passes but its documentation contradicts the intended behavior.

### Pitfall 2: Recipe Test Flakiness from Network Dependency
**What goes wrong:** If the mock patches are too narrow (e.g., only patching one tier), real network calls can leak through and cause intermittent failures.
**Why it happens:** The three-tier strategy means the code tries multiple fetch methods before reaching the mocked one.
**How to avoid:** Patch both `_fetch_jina` and `_fetch_simple` together. Verify by checking that no real HTTP calls are made during tests.
**Warning signs:** Tests pass locally but fail in CI, or vice versa.

### Pitfall 3: In-Flight Set Not Updated for Retry Items
**What goes wrong:** The `admin_processing_ids` in-flight set prevents duplicate processing. When the query now returns `failed` and `pending` items, these items may already have IDs in the in-flight set from a previous attempt.
**Why it happens:** The cleanup callback `_cleanup_in_flight` removes IDs after processing completes. If a previous attempt completed (and removed the ID), the retry will work correctly. If it's still in-flight, the existing filter at line 197-199 already handles this.
**How to avoid:** No code change needed -- the existing in-flight filter handles this correctly. But worth verifying in the test.
**Warning signs:** Items stuck in "processing" state on Status screen.

## Code Examples

### Fix 1: Retry Query in errands.py

```python
# backend/src/second_brain/api/errands.py, lines 174-180
# BEFORE (broken):
query = (
    "SELECT c.id, c.rawText FROM c "
    "WHERE c.userId = @userId "
    "AND c.classificationMeta.bucket = 'Admin' "
    "AND (NOT IS_DEFINED(c.adminProcessingStatus) "
    "     OR IS_NULL(c.adminProcessingStatus))"
)

# AFTER (fixed):
query = (
    "SELECT c.id, c.rawText FROM c "
    "WHERE c.userId = @userId "
    "AND c.classificationMeta.bucket = 'Admin' "
    "AND (NOT IS_DEFINED(c.adminProcessingStatus) "
    "     OR IS_NULL(c.adminProcessingStatus) "
    "     OR c.adminProcessingStatus = 'failed' "
    "     OR c.adminProcessingStatus = 'pending')"
)
```

### Fix 2: Defensive Variable Initialization in admin_handoff.py

```python
# Before the first try block (around line 170):
inbox_container = None
log_extra: dict = {"component": "admin_agent"}

# In the except block (around line 376):
if inbox_container is not None:
    await _mark_inbox_failed(inbox_container, inbox_item_id, span)
```

### Fix 3: Recipe Test Network Isolation

```python
# Patch Jina and simple HTTP to force Playwright path
from unittest.mock import AsyncMock, MagicMock, patch

class TestFetchRecipeUrl:
    async def test_successful_fetch_returns_page_text(self) -> None:
        browser = _build_mock_browser(visible_text="Chicken Tikka Recipe")
        tools = RecipeTools(browser=browser)

        with (
            patch.object(tools, "_fetch_jina", return_value=""),
            patch.object(tools, "_fetch_simple", return_value=("", "", "mock")),
        ):
            result = await tools.fetch_recipe_url(url="https://example.com/recipe")

        assert "Chicken Tikka Recipe" in result
```

### Fix 4: Stale Comment in test_admin_handoff.py

```python
# Line 293, BEFORE:
# deleted from Inbox even though no shopping list items were written.

# AFTER:
# deleted from Inbox even though no errand items were written.
```

## State of the Art

Not applicable -- this is a code cleanup phase, not a technology adoption phase.

## Open Questions

1. **REQUIREMENTS.md traceability: already fixed?**
   - What we know: The current REQUIREMENTS.md file (read during this research) already shows OBS-01 through OBS-08 as "Complete" with Phase 14, and DEST-01 through DEST-07 and VOICE-OD-01 through VOICE-OD-03 are registered. The file says "Last updated: 2026-03-23 after v3.0 milestone audit gap closure."
   - What's unclear: Whether this was done as part of the Phase 15 roadmap entry creation or as a separate fix.
   - Recommendation: Verify during planning. If already correct, mark this success criterion as pre-satisfied and skip it in the plan. The current state of the file shows all 40 requirements mapped and complete.

2. **test_get_errands_skips_pending_items test intent**
   - What we know: This test passes an empty list and verifies no processing is triggered. After the query fix, `pending` and `failed` items WILL be included in the query results. The test mechanically still passes because it feeds an empty list.
   - What's unclear: Whether the test should be updated to verify that pending/failed items ARE returned by the query (testing the query itself, not just the processing trigger), or just renamed.
   - Recommendation: At minimum, rename the test and update its docstring. Ideally, add a new test that verifies pending/failed items are picked up by the processing trigger. The existing test can remain as a "no items means no processing" baseline.

3. **Number of broken tests: 4 vs audit's 3**
   - What we know: The audit identified 3 broken tests across 3 test files. Current test run shows 4 failures, all in `test_recipe_tools.py`. The `test_admin_handoff.py` and `test_transcription.py` tests now pass (19/19 and 3/3 respectively).
   - What's unclear: The admin_handoff and transcription test issues may have been fixed between the audit and now.
   - Recommendation: Fix the 4 recipe tool test failures. The other tests are green and don't need attention.

## Sources

### Primary (HIGH confidence)
- Direct code inspection of `backend/src/second_brain/api/errands.py` lines 174-180 -- confirmed missing `failed`/`pending` conditions
- Direct code inspection of `backend/src/second_brain/processing/admin_handoff.py` -- analyzed variable scoping for UnboundLocalError risk
- `uv run pytest` execution -- confirmed 4 failures in `test_recipe_tools.py`, 148 passed, 5 skipped
- Phase 12.1-02 SUMMARY (commit c9f7e57) -- confirmed original fix was in `shopping_lists.py` before rename
- `.planning/v3.0-MILESTONE-AUDIT.md` -- authoritative gap list

### Secondary (MEDIUM confidence)
- REQUIREMENTS.md traceability table appears already fixed (but unclear when/by whom)

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Retry query fix: HIGH - direct code inspection confirms the regression, root cause clear
- UnboundLocalError fix: HIGH - variable scoping analysis complete, fix pattern straightforward
- Test repairs: HIGH - test run confirms exactly which tests fail and why
- Stale comments: HIGH - grep confirms exactly one remaining instance
- REQUIREMENTS.md: HIGH - file inspection shows it may already be complete

**Research date:** 2026-03-23
**Valid until:** 2026-04-23 (stable -- no moving targets in this cleanup phase)
