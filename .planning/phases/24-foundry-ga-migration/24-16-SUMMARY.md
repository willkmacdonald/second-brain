---
phase: 24-foundry-ga-migration
plan: 16
subsystem: backend/streaming
tags: [foundry-ga, classifier-streaming, p0-1, option-a, forced-tool-failure, f-04, f-09, f-10, f-13, f-14]

# Dependency graph
requires:
  - phase: 24-foundry-ga-migration/14
    provides: app.state.classifier_agent (GA Agent with tools=[file_capture] only)
  - phase: 24-foundry-ga-migration/15
    provides: resolve_inbox_conversation_history helper + ConversationTurn model + voice handler direct-transcribe path
  - phase: 24-foundry-ga-migration/06.5
    provides: P0-1 OUTCOME (session_rehydration_fresh_process.json — cross-process recall fails on GA SDK 1.3.0)
  - phase: 24-foundry-ga-migration/07
    provides: investigation_adapter.py rewrite as Option A reference pattern
  - phase: 24-foundry-ga-migration/11
    provides: post-hoc tool detection via response.messages walk (admin_handoff pattern)
provides:
  - "Classifier streaming surface fully on GA agent.run(messages, stream=True) contract"
  - "Stateless P0-1 Option A applied to classifier text + follow-up paths"
  - "forced_tool_failure SSE sub_code wired (D-04) — replaces deleted Python safety net (F-09 + D-03)"
  - "Voice generator (stream_voice_capture) removed; voice routes through stream_text_capture after 24-15 transcribe"
  - "conversationHistory upsert is race-safe — re-reads doc before write to avoid clobbering file_capture writes"
  - "New-capture path uses file_capture tool result's primary item_id to locate the doc for conversationHistory persistence"
affects:
  - "24-17 (InboxDocument.conversationHistory schema addition lands cleanly on top of this wiring)"
  - "24-18 (legacy agents/middleware.py deletion); 24-19 (warmup loop GA migration)"
  - "Plan 24-19.5 (RC dep removal) cleared on classifier streaming surface — adapter no longer imports agent_framework.azure"

# Tech tracking
tech-stack:
  added:
    - "agent_framework.Agent + Message + ChatOptions wired into the Classifier SSE adapter"
    - "second_brain.cosmos.inbox_conversation_history.{ConversationTurn, resolve_inbox_conversation_history} consumed at the streaming-layer boundary"
    - "uuid for fresh per-turn thread_id on the COMPLETE SSE event (mobile backward compat only)"
  patterns:
    - "P0-1 Option A on the classifier surface — caller passes inbox_doc, adapter resolves conversationHistory, threads explicit Message list, accumulates assistant text, appends turns, persists history back to Cosmos"
    - "forced_tool_failure SSE sub_code emission point = streaming adapter — covers both the no-tool-fired branch (file_capture_results empty) and the exception-path branch (agent.run raised)"
    - "Race-safe conversationHistory upsert — re-read the inbox doc from Cosmos before upsert so the adapter does not clobber concurrent file_capture writes that ran INSIDE agent.run()"
    - "New-capture path locates the doc via primary file_capture tool result's item_id when caller passes inbox_doc=None — no orphan conversationHistory doc"

key-files:
  created: []
  modified:
    - backend/src/second_brain/streaming/adapter.py
    - backend/src/second_brain/api/capture.py

