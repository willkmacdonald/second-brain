# Phase 25: Admin Inbox Soft-Delete + 30-day Retention — Research

**Researched:** 2026-05-17
**Domain:** Cosmos DB per-document TTL; Admin agent lifecycle (admin_handoff.py); cross-file Inbox query consistency
**Confidence:** HIGH

## Summary

Phase 25 swaps a single `delete_item` call for a `read → mutate (status="filed" + ttl) → upsert_item` triplet, threads a 30-day per-doc TTL through a new `Settings.inbox_filed_retention_days` env-driven config, prepares the Inbox container with `defaultTtl = -1` via `az cosmosdb sql container update --ttl -1` (idempotent), and adds two optional backlink fields (`sourceInboxItemId`, `sourceCaptureTraceId`) to the `ErrandItem` and `TaskItem` Pydantic models populated at admin tool call time via the existing `capture_trace_id_var` ContextVar.

The CONTEXT.md `tools/investigation.py:443,812` line refs are **incorrect** — those lines query the **Feedback** and **EvalResults** containers, not Inbox. The Investigation agent has no Cosmos Inbox query path. It reads inbox state indirectly via App Insights KQL through `observability/queries.py`, where Inbox is referenced only as a bucket name (no SQL). **There is no investigation.py Inbox filter to add.**

What CONTEXT.md missed: there are TWO Inbox SQL queries in `api/errands.py` (lines 174 and 262) that also need to consider `status="filed"` semantics. Line 174 is the "unprocessed Admin items to fire the agent on" query — it already filters by `adminProcessingStatus`, so it will naturally exclude filed items (because filed items have `adminProcessingStatus="completed"` not pending/failed/null). Line 262 is the "deliver admin notifications" query — same orthogonal-status logic. Both are safe today but should be verified by tests.

**Primary recommendation:** 2-plan phase. Plan 01: backend code changes (admin_handoff soft-delete + model field additions + admin.py tool wiring + api/inbox.py filter + config). Plan 02: infra step (az TTL update) + deploy + UAT smoke. Container TTL update can be folded into Plan 01's operator-authorized step list if planner prefers a single plan, but the deploy gate makes a clean two-plan split safer.

## User Constraints (from CONTEXT.md)

### Locked Decisions

**1. TTL mechanism — Per-document Cosmos `ttl`**
When `admin_handoff` marks an Inbox doc as `filed`, it sets `doc["ttl"] = settings.inbox_filed_retention_days * 86400` on the same upsert. Cosmos auto-deletes 30 days after the document's `_ts` (last write timestamp). Zero ongoing operational cost, no new scheduler infrastructure. **Configuration:** New env var `INBOX_FILED_RETENTION_DAYS` (defaults to 30). Threads through `Settings.inbox_filed_retention_days: int = 30`. **Trade-off accepted:** Cosmos doesn't log per-document TTL deletions to spine_events.

**2. Container TTL prep — Plan invokes az CLI**
Cosmos requires the container to have TTL machinery enabled (default TTL ≥ 0 or = -1) before per-doc `ttl` values take effect. Phase 25 plan includes `az cosmosdb sql container update --account-name shared-services-cosmosdb --database-name second-brain --name Inbox --resource-group shared-services-rg --ttl -1` step. `ttl=-1` enables the machinery but doesn't expire anything by default; per-doc `ttl=N` overrides at filing time. **Operator authorization required.** **Verification:** Plan asserts via `az cosmosdb sql container show --query "resource.defaultTtl"` that the value is `-1` after the update.

**3. Filed visibility — Fully out of sight**
Phone inbox view filters out `status="filed"` items. `/investigate` Inbox queries default to excluding `filed` items. **No `include_filed=true` opt-in.** **ROADMAP amendment required:** ROADMAP success criterion #4 currently reads `/investigate Inbox queries default to excluding filed (with opt-in include_filed=true)`. The "with opt-in" clause is dropped.

**4. Bundled scope — Source backlinks on Errand/Task**
Adds two optional fields to `ErrandItem` and `TaskItem` Pydantic models:
- `sourceInboxItemId: str | None = None`
- `sourceCaptureTraceId: str | None = None`
Populated at creation time in `tools/admin.py` when `add_errand_items` / `add_task_items` fires. **Field durability:** `sourceCaptureTraceId` — durable forever (useful for spine_events correlation even after the 30-day Inbox TTL purges the source doc); `sourceInboxItemId` — durable for 30 days while the source Inbox doc exists. UI must gracefully handle absent backlinks (pre-Phase-25 docs).

**5. Backfill — None**
Existing Admin Inbox docs that already got hard-deleted are gone forever. Phase 25 only changes behavior for **new** Admin captures going forward.

### Claude's Discretion
None. CONTEXT.md is fully locked.

### Deferred Ideas (OUT OF SCOPE)
- Filed audit dashboard (`include_filed=true` opt-in for /investigate)
- Per-bucket retention windows
- Soft-delete for non-Admin buckets
- UI "history view" on the phone with greyed filed items

## Phase Requirements

No phase requirement IDs assigned (ROADMAP lists "TBD (likely OBS-XX, EVAL-XX series)"). Planner may either:
- Assign new REQ-IDs in REQUIREMENTS.md at plan-phase time, OR
- Proceed without (planning gate skips when `phase_req_ids` is null).

Functionally derived requirements from ROADMAP success criteria + bundled scope:

| Derived ID | Description | Research Support |
|------------|-------------|------------------|
| REQ-SD-01 | Admin agent success path sets `status="filed"` + per-doc `ttl` on the Inbox doc | admin_handoff.py:396-405 site documented in "Current Code State" |
| REQ-SD-02 | Cosmos container TTL is enabled via `defaultTtl=-1` | "Cosmos TTL Mechanics" section, az CLI syntax verified |
| REQ-SD-03 | Per-doc `ttl` value = `settings.inbox_filed_retention_days * 86400` (default 30 days) | "Cosmos TTL Mechanics" — `ttl` is seconds-since-`_ts`, integer |
| REQ-SD-04 | Phone inbox view excludes `status="filed"` (server-side filter in api/inbox.py) | "Mobile Inbox Filter Location" — client filters by bucket only, server is the right layer |
| REQ-SD-05 | Errand/Task docs created during admin path carry `sourceInboxItemId` + `sourceCaptureTraceId` | "ContextVar Trace Propagation" + admin.py tool surface |
| REQ-SD-06 | `adminProcessingStatus=failed` + retry-cap items NEVER get `status="filed"` | "Landmines" — Phase 24 backlog interaction |
| REQ-SD-07 | Container TTL update is idempotent (safe to re-run) | "Cosmos TTL Mechanics" — verified via az CLI docs |

