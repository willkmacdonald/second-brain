# Phase 21.1 Deferred Items

## Pre-existing: agent-framework-azure-ai import path change

- **Discovered during:** 21.1-02 Task 2 automated verification
- **Issue:** `agent-framework-azure-ai` upgraded from 1.0.0rc2 to 1.2.0 (visible in uv.lock diff). The import `from agent_framework.azure import AzureAIAgentClient` in `admin_handoff.py` no longer resolves. This causes `tests/test_admin_handoff.py` (and likely other tests importing from admin_handoff) to fail with ImportError.
- **Scope:** Pre-existing -- not caused by Phase 21.1 changes. The uv.lock was modified before Phase 21.1 plan 02 execution.
- **Impact:** Backend test suite cannot run all tests. Foundry eval tests (test_foundry_eval.py) pass independently (15/15).
- **Action needed:** Update import paths in `admin_handoff.py` (and any other files) to match the new `agent-framework-azure-ai` 1.2.0 API surface.
