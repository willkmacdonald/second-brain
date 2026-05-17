# Phase 25: Admin Inbox Soft-Delete + 30-day Retention — Pattern Map

**Mapped:** 2026-05-17
**Files analyzed:** 12 (5 source modify, 1 config modify, 6 test create/extend)
**Analogs found:** 12 / 12 (all with strong in-repo analogs)

---

## File Classification

| New/Modified File | Role | Data Flow | Action | Closest Analog | Match Quality |
|-------------------|------|-----------|--------|----------------|---------------|
| `backend/src/second_brain/processing/admin_handoff.py` | processing | mutating Cosmos | modify (swap delete → upsert) | self (Branch A at lines 372-394) + `streaming/adapter.py:178-228` | exact (self-clone) |
| `backend/src/second_brain/api/inbox.py` | API | read-only Cosmos query | modify (WHERE clause) | self (lines 76-85) | exact (in-place edit) |
| `backend/src/second_brain/api/errands.py` | API | mutating Cosmos | modify (dismiss soft-delete + verify unprocessed filter) | self (lines 174-194 + 446-472) + `admin_handoff.py:163-177` | exact |
| `backend/src/second_brain/tools/admin.py` | tool | new ContextVar + mutating writes | modify (ContextVar + body fields) | `tools/classification.py:36-55` (ContextVar) + self (lines 175-184) | exact |
| `backend/src/second_brain/models/documents.py` | model | new optional fields | modify (2 optional fields × 2 models) | self (`ErrandItem` sourceName/sourceUrl pattern at lines 118-119) | exact |
| `backend/src/second_brain/config.py` | config | new env-var setting w/ validation | modify (1 new Field) | `spine/api.py:48-49` (Field ge= pattern) | role-match |
| `backend/tests/test_admin_handoff.py` | test | unit mock-Cosmos | modify (rename + add filing tests) | self (lines 177-275 + 285-364) | exact (self-extend) |
| `backend/tests/test_admin_tools.py` | test | unit mock-Cosmos | modify (add backlink tests) | self (lines 78-104) + `test_event_tracing.py:413-446` (ContextVar set/reset) | exact |
| `backend/tests/test_inbox_api.py` | test | integration httpx | modify (add filed-filter test) | `test_errands_api.py:74-108` (`_make_async_iterator` + query side_effect) | role-match |
| `backend/tests/test_errands_api.py` | test | integration httpx | modify (unprocessed + dismiss-soft-delete tests) | self (lines 611-650) | exact (self-extend) |
| `backend/tests/test_documents_models.py` | test | unit Pydantic | create (new file) | `test_spine_models.py:85-94` (ValidationError pattern) | role-match |
| `backend/tests/test_config.py` | test | unit Pydantic Settings | create (new file) | `test_spine_registry.py:50-73` (config validation) | role-match |

---

## Pattern Assignments

### File 1: `backend/src/second_brain/processing/admin_handoff.py` (processing, mutating Cosmos)

**Analog:** Self — Branch A at lines 372-394 (already does read→mutate→upsert with `th = trace_headers(...)`). Plus `streaming/adapter.py:178-228` for the wider 24-15/24-16 idiom.

**Action:** Replace lines 397-420 (Branch B `delete_item` block) with a read→mutate→upsert that sets `status="filed"` + `adminProcessingStatus="completed"` + `ttl` in one body. Branch A unchanged. Also: amend `_mark_inbox_failed` if any guard required (none — already does NOT set `status="filed"`, just `adminProcessingStatus="failed"`).

**Imports pattern** (already present, lines 24-31 — NO new imports needed for Branch B mutation):
```python
import logging
import time

from agent_framework import Agent, ChatOptions
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from second_brain.db.cosmos import CosmosManager
from second_brain.spine.agent_emitter import emit_agent_workload
from second_brain.spine.cosmos_request_id import trace_headers
from second_brain.spine.storage import SpineRepository
from second_brain.tools.admin import build_routing_context
```

**NEW imports needed** (per Plan 01):
```python
from second_brain.config import get_settings
from second_brain.tools.admin import admin_inbox_item_id_var
```

**Branch A read-mutate-upsert pattern to copy** (lines 372-394 — the canonical idiom):
```python
if _response_needs_delivery(response_text):
    # Response contains info the user needs to see --
    # keep the inbox item with response attached
    try:
        doc = await inbox_container.read_item(
            item=inbox_item_id, partition_key="will", **th
        )
        doc["adminProcessingStatus"] = "completed"
        doc["adminAgentResponse"] = response_text
        await inbox_container.upsert_item(body=doc, **th)
        logger.info(
            "Stored admin response for delivery on inbox item %s. "
            "outcome=response_stored",
            inbox_item_id,
            extra=log_extra,
        )
    except Exception as store_exc:
        logger.warning(
            "Failed to store admin response for %s: %s",
            inbox_item_id,
            store_exc,
            extra=log_extra,
        )
```

**Branch B target shape after Phase 25 transformation** (replaces lines 395-420):
```python
else:
    # Simple confirmation -- soft-delete by filing the inbox item.
    # Setting status="filed" + adminProcessingStatus="completed" + ttl
    # in ONE upsert is critical: the api/errands.py:174 unprocessed query
    # gates on adminProcessingStatus, so partial writes would re-fire the
    # agent on a filed doc (Landmine #4). Container TTL must already be
    # enabled (defaultTtl=-1) for the per-doc ttl to take effect.
    try:
        settings = get_settings()
        ttl_seconds = settings.inbox_filed_retention_days * 86400
        doc = await inbox_container.read_item(
            item=inbox_item_id, partition_key="will", **th
        )
        doc["status"] = "filed"
        doc["adminProcessingStatus"] = "completed"
        doc["ttl"] = ttl_seconds
        await inbox_container.upsert_item(body=doc, **th)
        logger.info(
            "Filed processed inbox item %s. outcome=filed",
            inbox_item_id,
            extra=log_extra,
        )
    except CosmosResourceNotFoundError:
        # User may have swipe-deleted while processing
        logger.info(
            "Inbox item %s already deleted (user may have removed it)",
            inbox_item_id,
            extra=log_extra,
        )
    except Exception as file_exc:
        # Non-fatal: errand items are the durable output
        logger.warning(
            "Failed to file processed inbox item %s: %s",
            inbox_item_id,
            file_exc,
            extra=log_extra,
        )
```

**ContextVar set pattern to add** (insert at line 215-216 area, alongside existing `capture_trace_id_var.set(...)`):
```python
from second_brain.tools.admin import admin_inbox_item_id_var

if capture_trace_id:
    capture_trace_id_var.set(capture_trace_id)
admin_inbox_item_id_var.set(inbox_item_id)  # NEW — for backlinks
```

**Notes:**
- **Landmine #4 (critical):** Branch B's current `delete_item` skips setting `adminProcessingStatus="completed"` because the doc is being deleted. Phase 25 MUST add this flip. Without it, filed docs have `adminProcessingStatus="pending"` and the api/errands.py:174 re-fire query matches them → re-fire loop on filed items.
- **Landmine #5 (auto-format):** Adding `from second_brain.config import get_settings` + `from second_brain.tools.admin import admin_inbox_item_id_var` MUST land in the same edit as their first usage. Use a single `Write` for admin_handoff.py rather than stepwise Edits.
- **Landmine #6 (TTL type):** `ttl` MUST be an integer. `settings.inbox_filed_retention_days * 86400` = int * int = int. Never `timedelta(...)` or string.
- **Landmine #8 (order of deploy):** Container `defaultTtl=-1` must be set BEFORE this code ships. Plan orders: infra step → deploy. If code ships first, filed docs persist forever (silent).
- **Preserves:** `**th` (trace_headers) for native Cosmos correlation per Phase 19.4.
- Log `outcome=` key changes from `processed` to `filed` — search the repo before merging (researcher confirmed no current consumers).

---

### File 2: `backend/src/second_brain/api/inbox.py` (API, read-only Cosmos query)

**Analog:** Self — `list_inbox` at lines 56-112 (only the query string changes).

**Action:** Modify the `query` string at lines 76-80 to exclude `status="filed"` docs with `IS_DEFINED` guard for pre-Phase-25 backward compatibility.

