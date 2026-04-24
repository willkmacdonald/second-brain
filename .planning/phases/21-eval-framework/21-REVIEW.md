---
phase: 21-eval-framework
reviewed: 2026-04-23T18:45:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - backend/src/second_brain/api/eval.py
  - backend/src/second_brain/eval/__init__.py
  - backend/src/second_brain/eval/dry_run_tools.py
  - backend/src/second_brain/eval/metrics.py
  - backend/src/second_brain/eval/runner.py
  - backend/src/second_brain/main.py
  - backend/src/second_brain/models/documents.py
  - backend/src/second_brain/tools/investigation.py
  - backend/scripts/seed_golden_dataset.py
  - backend/tests/test_eval.py
  - backend/tests/test_eval_dry_run.py
  - backend/tests/test_eval_metrics.py
findings:
  critical: 0
  warning: 5
  info: 3
  total: 8
status: issues_found
---

# Phase 21: Code Review Report

**Reviewed:** 2026-04-23T18:45:00Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Phase 21 introduces an evaluation framework for the Classifier and Admin Agent, consisting of an eval runner module, dry-run tool handlers, metrics computation, API endpoints, investigation tool integrations, a golden dataset seeding script, and comprehensive tests. The architecture is clean, well-structured, and follows established codebase patterns. The dry-run tool signatures are byte-for-byte identical to their production counterparts (verified against `ClassifierTools.file_capture` and `AdminTools.add_errand_items/add_task_items/get_routing_context`). The metrics module is pure computation with no I/O, which is good design. Error handling is thorough with per-case try/except and top-level exception guards on background tasks.

Five warnings were identified: two related to fire-and-forget background tasks lacking GC protection, one module-level mutable state concern (documented as acceptable), one missing `exc_info=True` on error logging, and one `raise ... from None` that discards diagnostic context. Three informational items were noted.

## Warnings

### WR-01: Fire-and-forget `asyncio.create_task` in investigation tools lacks GC protection

**File:** `backend/src/second_brain/tools/investigation.py:632-639` (run_classifier_eval) and `:711-719` (run_admin_eval)
**Issue:** Both `run_classifier_eval` and `run_admin_eval` investigation tools call `asyncio.create_task()` without adding the task to a strong-reference set. The API endpoint in `eval.py:103-106` correctly uses `app.state.background_tasks` for GC prevention, but the investigation tool code path bypasses the API endpoint and calls the runner directly. If no strong reference exists, the garbage collector can silently destroy the task mid-execution, causing eval runs to disappear without completing or erroring. The RESEARCH.md Anti-Patterns section explicitly warns: "Use `app.state` for the eval runs dict, not a module-level global, to maintain test isolation" and the research Pattern 1 shows the `background_tasks` set pattern.
**Fix:**
The investigation tools don't have access to `app.state`. The simplest fix is to store the task reference in the module-level `_eval_runs` dict itself (keyed by run_id), which already serves as a strong reference container:
```python
# In run_classifier_eval tool:
task = asyncio.create_task(
    _run_classifier_eval(
        run_id=run_id,
        cosmos_manager=self._cosmos_manager,
        classifier_client=self._classifier_client,
        runs_dict=_eval_runs,
    )
)
# Prevent GC -- store strong reference alongside run metadata
_eval_runs[run_id]["_task"] = task
```
Apply the same pattern to `run_admin_eval` at line 711.

### WR-02: Module-level mutable `_eval_runs` dict shared between API and investigation tools

