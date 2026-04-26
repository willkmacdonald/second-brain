# Phase 20: Feedback Collection - Pattern Map

**Mapped:** 2026-04-22
**Files analyzed:** 8 (new/modified)
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/src/second_brain/api/feedback.py` | controller | request-response | `backend/src/second_brain/api/inbox.py` | exact |
| `backend/src/second_brain/api/inbox.py` | controller | request-response | self (inline modification) | exact |
| `backend/src/second_brain/api/errands.py` | controller | request-response | self (inline modification) | exact |
| `backend/src/second_brain/tools/investigation.py` | service | CRUD | self (add new @tool methods) | exact |
| `backend/src/second_brain/main.py` | config | request-response | self (router registration + tool list) | exact |
| `mobile/app/(tabs)/inbox.tsx` | component | event-driven | self (detail modal pattern) | exact |
| `docs/foundry/investigation-agent-instructions.md` | config | n/a | self (add tool sections) | exact |
| `backend/tests/test_feedback.py` | test | request-response | `backend/tests/test_inbox_api.py` | exact |

## Pattern Assignments

### `backend/src/second_brain/api/feedback.py` (controller, request-response) -- NEW

**Analog:** `backend/src/second_brain/api/inbox.py`

**Imports pattern** (lines 1-17):
```python
"""Feedback API endpoint for explicit thumbs up/down signals."""

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from second_brain.models.documents import FeedbackDocument

logger = logging.getLogger(__name__)

router = APIRouter()
```

**Request model pattern** (lines 24-28 of inbox.py):
```python
class RecategorizeRequest(BaseModel):
    """Request body for recategorizing an inbox item to a different bucket."""

    new_bucket: str  # "People", "Projects", "Ideas", or "Admin"  # noqa: N815
```

**Cosmos manager access pattern** (lines 62-68 of inbox.py):
```python
cosmos_manager = getattr(request.app.state, "cosmos_manager", None)
if cosmos_manager is None:
    raise HTTPException(
        status_code=503,
        detail="Cosmos DB not configured. Inbox is unavailable.",
    )
```

**Cosmos write pattern** (lines 294-296 of inbox.py -- create_item call):
```python
target_container = cosmos_manager.get_container(body.new_bucket)
await target_container.create_item(
    body=bucket_doc.model_dump(mode="json")
)
```

**Error handling pattern** -- follows standard try/except with HTTPException for validation errors. No custom error handler needed.

---

### `backend/src/second_brain/api/inbox.py` (controller, request-response) -- MODIFIED

**Analog:** Self -- the recategorize handler at lines 197-334

**Import to add** (line 16 area):
```python
from second_brain.models.documents import CONTAINER_MODELS, VALID_BUCKETS, ClassificationMeta, FeedbackDocument
```
Note: Must add `FeedbackDocument` import AND usage in the same edit to avoid ruff auto-format stripping the unused import (see MEMORY.md lesson).

**Signal emit insertion point -- cross-bucket branch** (after line 303, after Step 2 inbox upsert, before Step 3 old bucket delete):
```python
# Step 2: Update inbox document
item["classificationMeta"] = classification_meta.model_dump(mode="json")
item["filedRecordId"] = new_bucket_doc_id
item["status"] = "classified"
item["updatedAt"] = datetime.now(UTC).isoformat()
await inbox_container.upsert_item(body=item)

# --- Feedback signal (fire-and-forget per D-02) ---
try:
    feedback_doc = FeedbackDocument(
        signalType="recategorize",
        captureText=item.get("rawText", ""),
        originalBucket=old_bucket or "",
        correctedBucket=body.new_bucket,
        captureTraceId=item.get("captureTraceId"),
    )
    feedback_container = cosmos_manager.get_container("Feedback")
    await feedback_container.create_item(
        body=feedback_doc.model_dump(mode="json")
    )
except Exception:
    logger.warning(
        "Failed to write feedback signal for recategorize on item %s",
        item_id,
        exc_info=True,
    )