## Current Code State

### admin_handoff.py — confirmed delete site at lines 396-405

**File:** `backend/src/second_brain/processing/admin_handoff.py`

The CONTEXT.md description is correct. Two branches at the success post-tool path:

**Branch A: "Response needs delivery" (lines 372-394) — NO CHANGE in Phase 25**
- Triggered by `_response_needs_delivery(response_text)` returning True (rule queries, conflicts, etc.)
- Reads doc → sets `doc["adminProcessingStatus"]="completed"` + `doc["adminAgentResponse"]=response_text` → `upsert_item`
- Already preserves the inbox doc; Phase 25 does not modify this branch.

**Branch B: "Simple confirmation — delete" (lines 395-420) — THIS IS THE PHASE 25 SITE**
- Triggered when `_response_needs_delivery(response_text)` returns False (the normal add_errand_items/add_task_items happy path)
- Currently: `await inbox_container.delete_item(item=inbox_item_id, partition_key="will", **th)` at line 398
- `delete_item` is async (verified — `from azure.cosmos.aio import ContainerProxy`)
- Exception handling: `CosmosResourceNotFoundError` is swallowed (user may have swipe-deleted); generic exception logs warning but doesn't raise
- **Phase 25 transformation:** Replace lines 397-420 with read→mutate→upsert pattern:
  ```python
  # Pseudo-code — actual plan-level code in PLAN.md
  try:
      doc = await inbox_container.read_item(item=inbox_item_id, partition_key="will", **th)
      doc["status"] = "filed"
      doc["ttl"] = settings.inbox_filed_retention_days * 86400
      await inbox_container.upsert_item(body=doc, **th)
      logger.info("Filed processed inbox item %s. outcome=filed", inbox_item_id, extra=log_extra)
  except CosmosResourceNotFoundError:
      logger.info("Inbox item %s already deleted (user may have removed it)", inbox_item_id, extra=log_extra)
  except Exception as file_exc:
      logger.warning("Failed to file processed inbox item %s: %s", inbox_item_id, file_exc, extra=log_extra)
  ```
- `outcome=` log key changes from `processed` to `filed` — investigation queries that look for `outcome=processed` should be checked (none currently exist; verified via grep).

**Cosmos write pattern (consistent across file):**
- All upserts use `**th` (trace_headers from `spine.cosmos_request_id.trace_headers(capture_trace_id or None)`) — Phase 25 plan MUST preserve this for native correlation
- Uses `upsert_item(body=doc, **th)`, NOT `replace_item` (Phase 24-15/24-16 idiom)
- All inbox writes go through `cosmos_manager.get_container("Inbox")` then `read_item` → mutate → `upsert_item`

### api/inbox.py listing query (lines 76-85) — confirmed

**File:** `backend/src/second_brain/api/inbox.py`

Current SQL at lines 76-80:
```python
query = (
    "SELECT * FROM c WHERE c.userId = @userId "
    "ORDER BY c.createdAt DESC "
    "OFFSET @offset LIMIT @limit"
)
```

**Phase 25 modification:** Add `AND (NOT IS_DEFINED(c.status) OR c.status != "filed")` to the WHERE clause. The `NOT IS_DEFINED` guard is required because:
- Pre-Phase-25 docs have `status` set to "classified", "pending", "misunderstood", "unresolved", or "low_confidence" (from `tools/classification.py`)
- Some docs from older paths may have `status` unset; the `IS_DEFINED` guard handles both cleanly

Final query:
```python
query = (
    "SELECT * FROM c WHERE c.userId = @userId "
    "AND (NOT IS_DEFINED(c.status) OR c.status != 'filed') "
    "ORDER BY c.createdAt DESC "
    "OFFSET @offset LIMIT @limit"
)
```

**Other inbox endpoints in this file:**
- `GET /api/inbox/{item_id}` (line 116) — returns single item by ID; NO filter change (operator/code accessing a known-id should still get filed docs; mobile UI doesn't trigger this for filed items because they don't appear in the list)
- `DELETE /api/inbox/{item_id}` (line 141) — manual delete by user; NO filter change (cascade delete of filedRecordId works regardless of status)
- `PATCH /api/inbox/{item_id}/recategorize` (line 201) — manual recategorize; NO filter change (only used on visible items)

**Implication:** Only the listing query at lines 76-85 needs the filter. The single-item GET intentionally leaves a back-door for ops/debugging access to filed items.

### tools/investigation.py — CONTEXT.md line refs are INCORRECT

**File:** `backend/src/second_brain/tools/investigation.py`

CONTEXT.md says "lines 443,812 — investigation tool inbox queries that need the same filter." This is **wrong**:

- **Line 443:** `query_feedback_signals` Cosmos SQL: `"SELECT * FROM c WHERE c.userId = @userId AND c.createdAt >= @cutoff"` against the **Feedback** container (not Inbox). Line 456: `container = self._cosmos_manager.get_container("Feedback")`.
- **Line 812:** `get_eval_results` Cosmos SQL: `"SELECT * FROM c WHERE c.userId = @userId"` against the **EvalResults** container (not Inbox). Line 810: `container = self._cosmos_manager.get_container("EvalResults")`.

**Searching the entire file (`grep "Inbox\|inbox\|get_container" investigation.py`) returns ZERO Inbox container references.** The Investigation agent has no Cosmos Inbox query path at all. It queries:
1. App Insights / Log Analytics via KQL (in `observability/queries.py`)
2. Feedback + GoldenDataset + EvalResults Cosmos containers

The string "Inbox" appears only in `agents/instructions/investigation.md` as a bucket name (no SQL involved).

**Implication:** There is no investigation.py Inbox filter to add. The "/investigate Inbox queries default to excluding filed" success criterion is satisfied vacuously — the agent doesn't query Inbox directly. If the investigation agent needs to inspect filed items in the future, it would route through `api/inbox.py` (which has the filter) or App Insights KQL (which has no concept of filed/unfiled).