**Current query** (lines 76-80):
```python
query = (
    "SELECT * FROM c WHERE c.userId = @userId "
    "ORDER BY c.createdAt DESC "
    "OFFSET @offset LIMIT @limit"
)
```

**Target query**:
```python
query = (
    "SELECT * FROM c WHERE c.userId = @userId "
    "AND (NOT IS_DEFINED(c.status) OR c.status != 'filed') "
    "ORDER BY c.createdAt DESC "
    "OFFSET @offset LIMIT @limit"
)
```

**Notes:**
- ONLY the listing query at lines 76-80 needs the filter. Per researcher:
  - `GET /api/inbox/{item_id}` (line 115) — single-item GET intentionally leaves a back-door for ops/debug; NO filter change.
  - `DELETE /api/inbox/{item_id}` (line 140) — manual delete by user; NO filter change.
  - `PATCH /api/inbox/{item_id}/recategorize` (line 200) — only used on visible items; NO filter change.
- `NOT IS_DEFINED` guard required because pre-Phase-25 docs may have `status` unset for some legacy paths. The guard handles both unset and set-but-not-filed cases cleanly.
- Use string literal `'filed'` (single-quoted in SQL) to match Cosmos query convention used elsewhere in this file and `api/errands.py`.

---

### File 3: `backend/src/second_brain/api/errands.py` (API, mutating Cosmos)

**Analog:** Self — `dismiss_admin_notification` at lines 446-472 + `admin_handoff.py:163-177` (`_mark_inbox_failed` pattern).

**Action:** Replace `delete_item` at line 464 with the same read→mutate→upsert helper used in admin_handoff Branch B. Verify the unprocessed-admin query at lines 174-194 is orthogonal to `status="filed"` (it filters by `adminProcessingStatus`, so naturally excludes filed-and-completed items).

**Current dismiss endpoint** (lines 446-472):
```python
@router.post(
    "/api/errands/notifications/{inbox_item_id}/dismiss",
    status_code=204,
)
async def dismiss_admin_notification(
    request: Request,
    inbox_item_id: str,
) -> Response:
    """Dismiss an admin notification by deleting the completed inbox item.

    The mobile app calls this after the user has seen the notification.
    """
    cosmos_manager = getattr(request.app.state, "cosmos_manager", None)
    if cosmos_manager is None:
        raise HTTPException(
            status_code=503,
            detail="Cosmos DB not configured.",
        )

    inbox_container = cosmos_manager.get_container("Inbox")

    try:
        await inbox_container.delete_item(item=inbox_item_id, partition_key="will")
    except CosmosResourceNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Notification {inbox_item_id} not found",
        ) from exc

    logger.info("Dismissed admin notification %s", inbox_item_id)
    return Response(status_code=204)
```

**Target dismiss endpoint** (after Phase 25 transformation — keeps 404 semantics, swaps body for soft-delete):
```python
@router.post(
    "/api/errands/notifications/{inbox_item_id}/dismiss",
    status_code=204,
)
async def dismiss_admin_notification(
    request: Request,
    inbox_item_id: str,
) -> Response:
    """Dismiss an admin notification by filing the completed inbox item.

    The mobile app calls this after the user has seen the notification.
    Soft-deletes with status='filed' + per-doc ttl for lifecycle symmetry
    with admin_handoff Branch B (auto-file on success). The 30-day TTL is
    sourced from settings.inbox_filed_retention_days.
    """
    cosmos_manager = getattr(request.app.state, "cosmos_manager", None)
    if cosmos_manager is None:
        raise HTTPException(
            status_code=503,
            detail="Cosmos DB not configured.",
        )

    inbox_container = cosmos_manager.get_container("Inbox")
    settings = get_settings()
    ttl_seconds = settings.inbox_filed_retention_days * 86400

    try:
        doc = await inbox_container.read_item(
            item=inbox_item_id, partition_key="will"
        )
    except CosmosResourceNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Notification {inbox_item_id} not found",
        ) from exc

    doc["status"] = "filed"
    doc["adminProcessingStatus"] = "completed"  # idempotent — already 'completed' at this point
    doc["ttl"] = ttl_seconds
    await inbox_container.upsert_item(body=doc)

    logger.info("Dismissed admin notification %s (filed)", inbox_item_id)
    return Response(status_code=204)
```

**NEW import** (add at top of file alongside existing imports):
```python
from second_brain.config import get_settings
```

**Unprocessed-admin query** (lines 174-194 — NO CHANGE, but verify in tests):
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

**Notes:**
- **Open question #1 in RESEARCH.md**: dismiss_admin_notification is bundled into Phase 25 per the symmetry argument. CONTEXT.md scope says "hard-delete-on-Admin-success path" technically only covers Branch B; researcher recommends YES (fold in for lifecycle symmetry). Plan must explicitly call this out.
- **Notifications query at lines 262-269**: NO change needed. It only matches Branch A items (`adminProcessingStatus='completed'` AND `adminAgentResponse IS NOT NULL`). Filed Branch B items have `adminAgentResponse` unset, so they don't match.
- **Trace headers**: Unlike admin_handoff.py, the dismiss endpoint does NOT have `capture_trace_id` in scope today. Two options: (a) leave the upsert without `**th` (simplest; trace correlation already happened during processing), or (b) extract from `inbox_doc.get("captureTraceId")` to preserve correlation on the dismiss event. Plan picks (a) for minimal surface area; if observability demand surfaces, follow up separately.
- **Landmine #5 (auto-format)**: The new `from second_brain.config import get_settings` import + first usage MUST land in the same `Write`/`Edit` atomically. Use a single `Edit` that adds both lines together, or `Write` if doing multiple edits.

---

### File 4: `backend/src/second_brain/tools/admin.py` (tool, new ContextVar + mutating writes)

**Analog:** `tools/classification.py:36-55` (ContextVar definition + context manager pattern) + self at lines 175-184 (current `ErrandItem` construction).

**Action:**
1. Add module-level ContextVar `admin_inbox_item_id_var` (mirroring `_follow_up_inbox_item_id` in classification.py).
2. Import `capture_trace_id_var` from `tools.classification`.
3. In `add_errand_items` (after line 174 `needs_routing = ...`): read both ContextVars and pass as new ErrandItem fields.
4. In `add_task_items` (after line 224 `name = ...`): same pattern, pass as new TaskItem fields.

**ContextVar definition pattern to copy from `tools/classification.py:34-45`**:
```python
import contextvars

# Context var for follow-up mode: when set, file_capture updates the existing
# inbox doc in-place instead of creating a new one.
_follow_up_inbox_item_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_follow_up_inbox_item_id", default=None
)

# Context var for per-capture trace ID propagation.  The adapter sets this
# before invoking the Foundry agent so file_capture can persist the trace ID
# on the inbox document for end-to-end filtering in App Insights.
capture_trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "capture_trace_id_var", default=""
)
```

**Phase 25 ContextVar to add at top of `tools/admin.py`** (after the `from pydantic import Field` block, ~line 21):
```python
import contextvars

# Context var for source-inbox-item propagation. Set by admin_handoff.py
# before agent.run() so add_errand_items / add_task_items can stamp the
# sourceInboxItemId backlink on each created Errand/Task doc. Default None
# so non-admin code paths (eval, direct tool tests) don't crash on .get().
admin_inbox_item_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "admin_inbox_item_id_var", default=None
)
```

**ContextVar read pattern to copy from `tools/recipe.py:191` and `tools/classification.py:130-131,166`**:
```python
# tools/recipe.py:191
capture_trace_id = capture_trace_id_var.get() or None

# tools/classification.py:130-131,166
trace_id = capture_trace_id_var.get()
log_extra: dict = {"capture_trace_id": trace_id, "component": "classifier"}
```

**Current `add_errand_items` ErrandItem construction (lines 175-184) to modify**:
```python
needs_routing = destination == "unrouted"
source_name = item_data.get("sourceName")
source_url = item_data.get("sourceUrl")
doc = ErrandItem(
    destination=destination,
    name=name,
    needsRouting=needs_routing,
    sourceName=source_name,
    sourceUrl=source_url,
)
await container.create_item(body=doc.model_dump())
```

