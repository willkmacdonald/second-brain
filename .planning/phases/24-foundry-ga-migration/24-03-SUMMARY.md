---
phase: 24-foundry-ga-migration
plan: 03
subsystem: backend/agents
tags:
  - middleware
  - capture-trace
  - foundry-ga
  - p1-3
requires:
  - "24-02 strict cutover (GA SDK installed)"
provides:
  - "CaptureTraceAgentMiddleware tagging invoke_agent spans"
  - "CaptureTraceFunctionMiddleware tagging execute_tool spans + lifting classification.* / transcription.success"
  - "agents/instructions/investigation.md (D-02 source of truth)"
  - "P1-3 regression guard (test_legacy_middleware_imports_survive.py)"
affects:
  - "Plans 24-04 (Investigation rewrite), 24-09 (Admin rewrite), 24-14 (Classifier rewrite) -- all import from second_brain.agents.agent_middleware.capture_trace"
  - "Plan 24-18 -- responsible for deleting legacy agents/middleware.py and updating/removing this plan's red test"
tech-stack:
  added:
    - "agent_framework.AgentMiddleware (GA SDK)"
    - "agent_framework.FunctionMiddleware (GA SDK)"
    - "agent_framework.AgentContext (GA SDK)"
    - "agent_framework.FunctionInvocationContext (GA SDK)"
  patterns:
    - "Per-call span tagging via trace.get_current_span().set_attribute(...)"
    - "ContextVar-driven capture-trace propagation (capture_trace_id_var)"
    - "Defensive .value unwrapping for FunctionInvocationContext result variants"
key-files:
  created:
    - "backend/src/second_brain/agents/instructions/investigation.md (290 lines, verbatim copy of canonical Phase 17.1 portal source)"
    - "backend/src/second_brain/agents/agent_middleware/__init__.py (16 lines, package marker only)"
    - "backend/src/second_brain/agents/agent_middleware/capture_trace.py (120 lines, two GA-shaped middleware classes)"
    - "backend/tests/test_legacy_middleware_imports_survive.py (57 lines, 3 sub-tests)"
  modified: []
decisions:
  - "Used existing canonical source docs/foundry/investigation-agent-instructions.md (per MEMORY.md Phase 17.1 lock and plan read_first); NOT the CANDIDATE file at .planning/phases/23-foundry-ga-prep/CANDIDATE-instructions/investigation.md (which has reformatted ellipsis characters and minor wording drift)"
  - "Kept CaptureTraceAgentMiddleware as a no-op when capture_trace_id_var is empty (does not call set_attribute) -- matches legacy CaptureTraceSpanProcessor pattern in observability/span_processor.py:27-30"
  - "Defensive .value unwrapping added in FunctionMiddleware result handling -- the legacy ToolTimingMiddleware did this (middleware.py:84-86) and we mirror it so file_capture dict results are reachable regardless of GA wrapper shape"
  - "Adjusted plan body's middleware signatures to match actual GA SDK exports (AgentContext not AgentRunContext; call_next: Callable[[], Awaitable[None]] not next(context)) -- verified via inspect at execution time"
metrics:
  duration_minutes: 18
  tasks_completed: 4
  commits: 4
  completed_at: "2026-05-10T18:12:34Z"
---

# Phase 24 Plan 03: Capture-Trace Middleware + Investigation Instructions Summary

Land the GA-shaped capture-trace middleware classes and Investigation instructions
file FIRST per CONTEXT D-13 (middleware-first ordering), at the P1-3-correct
package path `agents/agent_middleware/` to keep the legacy `agents/middleware.py`
module unshadowed during the migration window.

## Files Added

| File | Purpose | Lines |
|------|---------|-------|
| `backend/src/second_brain/agents/instructions/investigation.md` | D-02 repo-owned Investigation agent instructions (verbatim copy of `docs/foundry/investigation-agent-instructions.md`) | 290 |
| `backend/src/second_brain/agents/agent_middleware/__init__.py` | Package marker; documents P1-3 amendment; no re-exports (callers import via FQN) | 16 |
| `backend/src/second_brain/agents/agent_middleware/capture_trace.py` | `CaptureTraceAgentMiddleware` + `CaptureTraceFunctionMiddleware` | 120 |
| `backend/tests/test_legacy_middleware_imports_survive.py` | 3 sub-tests guarding the P1-3 invariant | 57 |

## Files NOT Touched (Intentional)