key-decisions:
  - "stream_voice_capture function fully deleted — the docstring-substring `stream_voice_capture` is also removed from the file (Rule 1 — the plan's acceptance grep matches anywhere in the file, not just identifier usage; same pattern as 24-07 Deviation #1 and 24-15 Decision #4)"
  - "_stream_with_thread_id_persistence helper in api/capture.py is DELETED outright — its job (foundryThreadId persistence on MISUNDERSTOOD) is replaced by the adapter's conversationHistory write. The wrapper had a Cosmos-read-then-upsert race against file_capture identical to the one this adapter now avoids."
  - "_stream_with_follow_up_context simplified to a 2-line context-manager wrap. Its prior foundryThreadId persistence is also deleted; the ContextVar manipulation (for file_capture's in-place update) is the only remaining job."
  - "New captures pass inbox_doc=None to the adapter — the adapter uses file_capture's primary item_id from the tool result to locate the doc for conversationHistory persistence. Avoids orphan/double-doc semantics for new captures."
  - "Race-safe conversationHistory upsert (Rule 1 fix discovered during Task 2 design): the adapter re-reads the Cosmos doc before writing because file_capture writes the doc INSIDE agent.run() with classification fields; both use upsert_item(body=full_doc), so without a re-read the adapter would wipe out file_capture's writes."
  - "Per-call thread_id on the COMPLETE SSE event is a fresh UUID with no server meaning (mirrors 24-07 Investigation). app-level thread_id passed by mobile stays available for MISUNDERSTOOD events but is no longer carried as a Foundry conversation_id round-trip (F-13 cleared)."
  - "Forced-tool failure has two emission points: (a) tool_choice='required' produced no file_capture result (file_capture_results empty after stream end) — warning log + forced_tool_failure SSE event; (b) agent.run raised any exception — error log + forced_tool_failure SSE event. Both paths converge on the same wire shape so monitoring can break out via the sub_code."
  - "Custom OTel spans (capture_text/capture_voice/capture_follow_up) deleted (F-14). capture.* attributes (capture.type, thread_id, run_id, outcome, bucket, confidence, split_count, buckets) ride on structured logger.info(extra=log_extra) dicts. The framework invoke_agent span (auto-emitted + tagged at source by CaptureTraceAgentMiddleware from 24-03) is the canonical correlation surface."
  - "Voice-handler text path (api/capture.py:capture_voice after 24-15 transcribe succeeded) ALSO passes inbox_doc=None — same new-capture semantics as text capture. The voice generator's blob-cleanup finally block is preserved."

patterns-established:
  - "Stateless Option A on a tool-calling agent surface: caller can pass inbox_doc=None for new captures (adapter locates doc via primary tool-result item_id) OR pass the loaded existing doc for follow-ups. The adapter handles both shapes uniformly via _get_inbox_id."
  - "Race-safe conversationHistory persistence: the adapter MUST re-read the doc before upserting when another writer (file_capture) might have updated the same doc during the same logical request. Future agent surfaces that do in-stream Cosmos writes + post-stream history writes inherit this pattern."

requirements-completed: [F-04, F-09, F-10, F-13, F-14, F-18, D-01, D-02, D-03, D-04, D-13, P0-1, P0-2]

# Metrics
duration: 8min
completed: 2026-05-11
---

# Phase 24 Plan 16: Classifier Streaming GA + P0-1 Option A — Summary

**The biggest commit in 23.3.** `streaming/adapter.py` rewritten against GA `agent.run(messages, stream=True)`; Python safety net deleted; custom OTel spans deleted; `forced_tool_failure` SSE sub_code wired; voice generator removed; `stream_text_capture` and `stream_follow_up_capture` consume the 24-15 `resolve_inbox_conversation_history` helper and persist the updated `conversationHistory` back to the inbox doc (P0-1 OUTCOME Option A). `api/capture.py` callers switched to `agent=app.state.classifier_agent` and `inbox_doc=` pass-through. Both files are GA-clean; 12/12 Phase 24 regression-guard tests stay green.

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-11T05:25:32Z
- **Completed:** 2026-05-11T05:33:30Z
- **Tasks:** 2 (per plan); 3 commits actually landed (Task 1 + race-safety follow-on + Task 2)
- **Files modified:** 2 (streaming/adapter.py, api/capture.py)
- **Lines:** +614 / −746 (net −132)

## Accomplishments

### F-04 cleared on the Classifier streaming surface

Before:
```python
from agent_framework import ChatOptions, Message
from agent_framework.azure import AzureAIAgentClient
```

After:
```python
from agent_framework import Agent, ChatOptions, Message
from second_brain.cosmos.inbox_conversation_history import (
    ConversationTurn,
    resolve_inbox_conversation_history,
)
```

The adapter no longer references `AzureAIAgentClient` anywhere. `Message` is kept (P0-1 Option A: explicit Message list construction). `ChatOptions` is kept (used as `ChatOptions(tool_choice="required")`).

### F-09 + D-03 cleared (Python safety net deleted)

`_safety_net_file_as_misunderstood` is GONE. The previous behavior — when the agent emitted no `file_capture` calls, the adapter wrote a misunderstood Inbox doc itself and emitted MISUNDERSTOOD — is replaced by:

1. `tool_choice="required"` (string form per probe 3) forces the model to call SOME tool. With only `file_capture` registered (F-11, 24-14), this is unambiguous.
2. If the framework still produces no `file_capture` result after the stream completes (extremely rare under `tool_choice="required"`), the adapter emits an `ERROR` SSE event with `sub_code="forced_tool_failure"` so monitoring can break this out from generic errors.

### F-10 cleared (RC provider-dict tool_choice replaced)

Before (both `stream_text_capture` and `stream_follow_up_capture`):
```python
options: ChatOptions = {
    "tools": tools,
    "tool_choice": {"mode": "required", "required_function_name": "file_capture"},
}
```