**Target `add_errand_items` ErrandItem construction (after Phase 25)**:
```python
needs_routing = destination == "unrouted"
source_name = item_data.get("sourceName")
source_url = item_data.get("sourceUrl")
# Phase 25: stamp source backlinks if running inside an admin processing
# context (admin_handoff sets both ContextVars before agent.run).
source_inbox_id = admin_inbox_item_id_var.get()
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
await container.create_item(body=doc.model_dump())
```

**Current `add_task_items` TaskItem construction (lines 224-231)**:
```python
for task_data in tasks:
    name = task_data.get("name", "").strip()
    if not name:
        logger.warning("Skipping task with empty name: %s", task_data)
        continue

    doc = TaskItem(name=name)
    await container.create_item(body=doc.model_dump(mode="json"))
```

**Target `add_task_items` TaskItem construction (after Phase 25)**:
```python
for task_data in tasks:
    name = task_data.get("name", "").strip()
    if not name:
        logger.warning("Skipping task with empty name: %s", task_data)
        continue

    # Phase 25: stamp source backlinks if running inside an admin processing
    # context.
    source_inbox_id = admin_inbox_item_id_var.get()
    source_trace_id = capture_trace_id_var.get() or None
    doc = TaskItem(
        name=name,
        sourceInboxItemId=source_inbox_id,
        sourceCaptureTraceId=source_trace_id,
    )
    await container.create_item(body=doc.model_dump(mode="json"))
```

**NEW imports for admin.py** (at top of file alongside existing imports):
```python
import contextvars  # NEW
# (existing) from second_brain.models.documents import (...)
from second_brain.tools.classification import capture_trace_id_var  # NEW
```

**Notes:**
- **Landmine #5 (auto-format) — CRITICAL**: Adding `import contextvars` + the `from second_brain.tools.classification import capture_trace_id_var` + the ContextVar definition + the usage in `add_errand_items`/`add_task_items` MUST land atomically. **Use a single `Write` for admin.py** rather than stepwise `Edit` calls. Otherwise ruff strips unused imports between edits.
- **Empty-string handling**: `capture_trace_id_var` has default `""` (empty string). Use `.get() or None` to convert empty to None — matches the recipe.py:191 pattern and avoids storing empty strings as `sourceCaptureTraceId`.
- **None-default for admin_inbox_item_id_var**: Default is `None` (not empty string). `.get()` returns None directly — no `or None` needed.
- **Why not Option B (per-call AdminTools construction)**: Phase 24-09/24-11 cemented lifespan-singleton AdminTools. Constructing a fresh AdminTools per admin processing call would break the architecture. ContextVar is the recommended pattern.
- **Eval path compatibility**: `DryRunAdminTools` in `eval/dry_run_tools.py` does NOT construct `ErrandItem`/`TaskItem` (captures in memory as raw dicts). New optional fields with `None` defaults mean eval is unaffected.

---

### File 5: `backend/src/second_brain/models/documents.py` (model, new optional fields)

**Analog:** Self — `ErrandItem.sourceName` / `ErrandItem.sourceUrl` at lines 118-119 (existing optional string fields with `None` default).

**Action:** Add two optional string fields to `ErrandItem` and `TaskItem`. No validator, no Literal constraint — same pattern as the existing optional fields.

**Current `ErrandItem` (lines 105-119)**:
```python
class ErrandItem(BaseModel):
    """Individual errand item in the Errands Cosmos container.

    Partition key is /destination (not /userId like other containers).
    Items exist until deleted -- no status tracking, no timestamps.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    destination: str  # Partition key: dynamic slug from Destinations container
    name: str  # Full natural language: "2 lbs ground beef", "cat litter"
    needsRouting: bool = (
        False  # True when destination is "unrouted" (no affinity rule matched)
    )
    sourceName: str | None = None  # Recipe name for source attribution
    sourceUrl: str | None = None  # Recipe URL for source attribution
```

**Target `ErrandItem` (after Phase 25 — append two fields)**:
```python
class ErrandItem(BaseModel):
    """Individual errand item in the Errands Cosmos container.

    Partition key is /destination (not /userId like other containers).
    Items exist until deleted -- no status tracking, no timestamps.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    destination: str  # Partition key: dynamic slug from Destinations container
    name: str  # Full natural language: "2 lbs ground beef", "cat litter"
    needsRouting: bool = (
        False  # True when destination is "unrouted" (no affinity rule matched)
    )
    sourceName: str | None = None  # Recipe name for source attribution
    sourceUrl: str | None = None  # Recipe URL for source attribution
    # Phase 25 backlinks. Populated by tools/admin.py:add_errand_items when
    # running inside an admin processing context (admin_handoff sets the
    # ContextVars before agent.run). Absent on pre-Phase-25 docs; UI handles
    # missing backlinks gracefully (no affordance shown).
    sourceInboxItemId: str | None = None  # Source Inbox doc id (durable for 30d)
    sourceCaptureTraceId: str | None = None  # Source capture trace id (durable forever)
```

**Current `TaskItem` (lines 122-133)**:
```python
class TaskItem(BaseModel):
    """Individual task item in the Tasks Cosmos container.

    Partition key is /userId (like most containers).
    Tasks are actionable to-dos routed from Admin captures that aren't errands
    (e.g., "book eye appointment", "fill out expenses").
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    userId: str = "will"
    name: str  # Natural language: "book eye appointments", "fill out Peloton expenses"
    createdAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

**Target `TaskItem` (after Phase 25 — append two fields)**:
```python
class TaskItem(BaseModel):
    """Individual task item in the Tasks Cosmos container.

    Partition key is /userId (like most containers).
    Tasks are actionable to-dos routed from Admin captures that aren't errands
    (e.g., "book eye appointment", "fill out expenses").
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    userId: str = "will"
    name: str  # Natural language: "book eye appointments", "fill out Peloton expenses"
    createdAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
    # Phase 25 backlinks. Populated by tools/admin.py:add_task_items when
    # running inside an admin processing context. Absent on pre-Phase-25 docs.
    sourceInboxItemId: str | None = None  # Source Inbox doc id (durable for 30d)
    sourceCaptureTraceId: str | None = None  # Source capture trace id (durable forever)
```

**Notes:**
- **No `InboxDocument.status` change required**: `status: str = "classified"` (line 51) accepts any string. New `"filed"` value works without code change.
- **camelCase per Ruff N815 ignore in pyproject.toml**: `documents.py` is whitelisted for camelCase — `sourceInboxItemId`/`sourceCaptureTraceId` match the existing pattern (`sourceName`, `sourceUrl`, `filedRecordId`, `inboxRecordId`).
- **Order in the field list**: Append after existing `sourceName`/`sourceUrl` on ErrandItem and after `createdAt` on TaskItem. Conservative — preserves serialization order for any consumers that care.
- **Pre-Phase-25 doc compatibility**: Pydantic optional fields with `None` default deserialize existing docs cleanly (no migration needed; Decision 5 in CONTEXT.md confirms no backfill).

---

### File 6: `backend/src/second_brain/config.py` (config, new env-var setting w/ validation)

**Analog:** `spine/api.py:48-49` (only existing `Field(ge=...)` in the codebase) + self (`Settings` class structure).

**Action:** Add `inbox_filed_retention_days: int = Field(default=30, ge=1, description=...)` to `Settings`. Import `Field` from pydantic.

**Existing `Settings` (current state, line 1-69) — imports already include `BaseSettings`**:
```python
"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from .env file and environment variables."""

    # Azure AI Foundry
    azure_ai_project_endpoint: str = ""
    # ... (lots of fields) ...

    # Database
    database_name: str = "second-brain"
    # ... etc
```

**Existing `Field(ge=...)` precedent (`spine/api.py:48-49`)**:
```python
class AuditRequest(BaseModel):
    """Request body for POST /api/spine/audit/correlation."""

    correlation_kind: CorrelationKind
    correlation_id: str | None = None
    sample_size: int = Field(5, ge=1, le=20)
    time_range_seconds: int = Field(86400, ge=60, le=604800)  # 1min - 7d
