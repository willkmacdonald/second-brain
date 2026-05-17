---
phase: 24-foundry-ga-migration
status: shipped-with-hotfixes
shipped: 2026-05-11
verified: 2026-05-17
final_revision: second-brain-api--0000089 (image SHA 853a68b46ad920005e3d70fe39f810df814548a8)
plan_count: 26
plans_completed: 24
plans_deferred_to_phase_25_or_backlog: 2 (24-23 advanced via UAT-RESULTS; 24-24 to follow)
---

# Phase 24: Foundry GA Migration — Final Summary

**RC → GA migration of all three Foundry agents (Classifier / Admin /
Investigation) on Microsoft Agent Framework 1.3.0, delivered as a
single-deploy transition with task-group commit clustering. Production
serving GA since 2026-05-11; UAT verified 2026-05-17 after two hotfixes.**

## Performance

- **Duration:** 2026-05-05 (design lock) → 2026-05-17 (UAT pass) = 12 days
- **Plans completed:** 24 of 26
- **Plans deferred:** 24-24 (post-UAT foundryThreadId cleanup — next in queue)
- **Plans inserted:** 24-06.5, 24-13.5 (defect closure plans)
- **Hotfixes during UAT:** 2 (c5a2fc7, 853a68b — both were unshipped 24-16/24-11 fixes)

## What shipped to production

### Architectural changes

- All 3 Foundry agents (Classifier / Admin / Investigation) migrated from RC `AzureAIAgentClient` to GA `FoundryChatClient` + `Agent` factory pattern
- RC SDK fully retired — `grep -rE "AzureAIAgentClient|agent_framework\.azure" backend/src/second_brain/` returns empty
- `tool_choice="required"` enforced via `ChatOptions` replaces the Python safety-net retry that lived in the RC streaming adapter
- Custom OTel spans (capture_text / capture_voice / capture_follow_up / admin_agent_process / admin_agent_batch_process) deleted; framework `invoke_agent` spans + middleware-tagged `execute_tool` spans are the canonical traces
- Capture-trace middleware (`CaptureTraceAgentMiddleware` + `CaptureTraceFunctionMiddleware`) replaces RC `AuditAgentMiddleware` + `ToolTimingMiddleware`
- Agent instructions promoted from Foundry portal to repo (`backend/src/second_brain/agents/instructions/*.md`)
- 9 `@tool(approval_mode="never_require")` decorators stripped across InvestigationTools / AdminTools / RecipeTools / ClassifierTools / TranscriptionTools — GA passes bound methods directly to `Agent(tools=[...])`
- Voice path split — `transcribe_audio` is now a direct call from `api/capture.py`, no longer a Foundry tool. Classifier registers ONLY `file_capture`.
- EvalAgentInvoker Protocol facade (temp seam, deleted at end of 23.3 in Plan 24-18) bridged eval pipeline through the migration window
- Conversation history persistence via **Option A** (Plan 24-17 P0-1 OUTCOME): explicit `conversationHistory: list[ConversationTurn]` field on InboxDocument, threaded through stateless `agent.run(messages=[...])` calls. Cross-process `AgentSession(session_id=stored_id)` rehydration was proven broken on GA SDK 1.3.0 via three independent probe runs.

### Code metrics

- ~1500 lines of source modified across 60+ files
- 7 agent middleware files (3 deleted, 1 new package)
- 71 cross-cutting Phase 24 regression-guard tests pass (`test_no_rc_imports_after_cleanup`, `test_foundry_credential_shape`, `test_legacy_middleware_imports_survive`, etc.)
- 504 passing tests in the full backend suite (9 skipped, 0 failed)
- Cumulative framework-fidelity audit (Plan 24-20): PASS-WITH-WARNINGS, **0 in-scope ❌**, all 19 calibration F-## findings closed, all 8 plan defects closed

### Deployment

- Image SHA: 853a68b (after 2 in-flight hotfixes from initial 1bc40d8)
- Container App: second-brain-api at brain.willmacdonald.com
- Revision: --0000089 (final, post Step C env-var cleanup)
- `AZURE_AI_*_AGENT_ID` orphan env vars: REMOVED 2026-05-17T01:23Z
- `FOUNDRY_MODEL=gpt-4o` + `ENABLE_INSTRUMENTATION=true` + `ENABLE_SENSITIVE_DATA=false` set
- `Settings.extra='ignore'` tolerates residual env vars during transition window (Plan 24-21)

## Hotfixes during UAT (2026-05-17)

Both fixes were code that had been written during 24-16 / 24-11 but
**never committed**. The working tree carried the fix files in a
modified-but-unstaged state when those plan commits landed.

### Hotfix 1: `c5a2fc7` — _parse_args partial-chunk protection