# Step 3: Delete old bucket document (non-fatal)
```

**Signal emit insertion point -- same-bucket HITL branch** (after line 259 `await inbox_container.upsert_item(body=item)`, before `span.set_attribute`):
```python
if item.get("status") == "pending":
    item["status"] = "classified"
    # ... existing code ...
    await inbox_container.upsert_item(body=item)

    # --- HITL confirmation signal (fire-and-forget) ---
    try:
        feedback_doc = FeedbackDocument(
            signalType="hitl_bucket",
            captureText=item.get("rawText", ""),
            originalBucket=old_bucket or "",
            correctedBucket=None,
            captureTraceId=item.get("captureTraceId"),
        )
        feedback_container = cosmos_manager.get_container("Feedback")
        await feedback_container.create_item(
            body=feedback_doc.model_dump(mode="json")
        )
    except Exception:
        logger.warning(
            "Failed to write feedback signal for hitl_bucket on item %s",
            item_id,
            exc_info=True,
        )
```

**Fire-and-forget pattern** (lines 306-317 of inbox.py -- non-fatal delete is the exact same shape):
```python
# Step 3: Delete old bucket document (non-fatal)
if old_filed_id and old_bucket:
    try:
        old_container = cosmos_manager.get_container(old_bucket)
        await old_container.delete_item(
            item=old_filed_id, partition_key="will"
        )
    except Exception:
        logger.warning(
            "Could not delete old bucket doc %s/%s during recategorize",
            old_bucket,
            old_filed_id,
        )
```

---

### `backend/src/second_brain/api/errands.py` (controller, request-response) -- MODIFIED

**Analog:** Self -- the `route_errand_item` handler at lines 336-421

**Import to add** (line 19 area, alongside existing documents import):
```python
from second_brain.models.documents import AffinityRuleDocument, FeedbackDocument
```

**Signal emit insertion point** (after line 397 `await container.delete_item(...)`, before the saveRule block):
```python
# Delete from unrouted
await container.delete_item(item=item_id, partition_key="unrouted")

# --- Feedback signal (fire-and-forget per D-02) ---
try:
    feedback_doc = FeedbackDocument(
        signalType="errand_reroute",
        captureText=item_name,
        originalBucket="unrouted",
        correctedBucket=body.destinationSlug,
        captureTraceId=None,  # Errands don't carry captureTraceId
    )
    feedback_container = cosmos_manager.get_container("Feedback")
    await feedback_container.create_item(
        body=feedback_doc.model_dump(mode="json")
    )
except Exception:
    logger.warning(
        "Failed to write feedback signal for errand re-route %s",
        item_id,
        exc_info=True,
    )

# Optionally save an affinity rule
```

---

### `backend/src/second_brain/tools/investigation.py` (service, CRUD) -- MODIFIED

**Analog:** Self -- existing @tool methods (lines 81-335)

**Import additions** (line 1-27 area):
```python
# Add to existing imports at top of file:
from collections import Counter
from datetime import UTC, datetime, timedelta

# CosmosManager will be needed -- add to __init__ as optional param
```

**Constructor modification** (lines 69-75):
```python
class InvestigationTools:
    def __init__(
        self,
        logs_client: LogsQueryClient,
        workspace_id: str,
        cosmos_manager: "CosmosManager | None" = None,  # NEW
    ) -> None:
        self._logs_client = logs_client
        self._workspace_id = workspace_id
        self._cosmos_manager = cosmos_manager  # NEW