```

**Target `Settings` change** (add `Field` import + new setting near the existing `classification_threshold` and `database_name` block, ~line 45-50):
```python
"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from .env file and environment variables."""

    # ... (existing fields unchanged) ...

    # Classification
    classification_threshold: float = 0.6

    # Inbox filed-doc retention (Phase 25). Per-doc Cosmos TTL value =
    # this * 86400 seconds. Cosmos container `defaultTtl` must be -1 for
    # this to take effect (one-time infra step in Plan 02). Minimum 1 day
    # prevents accidental immediate-purge from a misconfigured env var.
    inbox_filed_retention_days: int = Field(
        default=30,
        ge=1,
        description="Days to retain filed admin inbox docs; minimum 1.",
    )

    # Database
    database_name: str = "second-brain"
    # ... rest unchanged
```

**Env var binding** (automatic via `BaseSettings` + `case_sensitive=False` already set in `model_config`):
- Setting `INBOX_FILED_RETENTION_DAYS=30` on the Container App env vars binds to `settings.inbox_filed_retention_days = 30`.
- Default 30 means the env var is optional — code works out-of-the-box without setting it.

**Notes:**
- **`Field` import is new** — config.py currently imports only `from pydantic_settings import BaseSettings`. Add `from pydantic import Field` alongside (Pydantic v2 ships `Field` from the `pydantic` namespace).
- **Landmine #7 (ge=1 critical)**: Without the `ge=1` constraint, `INBOX_FILED_RETENTION_DAYS=0` would set `ttl=0` → immediate-purge bug at the next Cosmos sweep. Pydantic's `Field(ge=1)` fails fast at app startup with `ValidationError` if a bad env var slips through.
- **Landmine #5 (auto-format)**: Adding `from pydantic import Field` import alongside the new field usage in the same `Edit` is safe (one Edit; import + first usage land together).
- **`model_config` block stays unchanged**: `extra="ignore"` already tolerates orphan env vars from prior phases.

---

### File 7: `backend/tests/test_admin_handoff.py` (test, unit mock-Cosmos)

**Analog:** Self — entire file is mock-Cosmos unit test pattern. Specifically rename `test_sets_pending_then_deletes_on_success` (line 180-204) and `test_tool_call_still_deletes` (line 542-554); extend `test_agent_error_sets_status_to_failed` (line 285-305).

**Action:**
1. Rename `test_sets_pending_then_deletes_on_success` → `test_simple_confirmation_files_inbox_item` and rewrite assertions (delete → upsert with status/ttl/adminProcessingStatus).
2. Add `test_filed_doc_ttl_matches_settings`.
3. Add `test_filing_writes_all_fields_atomically`.
4. Extend `test_agent_error_sets_status_to_failed` to assert `status != "filed"` on the failed-upsert body.
5. Add `test_agent_error_does_not_file_inbox_item`.
6. Add `test_admin_handoff_sets_inbox_item_id_contextvar`.
7. Update 5 other test fixtures that assert `delete_item.assert_called_once_with(...)` at lines 202, 453, 540, 552, 667.

**Current `test_sets_pending_then_deletes_on_success` (lines 180-204) — the canonical pattern to rewrite**:
```python
async def test_sets_pending_then_deletes_on_success(
    self, mock_admin_agent, mock_cosmos_manager
):
    """Status transitions: None -> pending, then delete on success."""
    await process_admin_capture(
        admin_agent=mock_admin_agent,
        cosmos_manager=mock_cosmos_manager,
        inbox_item_id="test-inbox-id",
        raw_text="need cat litter and milk",
    )

    container = mock_cosmos_manager.get_container("Inbox")

    # Only ONE upsert: the "pending" status
    upsert_calls = container.upsert_item.call_args_list
    assert len(upsert_calls) == 1
    first_body = upsert_calls[0].kwargs.get("body") or upsert_calls[0][1].get(
        "body"
    )
    assert first_body["adminProcessingStatus"] == "pending"

    # delete_item called once for the processed inbox item
    container.delete_item.assert_called_once_with(
        item="test-inbox-id", partition_key="will"
    )
```

**Target `test_simple_confirmation_files_inbox_item` (after Phase 25 rewrite)**:
```python
async def test_simple_confirmation_files_inbox_item(
    self, mock_admin_agent, mock_cosmos_manager
):
    """Branch B: status="filed" + ttl + adminProcessingStatus="completed" via upsert (no delete).

    Phase 25 swap: previously the success path called delete_item; now it
    soft-deletes via upsert with status='filed' + ttl + completed marker.
    All three fields must land in the SAME upsert body (Landmine #4 in
    RESEARCH.md — partial writes would re-fire the agent on filed docs).
    """
    await process_admin_capture(
        admin_agent=mock_admin_agent,
        cosmos_manager=mock_cosmos_manager,
        inbox_item_id="test-inbox-id",
        raw_text="need cat litter and milk",
    )

    container = mock_cosmos_manager.get_container("Inbox")

    # TWO upserts: pending (line ~247) + filing (Phase 25 swap)
    upsert_calls = container.upsert_item.call_args_list
    assert len(upsert_calls) == 2

    first_body = upsert_calls[0].kwargs.get("body") or upsert_calls[0][1].get(
        "body"
    )
    assert first_body["adminProcessingStatus"] == "pending"

    filing_body = upsert_calls[-1].kwargs.get("body") or upsert_calls[-1][1].get(
        "body"
    )
    assert filing_body["status"] == "filed"
    assert filing_body["adminProcessingStatus"] == "completed"
    assert filing_body["ttl"] > 0  # actual value asserted in test_filed_doc_ttl_matches_settings
    assert isinstance(filing_body["ttl"], int)

    # delete_item should NOT have been called (replaced by upsert)
    container.delete_item.assert_not_called()
```

**New `test_filed_doc_ttl_matches_settings`**:
```python
async def test_filed_doc_ttl_matches_settings(
    self, mock_admin_agent, mock_cosmos_manager
):
    """Filed doc ttl = settings.inbox_filed_retention_days * 86400."""
    from second_brain.config import get_settings

    await process_admin_capture(
        admin_agent=mock_admin_agent,
        cosmos_manager=mock_cosmos_manager,
        inbox_item_id="test-inbox-id",
        raw_text="need milk",
    )

    container = mock_cosmos_manager.get_container("Inbox")
    filing_body = container.upsert_item.call_args_list[-1].kwargs.get("body")

    expected_ttl = get_settings().inbox_filed_retention_days * 86400
    assert filing_body["ttl"] == expected_ttl
    assert expected_ttl == 30 * 86400  # 2592000 default
```

**New `test_filing_writes_all_fields_atomically`** (orthogonality test for Landmine #4):
```python
async def test_filing_writes_all_fields_atomically(
    self, mock_admin_agent, mock_cosmos_manager
):
    """status, adminProcessingStatus, and ttl land in the SAME upsert body.

    Landmine #4: if filed-status and completed-marker were written in
    separate upserts, a partial write would leave the doc with
    adminProcessingStatus='pending' (which matches the api/errands.py:174
    re-fire query) AND status='filed' (which the listing query hides).
    Net result: invisible re-fire loop. The test asserts atomicity.
    """
    await process_admin_capture(
        admin_agent=mock_admin_agent,
        cosmos_manager=mock_cosmos_manager,
        inbox_item_id="test-inbox-id",
        raw_text="need milk",
    )

    container = mock_cosmos_manager.get_container("Inbox")
    # The filing upsert is the LAST upsert call (after pending).
    filing_body = container.upsert_item.call_args_list[-1].kwargs.get("body")

    assert "status" in filing_body
    assert "adminProcessingStatus" in filing_body
    assert "ttl" in filing_body
    assert filing_body["status"] == "filed"
    assert filing_body["adminProcessingStatus"] == "completed"