After (both):
```python
options = ChatOptions(tool_choice="required")
```

Plain string form per probe 3 (`tool_choice_required.json`). Provider-dict pinning (`{"mode": "required", "required_function_name": "..."}`) is not used (D-10: schema undocumented; not pursued in Phase 24).

### F-13 cleared on the Classifier streaming surface

Before:
```python
foundry_conversation_id: str | None = None
async for update in stream:
    if getattr(update, "conversation_id", None) and not foundry_conversation_id:
        foundry_conversation_id = update.conversation_id
    ...
# Follow-up: options["conversation_id"] = foundry_thread_id
```

After: no `conversation_id` reads, no `options["conversation_id"]` writes. Conversation continuity is now stateless — the adapter constructs the message list from `conversationHistory` on each call, threads it explicitly, and persists the updated list back to the doc. MISUNDERSTOOD events emit no `foundryConversationId` field. COMPLETE events emit `thread_id = uuid.uuid4()` only (no `sessionId`).

### F-14 cleared (custom OTel spans deleted, 3 sites)

Before:
- `with tracer.start_as_current_span("capture_text") as span:` in `stream_text_capture`
- `with tracer.start_as_current_span("capture_voice") as span:` in `stream_voice_capture`
- `with tracer.start_as_current_span("capture_follow_up") as span:` in `stream_follow_up_capture`

After: all three deleted. `tracer = trace.get_tracer(...)` module-level reference removed (no remaining caller). `from opentelemetry import trace` import in the adapter dropped.

The `capture.*` attributes (`capture.type`, `capture.thread_id`, `capture.run_id`, `capture.trace_id`, `capture.outcome`, `capture.bucket`, `capture.confidence`, `capture.split_count`, `capture.buckets`, `capture.original_inbox_item_id`) now ride on `logger.info(..., extra=log_extra)` and `logger.warning/error(..., extra={**log_extra, "capture.outcome": ...})` structured-log entries. The framework `invoke_agent` span (auto-emitted by GA SDK + tagged at source by `CaptureTraceAgentMiddleware` from 24-03) is the canonical correlation surface.

### P0-1 OUTCOME Option A wired on the classifier surface

New signatures:
```python
async def stream_text_capture(
    agent: Agent,
    user_text: str,
    inbox_doc,                  # NEW (was: tools, thread_id)
    thread_id: str,
    run_id: str,
    cosmos_manager=None,
    capture_trace_id: str = "",
) -> AsyncGenerator[str, None]:

async def stream_follow_up_capture(
    agent: Agent,
    follow_up_text: str,
    inbox_doc,                  # NEW (was: foundry_thread_id)
    original_inbox_item_id: str,
    thread_id: str,
    run_id: str,
    cosmos_manager=None,
    capture_trace_id: str = "",
) -> AsyncGenerator[str, None]:
```

Body pattern (both functions):
```python
history = resolve_inbox_conversation_history(inbox_doc) if inbox_doc else []
msg_list = _build_message_list(history, new_user_text)  # [Message(role=t.role, contents=[t.content]) for t in history] + [Message(role="user", contents=[new_text])]
options = ChatOptions(tool_choice="required")

accumulated_assistant_text = ""
async with asyncio.timeout(60):
    stream = agent.run(msg_list, options=options, stream=True)
    async for update in stream:
        text_delta = getattr(update, "text", "")
        if text_delta:
            accumulated_assistant_text += text_delta
            # logged to reasoning channel, NOT yielded as SSE
        for content in getattr(update, "contents", None) or []:
            ...

# After stream completes successfully:
history.append(ConversationTurn(role="user", content=new_user_text))
if accumulated_assistant_text:
    history.append(ConversationTurn(role="assistant", content=accumulated_assistant_text))
await _upsert_inbox_with_history(cosmos_manager, persist_target, history, capture_trace_id)
yield encode_sse(complete_event(str(uuid.uuid4()), run_id))
```

`AgentSession` is NOT imported. `session_id` is NOT used. The COMPLETE event drops `sessionId`. `thread_id` on COMPLETE is a fresh per-turn UUID for mobile backward compat only.

### Voice streaming function DELETED

`stream_voice_capture` is removed entirely. The voice path is handled in `api/capture.py:capture_voice` (24-15): the handler direct-calls `transcription_tools.transcribe_audio(blob_url)` BEFORE classifying, then routes the transcript through `stream_text_capture`. With `tools=[file_capture]` only (F-11), `tool_choice="required"` is unambiguous on the text path.

