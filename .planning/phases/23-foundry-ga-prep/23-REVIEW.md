---
phase: 23-foundry-ga-prep
reviewed: 2026-05-09T16:10:00Z
depth: standard
files_reviewed: 1
files_reviewed_list:
  - backend/scripts/foundry_probe.py
findings:
  critical: 0
  warning: 3
  info: 2
  total: 5
status: issues_found
---

# Phase 23: Code Review Report

**Reviewed:** 2026-05-09T16:10:00Z
**Depth:** standard
**Files Reviewed:** 1
**Status:** issues_found

## Summary

Reviewed `backend/scripts/foundry_probe.py` -- a standalone probe harness for exercising the GA SDK against a live Foundry endpoint. The script is well-structured: telemetry tagging via ContextVars mirrors the production CaptureTraceSpanProcessor pattern, the fail-fast guards for telemetry setup are sound, and the probe/fixture separation is clean.

No critical issues found. Three warnings relate to: (1) module-level `sys.exit` during import preventing any use as a library or test import, (2) a bare `except Exception` in `_maybe_delete_session` that silently swallows errors that could indicate SDK contract changes (the very thing probes exist to detect), and (3) a subtle ContextVar bleed when running `all` probes sequentially. Two info items for minor code quality observations.

## Warnings

### WR-01: Module-level sys.exit blocks import and testability

**File:** `backend/scripts/foundry_probe.py:231`
**Issue:** `_setup_probe_telemetry()` is called at module scope (line 231). If `APPLICATIONINSIGHTS_CONNECTION_STRING` is unset, the function calls `sys.exit(2)` at line 127. This means simply importing the module (e.g., `from scripts.foundry_probe import PROBES` in a future test or orchestration script) kills the entire process. For a standalone CLI script this is tolerable today, but it becomes a trap the moment anyone imports from this module.
**Fix:** Move the `_setup_probe_telemetry()` call into `main()`, before probe dispatch. The module-level call site at line 231 becomes:

```python
# Inside main(), before any probe runs:
def main() -> int:
    parser = argparse.ArgumentParser(...)
    args = parser.parse_args()
    _setup_probe_telemetry()  # fail-fast here, after arg parse
    ...
```

### WR-02: Silent exception swallowing in _maybe_delete_session hides SDK contract information

**File:** `backend/scripts/foundry_probe.py:218-225`
**Issue:** `_maybe_delete_session` catches `Exception` on line 222 and `continue`s silently. The entire purpose of this probe harness is to discover the GA SDK's actual API shape. If a deletion method exists but raises (e.g., `NotImplementedError`, `PermissionError`, or a new SDK-specific error), that information is discarded. The fixture will record `thread_deleted_after_run: false` and the developer has no way to distinguish "method does not exist" from "method exists but the call failed."
**Fix:** Capture the exception and surface it in the return value so the fixture records what happened:

```python
async def _maybe_delete_session(agent: Agent, session: AgentSession | None) -> dict[str, Any]:
    """Try to delete probe-created sessions. Return outcome dict."""
    if session is None:
        return {"attempted": False, "reason": "no_session"}
    for method_name in ("delete_session", "delete_thread", "delete"):
        method = getattr(agent, method_name, None)
        if callable(method):
            try:
                result = method(session)
                if asyncio.iscoroutine(result):
                    await result
                return {"attempted": True, "deleted": True, "method": method_name}
            except Exception as exc:
                return {
                    "attempted": True,
                    "deleted": False,
                    "method": method_name,
                    "exc_type": type(exc).__name__,
                    "exc_str": str(exc),
                }
    return {"attempted": True, "deleted": False, "reason": "no_deletion_method_found"}
```

Callers would write the dict into the fixture payload instead of a bare boolean.

### WR-03: ContextVar bleed across sequential probe runs when using "all"

**File:** `backend/scripts/foundry_probe.py:691-695`
**Issue:** When running `all` probes via `_run_all()`, each probe sets `_probe_run_id` and `_probe_name` at its start (e.g., line 251-252 for `streaming_shape`). However, these are module-level `ContextVar` instances and `_run_all` runs probes sequentially in the same async task. If any probe's SDK call emits spans asynchronously after the probe function returns (e.g., connection pool cleanup, deferred telemetry flush), those spans will be tagged with the NEXT probe's run_id/name, not the one that created them. This is a minor data integrity issue in the fixture telemetry -- probe spans in App Insights could be misattributed.
**Fix:** Reset the ContextVars after each probe completes in `_run_all`:

```python
async def _run_all() -> list[Path]:
    paths: list[Path] = []
    for name in PROBES:
        paths.append(await _run_one(name))
        _probe_run_id.set("")
        _probe_name.set("")
    return paths
```

Alternatively, run each probe in its own `asyncio.Task` via `copy_context().run()` to get a fresh ContextVar scope per probe.

## Info

### IN-01: Unused variable `endpoint` in auth_probe RBAC block

**File:** `backend/scripts/foundry_probe.py:584-585`
**Issue:** The variable `endpoint` is assigned on line 584-585 inside the RBAC role-lookup block, and included in `rbac_outcome` on line 603. However, it is redundant with `inv_endpoint` assigned on line 617-618 for the same purpose. This is not a bug (it records useful context), but the double lookup is unnecessary noise.
**Fix:** Remove the `endpoint` assignment from the RBAC block (lines 584-585) and reference the value directly when building the outcome dict, or consolidate the endpoint lookup to a single variable before both blocks.

### IN-02: Probe functions repeat boilerplate tagging + client construction

**File:** `backend/scripts/foundry_probe.py:249-261`, `309-318`, `376-387`, `474-485`, `547-553`
**Issue:** All five probe functions repeat the same 6-line preamble (generate run_id, set two ContextVars, call `_ensure_probe_processor_installed`, call `_build_client`, construct `Agent`). This is not a bug, but the duplication increases maintenance cost if the setup sequence changes (e.g., adding a new ContextVar or changing the Agent constructor).
**Fix:** Extract a helper that returns a `(run_id, client, agent)` tuple, or use a context manager that handles tagging and cleanup (which would also address WR-03).

---

_Reviewed: 2026-05-09T16:10:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