```

**Extension to `test_agent_error_sets_status_to_failed` (lines 285-305) — append assertion**:
```python
async def test_agent_error_sets_status_to_failed(
    self, mock_admin_agent, mock_cosmos_manager
):
    """When Admin Agent raises, status transitions to 'failed' WITHOUT 'filed'."""
    mock_admin_agent.run.side_effect = RuntimeError("Foundry timeout")

    await process_admin_capture(
        admin_agent=mock_admin_agent,
        cosmos_manager=mock_cosmos_manager,
        inbox_item_id="test-inbox-id",
        raw_text="need cat litter",
    )

    container = mock_cosmos_manager.get_container("Inbox")
    upsert_calls = container.upsert_item.call_args_list
    assert len(upsert_calls) >= 2
    last_body = upsert_calls[-1].kwargs.get("body") or upsert_calls[-1][1].get(
        "body"
    )
    assert last_body["adminProcessingStatus"] == "failed"
    # Phase 25 orthogonality: failed items MUST NOT be marked filed (Landmine #1).
    assert last_body.get("status") != "filed"
```

**New `test_admin_handoff_sets_inbox_item_id_contextvar`**:
```python
async def test_admin_handoff_sets_inbox_item_id_contextvar(
    self, mock_admin_agent, mock_cosmos_manager
):
    """process_admin_capture sets admin_inbox_item_id_var before agent.run.

    add_errand_items / add_task_items read this ContextVar to stamp
    sourceInboxItemId backlinks on Errand/Task docs.
    """
    from second_brain.tools.admin import admin_inbox_item_id_var

    observed_id: list[str | None] = []

    async def _capture_var(*args, **kwargs):
        observed_id.append(admin_inbox_item_id_var.get())
        # Return a normal output-tool response so processing succeeds
        return _agent_response(
            text="Added items.",
            tool_names=["add_errand_items"],
        )

    mock_admin_agent.run = AsyncMock(side_effect=_capture_var)

    await process_admin_capture(
        admin_agent=mock_admin_agent,
        cosmos_manager=mock_cosmos_manager,
        inbox_item_id="ctx-inbox-id",
        raw_text="need milk",
    )

    assert observed_id == ["ctx-inbox-id"]
```

**Notes:**
- Five other test sites in this file assert `container.delete_item.assert_called_once...` — at lines 202, 453, 540, 552, 667. Each maps to a different success scenario. Per VALIDATION.md Wave 0, each must be flipped from "asserts delete" to "asserts upsert with filed body". Plan can batch these into a single Wave 0 task.
- **MagicMock body shape**: Tests use `call.kwargs.get("body") or call[1].get("body")` to support both keyword and positional call shapes. Preserve this idiom.
- **The autouse fixture at line 165-169** (`_setup_inbox_read`) returns mutable dicts via `lambda **kwargs: _inbox_doc()`. The new filing path will call `read_item` twice (once for pending, once for filing) — confirm `_inbox_doc()` returns a fresh dict each time so mutations don't leak across reads.

---

### File 8: `backend/tests/test_admin_tools.py` (test, unit mock-Cosmos)

**Analog:** Self — `test_add_items_happy_path` at lines 78-104 (Errands write assertion pattern) + `test_event_tracing.py:413-446` (ContextVar set/reset wrapper pattern).

**Action:** Add 3 new tests asserting backlink propagation, and 1 test asserting graceful no-op when ContextVars are unset.

**Helper `_get_all_bodies` pattern already exists (lines 33-36)**:
```python
def _get_all_bodies(mock_cosmos_manager: object, container: str) -> list[dict]:
    """Extract all body dicts from a container's create_item calls."""
    c = mock_cosmos_manager.get_container(container)
    return [call[1]["body"] for call in c.create_item.call_args_list]
```

**ContextVar set/reset pattern to copy from `test_event_tracing.py:413-446`**:
```python
from second_brain.tools.classification import ClassifierTools, capture_trace_id_var

async def test_file_capture_writes_trace_id_to_inbox_doc(self, mock_cosmos_manager):
    """Cosmos inbox document includes captureTraceId from ContextVar."""
    tools = ClassifierTools(mock_cosmos_manager, classification_threshold=0.6)

    # Simulate what the adapter does: set the ContextVar before tool call
    token = capture_trace_id_var.set(TRACE_ID)
    try:
        # ... test body ...
        result = await tools.file_capture(...)
    finally:
        capture_trace_id_var.reset(token)

    # Verify the inbox document written to Cosmos has captureTraceId
    assert created_docs[0]["captureTraceId"] == TRACE_ID
```

**New `test_add_errand_items_carries_backlinks`**:
```python
async def test_add_errand_items_carries_backlinks(
    mock_cosmos_manager: object,
) -> None:
    """add_errand_items stamps sourceInboxItemId + sourceCaptureTraceId from ContextVars.

    Phase 25 (REQ-BL-03): when admin_handoff sets both ContextVars before
    agent.run, the persisted ErrandItem doc must carry both backlink fields.
    """
    from second_brain.tools.admin import admin_inbox_item_id_var
    from second_brain.tools.classification import capture_trace_id_var

    _setup_echo(mock_cosmos_manager, "Errands")

    inbox_token = admin_inbox_item_id_var.set("inbox-source-42")
    trace_token = capture_trace_id_var.set("trace-source-99")
    try:
        tools = _make_tools(mock_cosmos_manager)
        await tools.add_errand_items(
            items=[{"name": "milk", "destination": "jewel"}]
        )
    finally:
        admin_inbox_item_id_var.reset(inbox_token)
        capture_trace_id_var.reset(trace_token)

    bodies = _get_all_bodies(mock_cosmos_manager, "Errands")
    assert len(bodies) == 1
    assert bodies[0]["sourceInboxItemId"] == "inbox-source-42"
    assert bodies[0]["sourceCaptureTraceId"] == "trace-source-99"


async def test_add_task_items_carries_backlinks(
    mock_cosmos_manager: object,
) -> None:
    """add_task_items stamps sourceInboxItemId + sourceCaptureTraceId from ContextVars."""
    from second_brain.tools.admin import admin_inbox_item_id_var
    from second_brain.tools.classification import capture_trace_id_var

    _setup_echo(mock_cosmos_manager, "Tasks")

    inbox_token = admin_inbox_item_id_var.set("inbox-task-7")
    trace_token = capture_trace_id_var.set("trace-task-13")
    try:
        tools = _make_tools(mock_cosmos_manager)
        await tools.add_task_items(
            tasks=[{"name": "Book eye appointment"}]
        )
    finally:
        admin_inbox_item_id_var.reset(inbox_token)
        capture_trace_id_var.reset(trace_token)

    bodies = _get_all_bodies(mock_cosmos_manager, "Tasks")
    assert len(bodies) == 1
    assert bodies[0]["sourceInboxItemId"] == "inbox-task-7"
    assert bodies[0]["sourceCaptureTraceId"] == "trace-task-13"


async def test_add_errand_items_no_contextvars_set(
    mock_cosmos_manager: object,
) -> None:
    """When ContextVars are unset (default), backlinks land as None — no crash.

    Eval and direct-invoke paths don't set these ContextVars. The tool MUST
    gracefully accept None defaults rather than crashing on .get().
    """
    _setup_echo(mock_cosmos_manager, "Errands")

    # NO ContextVar set — relies on defaults (admin_inbox_item_id_var=None,
    # capture_trace_id_var=""). The "" trace id should normalize to None
    # via the `.get() or None` idiom.
    tools = _make_tools(mock_cosmos_manager)
    await tools.add_errand_items(
        items=[{"name": "milk", "destination": "jewel"}]
    )

    bodies = _get_all_bodies(mock_cosmos_manager, "Errands")
    assert len(bodies) == 1
    assert bodies[0]["sourceInboxItemId"] is None
    assert bodies[0]["sourceCaptureTraceId"] is None
```

**Notes:**
- **ContextVar token discipline**: ALWAYS use `try/finally` with `var.reset(token)`. Test isolation depends on this — leaking a ContextVar to another test causes cascading failures.
- **`_setup_echo` helper** (line 27-30) makes `create_item` return the body — that's what `_get_all_bodies` reads. Don't try to mock `create_item` differently.
- **No Wave 0 dep on `documents.py` model edit**: the model change must land FIRST (or in the same wave) — otherwise `ErrandItem(sourceInboxItemId=...)` raises `ValidationError`. Plan ordering: model edit → tool edit → test add.

---

### File 9: `backend/tests/test_inbox_api.py` (test, integration httpx)

**Analog:** `test_errands_api.py:74-108` (`_make_async_iterator` + `query_items` side_effect pattern) + this file's existing fixtures.

**Action:** Add `test_list_inbox_excludes_filed_status` that mocks the Inbox query_items to return both a filed and a classified doc, then asserts the API response excludes the filed one.

**Pattern to copy for async iterator over Cosmos query results** (`test_errands_api.py:74-94`):
```python
def _make_async_iterator(items: list[dict]):
    """Create an async iterator from a list of dicts (mimics Cosmos query_items)."""

    async def _iter(*args, **kwargs):
        for item in items:
            yield item

    return _iter


