# Phase 21: Eval Framework - Pattern Map

**Mapped:** 2026-04-23
**Files analyzed:** 8 new/modified files
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/src/second_brain/eval/__init__.py` | config | -- | (empty init) | -- |
| `backend/src/second_brain/eval/runner.py` | service | batch | `backend/src/second_brain/processing/admin_handoff.py` | exact |
| `backend/src/second_brain/eval/metrics.py` | utility | transform | (no analog -- pure math) | no-analog |
| `backend/src/second_brain/eval/dry_run_tools.py` | service | request-response | `backend/src/second_brain/tools/classification.py` + `backend/src/second_brain/tools/admin.py` | exact |
| `backend/src/second_brain/api/eval.py` | controller | request-response | `backend/src/second_brain/api/feedback.py` + `backend/src/second_brain/api/errands.py` (background task pattern) | exact |
| `backend/src/second_brain/tools/investigation.py` | service | request-response | (self -- add new @tools to existing class) | exact |
| `backend/scripts/seed_golden_dataset.py` | utility | batch | `backend/scripts/seed_destinations.py` + `backend/scripts/create_eval_containers.py` | role-match |
| `backend/tests/test_eval.py` | test | -- | `backend/tests/test_feedback.py` | exact |
| `backend/src/second_brain/main.py` | config | -- | (self -- add eval router + wiring) | exact |

## Pattern Assignments

### `backend/src/second_brain/eval/runner.py` (service, batch)

**Analog:** `backend/src/second_brain/processing/admin_handoff.py`

**Imports pattern** (lines 1-25):
```python
"""Background processing for Admin-classified captures.
...
"""

import asyncio
import logging
import time

from agent_framework import ChatOptions, Message
from agent_framework.azure import AzureAIAgentClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from opentelemetry import trace

from second_brain.db.cosmos import CosmosManager
from second_brain.spine.agent_emitter import emit_agent_workload
from second_brain.spine.cosmos_request_id import trace_headers
from second_brain.spine.storage import SpineRepository
from second_brain.tools.admin import build_routing_context

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("second_brain.processing")
```

**Non-streaming agent call pattern** (lines 234-244):
```python
messages = [Message(role="user", text=enriched_text)]
options = ChatOptions(tools=admin_tools)

# Snapshot tool invocation counts before calling the agent
pre_count = _count_tool_invocations(admin_tools)
pre_output_count = _count_output_tool_invocations(admin_tools)

async with asyncio.timeout(60):
    response = await admin_client.get_response(
        messages=messages, options=options
    )
```

**Top-level error handling pattern** (lines 383-414):
```python
except Exception as exc:
    _spine_outcome = "failure"
    _spine_error_class = type(exc).__name__
    span.record_exception(exc)
    span.set_attribute("admin.outcome", "failed")
    logger.error(
        "Admin Agent failed for inbox item %s: %s",
        inbox_item_id,
        exc,
        exc_info=True,
        extra=log_extra,
    )

    # Update inbox item status to failed (only if container was resolved)
    if inbox_container is not None:
        await _mark_inbox_failed(
            inbox_container, inbox_item_id, span, capture_trace_id
        )