**Plan implication:** The "investigation filter" must-have in any draft plan is **deletable** — there's no code to change. The CONTEXT.md success criterion bullet 4 should be reinterpreted as "the investigation agent has no path that surfaces filed items to the user," which is true today.

### NEW INBOX QUERIES DISCOVERED (api/errands.py lines 174 and 262)

CONTEXT.md missed two Inbox container queries:

**Line 174-194: "unprocessed Admin items" query** (`GET /api/errands` side effect that triggers admin processing)
```python
query = (
    "SELECT c.id, c.rawText, c.captureTraceId FROM c "
    "WHERE c.userId = @userId "
    "AND c.classificationMeta.bucket = 'Admin' "
    "AND (NOT IS_DEFINED(c.adminProcessingStatus) "
    "     OR IS_NULL(c.adminProcessingStatus) "
    "     OR c.adminProcessingStatus = 'failed' "
    "     OR c.adminProcessingStatus = 'pending')"
)
```
**Phase 25 effect:** No change required. A filed item has `adminProcessingStatus="completed"` (per Phase 24 plan 24-11), so it will NEVER match the pending/failed/null filter. The two fields are orthogonal as CONTEXT.md states. **Verification test required:** assert that a doc with `status="filed"` AND `adminProcessingStatus="completed"` is NOT re-fired.