def _setup_destinations(
    mock_cosmos_manager: MagicMock,
    destinations: list[dict] | None = None,
) -> None:
    """Configure Destinations container mock to return destination documents."""
    if destinations is None:
        destinations = SAMPLE_DESTINATIONS
    dest_container = mock_cosmos_manager.get_container("Destinations")
    dest_container.query_items = MagicMock(
        return_value=_make_async_iterator(destinations)()
    )
```

**Existing inbox_app fixture (lines 77-86) — REUSE**:
```python
@pytest.fixture
def inbox_app(mock_cosmos_manager: MagicMock) -> FastAPI:
    """Create a FastAPI app with the inbox router and mock Cosmos."""
    app = FastAPI()
    app.include_router(inbox_router)
    app.state.api_key = TEST_API_KEY
    app.state.cosmos_manager = mock_cosmos_manager
    app.add_middleware(APIKeyMiddleware)
    return app
```

**New `test_list_inbox_excludes_filed_status`**:
```python
@pytest.mark.asyncio
async def test_list_inbox_excludes_filed_status(
    inbox_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """GET /api/inbox should NOT include docs with status="filed".

    Phase 25: the listing query has `AND (NOT IS_DEFINED(c.status) OR c.status != 'filed')`
    appended to its WHERE clause. The mock returns both filed and classified docs;
    we verify the API response excludes the filed one.

    Note: this test exercises the API contract, not the SQL itself (which is a
    string literal passed to a mock). To prove the SQL filter actually works
    against Cosmos, the test asserts BOTH (a) the query string contains the
    filed-exclusion clause AND (b) the API response shape doesn't surface filed
    items even when the mock returns them.
    """
    # Mock returns BOTH a filed and a classified doc to prove the API doesn't
    # surface filed items even if Cosmos somehow returns them. (We also check
    # the SQL string for the filter clause.)
    classified_doc = {
        "id": "inbox-classified",
        "userId": "will",
        "rawText": "buy milk",
        "title": "Milk errand",
        "status": "classified",
        "createdAt": "2026-05-17T10:00:00Z",
    }
    filed_doc = {
        "id": "inbox-filed",
        "userId": "will",
        "rawText": "old admin item",
        "title": "Old admin",
        "status": "filed",
        "createdAt": "2026-05-15T10:00:00Z",
        "ttl": 2592000,
    }

    captured_queries: list[str] = []

    def _async_iter(items):
        async def _iter(*args, **kwargs):
            captured_queries.append(kwargs.get("query", ""))
            for item in items:
                yield item
        return _iter

    inbox_container = mock_cosmos_manager.get_container("Inbox")
    # The mock returns ONLY classified — simulating Cosmos applying the WHERE
    # filter server-side. We also assert the SQL string contains the filter
    # clause (verification that the API code passed the right query).
    inbox_container.query_items = MagicMock(
        side_effect=_async_iter([classified_doc])
    )

    transport = httpx.ASGITransport(app=inbox_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/inbox",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 200
    data = response.json()
    ids = [item["id"] for item in data["items"]]
    assert "inbox-classified" in ids
    assert "inbox-filed" not in ids

    # Assert the SQL passed to Cosmos has the filed-exclusion clause.
    assert len(captured_queries) >= 1
    assert "c.status" in captured_queries[0]
    assert "filed" in captured_queries[0]
    assert "NOT IS_DEFINED" in captured_queries[0]
```

**Notes:**
- This file currently has zero list-endpoint tests — all existing tests cover recategorize. The test pattern needed (`async_iter` + `query_items` mock) doesn't exist here, so copy from `test_errands_api.py:74-83`.
- **Why assert on the SQL string**: the test mock can't enforce a server-side WHERE clause; we instead verify that the API code passed the right SQL. Combined with returning a fake classified-only result set, this proves both code paths.
- **Pytest-asyncio mode is `auto`** (per `pyproject.toml`) — `@pytest.mark.asyncio` is technically optional for async tests but used in this file consistently; keep the style.

---

### File 10: `backend/tests/test_errands_api.py` (test, integration httpx)

**Analog:** Self — `test_dismiss_admin_notification` at lines 611-630 + `test_get_errands_returns_admin_notifications` at lines 577-607.

**Action:**
1. Extend `test_dismiss_admin_notification` (lines 611-630) to assert upsert + filed body INSTEAD of delete_item (matches lifecycle symmetry decision).
2. Add `test_unprocessed_admin_query_skips_filed` asserting REQ-SD-07.

**Current `test_dismiss_admin_notification` (lines 611-630)**:
```python
@pytest.mark.asyncio
async def test_dismiss_admin_notification(
    errands_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """POST /dismiss deletes the inbox item for the notification."""
    inbox_container = mock_cosmos_manager.get_container("Inbox")
    inbox_container.delete_item = AsyncMock()

    transport = httpx.ASGITransport(app=errands_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/errands/notifications/notif-1/dismiss",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 204
    inbox_container.delete_item.assert_called_once_with(
        item="notif-1", partition_key="will"
    )
```

**Target `test_dismiss_admin_notification_files_instead_of_delete` (after Phase 25)**:
```python
@pytest.mark.asyncio
async def test_dismiss_admin_notification_files_instead_of_delete(
    errands_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """POST /dismiss soft-deletes (upsert with status='filed') — lifecycle symmetry with Branch B."""
    inbox_container = mock_cosmos_manager.get_container("Inbox")
    inbox_container.read_item = AsyncMock(
        return_value={
            "id": "notif-1",
            "userId": "will",
            "adminProcessingStatus": "completed",
            "adminAgentResponse": "I created a rule: chicken goes to jewel",
        }
    )
    inbox_container.upsert_item = AsyncMock()

    transport = httpx.ASGITransport(app=errands_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/errands/notifications/notif-1/dismiss",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 204
    # Phase 25: NO hard delete
    inbox_container.delete_item.assert_not_called()
    # Phase 25: upsert with filed body
    inbox_container.upsert_item.assert_called_once()
    body = inbox_container.upsert_item.call_args.kwargs["body"]
    assert body["status"] == "filed"
    assert body["adminProcessingStatus"] == "completed"
    assert body["ttl"] > 0
    assert isinstance(body["ttl"], int)


@pytest.mark.asyncio
async def test_dismiss_admin_notification_not_found(
    errands_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """POST /dismiss returns 404 when notification inbox item is missing.

    Phase 25: 404 is now produced by the read_item attempt, not the
    delete_item attempt. Otherwise identical to the pre-Phase-25 behavior.
    """
    inbox_container = mock_cosmos_manager.get_container("Inbox")
    inbox_container.read_item = AsyncMock(
        side_effect=CosmosResourceNotFoundError(status_code=404, message="Not found")
    )

    transport = httpx.ASGITransport(app=errands_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/errands/notifications/nonexistent/dismiss",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 404
```

**New `test_unprocessed_admin_query_skips_filed`**:
```python
@pytest.mark.asyncio
async def test_unprocessed_admin_query_skips_filed(
    errands_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """The unprocessed-admin query (api/errands.py:174) MUST NOT re-fire on filed docs.

    REQ-SD-07: a filed doc has adminProcessingStatus='completed' AND status='filed'.
    The unprocessed query filters by adminProcessingStatus IN (None, 'failed', 'pending')
    so filed-completed docs are naturally excluded. This test verifies the
    orthogonality by simulating a filed doc passed through the mock and asserting
    NO background task is created.
    """
    _setup_destinations(mock_cosmos_manager, [SAMPLE_DESTINATIONS[0]])
    _setup_destination_items(mock_cosmos_manager, {"jewel": JEWEL_ITEMS})

    # The mock simulates Cosmos applying the WHERE clause: filed-and-completed
    # docs are NOT returned by the unprocessed query (no match on the
    # adminProcessingStatus filter). So the side_effect returns an empty list
    # even though a filed doc exists in the container conceptually.
    inbox_container = mock_cosmos_manager.get_container("Inbox")

    def inbox_query_side_effect(**kwargs):
        query = kwargs.get("query", "")
        # Notifications query (Branch A items)
        if "adminProcessingStatus = 'completed'" in query:
            return _make_inbox_async_iterator([])(**kwargs)
        # Unprocessed query (line 174): a filed doc with
        # adminProcessingStatus='completed' would NOT match this WHERE clause.
        # Verify the query string DOES filter by adminProcessingStatus.
        assert "adminProcessingStatus" in query
        assert "'failed'" in query
        assert "'pending'" in query
        # Return empty — simulating server-side filter that excludes filed docs
        return _make_inbox_async_iterator([])(**kwargs)

    inbox_container.query_items = MagicMock(side_effect=inbox_query_side_effect)

    errands_app.state.admin_agent = AsyncMock()
    errands_app.state.background_tasks = set()

    with patch(
        "second_brain.api.errands.asyncio.create_task",
        side_effect=_close_coroutine,
    ) as mock_create_task:
        transport = httpx.ASGITransport(app=errands_app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/errands",
                headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["processingCount"] == 0  # No re-fire on filed-completed docs
    mock_create_task.assert_not_called()
```

**Notes:**
- **Symmetry decision**: Per researcher's Open Question #1 in RESEARCH.md, the dismiss endpoint is folded into Phase 25 for lifecycle symmetry. If the planner disagrees, this test changes accordingly (assert delete_item still called).
- **`_make_inbox_async_iterator` + `_close_coroutine` helpers** at lines 666-674 + 658-664 are already in the file — reuse them.
- The orthogonality test asserts on the SQL string contents (proves the query has the right filters) AND on the API response shape (proves no background task created). Combined verification.

---

### File 11: `backend/tests/test_documents_models.py` (test, unit Pydantic) — CREATE NEW

**Analog:** `test_spine_models.py:85-94` (Pydantic `ValidationError` pattern) + the inline structure here.

**Action:** Create new file. Add two tests proving ErrandItem and TaskItem accept the new optional backlink fields with None defaults and string values.

**ValidationError pattern from `test_spine_models.py:85-94`**:
```python
from pydantic import ValidationError

def test_unknown_event_type_rejected() -> None:
    with pytest.raises(ValidationError):
        IngestEvent.model_validate(
            {
                "segment_id": "backend_api",
                "event_type": "garbage",
                "timestamp": "2026-04-14T12:00:00Z",
                "payload": {},
            }
        )
```

**New file content**:
```python
"""Pydantic model tests for ErrandItem + TaskItem backlink fields (Phase 25).

REQ-BL-01: both models gain optional sourceInboxItemId + sourceCaptureTraceId
with default None. Pre-Phase-25 docs (no backlinks) must deserialize cleanly.
"""

from second_brain.models.documents import ErrandItem, TaskItem


def test_errand_item_optional_backlinks_default_none() -> None:
    """ErrandItem without backlinks parses cleanly and defaults both to None."""
    doc = ErrandItem(destination="jewel", name="milk")
    assert doc.sourceInboxItemId is None
    assert doc.sourceCaptureTraceId is None


def test_errand_item_optional_backlinks_accept_strings() -> None:
    """ErrandItem accepts both backlink fields as non-empty strings."""
    doc = ErrandItem(
        destination="jewel",
        name="milk",
        sourceInboxItemId="inbox-42",
        sourceCaptureTraceId="trace-99",
    )
    assert doc.sourceInboxItemId == "inbox-42"
    assert doc.sourceCaptureTraceId == "trace-99"


def test_errand_item_legacy_doc_compatibility() -> None:
    """Pre-Phase-25 raw dict (no backlink fields) deserializes via model_validate."""
    legacy = {
        "id": "legacy-1",
        "destination": "cvs",
        "name": "toothpaste",
        "needsRouting": False,
        "sourceName": None,
        "sourceUrl": None,
    }
    doc = ErrandItem.model_validate(legacy)
    assert doc.sourceInboxItemId is None
    assert doc.sourceCaptureTraceId is None


def test_task_item_optional_backlinks_default_none() -> None:
    """TaskItem without backlinks parses cleanly and defaults both to None."""
    doc = TaskItem(name="Book eye appointment")
    assert doc.sourceInboxItemId is None
    assert doc.sourceCaptureTraceId is None


def test_task_item_optional_backlinks_accept_strings() -> None:
    """TaskItem accepts both backlink fields as non-empty strings."""
    doc = TaskItem(
        name="Book eye appointment",
        sourceInboxItemId="inbox-7",
        sourceCaptureTraceId="trace-13",
    )
    assert doc.sourceInboxItemId == "inbox-7"
    assert doc.sourceCaptureTraceId == "trace-13"


def test_task_item_legacy_doc_compatibility() -> None:
    """Pre-Phase-25 raw dict (no backlink fields) deserializes via model_validate."""
    legacy = {
        "id": "legacy-task-1",
        "userId": "will",
        "name": "Call dentist",
        "createdAt": "2026-05-01T10:00:00Z",
    }
    doc = TaskItem.model_validate(legacy)
    assert doc.sourceInboxItemId is None
    assert doc.sourceCaptureTraceId is None
```

**Notes:**
- **No `@pytest.mark.asyncio`**: these are sync Pydantic validation tests.
- **Type-checker friendly**: `ErrandItem(destination="jewel", name="milk")` exercises the keyword-only construction Pydantic models support; mirrors how `tools/admin.py:177-184` builds them.
- **Forward compat (Phase 25 + N)**: legacy tests prove the model accepts pre-Phase-25 dict shapes. If a future phase adds another optional field, follow the same `test_xxx_legacy_doc_compatibility` pattern.

---

### File 12: `backend/tests/test_config.py` (test, unit Pydantic Settings) — CREATE NEW

**Analog:** `test_spine_registry.py:50-73` (config validation with `pytest.raises(ValueError, match=...)`) + `Field(ge=...)` constraint from `spine/api.py:48-49`.

**Action:** Create new file. Add test proving `Settings.inbox_filed_retention_days` rejects values < 1 via `ValidationError`.

**Config validation pattern from `test_spine_registry.py:62-73`**:
```python
def test_evaluator_config_rejects_workload_window_smaller_than_stale_window() -> None:
    # ... rationale comment ...
    with pytest.raises(ValueError, match="stale window"):
        EvaluatorConfig(
            segment_id="test",
            liveness_interval_seconds=300,  # stale window = 600s
            host_segment=None,
            workload_window_seconds=300,  # < 600s, misconfigured
        )
```

**New file content**:
```python
"""Settings validation tests (Phase 25)."""

import pytest
from pydantic import ValidationError

from second_brain.config import Settings


def test_inbox_filed_retention_days_default_is_30() -> None:
    """Default retention is 30 days (env var unset)."""
    s = Settings()
    assert s.inbox_filed_retention_days == 30


def test_inbox_filed_retention_days_accepts_positive_int() -> None:
    """Explicit positive integers (e.g., 14) are accepted."""
    s = Settings(inbox_filed_retention_days=14)
    assert s.inbox_filed_retention_days == 14


def test_inbox_filed_retention_days_min_validation_rejects_zero() -> None:
    """ge=1 constraint rejects 0 (would set ttl=0 = immediate purge).

    Landmine #7 in RESEARCH.md: without ge=1, a misconfigured
    INBOX_FILED_RETENTION_DAYS=0 env var would result in doc["ttl"]=0,
    causing immediate deletion at the next Cosmos TTL sweep. Pydantic
    fails fast at Settings construction.
    """
    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        Settings(inbox_filed_retention_days=0)


def test_inbox_filed_retention_days_min_validation_rejects_negative() -> None:
    """ge=1 also rejects negative values."""
    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        Settings(inbox_filed_retention_days=-1)
```

**Notes:**
- **`Settings()` is constructable at test time**: it reads `.env` if present but otherwise uses defaults. The `extra="ignore"` in `model_config` tolerates orphan env vars.
- **`ValidationError` message format**: Pydantic v2 emits "Input should be greater than or equal to 1" for `ge=1`. The `match=` regex `"greater than or equal to 1"` matches both Pydantic v2.0+ format. If the message format changes in future Pydantic versions, adjust the regex.
- **`get_settings()` cached**: Avoid using `from second_brain.config import get_settings` in tests because `@lru_cache` would cache across tests. Construct `Settings()` directly to test fresh validation.
- **Sync test (no `@pytest.mark.asyncio`)**: Pydantic validation is sync.

---

## Shared Patterns

### Cosmos Read → Mutate → Upsert (with trace_headers)

**Source:** `backend/src/second_brain/processing/admin_handoff.py:163-177` (`_mark_inbox_failed`) and lines 372-394 (Branch A).
**Apply to:** All admin_handoff Branch B + dismiss_admin_notification soft-delete sites.

```python
th = trace_headers(capture_trace_id or None)
try:
    doc = await inbox_container.read_item(
        item=inbox_item_id, partition_key="will", **th
    )
    doc["adminProcessingStatus"] = "completed"
    doc["adminAgentResponse"] = response_text
    await inbox_container.upsert_item(body=doc, **th)
except Exception as store_exc:
    logger.warning(
        "Failed to store admin response for %s: %s",
        inbox_item_id,
        store_exc,
        extra=log_extra,
    )
```

**Why this pattern, not the streaming/adapter race-safe re-read pattern**: per RESEARCH.md "How to apply to Phase 25" section, the filing happens AFTER `agent.run()` has fully returned. There's no concurrent in-stream tool firing on the same doc at this point. The simpler precedent in admin_handoff.py:375-381 (clone Branch A's structure) is the right analog.

### ContextVar definition + set/read

**Source:** `backend/src/second_brain/tools/classification.py:34-45` (definition) + `backend/src/second_brain/tools/recipe.py:191` (read) + `backend/tests/test_event_tracing.py:418-439` (test set/reset).
**Apply to:** `tools/admin.py` (new `admin_inbox_item_id_var`) + `processing/admin_handoff.py` (set site) + `tools/admin.py:add_errand_items` and `add_task_items` (read sites) + tests.

```python
# DEFINE (module top)
import contextvars

admin_inbox_item_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "admin_inbox_item_id_var", default=None
)

# SET (admin_handoff.py before agent.run)
admin_inbox_item_id_var.set(inbox_item_id)

# READ (admin.py tool methods)
source_inbox_id = admin_inbox_item_id_var.get()
source_trace_id = capture_trace_id_var.get() or None

# TEST set/reset (always use try/finally)
token = admin_inbox_item_id_var.set("test-value")
try:
    # ... test body ...
finally:
    admin_inbox_item_id_var.reset(token)
```

**Caveats:**
- `capture_trace_id_var` has empty-string default; use `.get() or None` to normalize.
- `admin_inbox_item_id_var` has `None` default; `.get()` returns None directly — no `or` needed.
- Test ContextVar reset is mandatory (try/finally), else cross-test leakage.

### Pydantic optional field with None default

**Source:** `backend/src/second_brain/models/documents.py:118-119` (`ErrandItem.sourceName` / `sourceUrl`).
**Apply to:** New `sourceInboxItemId` / `sourceCaptureTraceId` on `ErrandItem` + `TaskItem`.

```python
sourceName: str | None = None  # Recipe name for source attribution
sourceUrl: str | None = None  # Recipe URL for source attribution
# Phase 25 ADD:
sourceInboxItemId: str | None = None  # Source Inbox doc id (durable for 30d)
sourceCaptureTraceId: str | None = None  # Source capture trace id (durable forever)
```

### Pydantic `Field(ge=...)` constraint

**Source:** `backend/src/second_brain/spine/api.py:48-49`.
**Apply to:** `Settings.inbox_filed_retention_days` in `config.py`.

```python
# Reference:
sample_size: int = Field(5, ge=1, le=20)
time_range_seconds: int = Field(86400, ge=60, le=604800)  # 1min - 7d

# Phase 25 add to config.py:
inbox_filed_retention_days: int = Field(
    default=30,
    ge=1,
    description="Days to retain filed admin inbox docs; minimum 1.",
)
```

### Mock Cosmos `query_items` (async iterator pattern)

**Source:** `backend/tests/test_errands_api.py:74-94`.
**Apply to:** New test in `test_inbox_api.py` (list filter test) and `test_errands_api.py` (unprocessed orthogonality test).

```python
def _make_async_iterator(items: list[dict]):
    """Create an async iterator from a list of dicts (mimics Cosmos query_items)."""
    async def _iter(*args, **kwargs):
        for item in items:
            yield item
    return _iter

# Usage:
container = mock_cosmos_manager.get_container("Inbox")
container.query_items = MagicMock(return_value=_make_async_iterator(items)())

# OR with side_effect for query-string-aware mock:
def query_side_effect(**kwargs):
    query = kwargs.get("query", "")
    if "completed" in query:
        return _make_async_iterator(notifications)(**kwargs)
    return _make_async_iterator([])(**kwargs)
container.query_items = MagicMock(side_effect=query_side_effect)
```

### Mock Cosmos `upsert_item` body assertion

**Source:** `backend/tests/test_admin_handoff.py:191-204` (existing upsert body assertion idiom).
**Apply to:** All new Phase 25 tests asserting on filed body shape.

```python
upsert_calls = container.upsert_item.call_args_list
filing_body = upsert_calls[-1].kwargs.get("body") or upsert_calls[-1][1].get("body")
assert filing_body["status"] == "filed"
assert filing_body["adminProcessingStatus"] == "completed"
assert filing_body["ttl"] > 0
```

**Why the `kwargs.get("body") or [1].get("body")` double-pattern**: supports both `upsert_item(body=doc, **th)` (kwargs) and `upsert_item(doc)` (positional) call shapes. Defensive across the codebase's mixed call styles.

### Auto-format hook avoidance (Landmine #5)

**Source:** MEMORY.md lesson recurring across Phases 17.1, 24-09, 24-10, 24-14, 24-15, 24-21.
**Apply to:** Files where imports + first usage land in the same plan (admin_handoff.py, admin.py, errands.py).

**Rule:** when adding a new import line that won't be USED until a later Edit, ruff strips it on save. Workaround:
- **Option A:** Use a single `Write` that replaces the whole file (import + usage land atomically).
- **Option B:** Make the import addition the LAST edit, after the usage is already in place.
- For tests where imports come from existing modules, normal `Edit` chains are safe.

**Specific Phase 25 sites at risk:**
- `processing/admin_handoff.py` — new `from second_brain.config import get_settings` and `from second_brain.tools.admin import admin_inbox_item_id_var` imports. Use single `Write`.
- `tools/admin.py` — new `import contextvars` + `from second_brain.tools.classification import capture_trace_id_var` + module-level ContextVar definition + usage in two tool methods. Use single `Write`.
- `api/errands.py` — new `from second_brain.config import get_settings` import + first usage in `dismiss_admin_notification`. Use single `Edit` that adds both lines together, or `Write`.
- `config.py` — new `from pydantic import Field` import + first usage in the new field. Use single `Edit` adding both lines together (small enough file).
- `models/documents.py` — no new imports needed (`Field` already imported); pure field additions. Standard `Edit` is safe.

---

## No Analog Found

None. Every file in this phase has a strong, line-precise analog in the codebase. All Phase 25 changes are either self-clone (modify a file that already has the target pattern in an adjacent block) or cross-file pattern copy (e.g., ContextVar from classification.py → admin.py).

---

## Metadata

**Analog search scope:** `backend/src/second_brain/{processing,api,tools,models}/`, `backend/src/second_brain/config.py`, `backend/src/second_brain/spine/{api,cosmos_request_id}.py`, `backend/src/second_brain/streaming/adapter.py`, `backend/src/second_brain/cosmos/inbox_conversation_history.py`, `backend/tests/`
**Files scanned:** 11 source + 6 test files (direct read), plus 3 grep verifications (`Field(ge=`, ContextVar usage in tests, model_dump call sites).
**Pattern extraction date:** 2026-05-17

## PATTERN MAPPING COMPLETE