```

**Key adaptation for eval runner:**
- The runner iterates golden dataset entries sequentially (D-03), calling the agent once per entry
- Uses dry-run tool instances (from `dry_run_tools.py`) instead of production tools
- Captures predictions from the dry-run tool's state after each `get_response()` call
- Writes `EvalResultsDocument` to Cosmos at end, not per-entry
- Must update in-memory `_eval_runs` dict status throughout (progress, completed, failed)

---

### `backend/src/second_brain/eval/dry_run_tools.py` (service, request-response)

**Analog 1 (classifier):** `backend/src/second_brain/tools/classification.py`

**file_capture tool signature** (lines 75-109) -- dry-run MUST match exactly:
```python
@tool(approval_mode="never_require")
async def file_capture(
    self,
    text: Annotated[str, Field(description="The original captured text to file")],
    bucket: Annotated[
        str,
        Field(
            description="Classification bucket: People, Projects, Ideas, or Admin"
        ),
    ],
    confidence: Annotated[
        float,
        Field(description="Confidence score 0.0-1.0 for the chosen bucket"),
    ],
    status: Annotated[
        str,
        Field(
            description=(
                "Status: 'classified' (confidence >= 0.6), "
                "'pending' (confidence < 0.6), or 'misunderstood'"
            )
        ),
    ],
    title: Annotated[
        str | None,
        Field(description="Brief title (3-6 words) extracted from the text"),
    ] = None,
) -> dict:
```

**Analog 2 (admin):** `backend/src/second_brain/tools/admin.py`

**add_errand_items tool signature** (lines 121-140) -- dry-run MUST match exactly:
```python
@tool(approval_mode="never_require")
async def add_errand_items(
    self,
    items: Annotated[
        list[dict],
        Field(
            description=(
                "List of errand items to add. Each dict must have "
                "'name' (str, lowercase, natural language "
                "like '2 lbs ground beef') and 'destination' "
                "(str, the destination slug from routing context). "
                "Set destination to 'unrouted' if no affinity "
                "rule matches the item. Optionally include "
                "'sourceName' (str, recipe title) and "
                "'sourceUrl' (str, recipe page URL) "
                "for items extracted from recipes."
            )
        ),
    ],
) -> str:
```

**add_task_items tool signature** (lines 191-206):
```python
@tool(approval_mode="never_require")
async def add_task_items(
    self,
    tasks: Annotated[
        list[dict],
        Field(
            description=(
                "List of task items to add. Each dict must have "
                "'name' (str, natural language description of the task, "
                "e.g. 'book eye appointments', 'fill out Peloton expenses'). "
                "Use this for actionable to-dos that are NOT shopping/errands."
            )
        ),
    ],
) -> str:
```

**get_routing_context tool signature** (lines 235-243):
```python
@tool(approval_mode="never_require")
async def get_routing_context(self) -> str:
    """Load all destinations and affinity rules for routing decisions.

    Call this at the start of processing ANY Admin capture. Returns a
    formatted list of available destinations and routing rules so the
    agent can make informed routing decisions.
    """
```

**Class structure pattern** (admin.py lines 80-93):
```python
class AdminTools:
    """Admin agent tools bound to a CosmosManager instance.

    Usage:
        tools = AdminTools(cosmos_manager=cosmos_mgr)
        agent_tools = [
            tools.add_errand_items, tools.add_task_items,
            tools.get_routing_context, tools.manage_destination,
            tools.manage_affinity_rule, tools.query_rules,
        ]
    """

    def __init__(self, cosmos_manager: CosmosManager) -> None:
        """Store the CosmosManager reference."""
        self._manager = cosmos_manager
```

**Key adaptation for dry-run tools:**
- `EvalClassifierTools`: keeps all `file_capture` params identical, body just captures `self.last_bucket`, `self.last_confidence`, `self.last_status` instead of writing Cosmos
- `DryRunAdminTools`: keeps all tool param signatures identical, body captures `self.captured_destinations` and `self.captured_items` instead of writing Cosmos. `get_routing_context` returns a fixed routing context string (test fixture) instead of querying Cosmos

---

### `backend/src/second_brain/api/eval.py` (controller, request-response)

**Analog 1 (simple endpoint):** `backend/src/second_brain/api/feedback.py`

**Full file pattern** (lines 1-58):
```python
"""Feedback API endpoint for explicit thumbs up/down signals."""

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from second_brain.models.documents import FeedbackDocument

logger = logging.getLogger(__name__)

router = APIRouter()


class FeedbackRequest(BaseModel):
    """Request body for explicit feedback (thumbs up/down)."""

    inboxItemId: str  # noqa: N815
    signalType: str  # "thumbs_up" or "thumbs_down"  # noqa: N815
    captureText: str  # noqa: N815
    originalBucket: str  # noqa: N815
    captureTraceId: str | None = None  # noqa: N815


@router.post("/api/feedback", status_code=201)
async def submit_feedback(request: Request, body: FeedbackRequest) -> dict:
    """Record explicit user feedback on a classification."""
    cosmos_manager = getattr(request.app.state, "cosmos_manager", None)
    if cosmos_manager is None:
        raise HTTPException(status_code=503, detail="Cosmos DB not configured.")
    ...