**File:** `backend/src/second_brain/api/eval.py:18` and `backend/src/second_brain/tools/investigation.py:29`
**Issue:** The `_eval_runs` dict is a module-level global imported by both `api/eval.py` (where it is defined) and `tools/investigation.py` (which imports it directly). The RESEARCH.md Anti-Patterns section explicitly flags this: "Global mutable state for eval run tracking: Use `app.state` for the eval runs dict, not a module-level global." While the tests mitigate cross-test pollution with `_clear_eval_runs` fixture, the production concern is that container restarts lose all state (acknowledged as acceptable for single-user). The deeper issue is that this is a shared mutable singleton that makes testing and isolation harder than it needs to be.
**Fix:**
This is a known tradeoff documented in the RESEARCH.md (Open Question #2) and is acceptable for a single-user system. However, consider passing a reference via the `InvestigationTools` constructor to improve testability:
```python
class InvestigationTools:
    def __init__(self, ..., eval_runs: dict | None = None) -> None:
        ...
        self._eval_runs = eval_runs if eval_runs is not None else _eval_runs
```
This would let tests inject their own dict without relying on the autouse fixture clearing a global. Low priority -- current approach works.

### WR-03: `raise HTTPException(...) from None` discards exception context

**File:** `backend/src/second_brain/api/eval.py:178-179`
**Issue:** The `get_eval_results` endpoint catches all exceptions and re-raises an `HTTPException` using `from None`, which discards the original exception chain. While the error is logged on line 176, any downstream error handler or middleware that inspects `__cause__` will see nothing. The `from None` pattern is appropriate when hiding internals from API consumers, but here the exception is a 503 (server error) where preserving the chain aids debugging in local/dev scenarios.
**Fix:**
```python
raise HTTPException(
    status_code=503, detail="Failed to retrieve eval results."
) from exc
```

### WR-04: Missing `exc_info=True` on runner error logging

**File:** `backend/src/second_brain/eval/runner.py:165-173` (classifier) and `:310-319` (admin)
**Issue:** Both top-level `except` blocks in the eval runner log with `logger.error(...)` but do not include `exc_info=True`. This means the full traceback is not captured in App Insights. Compare with the API layer at `eval.py:176` which correctly includes `exc_info=True`. For a background task that runs unsupervised for 3-5 minutes, the traceback is essential for post-mortem debugging.
**Fix:**
```python
# runner.py line 166 (classifier) and line 311 (admin):
logger.error(
    "Classifier eval failed: %s",
    exc,
    exc_info=True,  # ADD THIS
    extra={
        "component": "eval",
        "eval_type": "classifier",
        "eval_run_id": run_id,
    },
)
```

### WR-05: Cosmos query in eval runner missing `partition_key` parameter

**File:** `backend/src/second_brain/eval/runner.py:62-65` and `:203-206`
**Issue:** The golden dataset queries in both `run_classifier_eval` and `run_admin_eval` use a parameterized `WHERE c.userId = @userId` filter but do not pass `partition_key="will"` to `query_items()`. While Cosmos will return correct results (the WHERE clause is equivalent), omitting `partition_key` forces a cross-partition query that is less efficient and costs more RUs. The existing codebase consistently passes `partition_key` when the partition key is known (see `tools/investigation.py:443`, `tools/admin.py:38`).
**Fix:**
```python
async for item in golden_container.query_items(
    query="SELECT * FROM c WHERE c.userId = @userId",
    parameters=[{"name": "@userId", "value": "will"}],
    partition_key="will",  # ADD THIS
):
```
Apply to both classifier (line 62) and admin (line 203) golden dataset queries.

## Info

### IN-01: Seed script export query uses string interpolation for partition key

**File:** `backend/scripts/seed_golden_dataset.py:66`
**Issue:** The export query uses `c.userId = 'will'` as a literal string in the SQL rather than a parameterized `@userId`. While this is not a security vulnerability (the value is hardcoded, not user-supplied, and the script runs locally with `az login`), the import query and all other Cosmos queries in the codebase use parameterized queries for consistency.
**Fix:** Minor consistency improvement -- parameterize the userId in the export query to match codebase conventions.

### IN-02: Unused `defaultdict` import in metrics module

**File:** `backend/src/second_brain/eval/metrics.py:10`
**Issue:** `defaultdict` is imported from `collections` and used in `compute_confidence_calibration` (line 90) and `compute_admin_metrics` (line 161). This is actually used -- no action needed. (Initial scan flagged this but upon closer inspection it is correctly used.)

### IN-03: `eval_type` field on `EvalRunRequest` lacks enum validation

**File:** `backend/src/second_brain/api/eval.py:22-25`
**Issue:** The `eval_type` field is typed as `str` and validated manually on line 36 with an `if` check. Using a `Literal["classifier", "admin_agent"]` type annotation would provide automatic Pydantic validation, cleaner OpenAPI documentation, and eliminate the manual check. The current approach works but is less idiomatic for a Pydantic model.
**Fix:**
```python
from typing import Literal

class EvalRunRequest(BaseModel):
    eval_type: Literal["classifier", "admin_agent"]
    routing_context: str | None = None
```
Then remove the manual validation block on lines 36-43.

---

_Reviewed: 2026-04-23T18:45:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