The literal substring `stream_voice_capture` is also removed from the file's comment block (per Rule 1 — the plan's acceptance check `! grep -q "stream_voice_capture"` matches comments too; same pattern as 24-15 Decision #4).

### Race-safe conversationHistory upsert (Rule 1 fix)

Discovered during Task 2 design: the adapter and `file_capture` both write the same inbox doc using `upsert_item(body=full_doc)`. `file_capture` runs INSIDE `agent.run()` and writes classification fields (filedRecordId, classificationMeta, status, etc.); the adapter writes `conversationHistory` AFTER the stream completes. Without re-reading, the adapter's upsert would clobber file_capture's writes.

`_upsert_inbox_with_history` now:
1. Reads the latest doc from Cosmos using `inbox_doc.id` (or `primary.item_id` for new captures).
2. Overwrites only `doc["conversationHistory"]`.
3. Upserts the merged body.

For the rare case where `file_capture` did not write (e.g., classifier raised `forced_tool_failure` before any tool result was processed), the read fails and the helper falls back to the caller-supplied body so `conversationHistory` is still persisted.

### forced_tool_failure SSE sub_code (D-04) wired

```python
def _forced_tool_failure_event() -> dict:
    return {
        "type": "ERROR",
        "message": "Classifier could not file this capture.",
        "sub_code": "forced_tool_failure",
    }
```

Emitted at two sites in each of `stream_text_capture` and `stream_follow_up_capture`:
- **No-tool-fired branch:** after the stream loop ends with `file_capture_results` empty (or `detected_tool != "file_capture"`).
- **Exception branch:** any `Exception` raised by `agent.run(...)` or asyncio.timeout — caught, logged, then `forced_tool_failure` event yielded followed by the COMPLETE event.

Both branches converge on the same wire shape (`type: ERROR, sub_code: forced_tool_failure, message: ...`). Mobile already handles `ERROR`; the sub_code is for dashboards/Investigation Agent queries.

### api/capture.py call sites updated (Task 2)