```

**Analog 2 (background task pattern):** `backend/src/second_brain/api/errands.py`

**Background task fire-and-forget pattern** (lines 217-248):
```python
task = asyncio.create_task(
    process_admin_capture(
        admin_client=admin_client,
        admin_tools=admin_tools,
        cosmos_manager=cosmos_manager,
        inbox_item_id=new_items[0]["id"],
        raw_text=new_items[0].get("rawText", ""),
        capture_trace_id=new_items[0].get("captureTraceId", ""),
        spine_repo=spine_repo,
    )
)
bg_tasks.add(task)
task.add_done_callback(bg_tasks.discard)
```

**Key adaptation for eval endpoint:**
- POST `/api/eval/run` accepts `eval_type` in body, creates background task via `asyncio.create_task`
- Returns immediately with `{"runId": ..., "status": "running"}`
- GET `/api/eval/status/{run_id}` polls the in-memory runs dict
- Uses `request.app.state.background_tasks` set for GC prevention (same pattern as errands)
- Single in-flight guard: reject if an eval of the same type is already running

---

### `backend/src/second_brain/tools/investigation.py` (MODIFIED -- add eval @tools)

**Analog:** Self (existing file, add new tools following established pattern)

**Existing @tool pattern** (lines 100-161, `trace_lifecycle` tool):
```python
@tool(approval_mode="never_require")
async def trace_lifecycle(
    self,
    trace_id: Annotated[
        str | None,
        Field(
            description=(
                "Capture trace ID (UUID) to look up. "
                "Pass null/None to trace the most recent capture."
            )
        ),
    ] = None,
) -> str:
    """Trace a specific capture through its full lifecycle.
    ...
    """
    log_extra: dict = {"component": "investigation_agent"}
    logger.info(
        "trace_lifecycle called: trace_id=%s",
        trace_id,
        extra=log_extra,
    )

    try:
        # ... business logic ...
        return json.dumps(result, default=str)

    except Exception as exc:
        logger.error(
            "trace_lifecycle error: %s", exc, exc_info=True, extra=log_extra
        )
        return json.dumps({"error": f"Failed to query trace lifecycle: {exc}"})
```

**Cosmos query pattern from existing tool** (lines 412-439, `query_feedback_signals`):
```python
container = self._cosmos_manager.get_container("Feedback")
items_iter = container.query_items(
    query=query,
    parameters=parameters,
    partition_key="will",
)

# Collect up to limit results
signals: list[dict] = []
async for item in items_iter:
    signals.append(item)
    if len(signals) >= limit:
        break
```

**Key adaptation for new eval tools:**
- Add `run_classifier_eval(self) -> str` and `run_admin_eval(self) -> str` that internally call the eval API endpoint or directly invoke the eval runner
- Add `get_eval_results(self, eval_type, limit) -> str` that queries EvalResults container and formats as JSON
- All follow the same try/except -> json.dumps pattern
- All use `log_extra: dict = {"component": "investigation_agent"}`

---

### `backend/scripts/seed_golden_dataset.py` (utility, batch)

**Analog:** `backend/scripts/seed_destinations.py` + `backend/scripts/create_eval_containers.py`

**Script structure pattern** (seed_destinations.py lines 1-19):
```python
"""Seed initial destinations into the Destinations Cosmos DB container.

Prerequisites:
  - Run `az login` first
  - Set COSMOS_ENDPOINT environment variable

Usage:
  python3 backend/scripts/seed_golden_dataset.py export --limit 100
  python3 backend/scripts/seed_golden_dataset.py import --file golden_dataset.json
"""

import asyncio
import logging
import os
import sys

from azure.cosmos.aio import CosmosClient
from azure.identity.aio import DefaultAzureCredential

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DATABASE_NAME = "second-brain"
```

**Cosmos client setup pattern** (seed_destinations.py lines 114-175):
```python
async def seed() -> None:
    endpoint = os.environ.get("COSMOS_ENDPOINT")
    if not endpoint:
        logger.error("COSMOS_ENDPOINT environment variable is not set")
        sys.exit(1)

    credential = DefaultAzureCredential()
    client = CosmosClient(url=endpoint, credential=credential)

    try:
        database = client.get_database_client(DATABASE_NAME)
        container = database.get_container_client("Destinations")

        # ... read/write operations ...

    finally:
        await client.close()
        await credential.close()