```

**New @tool pattern** -- copy the exact structure from `recent_errors` (lines 148-213):
```python
@tool(approval_mode="never_require")
async def recent_errors(
    self,
    time_range: Annotated[
        str,
        Field(
            description=(
                "Time range to query: '1h', '6h', '24h', '3d', or '7d'. "
                "Defaults to '24h'."
            )
        ),
    ] = "24h",
    component: Annotated[
        str | None,
        Field(
            description=(
                "Filter by component name (e.g., 'classifier', "
                "'admin_agent'). Pass null for all components."
            )
        ),
    ] = None,
) -> str:
    """Query recent errors and failures from App Insights. ..."""
    log_extra: dict = {"component": "investigation_agent"}
    logger.info(
        "recent_errors called: time_range=%s component=%s",
        time_range,
        component,
        extra=log_extra,
    )

    try:
        # ... business logic ...
        return json.dumps({...}, default=str)

    except Exception as exc:
        logger.error("recent_errors error: %s", exc, exc_info=True, extra=log_extra)
        return json.dumps({"error": f"Failed to query recent errors: {exc}"})
```

Key pattern elements for new tools:
1. `@tool(approval_mode="never_require")` decorator
2. `Annotated[type, Field(description=...)]` for all parameters
3. Return type is always `str` (JSON string)
4. `log_extra = {"component": "investigation_agent"}` for structured logging
5. `logger.info(...)` at entry with all parameter values
6. Try/except wrapping the entire body, returning JSON error on failure
7. Never raise -- always return JSON error string

**Cosmos query pattern for feedback signals** (uses the partition_key="will" + parameterized query pattern from inbox.py lines 71-87):
```python
container = cosmos_manager.get_container("Feedback")
query = "SELECT * FROM c WHERE c.userId = @userId AND c.createdAt >= @cutoff"
parameters = [
    {"name": "@userId", "value": "will"},
    {"name": "@cutoff", "value": cutoff},
]
signals = []
async for item in container.query_items(
    query=query,
    parameters=parameters,
    partition_key="will",
):
    signals.append(item)
    if len(signals) >= limit:
        break
```

**Python-side aggregation pattern** (from RESEARCH.md, established in spine/storage.py):
```python
from collections import Counter
misclassifications = [s for s in signals if s.get("signalType") == "recategorize"]
bucket_counts = Counter(
    f"{s.get('originalBucket', '?')} -> {s.get('correctedBucket', '?')}"
    for s in misclassifications
)
```

---

### `backend/src/second_brain/main.py` (config) -- MODIFIED

**Analog:** Self -- router imports at lines 49-55 and registrations at lines 902-908

**Router import pattern** (line 55 area):
```python
from second_brain.api.feedback import router as feedback_router  # noqa: E402
```

**Router registration pattern** (line 908 area):
```python
app.include_router(feedback_router)
```

**Investigation tool registration pattern** (lines 708-713):
```python
app.state.investigation_tools = [
    investigation_tools.trace_lifecycle,
    investigation_tools.recent_errors,
    investigation_tools.system_health,
    investigation_tools.usage_patterns,
]
```
Must add new tools to this list:
```python
app.state.investigation_tools = [
    investigation_tools.trace_lifecycle,
    investigation_tools.recent_errors,
    investigation_tools.system_health,
    investigation_tools.usage_patterns,
    investigation_tools.query_feedback_signals,       # NEW
    investigation_tools.promote_to_golden_dataset,    # NEW
]
```

**InvestigationTools constructor call** (lines 691-694 -- add cosmos_manager):
```python
investigation_tools = InvestigationTools(
    logs_client=app.state.logs_client,
    workspace_id=settings.log_analytics_workspace_id,
    cosmos_manager=app.state.cosmos_manager,  # NEW
)
```

---

### `mobile/app/(tabs)/inbox.tsx` (component, event-driven) -- MODIFIED

**Analog:** Self -- detail modal and bucket button section

**State declaration pattern** (lines 29-36):
```typescript
const [selectedItem, setSelectedItem] = useState<InboxItemData | null>(null);
const [isRecategorizing, setIsRecategorizing] = useState(false);
const [recategorizeToast, setRecategorizeToast] = useState<string | null>(null);
// NEW:
const [feedbackState, setFeedbackState] = useState<"none" | "thumbs_up" | "thumbs_down">("none");
```

**API call pattern -- fire-and-forget** (lines 161-220, handleRecategorize uses fetch + reportError):
```typescript
try {
  const res = await fetch(
    `${API_BASE_URL}/api/inbox/${itemId}/recategorize`,
    {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ new_bucket: newBucket }),
    },
  );
  // ...
} catch (err) {
  void reportError({
    eventType: "crud_failure",
    message: `Recategorize failed: ${String(err)}`,
    correlationKind: "crud",
    metadata: { operation: "recategorize", inbox_id: itemId },
  });
}
```

**Toast pattern** (lines 232-237 + 394-398):
```typescript
// Auto-dismiss recategorize toast after 2 seconds
useEffect(() => {
  if (!recategorizeToast) return;
  const timer = setTimeout(() => setRecategorizeToast(null), 2000);
  return () => clearTimeout(timer);
}, [recategorizeToast]);