- `backend/src/second_brain/agents/middleware.py` — legacy `AuditAgentMiddleware` + `ToolTimingMiddleware` STILL present and importable. Plan 24-18 deletes.
- `backend/src/second_brain/observability/span_processor.py` — narrowed-scope behavior is documented, not coded (per W-01); plan 24-06 amends the comment.

## Confirmed Invariants

- **F-17 anti-pattern absent.** `! grep -q "tracer.start_as_current_span" backend/src/second_brain/agents/agent_middleware/capture_trace.py` returns 0. Both middleware classes use `trace.get_current_span().set_attribute(...)` exclusively.
- **ContextVar import path correct.** `from second_brain.tools.classification import capture_trace_id_var` matches the existing CaptureTraceSpanProcessor (`observability/span_processor.py:13`).
- **P1-3 invariant — legacy unshadowed.** `cd backend && uv run python -c "from second_brain.agents.middleware import AuditAgentMiddleware, ToolTimingMiddleware"` exits 0. `! test -d backend/src/second_brain/agents/middleware` returns 0.
- **GA SDK subclass relationship.** `assert issubclass(CaptureTraceAgentMiddleware, AgentMiddleware)` and `assert issubclass(CaptureTraceFunctionMiddleware, FunctionMiddleware)` pass.
- **Red test fully green.** All 3 sub-tests in `test_legacy_middleware_imports_survive.py` pass (legacy importable, new GA at distinct path, no shadowing directory).

## Lifted Attributes

`CaptureTraceFunctionMiddleware` lifts the following attributes from tool results onto the framework's `execute_tool` span (lifted from legacy `agents/middleware.py:82-104`):

| Tool | Attribute | Type | Source |
|------|-----------|------|--------|
| `file_capture` | `classification.bucket` | str | `result["bucket"]` |
| `file_capture` | `classification.confidence` | float | `result["confidence"]` (cast with `contextlib.suppress(TypeError, ValueError)`) |
| `file_capture` | `classification.status` | str | `result["status"]` |
| `file_capture` | `classification.item_id` | str | `result["itemId"]` |
| `transcribe_audio` | `transcription.success` | bool | `bool(result and isinstance(result, str))` |

Legacy duration attributes (`agent.duration_ms`, `tool.duration_ms`) are intentionally NOT carried over — the GA framework emits duration via `gen_ai` semantic conventions, so duplicating them would be dead weight.

## Deviations from Plan

### Auto-fixed Issues (Rule 3 — blocking issues, mechanical fixes)

**1. [Rule 3 - Blocking] GA SDK exports `AgentContext` not `AgentRunContext`**

- **Found during:** Task 4
- **Issue:** Plan's `<interfaces>` block specified `from agent_framework import AgentRunContext`, but the GA SDK only exports `AgentContext`. Verified via `from agent_framework import AgentContext` and inspection of GA SDK signature: `AgentMiddleware.process(self, context: 'AgentContext', call_next: 'Callable[[], Awaitable[None]]') -> 'None'`.
- **Fix:** Used `AgentContext` for the `CaptureTraceAgentMiddleware.process` parameter type.
- **Files modified:** `backend/src/second_brain/agents/agent_middleware/capture_trace.py`
- **Commit:** `4b55be5`

**2. [Rule 3 - Blocking] GA SDK call_next signature**