if __name__ == "__main__":
    asyncio.run(seed())
```

**Key adaptation for golden dataset script:**
- `export` subcommand: queries Inbox container for classified items, writes to JSON file for human curation
- `import` subcommand: reads curated JSON, creates `GoldenDatasetDocument` entries in GoldenDataset container
- Uses `argparse` or simple `sys.argv` for export/import mode selection
- JSON output format for human review before import

---

### `backend/tests/test_eval.py` (test)

**Analog:** `backend/tests/test_feedback.py`

**Test file structure** (lines 1-22):
```python
"""Tests for feedback signal infrastructure.

Covers:
- POST /api/feedback explicit thumbs up/down endpoint (FEED-02)
- Inline feedback signal emission from recategorize, HITL, errand handlers (FEED-01)
- Investigation tool tests for query_feedback_signals
  and promote_to_golden_dataset (FEED-03, FEED-04)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI

from second_brain.api.feedback import router as feedback_router
from second_brain.api.inbox import router as inbox_router
from second_brain.auth import APIKeyMiddleware
from second_brain.tools.investigation import InvestigationTools

TEST_API_KEY = "test-api-key-12345"
```

**App fixture pattern** (lines 51-60):
```python
@pytest.fixture
def feedback_app(mock_cosmos_manager: MagicMock) -> FastAPI:
    """Create a FastAPI app with feedback and inbox routers plus mock Cosmos."""
    app = FastAPI()
    app.include_router(feedback_router)
    app.include_router(inbox_router)
    app.state.api_key = TEST_API_KEY
    app.state.cosmos_manager = mock_cosmos_manager
    app.add_middleware(APIKeyMiddleware)
    return app
```

**API endpoint test pattern** (lines 68-98):
```python
@pytest.mark.asyncio
async def test_explicit_feedback_thumbs_up(
    feedback_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """POST /api/feedback with thumbs_up writes FeedbackDocument and returns 201."""
    transport = httpx.ASGITransport(app=feedback_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/feedback",
            json={...},
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "recorded"

    feedback_container = mock_cosmos_manager.get_container("Feedback")
    feedback_container.create_item.assert_called_once()
    written = feedback_container.create_item.call_args[1]["body"]
    assert written["signalType"] == "thumbs_up"
```

**Investigation tool test pattern** (lines 362-371):
```python
@pytest.fixture
def investigation_tools(mock_cosmos_manager: MagicMock) -> InvestigationTools:
    """InvestigationTools with mock LogsQueryClient and mock cosmos_manager."""
    logs_client = MagicMock()
    return InvestigationTools(
        logs_client=logs_client,
        workspace_id="test-workspace-id",
        cosmos_manager=mock_cosmos_manager,
    )
```

**Mock async generator pattern** (lines 383-390):
```python
def _mock_feedback_query(signals: list[dict]):
    """Create an async generator returning the given signals."""

    async def _gen(*args, **kwargs):
        for item in signals:
            yield item

    return _gen
```

**conftest.py mock_cosmos_manager fixture** (`backend/tests/conftest.py` lines 74-96):
```python
@pytest.fixture
def mock_cosmos_manager() -> CosmosManager:
    """Return a mock CosmosManager with mock containers."""
    manager = MagicMock(spec=CosmosManager)

    containers: dict = {}
    for name in CONTAINER_NAMES:
        container = MagicMock()
        container.create_item = AsyncMock()
        container.read_item = AsyncMock()
        container.upsert_item = AsyncMock()
        container.delete_item = AsyncMock()
        container.query_items = MagicMock()  # Returns an async iterator
        containers[name] = container

    manager.containers = containers
    manager.get_container = MagicMock(side_effect=lambda n: containers[n])

    return manager
```

---

### `backend/src/second_brain/main.py` (MODIFIED -- add eval router + wiring)

**Analog:** Self (existing file)

**Router import and inclusion pattern** (lines 49-56, 906-913):
```python
# Import:
from second_brain.api.feedback import router as feedback_router

# Inclusion (at bottom):
app.include_router(feedback_router)
```

**Investigation tools wiring** (lines 692-717):
```python
investigation_tools = InvestigationTools(
    logs_client=app.state.logs_client,
    workspace_id=settings.log_analytics_workspace_id,
    cosmos_manager=app.state.cosmos_manager,
)
app.state.investigation_tools_instance = investigation_tools

investigation_client = AzureAIAgentClient(...)
app.state.investigation_client = investigation_client
app.state.investigation_tools = [
    investigation_tools.trace_lifecycle,
    investigation_tools.recent_errors,
    investigation_tools.system_health,
    investigation_tools.usage_patterns,
    investigation_tools.query_feedback_signals,
    investigation_tools.promote_to_golden_dataset,
]
```

**Key adaptation:**
- Import and include `eval_router` alongside other routers
- Add new eval investigation tools to `app.state.investigation_tools` list
- No new client wiring needed -- eval runner reuses existing `classifier_client` and `admin_client` from `app.state`

---

## Shared Patterns

### Cosmos Container Access
**Source:** `backend/src/second_brain/db/cosmos.py` (lines 17-35) + all tools/API files
**Apply to:** `eval/runner.py`, `api/eval.py`, `tools/investigation.py` (eval tools), `scripts/seed_golden_dataset.py`
```python
# Access a container via CosmosManager:
container = cosmos_manager.get_container("GoldenDataset")

# Async iteration over query results:
async for item in container.query_items(
    query="SELECT * FROM c WHERE c.userId = @userId",
    parameters=[{"name": "@userId", "value": "will"}],
    partition_key="will",
):
    results.append(item)

# Write a document:
await container.create_item(body=doc.model_dump(mode="json"))
```

### Background Task Management
**Source:** `backend/src/second_brain/api/errands.py` (lines 217-248)
**Apply to:** `api/eval.py`
```python
bg_tasks: set = getattr(request.app.state, "background_tasks", set())
task = asyncio.create_task(run_eval(...))
bg_tasks.add(task)
task.add_done_callback(bg_tasks.discard)
```

### Error Handling in @tool Functions
**Source:** `backend/src/second_brain/tools/investigation.py` (all tool methods)
**Apply to:** New eval-related investigation tools
```python
log_extra: dict = {"component": "investigation_agent"}
logger.info("tool_name called: param=%s", param, extra=log_extra)

try:
    # ... logic ...
    return json.dumps(result, default=str)
except Exception as exc:
    logger.error("tool_name error: %s", exc, exc_info=True, extra=log_extra)
    return json.dumps({"error": f"Failed to ...: {exc}"})
```

### Pydantic Document Models
**Source:** `backend/src/second_brain/models/documents.py` (lines 178-214)
**Apply to:** Any model modifications (adding `expectedDestination` to `GoldenDatasetDocument`)
```python
class GoldenDatasetDocument(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    userId: str = "will"
    inputText: str
    expectedBucket: str
    source: str  # "manual", "promoted_feedback", "synthetic"
    tags: list[str] = Field(default_factory=list)
    createdAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

### API Key Auth in Tests
**Source:** `backend/tests/conftest.py` (lines 71, 99-119) + `backend/tests/test_feedback.py` (lines 51-60)
**Apply to:** `backend/tests/test_eval.py`
```python
TEST_API_KEY = "test-api-key-12345"

# In test:
headers={"Authorization": f"Bearer {TEST_API_KEY}"}
```

### Logging with Component Extra
**Source:** All backend modules
**Apply to:** All new files
```python
logger = logging.getLogger(__name__)
log_extra: dict = {"component": "eval"}  # or "investigation_agent"
logger.info("message: param=%s", param, extra=log_extra)
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `backend/src/second_brain/eval/metrics.py` | utility | transform | Pure math module computing precision/recall/accuracy/calibration. No existing utility module in the codebase performs classification metrics. Use RESEARCH.md Pattern 4 code examples directly -- no external library needed. |

---

## Metadata

**Analog search scope:** `backend/src/second_brain/` (api, tools, processing, models, db), `backend/scripts/`, `backend/tests/`
**Files scanned:** 8 analogs read in detail
**Pattern extraction date:** 2026-04-23