// In JSX:
{recategorizeToast && (
  <View style={styles.toastBar}>
    <Text style={styles.toastText}>{recategorizeToast}</Text>
  </View>
)}
```

**Detail modal section layout** (lines 326-332 -- Timestamp section is the insertion point):
```tsx
<Text style={styles.detailLabel}>Timestamp</Text>
<Text style={styles.detailValue}>
  {selectedItem?.createdAt
    ? new Date(selectedItem.createdAt).toLocaleString()
    : "N/A"}
</Text>

{/* NEW: Feedback section goes here, between Timestamp and bucket section */}
```

**Button row pattern** (lines 343-381 -- bucket buttons to copy structure from):
```tsx
<View style={styles.bucketSection}>
  <Text style={styles.detailLabel}>
    {isClassifiedItem ? "Move to bucket" : "File to bucket"}
  </Text>
  <View style={styles.bucketRow}>
    {BUCKETS.map((bucket) => {
      const isCurrent = ...;
      return (
        <Pressable
          key={bucket}
          onPress={() => handleRecategorize(selectedItem!.id, bucket)}
          style={({ pressed }) => [
            styles.bucketButton,
            isCurrent && styles.bucketButtonCurrent,
            pressed && !isCurrent && styles.bucketButtonPressed,
          ]}
        >
          <Text style={[styles.bucketButtonText, ...]}>
            {bucket}
          </Text>
        </Pressable>
      );
    })}
  </View>
</View>
```

**StyleSheet pattern** (lines 403-534 -- existing styles to extend):
```typescript
// Existing patterns for button styling:
bucketButton: {
  flex: 1,
  backgroundColor: "#2a2a4e",
  paddingVertical: 10,
  borderRadius: 8,
  alignItems: "center",
},
bucketButtonCurrent: {
  backgroundColor: "#4a90d9",
},
```

**Reset feedbackState on modal open** -- pattern from line 155:
```typescript
const handleItemPress = useCallback(
  (item: InboxItemData) => {
    setSelectedItem(item);
    setFeedbackState("none");  // NEW: reset on modal open
  },
  [],
);
```

---

### `docs/foundry/investigation-agent-instructions.md` (config) -- MODIFIED

**Analog:** Self -- existing tool documentation sections

**Tool section pattern** (from lines 14-46 of the file -- tools are described under "Query Boundaries & Scope" and have individual subsections):
```markdown
## Query Boundaries & Scope

You can answer questions about:
- Capture history and individual trace lifecycles
- Errors and exceptions by component and time window
- System health: capture volume, error rates, P95/P99 latency
- Usage patterns: capture counts by day/hour, bucket distribution
- Quality feedback signals: misclassifications, HITL resolutions, user feedback  (NEW)
- Golden dataset promotion: reviewing and promoting signals to test cases  (NEW)
```

---

### `backend/tests/test_feedback.py` (test, request-response) -- NEW

**Analog:** `backend/tests/test_inbox_api.py`

**Test file structure** (lines 1-86):
```python
"""Tests for feedback signal capture and investigation tools.

Validates FEED-01 through FEED-04: implicit signal emission, explicit feedback
endpoint, golden dataset promotion, and signal querying.
"""