**Line 262-269: "completed admin notifications" query** (deliver admin agent responses to mobile)
```python
notify_query = (
    "SELECT c.id, c.adminAgentResponse FROM c "
    "WHERE c.userId = @userId "
    "AND c.adminProcessingStatus = 'completed' "
    "AND IS_DEFINED(c.adminAgentResponse) "
    "AND NOT IS_NULL(c.adminAgentResponse)"
)
```
**Phase 25 effect:** This query only matches Branch A items (completed WITH a response stored). Branch B items get `status="filed"` but Branch A items DO NOT get `status="filed"` (they're kept for delivery). So this query is unchanged. **However:** after the mobile UI dismisses the notification via `DELETE /api/errands/notifications/{inbox_item_id}/dismiss` at line 443, the doc is currently `delete_item`'d. **PLANNER DECISION POINT:** does the dismiss endpoint also become a soft-delete-with-filed? CONTEXT.md scope says "hard-delete-on-Admin-success path"; the notification-dismiss is technically a separate user action (Branch A items, manually acknowledged). Recommendation: yes, treat dismiss as the same "now done" event and soft-delete with `status="filed"` + ttl. This keeps Branch A and Branch B lifecycle symmetric. Document this in the plan and flag for operator review.

**File:** `backend/src/second_brain/api/errands.py` lines 461-471 — `dismiss_admin_notification` endpoint currently does `await inbox_container.delete_item(item=inbox_item_id, partition_key="will")`.

## Cosmos TTL Mechanics

**Source:** [Microsoft Learn — Configure and Manage Time to Live (Azure Cosmos DB NoSQL)](https://learn.microsoft.com/en-us/azure/cosmos-db/how-to-time-to-live) and [az cosmosdb sql container CLI reference](https://learn.microsoft.com/en-us/cli/azure/cosmosdb/sql/container?view=azure-cli-latest) — both verified 2026-05-17.

### Container `defaultTtl` (DefaultTimeToLive) semantics

| Value | Meaning |
|-------|---------|
| `null` / unset | TTL feature **OFF** — per-doc `ttl` values are **IGNORED** |
| `-1` | TTL feature **ON, no default expiration** — per-doc `ttl` values take effect; docs without `ttl` never expire |
| `0` | (Implicit "off" in some SDK semantics; not documented as a separate state. Treat as "do not use") |
| Positive integer N | TTL feature **ON, default = N seconds** — all docs expire N seconds after last `_ts`; per-doc `ttl` overrides default; per-doc `ttl=-1` opts out |

**Critical disable behavior:** Removing `DefaultTimeToLive` (setting to null) is different from setting to `-1`. When set to null, items never expire EVEN IF they explicitly set their own `ttl`. The per-doc `ttl` is only honored if container TTL is enabled.

### Per-document `ttl` field semantics

- **Type:** Integer (seconds). Verified via Python SDK example: `'ttl': 60 * 60 * 24 * 30`
- **Reference point:** Counted from `_ts` (system-managed last-modified timestamp), NOT a custom field. Re-writing the doc resets the clock.
- **Override:** Per-doc `ttl=N` overrides container default. Per-doc `ttl=-1` opts out of expiration.
- **Requirement:** Container `defaultTtl` MUST be set (to -1 or a positive int) for per-doc `ttl` to take effect. If container is unset/null, per-doc `ttl` is ignored. **THIS IS WHY PHASE 25 NEEDS THE az CLI STEP FIRST.**

### TTL deletion mechanics (audit trail caveat)

- **Asynchronous, eventually consistent** — typically within seconds of expiration but not real-time
- **RU consumption** from background sweep, not from user requests
- **No portal/diagnostics log** of per-doc TTL deletions in any standard table. AzureDiagnostics shows user-initiated CRUD; TTL purges are background-pool operations. CONTEXT.md's "no audit trail for TTL purges" trade-off is correct.

### `az cosmosdb sql container update` syntax — VERIFIED

**Exact CLI command for Phase 25:**
```bash
az cosmosdb sql container update \
  --account-name shared-services-cosmosdb \
  --database-name second-brain \
  --name Inbox \
  --resource-group shared-services-rg \
  --ttl -1
```

**Verification command:**
```bash
az cosmosdb sql container show \
  --account-name shared-services-cosmosdb \
  --database-name second-brain \
  --name Inbox \
  --resource-group shared-services-rg \
  --query "resource.defaultTtl"
```
Expected output: `-1`

**Docs quote:** "Default TTL. If the value is missing or set to '-1', items don't expire. If the value is set to 'n', items will expire 'n' seconds after last modified time." — applies to both `az cosmosdb sql container update` and `az cosmosdb sql container create`.

### Idempotency answer (CRITICAL for plan)

**The `--ttl -1` update is idempotent at the API level.** Running it twice when `defaultTtl` is already `-1` returns the same result (HTTP 200 with the unchanged container resource). The Azure Resource Manager PATCH semantics make this safe. Verification via `--query` is the canonical idempotency check; plan should:

1. Read current value: `current=$(az cosmosdb sql container show ... --query "resource.defaultTtl" -o tsv)`
2. If `current == -1`, skip the update (or run it anyway — both safe)
3. Else, run the update
4. Re-read to assert post-state

**Note:** `az cosmosdb sql container update` is documented as Core GA. The command DOES NOT have a separate `--default-ttl` parameter — just `--ttl` (which sets `defaultTtl` on the underlying resource). Confused references to `--default-ttl` elsewhere on the web come from older SDK versions; the current CLI uses `--ttl` only.

## Phase 24-15 Filing Pattern Reference

**Source:** `backend/src/second_brain/cosmos/inbox_conversation_history.py` + `backend/src/second_brain/streaming/adapter.py` lines 178-228

The canonical Phase 24-15/24-16 pattern for "read → mutate → upsert" on an Inbox doc is in `streaming/adapter.py:_upsert_inbox_with_history`:

```python
async def _upsert_inbox_with_history(cosmos_manager, inbox_doc, history, capture_trace_id):
    if cosmos_manager is None or inbox_doc is None:
        return
    log_extra = {"capture_trace_id": capture_trace_id, "component": "classifier"}
    doc_id = _get_inbox_id(inbox_doc)
    if not doc_id:
        return
    serialized = [t.model_dump() for t in history]
    try:
        inbox_container = cosmos_manager.get_container("Inbox")
        # Re-read the latest doc state so we don't clobber concurrent writes
        try:
            fresh_doc = await inbox_container.read_item(
                item=doc_id, partition_key="will",
                **trace_headers(capture_trace_id or None),
            )
        except Exception:
            fresh_doc = _persist_conversation_history_inplace(inbox_doc, history)
        else:
            fresh_doc["conversationHistory"] = serialized
        await inbox_container.upsert_item(
            body=fresh_doc, **trace_headers(capture_trace_id or None)
        )
    except Exception:
        logger.warning("Failed to persist conversationHistory back to inbox doc",
                       exc_info=True, extra=log_extra)
```

### How to apply to Phase 25

The admin_handoff filing site shares the same pattern: read → mutate → upsert with `trace_headers(...)` for native correlation. **Differences from the 24-15 site:**

1. **No race-safety re-read needed** — the filing happens AFTER `agent.run()` has fully returned. There's no concurrent in-stream tool firing on the same doc at this point (file_capture runs during classify; the admin agent's add_errand_items writes to Errands/Tasks containers, not Inbox). The simple existing `try: doc = read_item(); doc["adminProcessingStatus"]="completed"; upsert_item` pattern at admin_handoff.py:375-381 is the precedent — clone that.
2. **Mutation is `status="filed"` + `ttl=N`** — not `conversationHistory`.
3. **Same `trace_headers(capture_trace_id or None)` propagation** — preserves Cosmos x-ms-client-request-id correlation per Phase 19.4.

**Recommended Phase 25 filing helper signature** (Plan 01 decides whether to extract a helper or inline; either is fine):
```python
async def _file_inbox_item(
    inbox_container,
    inbox_item_id: str,
    capture_trace_id: str,
    ttl_seconds: int,
    log_extra: dict,
) -> None:
    """Soft-delete by setting status='filed' + ttl. Best-effort, never raises."""
    th = trace_headers(capture_trace_id or None)
    try:
        doc = await inbox_container.read_item(item=inbox_item_id, partition_key="will", **th)
        doc["status"] = "filed"
        doc["ttl"] = ttl_seconds
        await inbox_container.upsert_item(body=doc, **th)
        logger.info("Filed processed inbox item %s. outcome=filed", inbox_item_id, extra=log_extra)
    except CosmosResourceNotFoundError:
        logger.info("Inbox item %s already deleted (user may have removed it)", inbox_item_id, extra=log_extra)
    except Exception as file_exc:
        logger.warning("Failed to file processed inbox item %s: %s", inbox_item_id, file_exc, extra=log_extra)
```

## ContextVar Trace Propagation

**Definition site:** `backend/src/second_brain/tools/classification.py:43-45`
```python
capture_trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "capture_trace_id_var", default=""
)
```

**Set sites (where the ContextVar gets populated):**
1. `api/capture.py:197` — text capture entry point (`/api/capture`)
2. `api/capture.py:284` — voice capture entry point (`/api/capture/voice`)
3. `api/capture.py:443` — multi-split capture entry
4. `api/capture.py:530` — additional capture entry
5. `streaming/adapter.py:295` — adapter sets it before `agent.run` (with `trace_token = capture_trace_id_var.set(...)`)
6. `streaming/adapter.py:583` — voice streaming adapter
7. `processing/admin_handoff.py:215` — admin_handoff sets it on entry (because admin processing runs in `asyncio.create_task()` which has its own context copy)

**Read sites:**
1. `tools/classification.py:130,166,295` — file_capture reads it to tag the inbox doc
2. `tools/recipe.py:191` — recipe tool reads it for spine emit correlation
3. `agents/agent_middleware/capture_trace.py:54,77` — middleware tags agent middleware spans
4. `observability/span_processor.py:42` — CaptureTraceSpanProcessor tags OTel spans

**Phase 25 read site (NEW):** `tools/admin.py:add_errand_items` and `add_task_items`. The ContextVar is **already populated** when these methods run because:

- The admin agent's tool invocations happen INSIDE `await admin_agent.run(...)` which is called from `process_admin_capture` (admin_handoff.py)
- `process_admin_capture` sets `capture_trace_id_var.set(capture_trace_id)` at line 215 BEFORE the agent runs
- Async `ContextVar`s propagate through `await` chains within the same task

**Verified pattern** (from `tools/recipe.py:191`):
```python
from second_brain.tools.classification import capture_trace_id_var
# ... inside async tool method ...
capture_trace_id = capture_trace_id_var.get() or None
```

This is the exact pattern Phase 25 should use in `add_errand_items` and `add_task_items`. **Note:** `.get() or None` returns `None` when the ContextVar holds the empty-string default — this avoids storing empty strings as `sourceCaptureTraceId`.

**Inbox item ID propagation for `sourceInboxItemId`:** The admin agent's tool invocation does NOT have direct access to the inbox_item_id today. The id is passed as an argument to `process_admin_capture(inbox_item_id, ...)` but is NOT threaded through to the tool. **Two options for the planner:**

**Option A — Use a second ContextVar (consistent with existing pattern):**
Add a new `admin_inbox_item_id_var: ContextVar[str | None]` in tools/admin.py (mirrors `_follow_up_inbox_item_id` ContextVar in classification.py). Set it in `process_admin_capture` before `agent.run`, read it in `add_errand_items` / `add_task_items`. **Recommended.** Aligns with the existing classification.py `follow_up_context` ContextVar pattern.

**Option B — Construct AdminTools per-call with the inbox_item_id in constructor:**
Today AdminTools is lifespan-singleton (constructed once in main.py and shared across all admin captures). Constructing a fresh AdminTools per admin processing call would break the lifespan pattern Phase 24-09/24-11 cemented. **Rejected.**

**Recommendation:** Option A. New ContextVar at module top of `tools/admin.py`:
```python
import contextvars
admin_inbox_item_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "admin_inbox_item_id_var", default=None
)
```
Set in `process_admin_capture` before `agent.run`:
```python
# admin_handoff.py:
from second_brain.tools.admin import admin_inbox_item_id_var
admin_inbox_item_id_var.set(inbox_item_id)
```
Read in `add_errand_items` / `add_task_items`:
```python
source_inbox_id = admin_inbox_item_id_var.get()  # may be None for eval/test paths
source_trace_id = capture_trace_id_var.get() or None
doc = ErrandItem(
    destination=destination,
    name=name,
    needsRouting=needs_routing,
    sourceName=source_name,
    sourceUrl=source_url,
    sourceInboxItemId=source_inbox_id,
    sourceCaptureTraceId=source_trace_id,
)
```

## Mobile Inbox Filter Location

**Source:** `mobile/app/(tabs)/inbox.tsx`

**Server-side vs client-side answer:** Mobile inbox already does **client-side bucket filtering** (line 295-300) but **all status-based filtering is server-driven** (mobile reads the API response and displays as-is). The mobile screen calls `GET /api/inbox?limit=20&offset=...` (line 51-56) and renders `data.items` directly.

**Recommendation:** Server-side filter only. The mobile screen needs **zero changes**. Add the `AND (NOT IS_DEFINED(c.status) OR c.status != 'filed')` clause to the api/inbox.py query at lines 76-80 and the filtering happens at the data layer. The mobile UI never sees filed items.

**Side benefit:** No EAS rebuild needed for Phase 25. Mobile changes are out of scope.

**Caveat:** The badge count calculation at line 102-107 (`pendingCount`) filters by status `pending|low_confidence|unresolved|misunderstood` — filed items are correctly excluded from this count even pre-filter because filed is not in the list. No mobile test breakage from this angle.

## Pydantic Model Touchpoints

### ErrandItem + TaskItem writers

**File:** `backend/src/second_brain/models/documents.py` lines 105-134

```python
class ErrandItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    destination: str
    name: str
    needsRouting: bool = False
    sourceName: str | None = None
    sourceUrl: str | None = None
    # Phase 25 additions:
    # sourceInboxItemId: str | None = None
    # sourceCaptureTraceId: str | None = None

class TaskItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    userId: str = "will"
    name: str
    createdAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
    # Phase 25 additions:
    # sourceInboxItemId: str | None = None
    # sourceCaptureTraceId: str | None = None
```

**All ErrandItem writers (grep verified):**
1. `backend/src/second_brain/tools/admin.py:177` — `add_errand_items` production tool ✓ POPULATE backlinks here
2. `backend/src/second_brain/eval/dry_run_tools.py:104-131` — `DryRunAdminTools.add_errand_items` does NOT construct ErrandItem (captures in memory as raw dict). **No model change visible to eval.**
3. `backend/src/second_brain/eval/foundry.py:162,194,788,933` — eval/foundry references but only as a tool **name** string for routing-accuracy scoring; does not instantiate ErrandItem.
4. `backend/src/second_brain/api/errands.py` — only constructs `ErrandItemResponse` (response model, not the Cosmos doc model)
5. Tests: `backend/tests/test_admin_tools.py`, `test_admin_task_tools.py` — test the admin tool methods (may need new assertions for backlink fields)

**All TaskItem writers:**
1. `backend/src/second_brain/tools/admin.py:230` — `add_task_items` production tool ✓ POPULATE backlinks here
2. `backend/src/second_brain/eval/dry_run_tools.py:133-153` — `DryRunAdminTools.add_task_items` captures in memory (no model construction)
3. `backend/src/second_brain/api/tasks.py` — only constructs `TaskItemResponse`

**Migration helpers / fixtures / seeders for ErrandItem/TaskItem:** NONE found. No backfill scripts to update.

**Pre-Phase-25 doc compatibility:** Pydantic defaults handle absent fields gracefully (`sourceInboxItemId: str | None = None` makes the field optional with None default). Existing Cosmos docs without these fields will deserialize correctly. CONTEXT.md decision 5 confirms no backfill needed.

### InboxDocument status field check

**File:** `backend/src/second_brain/models/documents.py` line 51

```python
class InboxDocument(BaseDocument):
    ...
    status: str = "classified"
```

**Current observed status values** (from grep across codebase):
- `"classified"` — default; classifier filed successfully
- `"pending"` — confidence below threshold
- `"misunderstood"` — classifier asked for clarification
- `"unresolved"` — clarification path exhausted
- `"low_confidence"` — referenced in mobile filter (likely synonymous with pending)

**Phase 25 adds:** `"filed"` — sixth value.

**Pydantic validator check:** The field is typed `str` with no `Literal[...]` constraint or `@validator`. **No whitelist exists.** Adding `"filed"` requires NO model code change; the value is just a new string. (If a future planner wants a whitelist, that's a separate concern.)

**Code that does positive status checks** (would silently exclude filed if not updated):
- `mobile/app/(tabs)/inbox.tsx:102-107` — `isPendingStatus` checks `pending|low_confidence|unresolved|misunderstood` — filed items would NOT be classified as pending (correct behavior).
- `mobile/app/(tabs)/inbox.tsx:519` — `isClassifiedItem = selectedItem?.status === "classified"` — filed items would NOT be classified-status (correct behavior — they're a separate state).
- `backend/src/second_brain/api/inbox.py:252` — `if item.get("status") == "pending"` recategorize same-bucket path — irrelevant to filed.
- `backend/src/second_brain/api/inbox.py:324` — sets `item["status"] = "classified"` on recategorize — irrelevant to filed (a filed item shouldn't be recategorized; UI hides it).

**Conclusion:** No existing positive-status check will accidentally skip filed items. The model field is permissive; the only enforcement is at query time (api/inbox.py:76-85 filter).

## Validation Architecture

**Test framework:**
| Property | Value |
|----------|-------|
| Framework | pytest (existing — `backend/tests/`) |
| Config file | `backend/pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest backend/tests/test_admin_handoff.py -x` |
| Full suite command | `pytest backend/tests/ -x --tb=short` |

**Phase 25 requirements → test map:**

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REQ-SD-01 | admin_handoff Branch B sets status="filed" + ttl on inbox doc instead of delete_item | unit | `pytest backend/tests/test_admin_handoff.py::TestProcessAdminCapture::test_simple_confirmation_files_inbox_item -x` | NEEDS Wave 0 (rename existing test_delete_on_success → test_files_on_success + add upsert+status+ttl assertions) |
| REQ-SD-03 | per-doc ttl value = settings.inbox_filed_retention_days * 86400 (default = 2592000 for 30 days) | unit | `pytest backend/tests/test_admin_handoff.py::TestProcessAdminCapture::test_filed_doc_ttl_matches_settings -x` | NEEDS Wave 0 (new test) |
| REQ-SD-04 | api/inbox.py listing query excludes status="filed" docs | integration | `pytest backend/tests/test_inbox_api.py::test_list_inbox_excludes_filed_status -x` | NEEDS Wave 0 (new test against mock Cosmos query items) |
| REQ-SD-05 | ErrandItem and TaskItem created via add_errand_items / add_task_items carry sourceInboxItemId + sourceCaptureTraceId | unit | `pytest backend/tests/test_admin_tools.py::test_add_errand_items_carries_backlinks -x` and `test_add_task_items_carries_backlinks` | NEEDS Wave 0 (new tests setting both ContextVars and asserting on model_dump) |
| REQ-SD-06 | Admin retry-failed path does NOT set status="filed" (orthogonality with adminProcessingStatus=failed) | unit | `pytest backend/tests/test_admin_handoff.py::TestProcessAdminCapture::test_agent_error_does_not_file_inbox_item -x` | NEEDS Wave 0 (new test — existing test_agent_error_sets_status_to_failed at line 285 covers failed-status but should also assert status != "filed" after the failure path) |
| REQ-SD-02+SD-07 | Container TTL update is idempotent (az CLI returns success when run twice with same value) | manual-only | Plan 02 operator step: `az cosmosdb sql container update ... --ttl -1 && az cosmosdb sql container show ... --query "resource.defaultTtl"` twice | N/A — operator-executed against live infra |
| REQ-SD-02 deploy verification | Post-deploy, a fresh admin capture results in a Cosmos Inbox doc with status="filed" + ttl set | UAT | Manual capture → wait → query Inbox container in Data Explorer for the most recent admin-bucket doc and verify `status` and `ttl` fields | N/A — UAT step in Plan 02 |

### Sampling rate
- **Per task commit:** `pytest backend/tests/test_admin_handoff.py backend/tests/test_admin_tools.py backend/tests/test_inbox_api.py -x` (~3 sec)
- **Per wave merge:** `pytest backend/tests/ -x --tb=short` (full suite)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 gaps
- [ ] `backend/tests/test_admin_handoff.py` — rename `test_simple_confirmation_deletes_inbox_item` (and similar tests around line 193-202) to assert upsert with status="filed" + ttl, NOT delete_item
- [ ] `backend/tests/test_admin_handoff.py` — add `test_filed_doc_ttl_matches_settings` and `test_agent_error_does_not_file_inbox_item`
- [ ] `backend/tests/test_admin_tools.py` — add `test_add_errand_items_carries_backlinks` and `test_add_task_items_carries_backlinks` (use `capture_trace_id_var.set("trace-X")` and `admin_inbox_item_id_var.set("inbox-Y")` then assert on captured doc body)
- [ ] `backend/tests/test_inbox_api.py` — add `test_list_inbox_excludes_filed_status` (mock query_items result to include a filed doc and assert it doesn't surface)
- [ ] `backend/tests/test_admin_handoff.py` — update existing test fixtures that assert `delete_item.assert_called_once_with(...)` at lines 202, 453, 540, 552, 667 (six call sites — these are the existing delete-on-success tests that need rewriting)

## Recipe Path Confirmation

**Source:** `backend/src/second_brain/tools/recipe.py` + `backend/src/second_brain/processing/admin_handoff.py`

**Does the recipe path share admin_handoff.py filing site?** YES.

**Verification trail:**
1. User pastes recipe URL → classifier files to Inbox with bucket=Admin (admin_handoff is triggered via api/errands.py:217)
2. Admin agent runs (`admin_handoff.py:285 admin_agent.run`)
3. Admin agent calls `fetch_recipe_url` tool (recipe.py:110) which returns recipe text. **`fetch_recipe_url` does NOT touch the Inbox container** — confirmed via grep (recipe.py has zero Inbox references; the only Cosmos write is via `emit_agent_workload` to spine_events at line 194).
4. Admin agent (in the same `agent.run` invocation, after recipe.py returns) calls `add_errand_items` N times with the extracted ingredients
5. `_output_tool_called(response)` returns True (add_errand_items is in `_OUTPUT_TOOL_NAMES`)
6. `_response_needs_delivery(response_text)` returns False (recipe success path produces "Added N items: ..." not a delivery-worthy response)
7. Branch B fires → `delete_item` at admin_handoff.py:398 — the SAME site. Phase 25's soft-delete replacement at this single site handles recipe captures identically.

**Phase 26 interaction:** Phase 26 removes recipe extraction entirely. After Phase 26, the only paths through Branch B will be non-recipe Admin captures. Phase 25 does not need to handle "recipe path differently" — there's no separate filing path. ROADMAP success criterion #6 ("Recipe URL captures follow the same path: source Inbox → filed once") is satisfied trivially.

**If Phase 26 ships BEFORE Phase 25:** No conflict. Phase 25's changes are recipe-agnostic; they just change one filing site that all admin captures pass through.

## Landmines

### 1. Phase 24 Admin Retry Bound orthogonality (CRITICAL)
**Source:** Phase 24 backlog item per CONTEXT.md line 26 + 106.

The "Admin Retry Bound" backlog item (cap retries at N=3 via `adminRetryCount`) **interacts with** `status="filed"` semantics. A retry-exhausted item:
- has `adminProcessingStatus = "failed"`
- has `adminRetryCount = 3`
- MUST NOT have `status = "filed"` (it's not "done", it's failed)

**Phase 25 plan MUST:**
- Only set `status="filed"` in Branch B (success path) — NOT in `_mark_inbox_failed` at admin_handoff.py:149-177
- Verify in tests: when `_mark_inbox_failed` runs, the doc gets `adminProcessingStatus="failed"` and does NOT get `status="filed"`

**Existing test to extend:** `test_agent_error_sets_status_to_failed` at test_admin_handoff.py:285. Add assertion that the upsert body does NOT contain `status="filed"`.

### 2. CONTEXT.md investigation.py line refs are wrong
Line 443 = Feedback query, line 812 = EvalResults query. **Neither queries Inbox.** Investigation agent has zero direct Cosmos Inbox query path. Any plan that has "modify investigation.py to filter filed inbox items" is wrong work. Plan should explicitly state "investigation.py: no change required — verified no Inbox container query exists."

### 3. api/errands.py has two NEW Inbox queries CONTEXT.md missed
- Line 174 (unprocessed admin items): naturally compatible with filed semantics via adminProcessingStatus orthogonality
- Line 262 (admin notifications): operates only on Branch A items; no filter change but test should confirm a status="filed" doc with adminProcessingStatus="completed" but NO adminAgentResponse is excluded
- Line 461 (dismiss_admin_notification): currently delete_item; planner decision needed — should this also become soft-delete-with-filed for lifecycle symmetry?

### 4. Re-firing risk if status flag write succeeds but adminProcessingStatus flip fails
Today admin_handoff flow: pending → completed → delete. With soft-delete: pending → completed → filed (single upsert). If a partial write happens (status set but adminProcessingStatus not), the api/errands.py:174 query could re-fire the agent on a filed doc.

**Mitigation:** Both fields MUST be written in the SAME upsert. The current code in Branch A already does this (`adminProcessingStatus="completed"` + `adminAgentResponse=response_text` in one upsert at line 379-381). Phase 25 Branch B should do the same: read once, set `status="filed"` AND ensure `adminProcessingStatus="completed"` AND set `ttl`, write once. Today Branch B's `delete_item` skips setting adminProcessingStatus="completed" because the doc is being deleted — Phase 25 plan MUST add that flip (otherwise filed docs would have `adminProcessingStatus="pending"` lingering, and the re-fire query at api/errands.py:179 explicitly matches pending).

**This is a real defect risk.** Recommended Phase 25 filing helper sets BOTH fields:
```python
doc["status"] = "filed"
doc["adminProcessingStatus"] = "completed"  # CRITICAL — orthogonal but both required
doc["ttl"] = ttl_seconds
```

### 5. Auto-format hook strips unused imports
**Source:** MEMORY.md lesson, repeated across Phases 17.1, 24-09, 24-10, 24-14, 24-15, 24-21.

If Plan 01 adds `from second_brain.config import get_settings` to admin_handoff.py as a stepwise Edit BEFORE the usage line is added, ruff will strip the import on save. Same risk for the new `admin_inbox_item_id_var` ContextVar import in admin.py.

**Mitigation:** Use single Write for files where imports + usages land together (admin.py, admin_handoff.py). For tests where imports come from existing modules, normal Edit chains are safe.

### 6. ttl is an integer, NOT a duration string
A common pitfall is writing `doc["ttl"] = "30d"` or `timedelta(days=30)`. Cosmos REST requires integer seconds. The Python SDK passes the dict body as-is; if ttl is anything other than an integer, the write succeeds but TTL is silently ignored (the field is parsed by the server, not validated client-side in older SDK versions). Plan MUST: `doc["ttl"] = settings.inbox_filed_retention_days * 86400` (int * int = int).

### 7. settings.inbox_filed_retention_days = 0 would set ttl=0 = "delete immediately"
A misconfigured env var `INBOX_FILED_RETENTION_DAYS=0` would result in `doc["ttl"] = 0` which means "expire immediately at next sweep." Plan should add a `>= 1` validation in Settings:
```python
inbox_filed_retention_days: int = Field(default=30, ge=1, description="Days to retain filed inbox docs; minimum 1")
```
Pydantic `Field(ge=1)` constraint will fail-fast at app startup if a bad env var slips through.

### 8. Container `defaultTtl=-1` must be set BEFORE any code writes `ttl` to a doc
If Plan 01 (code) ships before Plan 02 (az CLI infra change), the first soft-delete will write a `ttl` field that Cosmos silently ignores. The filed doc will live forever (no TTL takes effect). **Plan ordering MUST be:** infra TTL update → deploy code change. OR: combine into single plan and gate the deploy on operator confirmation that the az CLI step succeeded.

**Recommendation:** Plan 02 runs az CLI step FIRST (operator-authorized), THEN merges Plan 01's code changes. Or single-plan with a sequencing acceptance gate.

### 9. Container-level TTL=-1 vs positive default
Setting container `defaultTtl=N` (positive) would expire ALL Inbox docs after N seconds, including People/Ideas/Projects/Admin docs that should be durable. We MUST use `-1` (no default, opt-in per-doc only). The CLI command in CONTEXT.md `az cosmosdb sql container update ... --ttl -1` is correct. **Verify in plan** that `--ttl -1` (with the integer literal `-1`, NOT a string) is used.

### 10. Pre-existing `status` values that are not in any "active" allowlist
There is no positive `status="active"` check anywhere in the codebase (verified via grep). All status checks are either positive-match-specific (`status == "pending"`, `status == "classified"`) or status-list-membership for UI categorization. The new `"filed"` value will simply not match any of these positive checks, which is the intended behavior. **No allowlist exists to update.**

## Open Questions for Planner

CONTEXT.md is locked. However, code reading surfaced **three small clarifications** worth flagging:

1. **Should `dismiss_admin_notification` (api/errands.py:461) also become soft-delete-with-filed?**
   - Today: hard delete via `inbox_container.delete_item`
   - Phase 25 logic: Branch A items (kept for delivery) get manually dismissed by user; this is functionally "done"
   - Symmetry argument: yes, treat dismissal as the same lifecycle event as Branch B's auto-file
   - Out-of-scope argument: CONTEXT.md says "hard-delete-on-Admin-success path" which technically only covers Branch B
   - **Recommendation:** YES, fold into Phase 25 for lifecycle symmetry. Documented in Plan 01.

2. **CONTEXT.md success criterion #4 (investigation filter) — should plan explicitly state "no-op"?**
   - Investigation agent has no direct Inbox Cosmos query path
   - Success criterion is satisfied vacuously
   - **Recommendation:** Plan must-haves should include "verify no investigation.py Inbox query exists" as an explicit no-op check, with a grep test in CI: `grep -rn 'get_container(\"Inbox\"' backend/src/second_brain/tools/investigation.py` should return zero matches.

3. **Branch B currently does NOT set `adminProcessingStatus="completed"` (because the doc is being deleted)**
   - Phase 25 MUST add this flip in the soft-delete path
   - Otherwise filed docs will have lingering `adminProcessingStatus="pending"` and the api/errands.py:174 re-fire query will match them
   - This is a critical correctness change buried in the soft-delete swap
   - **Recommendation:** Plan 01 explicit must-have: the filing upsert sets BOTH `status="filed"` AND `adminProcessingStatus="completed"` AND `ttl` in the same body. Test: assert the upserted body has all three fields.

## Project Constraints (from CLAUDE.md)

From `./CLAUDE.md` (project):
- Backend uses `uv` for all package management
- Python 3.12+, FastAPI, Cosmos DB
- **Never run the backend locally** — testing happens against the deployed endpoint after CI/CD
- After making code changes: `qmd update` to re-index for code search

From `~/.claude/CLAUDE.md` (global):
- Type hints required on all functions
- Async/await for FastAPI route I/O (admin_handoff.py is already async ✓)
- Use `logging` module, not print
- Use `uv pip install`, not `pip install`
- Pydantic Settings for configuration (Settings class pattern already in place ✓)

From MEMORY.md (project lessons):
- App Insights `logger.info` exports via configured `second_brain` logger at INFO level
- Auto-format hook strips unused imports — use single Write for import+usage atoms
- Cosmos `activityId_g` is server-side activity ID, NOT x-ms-client-request-id (irrelevant for Phase 25 but mentioned for completeness)

## Sources

### Primary (HIGH confidence)
- [Microsoft Learn — Configure and Manage Time to Live (Azure Cosmos DB NoSQL)](https://learn.microsoft.com/en-us/azure/cosmos-db/how-to-time-to-live) — fetched 2026-05-17; TTL container/item semantics, value table, RU/audit caveats
- [Microsoft Learn — az cosmosdb sql container CLI reference](https://learn.microsoft.com/en-us/cli/azure/cosmosdb/sql/container?view=azure-cli-latest) — fetched 2026-05-17; --ttl parameter, idempotency, --query verification
- `backend/src/second_brain/processing/admin_handoff.py` (lines 1-503) — direct read; confirmed Branch A/B structure
- `backend/src/second_brain/api/inbox.py` (lines 1-378) — direct read; confirmed listing query shape and other endpoints
- `backend/src/second_brain/tools/investigation.py` (lines 1-200, 400-862) — direct read; confirmed NO Inbox Cosmos query
- `backend/src/second_brain/cosmos/inbox_conversation_history.py` (full) — direct read; reference pattern for 24-15 idiom
- `backend/src/second_brain/tools/admin.py` (full) — direct read; AdminTools surface and write sites
- `backend/src/second_brain/models/documents.py` (full) — direct read; ErrandItem/TaskItem/InboxDocument shapes
- `backend/src/second_brain/config.py` (full) — direct read; Settings pattern
- `backend/src/second_brain/tools/classification.py` (lines 35-100) — direct read; capture_trace_id_var ContextVar definition
- `backend/src/second_brain/streaming/adapter.py` (lines 100-300) — direct read; _upsert_inbox_with_history pattern
- `backend/src/second_brain/api/errands.py` (lines 160-300, 440-470) — direct read; admin agent firing query + dismiss endpoint
- `backend/src/second_brain/db/cosmos.py` (full) — direct read; CosmosManager + container list
- `backend/src/second_brain/eval/dry_run_tools.py` (full) — direct read; eval tool dry-run path
- `mobile/app/(tabs)/inbox.tsx` (full) — direct read; client-side filter location

### Secondary (MEDIUM confidence)
- Codebase grep verification for ErrandItem/TaskItem writers, status field references, Inbox query sites, ContextVar usage

### Tertiary
- None — all claims verified against direct code reads or Microsoft Learn docs

## Metadata

**Confidence breakdown:**
- Current Code State: HIGH — direct reads of all canonical refs
- Cosmos TTL Mechanics: HIGH — Microsoft Learn docs cross-referenced with az CLI reference
- Phase 24-15 Filing Pattern: HIGH — direct read of streaming/adapter.py
- ContextVar Propagation: HIGH — grep + read of all set/read sites
- Mobile Filter Location: HIGH — direct read of inbox.tsx
- Pydantic Touchpoints: HIGH — grep + read of all ErrandItem/TaskItem references
- Validation Architecture: HIGH — based on existing test patterns
- Recipe Path Confirmation: HIGH — direct grep + read of recipe.py and admin_handoff.py
- Landmines: HIGH — derived from code reading + cross-phase memory

**Research date:** 2026-05-17
**Valid until:** 2026-06-17 (30 days) — Cosmos TTL docs are stable; az CLI may add new options but `--ttl` parameter is GA

## RESEARCH COMPLETE