**Root cause:** `streaming/adapter.py:_parse_args()` had a bare
`json.loads(raw)` with no exception handling. The GA framework streams
tool-call arguments as partial JSON chunks (`'{"'`, `'text'`, `'":"'`,
`'buy'`, ...) — the first call to `_parse_args` on the first chunk
raised JSONDecodeError, bubbled through the streaming adapter's outer
except, emitted `forced_tool_failure` SSE. Every text/voice capture
failed silently between 2026-05-15 and 2026-05-17.

**Fix:** Wrap `json.loads` in try/except, return `{}` on partial
chunks. The final function_result carries authoritative fields so
dropping partials is safe. 28 streaming-adapter regression tests pass.

**Why local harness missed it:** Harness iterated the GA stream and
logged content but never called `_parse_args` on partials. Production
code calls it on every `function_call` content type seen, including
partial chunks.

### Hotfix 2: `853a68b` — admin _output_tool_called detection

**Root cause:** `processing/admin_handoff.py:_output_tool_called()`
walked `role='tool'` messages looking for `content.name` on
function_result Content blocks. The GA framework puts the tool name on
the **function_call** Content (in the prior `role='assistant'` message),
NOT on the function_result. Detection always returned `(False, set())`.

This caused: admin agent fired output tool (Errand/Task created in
Cosmos) → detection said "no tool called" → inbox doc marked failed →
NOT deleted → next `/api/errands` poll re-fired the agent → duplicate
items piled up → "Processing 1 new capture..." banner stuck forever.

**Fix:** Walk function_call content blocks (any role) for
`(name, call_id)` pairs. Correlate with function_result's `exception`
field to filter out validation-failure results (still count as
attempted but not fired, triggering the retry-with-nudge path).
19 admin_handoff tests rewritten against the real shape (probe-verified
2026-05-17 by local probe against deployed Foundry).

**Why local harness missed it:** Plan 24-11 calibrated against probe
fixture `tool_call_extraction.json` which showed `role='tool'` messages
but didn't expose what `name` looks like on the result content. The
test mocks built against the wrong assumption never caught the bug.

## Lessons learned

1. **Uncommitted fixes are silent failures.** Both hotfixes were written
   during the original plans but never `git add`-ed. CI cleared because
   tests passed against the working-tree code, but the deployed image
   only contained what was staged. Future plans need a "git status
   clean before push" guardrail.

2. **Probe-driven detection requires probing the actual data shape, not
   just the schema names.** Plan 24-11's probe showed `role='tool'`
   messages existed but didn't enumerate the fields on the contents
   inside. Test mocks calibrated against incomplete probe data baked
   the wrong assumption in.

3. **Post-deploy UAT catches what test suites miss.** Both hotfixes
   were surfaced only by driving real captures through the deployed
   system. The 504-test suite passed against both broken versions.

4. **Streaming behavior differs from request-response behavior.** RC
   delivered tool args as a single dict; GA streams them as partial
   chunks. Code written for the RC shape needs to be re-verified
   against streaming.

## Acceptance criteria — final tally

Per ROADMAP.md Phase 24 success criteria:

- ✓ All RC SDK references retired (`grep -rE "AzureAIAgentClient|agent_framework\.azure"` empty)
- ✓ All 3 agents constructed via GA `FoundryChatClient` + `Agent` factories
- ✓ `tool_choice="required"` replaces Python safety net
- ✓ Voice path split (transcribe_audio direct-call, not a tool)
- ✓ Option A conversation history (P0-1 OUTCOME, verified end-to-end UAT #5)
- ✓ Capture-trace middleware tags framework spans
- ✓ AZURE_AI_*_AGENT_ID env vars removed (Step C completed 2026-05-17T01:23Z)
- ✓ /health probe migrated to per-agent attrs
- ✓ Settings.extra='ignore' tolerates residual env vars
- ✓ Pre-deploy gates resolved (cumulative fidelity audit PASS-WITH-WARNINGS, 0 in-scope ❌)
- ✓ Post-deploy UAT verified (see 24-UAT-RESULTS.md)

## Open items rolling forward

| Item | Disposition |
|------|-------------|
| Plan 24-24: foundryThreadId field removal + backfill script | Next in queue after this artifact lands |
| `test_health.py` stale foundry_client reference | Follow-up — matches yesterday's test_observability.py fix |
| `test_event_tracing.py` / `test_streaming_adapter.py::TestPendingCallsPairing` / `test_classifier_integration.py` rewrite for GA shape | Follow-up |
| Phase 25 (Admin Inbox Soft-Delete + 30-day Retention) | Roadmap-staged |
| Phase 26 (Remove Recipe Extraction) | Roadmap-staged after UAT decision |
| Backlog: Admin Retry Bound (cap retries at N=3) | Backlogged |
| Backlog: Admin Recipe-Fetch Fallback | Backlogged (becomes obsolete on Phase 26) |
| 7-day forced_tool_failure tracking window (through 2026-05-24) | Open for monitoring |

---
*Phase 24: Foundry GA Migration — SHIPPED*
*Final revision: second-brain-api--0000089*
*Image SHA: 853a68b46ad920005e3d70fe39f810df814548a8*
*UAT verified: 2026-05-17*