from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import FastAPI

from second_brain.api.inbox import router as inbox_router
from second_brain.auth import APIKeyMiddleware

TEST_API_KEY = "test-api-key-12345"
```

**Fixture pattern** (lines 77-85 of test_inbox_api.py):
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

**Test function pattern** (lines 88-128 of test_inbox_api.py):
```python
@pytest.mark.asyncio
async def test_recategorize_success(
    inbox_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """PATCH moves item from Ideas to Projects: create, update, delete."""
    inbox_container = mock_cosmos_manager.get_container("Inbox")
    inbox_container.read_item.return_value = {**SAMPLE_CLASSIFIED_ITEM}

    transport = httpx.ASGITransport(app=inbox_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.patch(
            "/api/inbox/inbox-100/recategorize",
            json={"new_bucket": "Projects"},
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 200
    # Verify Cosmos writes via mock assertions
    projects_container = mock_cosmos_manager.get_container("Projects")
    projects_container.create_item.assert_called_once()
```

**Sample data pattern** (lines 19-74 of test_inbox_api.py):
```python
SAMPLE_CLASSIFIED_ITEM = {
    "id": "inbox-100",
    "userId": "will",
    "rawText": "Build the new dashboard feature",
    "title": "Dashboard feature",
    "status": "classified",
    "createdAt": "2026-02-23T10:00:00Z",
    "classificationMeta": {
        "bucket": "Ideas",
        "confidence": 0.72,
        "allScores": {"People": 0.05, "Projects": 0.20, "Ideas": 0.72, "Admin": 0.03},
        "classifiedBy": "Classifier",
        "agentChain": ["Orchestrator", "Classifier"],
        "classifiedAt": "2026-02-23T10:00:00Z",
    },
}
```

**Asserting fire-and-forget Cosmos writes** (lines 113-114 of test_inbox_api.py):
```python
# Step 1: New bucket container got create_item
projects_container = mock_cosmos_manager.get_container("Projects")
projects_container.create_item.assert_called_once()
created_doc = projects_container.create_item.call_args[1]["body"]
assert created_doc["rawText"] == "Build the new dashboard feature"
```

**Asserting non-fatal failure** (lines 232-261 of test_inbox_api.py):
```python
async def test_recategorize_old_delete_fails_nonfatal(
    inbox_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """PATCH succeeds even when old bucket doc delete fails."""
    inbox_container = mock_cosmos_manager.get_container("Inbox")
    inbox_container.read_item.return_value = {**SAMPLE_CLASSIFIED_ITEM}

    # Make old bucket delete fail
    ideas_container = mock_cosmos_manager.get_container("Ideas")
    ideas_container.delete_item.side_effect = RuntimeError("Cosmos timeout")

    # ... test still passes (200 status) ...
    assert response.status_code == 200
```

**Mock async iterator for query_items** (from conftest.py line 90):
```python
container.query_items = MagicMock()  # Returns an async iterator
```
For feedback signal tests, configure it to return async iterable:
```python
async def mock_query_results():
    for item in sample_signals:
        yield item

feedback_container = mock_cosmos_manager.get_container("Feedback")
feedback_container.query_items.return_value = mock_query_results()
```

---

## Shared Patterns

### Fire-and-Forget Cosmos Write (D-02)
**Source:** `backend/src/second_brain/api/inbox.py` lines 306-317 (non-fatal delete pattern)
**Apply to:** All signal emit points in `inbox.py`, `errands.py`, and `feedback.py`
```python
try:
    feedback_doc = FeedbackDocument(
        signalType=signal_type,
        captureText=capture_text,
        originalBucket=original_bucket,
        correctedBucket=corrected_bucket,
        captureTraceId=capture_trace_id,
    )
    feedback_container = cosmos_manager.get_container("Feedback")
    await feedback_container.create_item(
        body=feedback_doc.model_dump(mode="json")
    )
except Exception:
    logger.warning(
        "Failed to write feedback signal for %s on item %s",
        signal_type,
        item_id,
        exc_info=True,
    )
```

### Cosmos Manager Access
**Source:** `backend/src/second_brain/api/inbox.py` lines 62-68
**Apply to:** `feedback.py` new endpoint, any code that needs container access
```python
cosmos_manager = getattr(request.app.state, "cosmos_manager", None)
if cosmos_manager is None:
    raise HTTPException(
        status_code=503,
        detail="Cosmos DB not configured.",
    )
```

### Investigation Agent @tool Signature
**Source:** `backend/src/second_brain/tools/investigation.py` lines 81-142
**Apply to:** `query_feedback_signals` and `promote_to_golden_dataset`
```python
@tool(approval_mode="never_require")
async def tool_name(
    self,
    param: Annotated[
        str,
        Field(description="Description of the parameter."),
    ] = "default",
) -> str:
    """Docstring used by agent for tool selection."""
    log_extra: dict = {"component": "investigation_agent"}
    logger.info("tool_name called: param=%s", param, extra=log_extra)
    try:
        # ... business logic ...
        return json.dumps({...}, default=str)
    except Exception as exc:
        logger.error("tool_name error: %s", exc, exc_info=True, extra=log_extra)
        return json.dumps({"error": f"Failed: {exc}"})
```

### API Key Authentication
**Source:** `backend/src/second_brain/main.py` line 899
**Apply to:** New `feedback.py` endpoint (automatic -- middleware applied to all routes)
```python
# No per-route auth needed -- APIKeyMiddleware covers all routes
app.add_middleware(APIKeyMiddleware)
```

### Document Model Usage
**Source:** `backend/src/second_brain/models/documents.py` lines 160-175
**Apply to:** All signal emit points and the feedback endpoint
```python
from second_brain.models.documents import FeedbackDocument

feedback_doc = FeedbackDocument(
    signalType="recategorize",           # enum string
    captureText=item.get("rawText", ""),  # snapshot
    originalBucket=old_bucket or "",
    correctedBucket=body.new_bucket,      # None for thumbs/hitl
    captureTraceId=item.get("captureTraceId"),  # defensive .get()
)
# id, userId, createdAt auto-populated by Field defaults
```

### Test Pattern (httpx + mock Cosmos)
**Source:** `backend/tests/test_inbox_api.py` lines 77-128
**Apply to:** All new test functions in `test_feedback.py`
```python
@pytest.fixture
def feedback_app(mock_cosmos_manager: MagicMock) -> FastAPI:
    app = FastAPI()
    app.include_router(inbox_router)
    app.include_router(feedback_router)
    app.state.api_key = TEST_API_KEY
    app.state.cosmos_manager = mock_cosmos_manager
    app.add_middleware(APIKeyMiddleware)
    return app

@pytest.mark.asyncio
async def test_something(feedback_app: FastAPI, mock_cosmos_manager: MagicMock) -> None:
    transport = httpx.ASGITransport(app=feedback_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(...)
    assert response.status_code == 201
    feedback_container = mock_cosmos_manager.get_container("Feedback")
    feedback_container.create_item.assert_called_once()
```

## No Analog Found

No files lack analogs. All 8 files have exact-match patterns from existing codebase files.

## Metadata

**Analog search scope:** `backend/src/second_brain/api/`, `backend/src/second_brain/tools/`, `backend/src/second_brain/models/`, `backend/src/second_brain/db/`, `backend/src/second_brain/main.py`, `backend/tests/`, `mobile/app/(tabs)/`, `docs/foundry/`
**Files scanned:** 12 analog files read
**Pattern extraction date:** 2026-04-22