- **Found during:** Task 4
- **Issue:** Plan body wrote `next: Callable[[AgentRunContext], Awaitable[None]]` and `await next(context)`. The GA SDK's actual signature is `call_next: Callable[[], Awaitable[None]]` — call_next takes NO argument and is named `call_next` (matches the legacy middleware.py shape and the GA SDK docstring example).
- **Fix:** Renamed parameter from `next` to `call_next` in both classes (also avoids shadowing Python's builtin `next`); calls site changed to `await call_next()` (no argument).
- **Files modified:** `backend/src/second_brain/agents/agent_middleware/capture_trace.py`
- **Commit:** `4b55be5`
- **Plan acknowledgment:** The plan body itself notes "If the GA SDK's actual parameter name differs (e.g., `call_next`), adjust both classes consistently — the working contract is that the framework awaits `await next(context)` exactly once." We adjusted as required.

**3. [Rule 3 - Blocking] Plan's strict pre-push grep guards forbid literal strings even in docstrings**

- **Found during:** Task 4 acceptance criteria
- **Issue:** The plan's verify command `! grep -q "tracer.start_as_current_span"` and `! grep -qE "agent.duration_ms|tool.duration_ms"` are mechanical greps that don't distinguish docstring from code. The original plan body's docstring contained both forbidden literal strings (as F-17 explanatory text and "duration attributes are dropped because..." text), causing the verify chain to fail.
- **Fix:** Rephrased docstrings to keep the same guidance using non-matching wording. The forbidden patterns now appear NOWHERE in the file (neither code nor docstring), so the mechanical grep guard works as intended. Behavior unchanged.
- **Files modified:** `backend/src/second_brain/agents/agent_middleware/capture_trace.py`
- **Commit:** `4b55be5`

**4. [Rule 3 - Blocking] Ruff SIM105: try-except-pass replaced with contextlib.suppress**

- **Found during:** Task 4 lint check
- **Issue:** Project-level ruff config enforces SIM105: prefer `contextlib.suppress(TypeError, ValueError)` over `try-except-pass`. The plan's literal code body used `try-except-pass` for the confidence cast.
- **Fix:** Added `import contextlib` and replaced the `try-except-pass` block with `with contextlib.suppress(TypeError, ValueError):`. Behavior identical (both swallow `TypeError`/`ValueError`).
- **Files modified:** `backend/src/second_brain/agents/agent_middleware/capture_trace.py`
- **Commit:** `4b55be5`

### Auto-added Defensiveness (Rule 2 — missing critical correctness)

**5. [Rule 2 - Missing critical correctness] Defensive `.value` unwrapping for tool result**

- **Found during:** Task 4
- **Issue:** Legacy `ToolTimingMiddleware` (lines 84-86 of agents/middleware.py) does `if hasattr(raw_result, "value"): raw_result = raw_result.value` BEFORE checking `isinstance(raw_result, dict)`. This unwrapping was NOT in the plan body. Without it, if the GA `FunctionInvocationContext.result` wraps the tool's actual return in a value-bearing object (which the legacy middleware's existence implies happens with the agent_framework), our `isinstance(result, dict)` check on the wrapper would be False and `classification.*` attributes would silently NOT be lifted onto the span — exactly the observability gap we're trying to NOT regress on.
- **Fix:** Added the same defensive unwrap in `CaptureTraceFunctionMiddleware.process`: `if result is not None and hasattr(result, "value"): result = result.value` BEFORE the dict-shape check.
- **Files modified:** `backend/src/second_brain/agents/agent_middleware/capture_trace.py`
- **Commit:** `4b55be5`

## Authentication Gates

None. This plan is pure local code + tests; no Azure interactions.

## Verification Notes

- Local main is intentionally not buildable (8 source files still import RC; AST scan test in 24-02 is intentionally RED). All verification used direct module imports against the test target files (which DO resolve cleanly because they only import `agent_framework`/`opentelemetry`/`second_brain.tools.classification`, none of which hit the unbuildable RC import sites).
- `cd backend && uv run pytest tests/test_legacy_middleware_imports_survive.py -v` exits 0 with all 3 sub-tests green.
- `cd backend && uv run ruff check src/second_brain/agents/agent_middleware/capture_trace.py` reports "All checks passed!".

## Commits

| Hash | Task | Message |
|------|------|---------|
| `b3dd29a` | Task 1 | feat(24-03): promote Investigation instructions to repo |
| `502c3de` | Task 2 | test(24-03): land RED test for P1-3 package-rename invariant |
| `f6692f0` | Task 3 | feat(24-03): create agents/agent_middleware/ package marker |
| `4b55be5` | Task 4 | feat(24-03): implement CaptureTrace AgentMiddleware + FunctionMiddleware |

## Deferred Items

- Legacy `agents/middleware.py` deletion (owned by plan 24-18).
- Optional package rename `agent_middleware/` → `middleware/` after legacy deletion (owned by plan 24-18).
- Red test removal/inversion (owned by plan 24-18 — the file's docstring already states this).
- `observability/span_processor.py` narrowed-scope comment update (owned by plan 24-06 per W-01).

## Plan Self-Check: PASSED

- All 4 created files exist on disk.
- All 4 commits exist in git log on local main.
- All acceptance criteria from the plan's verify and acceptance_criteria blocks pass.
- Red test `test_legacy_middleware_imports_survive.py` has all 3 sub-tests green.
- F-17 anti-pattern absent from new file (no `tracer.start_as_current_span` literal anywhere).
- P1-3 invariant holds: legacy `agents/middleware.py` still importable; no `agents/middleware/` directory exists.