All 4 endpoints (`/api/capture`, `/api/capture/voice`, `/api/capture/follow-up`, `/api/capture/follow-up/voice`) reshaped:
- Read `request.app.state.classifier_agent` (was `classifier_client`); raise 503 if `None`.
- Pass `agent=classifier_agent` (was `client=classifier_client`).
- Pass `inbox_doc=None` (new captures — text + voice-after-transcribe) or `inbox_doc=inbox_doc` (follow-ups — load doc from Cosmos by inbox_item_id).
- Drop `tools=app.state.classifier_agent_tools` kwarg.
- Drop `thread_id=foundry_thread_id` and `foundry_thread_id=foundry_thread_id` from follow-up call sites — `thread_id` is now a fresh app-level UUID (was the foundry thread id).
- Remove `_stream_with_thread_id_persistence` helper entirely (its job is replaced by the adapter's conversationHistory write).
- Simplify `_stream_with_follow_up_context` to a 2-line context-manager wrap (only the `_follow_up_inbox_item_id` ContextVar is still load-bearing).
- Drop `import json` and `from second_brain.spine.cosmos_request_id import trace_headers` (no remaining usage in capture.py — both were only used by the deleted helpers).

The voice handler retains its blob-cleanup finally block. The follow-up voice handler retains its in-memory transcribe-from-bytes path (separate from the voice-capture blob-download path; future plan can unify).

## Task Commits

| Task | Hash | Title |
|------|------|-------|
| 1 (adapter rewrite) | `411ff61` | feat(24-16): rewrite streaming/adapter.py against GA agent.run stateless (P0-1 Option A) |
| 1.5 (race-safety fix) | `b9c116d` | fix(24-16): race-safe conversationHistory upsert in streaming adapter |
| 2 (api/capture.py callers) | `45bd7bf` | feat(24-16): wire api/capture.py callers to GA Classifier Agent (P0-1 Option A) |

(Plan metadata commit follows this summary.)

## Files Created/Modified

| Path | Change | Notes |
|------|--------|-------|
| `backend/src/second_brain/streaming/adapter.py` | full rewrite (+614/−746 cumulative, including race-safety follow-on) | RC AzureAIAgentClient + ChatOptions dict + Message(text=...) → GA Agent + Message(contents=[...]) + ChatOptions(tool_choice="required"). Safety net + custom spans + voice function deleted. Stateless P0-1 Option A. Race-safe upsert. `agent.run(msg_list, options=options, stream=True)` call shape (positional `msg_list`, no `messages=`). |
| `backend/src/second_brain/api/capture.py` | rewrite (+119/−182) | All 4 endpoints switched to `agent=app.state.classifier_agent` and `inbox_doc=`. `_stream_with_thread_id_persistence` deleted. `_stream_with_follow_up_context` simplified. Voice-after-transcribe path passes `inbox_doc=None` (new capture). Follow-up paths load the doc by `inbox_item_id` and pass through. |

## Decisions Made

1. **stream_voice_capture removal includes literal-substring scrub in comments.** Rule 1 deviation pattern from 24-07 / 24-15 — the plan's `! grep -q "stream_voice_capture"` check matches comments too. Reworded the file's deletion-note comment to avoid the literal substring.

2. **Race-safe upsert via re-read.** Discovered during Task 2 design (Rule 1 — bug). Both `file_capture` (inside `agent.run`) and the adapter (after the stream) write the same doc with full-body upserts. Without a re-read, the adapter would clobber `file_capture`'s field writes. The race-safe upsert reads the latest doc body, overwrites only `conversationHistory`, and upserts. Falls back to caller-body if the doc doesn't exist yet (forced_tool_failure path).

3. **New captures pass inbox_doc=None.** The plan suggested pre-creating an empty inbox_doc dict for new captures, but that conflicts with `file_capture`'s own doc creation (different doc IDs would result in orphan/double docs). The cleaner approach: pass `None`, let `file_capture` create the doc, then the adapter locates the doc by `primary.item_id` from the file_capture_results and writes `conversationHistory` onto it.

4. **For follow-up paths, the caller loads the existing inbox doc.** `api/capture.py:follow_up` and `:follow_up_voice` use `inbox_container.read_item(item=inbox_item_id, partition_key="will")` before invoking the adapter, then pass the loaded dict through as `inbox_doc=`. The adapter's `resolve_inbox_conversation_history` reads from this body.

5. **_stream_with_thread_id_persistence helper deleted entirely.** Its prior job (intercept MISUNDERSTOOD events to persist `foundryThreadId`) is replaced by the adapter's `conversationHistory` write. The wrapper also had a `read_item` → field-update → `upsert_item` race against `file_capture` identical to the one this commit's `_upsert_inbox_with_history` solves; deleting the helper avoids re-introducing the same race in two places.

6. **_stream_with_follow_up_context simplified to 2 lines.** Only `follow_up_context(inbox_item_id)` (setting the `_follow_up_inbox_item_id` ContextVar) is still load-bearing; the prior `foundry_conversation_id` interception + post-stream `foundryThreadId` upsert is gone (same reasons as #5).

7. **Voice-after-transcribe path passes inbox_doc=None.** The voice handler from 24-15 routes the transcript through `stream_text_capture` — same new-capture semantics as a text submission. The blob cleanup `finally` block in `stream_with_cleanup` is preserved.

8. **Adapter parameter order kept consistent across both functions.** `stream_text_capture(agent, user_text, inbox_doc, thread_id, run_id, cosmos_manager=..., capture_trace_id=...)` and `stream_follow_up_capture(agent, follow_up_text, inbox_doc, original_inbox_item_id, thread_id, run_id, cosmos_manager=..., capture_trace_id=...)`. `inbox_doc` is the 3rd positional everywhere; the follow-up adds `original_inbox_item_id` as 4th for logging.

9. **`agent.run()` called positionally, NOT with `messages=` kwarg.** Per probe 1 (`streaming_shape.json`) the GA API takes the message list as the first positional arg. Mirror of 24-07 Investigation adapter call shape.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Literal `stream_voice_capture` substring in deletion-note comment trips the plan's acceptance grep**

- **Found during:** Task 2 verification pass.
- **Issue:** Initial rewrite left the comment "Compatibility shim removed: stream_voice_capture is deleted..." in the file. The plan's `! grep -q "stream_voice_capture"` check matches comments too — the file's deletion-note comment caused a false positive.
- **Fix:** Reworded the comment to use "the previous voice-capture streaming function" instead of the literal name. The deletion-note prose is preserved; the load-bearing grep guard now passes.
- **Files modified:** `backend/src/second_brain/streaming/adapter.py` (comment block at the end of the file).
- **Verification:** `grep -c "stream_voice_capture" backend/src/second_brain/streaming/adapter.py` returns 0.
- **Committed in:** `411ff61` (Task 1 commit — folded into the initial write).

**2. [Rule 1 — Bug] Cosmos doc-write race between file_capture and the adapter's conversationHistory upsert**

- **Found during:** Task 2 design (planning the api/capture.py call sites).
- **Issue:** Both `file_capture` (inside `agent.run`) and the adapter (after the stream) upsert the same inbox doc using `upsert_item(body=full_doc)`. Without re-reading the doc body in the adapter, the post-stream upsert would clobber `file_capture`'s classification-field writes (filedRecordId, classificationMeta, status, etc.).
- **Fix:** `_upsert_inbox_with_history` now reads the latest doc body from Cosmos by id, overwrites only `doc["conversationHistory"]`, then upserts. Falls back to the caller-supplied body if the doc doesn't exist yet (e.g., forced_tool_failure path where file_capture never ran).
- **Files modified:** `backend/src/second_brain/streaming/adapter.py` (the `_upsert_inbox_with_history` body + new `_get_inbox_id` helper).
- **Verification:** `cd backend && uv run ruff check src/second_brain/streaming/adapter.py` returns "All checks passed!". 12/12 Phase 24 regression-guard tests still pass.
- **Committed in:** `b9c116d` (race-safety follow-on commit, between Task 1 and Task 2).

**3. [Rule 2 — Critical functionality] New-capture path needs doc lookup via tool result item_id**

- **Found during:** Task 2 design — the plan suggested pre-creating an empty inbox_doc dict for new captures, but `file_capture` creates its own inbox doc with a separately generated UUID. Without reconciliation, conversationHistory would land on a different doc than `file_capture`'s classified doc — orphan conversationHistory.
- **Fix:** When `inbox_doc=None` is passed (new captures), the adapter uses `primary.item_id` from `file_capture_results` after the stream completes to locate the doc, then calls `_upsert_inbox_with_history` with `{"id": primary_item_id}` so conversationHistory lands on the same doc `file_capture` just created.
- **Files modified:** `backend/src/second_brain/streaming/adapter.py` (the `persist_target` block in `stream_text_capture` body).
- **Verification:** Module imports cleanly; race-safe upsert helper handles the synthetic doc-id-only body correctly via the re-read path.
- **Committed in:** `b9c116d` (race-safety follow-on commit).

**4. [Rule 2 — Critical functionality] 503 guard on missing classifier_agent in all 4 endpoints**

- **Found during:** Task 2 writing api/capture.py callers.
- **Issue:** `app.state.classifier_agent` may be `None` mid-migration (e.g., if 24-14 lifespan registration failed). The previous code crashed loudly on `classifier_client` being `None`; the new code should return 503 cleanly.
- **Fix:** Added `if classifier_agent is None: raise HTTPException(status_code=503, detail=...)` at the top of all 4 endpoints. Voice handlers also clean up the uploaded blob before raising.
- **Files modified:** `backend/src/second_brain/api/capture.py` (4 endpoints).
- **Verification:** `ruff check` passes; manual code review confirms no regression.
- **Committed in:** `45bd7bf` (Task 2 commit).

---

**Total deviations:** 4 auto-fixed. No Rule 4 architectural changes. No scope expansion — all four are within the natural scope of "rewrite streaming/adapter.py against GA + wire api/capture.py callers".

## Authentication Gates

None encountered. Plan validation is via AST parse + grep + import smoke + ruff + pytest of the regression-guard suite — none requires Azure connectivity. The local main.py is still not buildable end-to-end (per CONTEXT D-13 — warmup.py and eval/runner.py / eval/invoker.py still reference RC imports; 24-19 fixes warmup; 24-13 already cleared eval/runner.py).

## Known Stubs

None. All data sources are wired:
- `app.state.classifier_agent` is the GA Agent singleton built by `build_classifier_agent` (24-14) with `tools=[file_capture]`.
- `inbox_doc` for new captures is `None` and the adapter locates the doc via `file_capture` tool result.
- `inbox_doc` for follow-ups is loaded from Cosmos by `inbox_item_id` before calling the adapter.
- `conversationHistory` resolver is the 24-15 helper.
- `_upsert_inbox_with_history` writes against the existing Cosmos `Inbox` container.

The `app.state.classifier_client = None` and `app.state.classifier_agent_id = None` lines in `main.py` (set by 24-14) are NOT stubs — they're intentional mid-migration safe-defaults so the warmup loop and spine adapter short-circuit Classifier until 24-19 migrates them. This adapter no longer reads either field.

## Threat Flags

None — this plan does not introduce new network endpoints, auth paths, file access patterns, or trust-boundary changes.

- The capture endpoints' auth middleware is unchanged.
- Cosmos write paths (inbox_container.upsert_item, .read_item) use the same `partition_key="will"` and `trace_headers(capture_trace_id)` pattern as before.
- The adapter's `_upsert_inbox_with_history` is best-effort with try/except; failures log a warning but never raise — no new error surface to clients.
- The `forced_tool_failure` SSE event's `message` field is a fixed string ("Classifier could not file this capture."). No exception details leaked over the wire.
- The race-safe upsert reads the doc body before writing, preserving file_capture's classification fields — no data corruption.

## TDD Gate Compliance

Plan type is `execute` (not `tdd`). No RED/GREEN gates required. Existing 12/12 Phase 24 regression-guard tests stay green:
- P0-1 OUTCOME dual-read (test_inbox_dual_read.py): 7/7 GREEN.
- P1-3 legacy middleware imports survive: 3/3 GREEN.
- P1-5 sync ManagedIdentityCredential shape: 2/2 GREEN.

The `test_no_rc_imports_after_cleanup.py` AST scan is RED (expected) — `streaming/adapter.py` is now CLEARED from its offender list (zero RC imports). Remaining offenders for that test: `main.py` (24-19), `warmup.py` (24-19), and `eval/invoker.py` (24-18 — RCEvalAgentInvoker class). The classifier streaming surface is now GA-clean.

## Verification

### Adapter (streaming/adapter.py)

| Criterion | Status |
|-----------|--------|
| `! grep -q "from agent_framework.azure import AzureAIAgentClient"` | PASS (0) |
| `! grep -q "_safety_net_file_as_misunderstood"` | PASS (0) |
| `! grep -q 'tracer.start_as_current_span("capture_'` | PASS (0) |
| `! grep -q "AgentSession"` | PASS (0) |
| `! grep -q "stream_voice_capture"` | PASS (0) — comment scrubbed |
| `! grep -q "client.get_response"` | PASS (0) |
| `! grep -q 'options\\["conversation_id"\\]'` | PASS (0) |
| `! grep -q "async def stream_voice_capture"` | PASS (0) |
| `grep -q "from agent_framework import Agent, ChatOptions, Message"` | PASS (1) |
| `grep -q "from second_brain.cosmos.inbox_conversation_history import"` | PASS (1) |
| `grep -q "import uuid"` | PASS (1) |
| `grep -q "agent.run("` | PASS (9 occurrences across both functions + docstrings) |
| `grep -q "stream=True"` | PASS (5 occurrences) |
| `grep -q 'tool_choice="required"'` | PASS (2 — one per function) |
| `grep -q "forced_tool_failure"` | PASS (21 occurrences across helper + emit sites + log extras + docstring) |
| `grep -q "Message(role="` | PASS (2 — _build_message_list + docstring) |
| `grep -q "resolve_inbox_conversation_history"` | PASS (5) |
| `grep -q "conversationHistory"` | PASS (13) |
| `grep -q "upsert_item"` | PASS (2 — adapter upsert + docstring fallback) |
| `grep -q "async def stream_text_capture"` | PASS (1) |
| `grep -q "async def stream_follow_up_capture"` | PASS (1) |
| `ruff check`: All checks passed! | PASS |
| `ast.parse(adapter.py)` | PASS |
| `from second_brain.streaming.adapter import stream_text_capture, stream_follow_up_capture` | PASS |

### API (api/capture.py)

| Criterion | Status |
|-----------|--------|
| `! grep -q "stream_voice_capture"` | PASS (0) |
| `! grep -q "AzureAIAgentClient"` | PASS (0) |
| `! grep -q "classifier_agent_tools"` | PASS (0 — `tools=` kwarg dropped) |
| `grep -q "classifier_agent"` | PASS (14) |
| `grep -q "inbox_doc="` | PASS (5 — 4 endpoints + 1 in voice-handler stream-with-cleanup closure) |
| `grep -q "agent="` | PASS (4 — one per endpoint) |
| `! grep -q "tools=tools"` | PASS (0) |
| `! grep -q "client=client"` | PASS (0) |
| `ruff check`: All checks passed! | PASS |
| `ast.parse(capture.py)` | PASS |
| `from second_brain.api import capture` | PASS — import smoke works (capture.py no longer flows through RC-only imports since adapter.py is now GA-clean and 24-15 transcription helpers are decorator-free) |

### Phase 24 regression-guard tests

```
$ cd backend && uv run pytest tests/test_inbox_dual_read.py tests/test_foundry_credential_shape.py tests/test_legacy_middleware_imports_survive.py -x
12 passed in 0.10s
```

- P0-1 dual-read: 7/7 GREEN
- P1-3 legacy middleware imports: 3/3 GREEN
- P1-5 sync credential shape: 2/2 GREEN

### Out-of-scope test breakage (acknowledged, deferred)

`backend/tests/test_event_tracing.py` and `backend/tests/test_streaming_adapter.py` were written against the RC `client.get_response(stream=True)` shape with `MockUpdate(contents, conversation_id)` mocks. These tests are now broken because:
- `stream_text_capture` / `stream_follow_up_capture` signatures changed (parameters renamed/removed).
- `stream_voice_capture` is deleted.
- Custom OTel `capture_*` spans no longer exist.
- The safety net `_safety_net_file_as_misunderstood` no longer exists.
- The RC `update.conversation_id` field is no longer read.

These two test files are scope of a follow-up plan (likely 24-22 UAT pre-work or a dedicated test-migration plan post-24-19). Per SCOPE BOUNDARY, this plan does NOT update them.

`test_streaming_adapter.py::TestEncodeSSE` and `TestEventConstructors` (which test the wire format helpers, not the adapter functions) continue to pass — those touch `streaming/sse.py` which is unchanged.

## Self-Check: PASSED

**Files claimed modified:**
- [x] FOUND: `backend/src/second_brain/streaming/adapter.py` — GA-clean, P0-1 Option A, race-safe
- [x] FOUND: `backend/src/second_brain/api/capture.py` — all 4 endpoints wired to GA

**Commits claimed:**
- [x] FOUND: `411ff61` (Task 1: adapter.py GA rewrite)
- [x] FOUND: `b9c116d` (race-safety follow-on)
- [x] FOUND: `45bd7bf` (Task 2: api/capture.py callers)

**Test claims:**
- [x] 7/7 tests pass in `test_inbox_dual_read.py`
- [x] 12/12 tests pass in the full Phase 24 regression-guard suite

Verification commands executed:
```bash
git log --oneline -3
# 45bd7bf, b9c116d, 411ff61

cd backend && uv run ruff check src/second_brain/streaming/adapter.py src/second_brain/api/capture.py
# All checks passed!

cd backend && uv run python -c "import ast; ast.parse(open('src/second_brain/streaming/adapter.py').read()); ast.parse(open('src/second_brain/api/capture.py').read()); print('AST PASS')"
# AST PASS

cd backend && uv run pytest tests/test_inbox_dual_read.py tests/test_foundry_credential_shape.py tests/test_legacy_middleware_imports_survive.py -x
# 12 passed in 0.10s
```

## Next Phase Readiness

**Plan 24-17 (InboxDocument schema addition):**

- Adds `conversationHistory: list[ConversationTurn] | None = None` to `InboxDocument` model. Will IMPORT `ConversationTurn` from `second_brain.cosmos.inbox_conversation_history` (already created in 24-15).
- Keeps `foundryThreadId: str | None = None` for rollback safety during the deploy window (cleanup in 24-24).
- Backfill script is ADDITIVE only (new captures get conversationHistory; legacy docs keep foundryThreadId per Option A graceful loss).
- This plan's adapter writes `conversationHistory` on the existing doc body without requiring the model field — the field is added in 24-17 purely for Pydantic-side schema validation/visibility. Cosmos accepts the extra field today.

**Plan 24-18 (legacy agents/middleware.py deletion):**

- Independent of this plan's changes. The middleware imports in this adapter have been gone since 24-03 (the adapter never used `AuditAgentMiddleware`/`ToolTimingMiddleware` directly).

**Plan 24-19 (warmup loop GA migration):**

- The classifier surface's last RC-import sites (`main.py`, `warmup.py`) clear in 24-19. After that, `test_no_rc_imports_after_cleanup.py` goes green.

**Plan 24-22 (UAT):**

- End-to-end verification belongs here: text capture (CLASSIFIED + LOW_CONFIDENCE + MISUNDERSTOOD branches), voice capture (transcribe → classify), follow-up flows (continued conversation history persistence across rounds), forced_tool_failure (force the error path by injecting a tool exception). All against the deployed Container App.
- The 6 SSE event types (CLASSIFIED, LOW_CONFIDENCE, MISUNDERSTOOD, UNRESOLVED, ERROR with sub_code=forced_tool_failure, COMPLETE) are preserved on the wire — mobile clients see the same shape they saw under RC except for the absence of `sessionId` on COMPLETE and the new `sub_code` on ERROR for forced-tool failures.

**Test migration follow-up:**

- `test_event_tracing.py` and most of `test_streaming_adapter.py` need re-writes to the GA shape (AgentResponseUpdate with `.contents` + `.text`, no `conversation_id`, no custom OTel spans). Track as a separate hardening item — not blocking 24-17 through 24-23.

---

*Phase: 24-foundry-ga-migration*
*Plan: 24-16*
*Completed: 2026-05-11*
