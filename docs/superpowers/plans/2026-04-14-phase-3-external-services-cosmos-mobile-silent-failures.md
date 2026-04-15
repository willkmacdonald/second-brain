# Phase 3: External Services + Cosmos + Mobile Silent-Failure Instrumentation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add External Services (recipe scraping) and Cosmos DB as spine segments. Plug the known mobile silent-failure gaps from `docs/instrumentation.md` lines 71+89 (Inbox CRUD + Status errand operations) so Phase 4's mobile segments have real data to surface. Add Cosmos `client_request_id` propagation for trace-correlated diagnostic logs.

**Architecture:** External Services is push-based (wraps existing recipe-scraping helpers). Cosmos is pull-based against Azure Monitor diagnostic logs. Mobile silent-failure instrumentation extends the existing `reportError()` helper in `mobile/lib/telemetry.ts` with a new `event_type: "crud_failure"` and a new `correlation_kind: "crud"`. New `CosmosDiagnosticDetail` web renderer; External Services reuses `AppInsightsDetail` (its native shape is App Insights structured logs).

**Tech Stack:** Same as Phase 1+2.

**Spec reference:** `docs/superpowers/specs/2026-04-14-per-segment-observability-design.md`

**Phase 1+2 dependency:** All Phase 1 and Phase 2 tasks must be complete and deployed.

---

## File Structure

**Backend — additions:**

| File | Responsibility |
|---|---|
| `backend/src/second_brain/spine/adapters/cosmos.py` | Pull adapter for Cosmos diagnostic logs |
| `backend/src/second_brain/spine/cosmos_request_id.py` | Helper to set `x-ms-client-request-id` header on Cosmos calls |
| `backend/src/second_brain/api/telemetry.py` (modify) | Accept new `event_type: "crud_failure"` and write to spine ingest |

**Backend — modifications:**

| File | Change |
|---|---|
| `backend/src/second_brain/spine/registry.py` | Add `external_services` and `cosmos` segments |
| `backend/src/second_brain/observability/kql_templates.py` | Add `COSMOS_DIAGNOSTIC_LOGS` template |
| `backend/src/second_brain/observability/queries.py` | Add `fetch_cosmos_diagnostics` |
| `backend/src/second_brain/tools/recipe.py` (verify path) | Wrap fetch tiers (Jina/httpx/Playwright) with workload emission |
| `backend/src/second_brain/db/cosmos.py` (or wherever Cosmos containers are created) | Set `request_options={"client_request_id": correlation_id}` on every CRUD call |
| `backend/src/second_brain/main.py` | Register cosmos + external_services adapters and emitters |

**Backend — tests:**

| File | Purpose |
|---|---|
| `backend/tests/test_spine_cosmos_adapter.py` | Cosmos adapter returns native diagnostic logs shape |
| `backend/tests/test_cosmos_request_id_propagation.py` | Verify `x-ms-client-request-id` flows on Cosmos calls |
| `backend/tests/test_recipe_workload_emission.py` | Recipe tiers emit workload events with success/failure |

**Mobile — modifications:**

| File | Change |
|---|---|
| `mobile/lib/telemetry.ts` | Add `crud_failure` event type + `correlation_kind: "crud"` field |
| `mobile/components/<inbox screens>` | Wire `reportError({ event_type: "crud_failure" })` at the 6 silent sites in Inbox screen (lines 71-76 of instrumentation.md) |
| `mobile/components/<status screen>` | Wire same at the 7 silent sites in Status/Errands screen (lines 89-95) |
| `mobile/app/<status-screen-file>.tsx` | Add 2 more `<SpineStatusTile>` instances |

**Web — additions:**

| File | Responsibility |
|---|---|
| `web/components/renderers/CosmosDiagnosticDetail.tsx` | Renderer for `azure_monitor_cosmos` schema |
| `web/app/segment/[id]/page.tsx` | Add `azure_monitor_cosmos` branch to dispatcher |

---

## Task 1: Extend registry with cosmos + external_services segments

**Files:**
- Modify: `backend/src/second_brain/spine/registry.py`
- Create: `backend/tests/test_spine_registry_phase3.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_spine_registry_phase3.py`:

```python
"""Phase 3: registry includes cosmos and external_services."""

from second_brain.spine.registry import get_default_registry


def test_registry_includes_cosmos() -> None:
    cfg = get_default_registry().get("cosmos")
    assert cfg.host_segment is None  # Cosmos is independent of Container App
    assert cfg.acceptable_lag_seconds >= 300  # diagnostic logs lag 5-10min


def test_registry_includes_external_services() -> None:
    cfg = get_default_registry().get("external_services")
    assert cfg.host_segment == "container_app"
    assert cfg.display_name == "External Services"
```

- [ ] **Step 2: Verify failure**

```bash
cd backend && uv run pytest tests/test_spine_registry_phase3.py -v
```

Expected: FAIL with KeyError.

- [ ] **Step 3: Add segments**

In `get_default_registry()`:

```python
        EvaluatorConfig(
            segment_id="cosmos",
            display_name="Cosmos DB",
            liveness_interval_seconds=120,  # liveness from periodic Azure Monitor poll
            host_segment=None,
            workload_window_seconds=900,  # widen window because of lag
            acceptable_lag_seconds=600,   # diagnostic logs lag up to 10 minutes
            yellow_thresholds={
                "workload_failure_rate": 0.05,
            },
            red_thresholds={
                "workload_failure_rate": 0.20,
                "consecutive_failures": 5,
            },
        ),
        EvaluatorConfig(
            segment_id="external_services",
            display_name="External Services",
            liveness_interval_seconds=300,  # idle when no recipes scraped
            host_segment="container_app",
            workload_window_seconds=3600,
            yellow_thresholds={
                "workload_failure_rate": 0.30,  # external sites flake
            },
            red_thresholds={
                "workload_failure_rate": 0.70,
                "consecutive_failures": 3,
            },
        ),
```

- [ ] **Step 4: Tests pass**

```bash
cd backend && uv run pytest tests/test_spine_registry_phase3.py tests/test_spine_registry.py tests/test_spine_registry_phase2.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/second_brain/spine/registry.py backend/tests/test_spine_registry_phase3.py
git commit -m "feat(spine): register cosmos and external_services segments"
```

---

## Task 2: Cosmos `client_request_id` propagation helper

**Files:**
- Create: `backend/src/second_brain/spine/cosmos_request_id.py`
- Test: `backend/tests/test_cosmos_request_id_propagation.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_cosmos_request_id_propagation.py`:

```python
"""Verify capture_trace_id flows as x-ms-client-request-id on Cosmos calls."""

from contextvars import ContextVar
from unittest.mock import AsyncMock

import pytest

from second_brain.spine.cosmos_request_id import (
    apply_request_id,
    get_current_request_id,
)


@pytest.mark.asyncio
async def test_get_current_request_id_returns_contextvar_value() -> None:
    var: ContextVar[str | None] = ContextVar("test", default=None)
    var.set("trace-1")
    assert get_current_request_id(var) == "trace-1"


@pytest.mark.asyncio
async def test_apply_request_id_sets_initial_headers() -> None:
    kwargs: dict = {}
    apply_request_id(kwargs, "trace-1")
    assert kwargs["initial_headers"]["x-ms-client-request-id"] == "trace-1"


@pytest.mark.asyncio
async def test_apply_request_id_no_op_when_none() -> None:
    kwargs: dict = {}
    apply_request_id(kwargs, None)
    assert "initial_headers" not in kwargs
```

- [ ] **Step 2: Verify failure**

```bash
cd backend && uv run pytest tests/test_cosmos_request_id_propagation.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement helper**

Create `backend/src/second_brain/spine/cosmos_request_id.py`:

```python
"""Helper for propagating capture_trace_id (and similar) as Cosmos client_request_id.

Azure Cosmos SDK accepts `initial_headers` in request_options to forward
custom headers; this is the documented mechanism for client_request_id.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any


def get_current_request_id(var: ContextVar[str | None]) -> str | None:
    """Read a context-local request id (caller supplies the ContextVar)."""
    return var.get()


def apply_request_id(request_kwargs: dict[str, Any], request_id: str | None) -> None:
    """Mutate request_kwargs to include the x-ms-client-request-id header.

    No-op when request_id is None — never adds an empty header.
    """
    if not request_id:
        return
    headers = request_kwargs.setdefault("initial_headers", {})
    headers["x-ms-client-request-id"] = request_id
```

- [ ] **Step 4: Tests pass**

```bash
cd backend && uv run pytest tests/test_cosmos_request_id_propagation.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/second_brain/spine/cosmos_request_id.py backend/tests/test_cosmos_request_id_propagation.py
git commit -m "feat(spine): cosmos client_request_id propagation helper"
```

---

## Task 3: Wire `apply_request_id` into Cosmos call sites

**Files:**
- Modify: `backend/src/second_brain/db/cosmos.py` (or wherever Cosmos containers are created and used — verify path)

- [ ] **Step 1: Locate Cosmos call sites**

```bash
grep -rn "create_item\|upsert_item\|read_item\|delete_item\|query_items\|replace_item" backend/src/second_brain/ --include="*.py" | grep -v test_ | head -30
```

- [ ] **Step 2: Identify the existing capture_trace_id ContextVar**

```bash
grep -rn "capture_trace_id\|trace_id_var" backend/src/second_brain/ --include="*.py" | head -10
```

You should find an existing ContextVar (likely in `observability/` or `streaming/`). Note its import path.

- [ ] **Step 3: Wrap call sites**

The cleanest approach is a small wrapper module that encapsulates the call sites. If the project already has a thin Cosmos abstraction (`db/cosmos.py` or similar), modify that. Otherwise create `backend/src/second_brain/db/cosmos_wrapped.py` with helpers that wrap each verb:

```python
"""Cosmos call wrappers that auto-propagate x-ms-client-request-id."""

from __future__ import annotations

from typing import Any

from azure.cosmos.aio import ContainerProxy

from second_brain.spine.cosmos_request_id import apply_request_id, get_current_request_id
from second_brain.observability.context import capture_trace_id_var  # adjust to actual import


async def create_item(container: ContainerProxy, body: dict, **kwargs: Any) -> dict:
    apply_request_id(kwargs, get_current_request_id(capture_trace_id_var))
    return await container.create_item(body=body, **kwargs)


async def upsert_item(container: ContainerProxy, body: dict, **kwargs: Any) -> dict:
    apply_request_id(kwargs, get_current_request_id(capture_trace_id_var))
    return await container.upsert_item(body=body, **kwargs)


async def read_item(container: ContainerProxy, item: str, partition_key: str, **kwargs: Any) -> dict:
    apply_request_id(kwargs, get_current_request_id(capture_trace_id_var))
    return await container.read_item(item=item, partition_key=partition_key, **kwargs)


async def delete_item(container: ContainerProxy, item: str, partition_key: str, **kwargs: Any) -> None:
    apply_request_id(kwargs, get_current_request_id(capture_trace_id_var))
    await container.delete_item(item=item, partition_key=partition_key, **kwargs)
```

Then refactor existing call sites to import from `db.cosmos_wrapped` instead of calling Cosmos containers directly. This is potentially many touchpoints — do it incrementally, verifying tests after each module's migration.

- [ ] **Step 4: After migration, run all backend tests**

```bash
cd backend && uv run pytest -x
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/second_brain/db/cosmos_wrapped.py <all migrated files>
git commit -m "feat(spine): propagate capture_trace_id as cosmos client_request_id"
```

---

## Task 4: COSMOS_DIAGNOSTIC_LOGS KQL template + fetcher

**Files:**
- Modify: `backend/src/second_brain/observability/kql_templates.py`
- Modify: `backend/src/second_brain/observability/queries.py`

- [ ] **Step 1: Add KQL template**

In `kql_templates.py`:

```python
# ---------------------------------------------------------------------------
# Cosmos diagnostic logs (Phase 3: cosmos adapter)
# ---------------------------------------------------------------------------
# Returns recent Cosmos operations from diagnostic logs.
# Note: diagnostic logs flow with 5-10 minute lag.
# {capture_filter} is e.g. '| where clientRequestId_g == "trace-1"' or empty.
# {limit} is row limit.

COSMOS_DIAGNOSTIC_LOGS = """\
CDBDataPlaneRequests
{capture_filter}
| project
    timestamp = TimeGenerated,
    operation_name = OperationName,
    status_code = StatusCode,
    duration_ms = DurationMs,
    request_charge = RequestCharge,
    request_length = RequestLength,
    response_length = ResponseLength,
    partition_key_range_id = PartitionKeyRangeId,
    client_request_id = clientRequestId_g,
    collection_name = CollectionName
| order by timestamp desc
| take {limit}
"""
```

- [ ] **Step 2: Add fetcher**

In `queries.py`:

```python
async def fetch_cosmos_diagnostics(
    client: LogsQueryClient,
    workspace_id: str,
    capture_trace_id: str | None = None,
    time_range_seconds: int = 3600,
    limit: int = 50,
) -> list[dict]:
    """Fetch Cosmos data-plane requests from diagnostic logs.

    Diagnostic logs lag 5-10 minutes. Time range should be wide enough
    to compensate.
    """
    capture_filter = (
        f'| where clientRequestId_g == "{capture_trace_id}"'
        if capture_trace_id else ""
    )
    query = COSMOS_DIAGNOSTIC_LOGS.format(
        capture_filter=capture_filter, limit=limit,
    )
    response = await client.query_workspace(
        workspace_id=workspace_id,
        query=query,
        timespan=timedelta(seconds=time_range_seconds),
    )
    if response.status != LogsQueryStatus.SUCCESS:
        return []
    table = response.tables[0] if response.tables else None
    if table is None:
        return []
    return [
        {col: val for col, val in zip(table.columns, row, strict=False)}
        for row in table.rows
    ]
```

(Add `from second_brain.observability.kql_templates import COSMOS_DIAGNOSTIC_LOGS` import at top.)

- [ ] **Step 3: Quick test**

Add to `backend/tests/test_kql_projections.py`:

```python
def test_cosmos_diagnostic_logs_template_filters_compose() -> None:
    from second_brain.observability.kql_templates import COSMOS_DIAGNOSTIC_LOGS
    rendered = COSMOS_DIAGNOSTIC_LOGS.format(
        capture_filter='| where clientRequestId_g == "trace-1"',
        limit=50,
    )
    assert "trace-1" in rendered
    assert "CDBDataPlaneRequests" in rendered
```

```bash
cd backend && uv run pytest tests/test_kql_projections.py -v
```

Expected: PASS.

- [ ] **Step 4: Verify Cosmos diagnostic settings are routed to Log Analytics**

This is an Azure portal toggle. Run:

```bash
ACCOUNT=$(az cosmosdb list -g shared-services-rg --query "[?contains(name, 'second-brain')].name | [0]" -o tsv)
az monitor diagnostic-settings list --resource $(az cosmosdb show -n $ACCOUNT -g shared-services-rg --query id -o tsv)
```

Expected: at least one setting with `categories: [{ category: "DataPlaneRequests", enabled: true }]` routed to your Log Analytics workspace. If absent, create one:

```bash
WS_ID=$(az monitor log-analytics workspace show -g shared-services-rg -n <workspace> --query id -o tsv)
az monitor diagnostic-settings create \
  --name spine-cosmos-diag \
  --resource $(az cosmosdb show -n $ACCOUNT -g shared-services-rg --query id -o tsv) \
  --workspace $WS_ID \
  --logs '[{"category": "DataPlaneRequests", "enabled": true}]'
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/second_brain/observability/kql_templates.py backend/src/second_brain/observability/queries.py backend/tests/test_kql_projections.py
git commit -m "feat(observability): cosmos diagnostic logs KQL template + fetcher"
```

---

## Task 5: Cosmos pull adapter

**Files:**
- Create: `backend/src/second_brain/spine/adapters/cosmos.py`
- Test: `backend/tests/test_spine_cosmos_adapter.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_spine_cosmos_adapter.py`:

```python
"""Tests for the Cosmos diagnostic-logs pull adapter."""

from unittest.mock import AsyncMock

import pytest

from second_brain.spine.adapters.cosmos import CosmosAdapter


@pytest.mark.asyncio
async def test_fetch_detail_returns_cosmos_schema() -> None:
    diag_query = AsyncMock(return_value=[])
    adapter = CosmosAdapter(
        diagnostics_fetcher=diag_query,
        native_url="https://portal.azure.com/#blade/CosmosDB",
    )
    result = await adapter.fetch_detail()
    assert result["schema"] == "azure_monitor_cosmos"
    assert "diagnostic_logs" in result
    assert result["native_url"] == "https://portal.azure.com/#blade/CosmosDB"


@pytest.mark.asyncio
async def test_fetch_detail_with_capture_correlation_passes_filter() -> None:
    diag_query = AsyncMock(return_value=[
        {"client_request_id": "trace-1", "operation_name": "Create", "status_code": 201}
    ])
    adapter = CosmosAdapter(
        diagnostics_fetcher=diag_query,
        native_url="x",
    )
    result = await adapter.fetch_detail(
        correlation_kind="capture", correlation_id="trace-1",
    )
    diag_query.assert_called_once()
    assert diag_query.call_args.kwargs.get("capture_trace_id") == "trace-1"
    assert result["diagnostic_logs"][0]["client_request_id"] == "trace-1"
```

- [ ] **Step 2: Verify failure**

```bash
cd backend && uv run pytest tests/test_spine_cosmos_adapter.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement adapter**

Create `backend/src/second_brain/spine/adapters/cosmos.py`:

```python
"""Cosmos DB segment adapter — pulls from Azure Monitor diagnostic logs."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from second_brain.spine.models import CorrelationKind


class CosmosAdapter:
    """Pulls Cosmos data-plane diagnostic logs from Log Analytics workspace."""

    segment_id: str = "cosmos"

    def __init__(
        self,
        diagnostics_fetcher: Callable[..., Awaitable[list[dict[str, Any]]]],
        native_url: str,
    ) -> None:
        self._diagnostics = diagnostics_fetcher
        self.native_url_template = native_url

    async def fetch_detail(
        self,
        correlation_kind: CorrelationKind | None = None,
        correlation_id: str | None = None,
        time_range_seconds: int = 3600,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"time_range_seconds": time_range_seconds}
        if correlation_kind == "capture" and correlation_id:
            kwargs["capture_trace_id"] = correlation_id

        logs = await self._diagnostics(**kwargs)
        return {
            "schema": "azure_monitor_cosmos",
            "diagnostic_logs": logs,
            "native_url": self.native_url_template,
        }
```

- [ ] **Step 4: Tests pass**

```bash
cd backend && uv run pytest tests/test_spine_cosmos_adapter.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/second_brain/spine/adapters/cosmos.py backend/tests/test_spine_cosmos_adapter.py
git commit -m "feat(spine): cosmos pull adapter for diagnostic logs"
```

---

## Task 6: External Services workload emission

**Files:**
- Modify: `backend/src/second_brain/tools/recipe.py` (verify path — likely the file that implements three-tier recipe fetch: Jina, httpx, Playwright)
- Test: `backend/tests/test_recipe_workload_emission.py`

- [ ] **Step 1: Locate the recipe fetch code**

```bash
grep -rn "def fetch_recipe\|jina\|playwright" backend/src/second_brain/tools/ --include="*.py" | head -10
```

Identify the entrypoint that orchestrates the three tiers.

- [ ] **Step 2: Write failing test**

Create `backend/tests/test_recipe_workload_emission.py`:

```python
"""Recipe scraping emits a workload event per fetch."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_recipe_fetch_success_emits_workload_event(monkeypatch) -> None:
    repo = AsyncMock()
    # Patch the spine repo accessor used inside recipe.py
    monkeypatch.setattr(
        "second_brain.tools.recipe.get_spine_repo",
        lambda: repo,
        raising=False,
    )

    from second_brain.tools.recipe import fetch_recipe_url

    # Mock the three tiers — assume tier 1 succeeds
    with patch("second_brain.tools.recipe._fetch_via_jina", new=AsyncMock(return_value="<html>...</html>")):
        await fetch_recipe_url("https://example.com/recipe", capture_trace_id="trace-1")

    repo.record_event.assert_called()
    # Find the workload event among calls
    workload_events = [
        c.args[0] for c in repo.record_event.call_args_list
        if c.args[0].event_type == "workload"
    ]
    assert len(workload_events) >= 1
    assert workload_events[0].segment_id == "external_services"
    assert workload_events[0].payload.outcome == "success"


@pytest.mark.asyncio
async def test_recipe_fetch_all_tiers_failed_emits_failure(monkeypatch) -> None:
    repo = AsyncMock()
    monkeypatch.setattr(
        "second_brain.tools.recipe.get_spine_repo",
        lambda: repo,
        raising=False,
    )

    from second_brain.tools.recipe import fetch_recipe_url

    with patch("second_brain.tools.recipe._fetch_via_jina", new=AsyncMock(side_effect=RuntimeError("jina failed"))), \
         patch("second_brain.tools.recipe._fetch_via_httpx", new=AsyncMock(side_effect=RuntimeError("httpx failed"))), \
         patch("second_brain.tools.recipe._fetch_via_playwright", new=AsyncMock(side_effect=RuntimeError("playwright failed"))):
        try:
            await fetch_recipe_url("https://example.com/recipe", capture_trace_id="trace-1")
        except Exception:
            pass

    workload_events = [
        c.args[0] for c in repo.record_event.call_args_list
        if c.args[0].event_type == "workload"
    ]
    assert any(e.payload.outcome == "failure" for e in workload_events)
```

- [ ] **Step 3: Verify failure**

```bash
cd backend && uv run pytest tests/test_recipe_workload_emission.py -v
```

Expected: FAIL — no `get_spine_repo` accessor yet.

- [ ] **Step 4: Add accessor + wrap fetch**

In `backend/src/second_brain/tools/recipe.py`, near top:

```python
import time
from datetime import datetime, timezone
from typing import Optional

from second_brain.spine.agent_emitter import emit_agent_workload  # reuse the helper
from second_brain.spine.storage import SpineRepository

# Module-level accessor — wired in main.py during lifespan
_spine_repo: Optional[SpineRepository] = None


def set_spine_repo(repo: SpineRepository) -> None:
    """Called once during app startup."""
    global _spine_repo
    _spine_repo = repo


def get_spine_repo() -> Optional[SpineRepository]:
    return _spine_repo
```

Then in the orchestrator function (`fetch_recipe_url` or equivalent), wrap each tier:

```python
async def fetch_recipe_url(url: str, capture_trace_id: str | None = None) -> str:
    repo = get_spine_repo()
    start = time.perf_counter()
    operation = "fetch_recipe"
    error_class: str | None = None
    outcome = "success"
    tier_used = "none"
    try:
        try:
            content = await _fetch_via_jina(url)
            tier_used = "jina"
        except Exception:
            try:
                content = await _fetch_via_httpx(url)
                tier_used = "httpx"
            except Exception:
                content = await _fetch_via_playwright(url)
                tier_used = "playwright"
        return content
    except Exception as exc:
        outcome = "failure"
        error_class = type(exc).__name__
        raise
    finally:
        if repo:
            duration_ms = int((time.perf_counter() - start) * 1000)
            await emit_agent_workload(
                repo=repo,
                segment_id="external_services",
                operation=f"{operation}:{tier_used}",
                outcome=outcome,
                duration_ms=duration_ms,
                capture_trace_id=capture_trace_id,
                run_id=None,
                thread_id=None,
                error_class=error_class,
            )
```

- [ ] **Step 5: Tests pass**

```bash
cd backend && uv run pytest tests/test_recipe_workload_emission.py tests/test_recipe_tools.py -v
```

Expected: PASS — both new and existing recipe tests.

- [ ] **Step 6: Commit**

```bash
git add backend/src/second_brain/tools/recipe.py backend/tests/test_recipe_workload_emission.py
git commit -m "feat(spine): emit workload events from recipe scraping tiers"
```

---

## Task 7: Wire cosmos + external_services into main.py

**Files:**
- Modify: `backend/src/second_brain/main.py`

- [ ] **Step 1: Add cosmos adapter and wire spine_repo into recipe module**

Inside the lifespan, after Phase 2 wiring:

```python
from second_brain.spine.adapters.cosmos import CosmosAdapter
from second_brain.observability.queries import fetch_cosmos_diagnostics
from second_brain.tools import recipe as recipe_tools

# Cosmos adapter
async def _cosmos_diag_fetcher(**kwargs):
    return await fetch_cosmos_diagnostics(
        client=log_client, workspace_id=workspace_id, **kwargs,
    )

cosmos_adapter = CosmosAdapter(
    diagnostics_fetcher=_cosmos_diag_fetcher,
    native_url="https://portal.azure.com/#blade/Microsoft_Azure_DocumentDB/DocumentDBAccountMenuBlade",
)

# Update adapter_registry
adapter_registry = AdapterRegistry([
    backend_api_adapter,
    classifier_adapter, admin_adapter, investigation_adapter,
    cosmos_adapter,
    # external_services has no pull adapter — its data is in App Insights
    # via existing structured logs. Reuse BackendApiAdapter pattern with a
    # different filter, OR omit detail and let drill-down go to App Insights.
])

# Wire spine_repo into recipe module so its workload events flow
recipe_tools.set_spine_repo(spine_repo)

# Liveness emitters for cosmos and external_services
cosmos_liveness_task = asyncio.create_task(
    liveness_emitter(spine_repo, segment_id="cosmos", interval_seconds=120)
)
external_services_liveness_task = asyncio.create_task(
    liveness_emitter(spine_repo, segment_id="external_services", interval_seconds=300)
)
```

- [ ] **Step 2: For external_services detail**

Decide between:
- (A) Add an `ExternalServicesAdapter` that wraps `fetch_recent_failures` filtered to `Properties.component == "external_services"`. Returns `azure_monitor_app_insights` schema (reuses Phase 1's renderer).
- (B) Skip detail for now — external_services tile shows status only, click does nothing.

Recommended: **A** — minimal additional code. Add to `backend/src/second_brain/spine/adapters/__init__.py`:

```python
from second_brain.spine.adapters.backend_api import BackendApiAdapter

class ExternalServicesAdapter(BackendApiAdapter):
    """Same as BackendApiAdapter but filters App Insights to external_services component."""
    segment_id = "external_services"
    # Override fetch_detail to inject component filter into kwargs.
```

Or simpler: instantiate `BackendApiAdapter` with a different fetcher closure that pre-filters by component, and override `segment_id`. Implementation detail — pick the cleanest.

- [ ] **Step 3: Run tests + push**

```bash
cd backend && uv run pytest -x
git add backend/src/second_brain/main.py backend/src/second_brain/spine/adapters/__init__.py
git commit -m "feat(spine): wire cosmos and external_services adapters"
git push
```

After deploy:

```bash
curl -sS -H "Authorization: Bearer ${API_KEY}" https://brain.willmacdonald.com/api/spine/status \
  | jq '.segments[].id'
```

Expected: 7 segments — `backend_api`, `classifier`, `admin`, `investigation`, `cosmos`, `external_services`, `container_app`.

---

## Task 8: Mobile silent-failure instrumentation

**Files:**
- Modify: `mobile/lib/telemetry.ts`
- Modify: Inbox screen file (path varies — see Step 2 below for grep command to find it)
- Modify: Status/Errands screen file

Reference: `docs/instrumentation.md` lines 71-76 (Inbox screen) and lines 89-95 (Status screen) list 13 silent failure sites total.

- [ ] **Step 1: Extend telemetry.ts to support crud_failure event type and correlation_kind**

Open `mobile/lib/telemetry.ts`. Modify:

```typescript
interface TelemetryEvent {
  eventType: "error" | "network_failure" | "performance" | "crud_failure";
  message: string;
  captureTraceId?: string;
  correlationKind?: "capture" | "thread" | "request" | "crud";
  correlationId?: string;
  metadata?: Record<string, string | number | boolean>;
}

export async function reportError(event: TelemetryEvent): Promise<void> {
  try {
    await fetch(`${API_BASE_URL}/api/telemetry`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${API_KEY}`,
      },
      body: JSON.stringify({
        event_type: event.eventType,
        message: event.message,
        capture_trace_id: event.captureTraceId,
        correlation_kind: event.correlationKind,
        correlation_id: event.correlationId,
        metadata: event.metadata,
      }),
    });
  } catch {
    // Silently swallow — telemetry must never break the app
  }
}
```

- [ ] **Step 2: Locate Inbox screen call sites**

```bash
grep -rn "GET /api/inbox\|api/inbox" mobile/ --include="*.tsx" --include="*.ts" | head -20
```

Identify the file containing the 6 silent operations from `docs/instrumentation.md` lines 71-76:
1. Load inbox list (`GET /api/inbox`)
2. Pull-to-refresh
3. Pagination scroll
4. Recategorize from detail card (`PATCH /api/inbox/{id}/recategorize`)
5. Swipe-to-delete (`DELETE /api/inbox/{id}`)

- [ ] **Step 3: Wrap each Inbox call site**

For each silent site, find the existing fetch call and wrap with try/catch + reportError. Pattern:

```typescript
import { reportError } from "../lib/telemetry";

async function loadInbox(): Promise<InboxItem[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/inbox`, {
      headers: { Authorization: `Bearer ${API_KEY}` },
    });
    if (!res.ok) {
      await reportError({
        eventType: "crud_failure",
        message: `Inbox load failed: ${res.status}`,
        correlationKind: "crud",
        metadata: { operation: "load_inbox", status: res.status },
      });
      return [];
    }
    return await res.json();
  } catch (err) {
    await reportError({
      eventType: "crud_failure",
      message: `Inbox load network failure: ${String(err)}`,
      correlationKind: "crud",
      metadata: { operation: "load_inbox" },
    });
    return [];
  }
}
```

Apply analogously to:
- Pull-to-refresh handler
- Pagination handler
- Recategorize handler (with `metadata: { operation: "recategorize", inbox_id: id }`)
- Swipe-to-delete handler (with `metadata: { operation: "delete_inbox", inbox_id: id }`)
- Conversation screen — load item details + bucket selection (instrumentation.md lines 82-83)

- [ ] **Step 4: Locate Status/Errands screen call sites**

```bash
grep -rn "api/errands\|api/tasks" mobile/ --include="*.tsx" --include="*.ts" | head -20
```

Identify the file with the 7 silent operations from `docs/instrumentation.md` lines 89-95:
1. Load errands+tasks (`GET /api/errands` + `GET /api/tasks`)
2. Focus-based polling
3. Processing-count polling
4. Dismiss admin notification (`POST /api/errands/notifications/{id}/dismiss`)
5. Delete errand (`DELETE /api/errands/{id}`)
6. Complete task (`DELETE /api/tasks/{id}`)
7. Route unrouted errand (`POST /api/errands/{id}/route`)

- [ ] **Step 5: Wrap each Status/Errands call site**

Same pattern as Inbox. Each gets `eventType: "crud_failure"`, `correlationKind: "crud"`, and `metadata: { operation: "<op_name>", ... }`.

For the polling cases (focus-based + processing-count): only fire `reportError` on actual failure (don't spam telemetry on every successful poll).

- [ ] **Step 6: Type-check + EAS rebuild**

```bash
cd mobile && npx tsc --noEmit
```

Then EAS rebuild.

- [ ] **Step 7: Commit**

```bash
git add mobile/lib/telemetry.ts mobile/<inbox files> mobile/<status files>
git commit -m "feat(mobile): instrument silent crud failures across inbox and status screens"
```

---

## Task 9: Backend telemetry endpoint accepts crud_failure events

**Files:**
- Modify: `backend/src/second_brain/api/telemetry.py` (verify path)

- [ ] **Step 1: Locate the telemetry endpoint**

```bash
grep -rn "/api/telemetry\|telemetry_endpoint\|TelemetryEvent" backend/src/second_brain/ | head
```

- [ ] **Step 2: Extend the endpoint to accept new fields and forward to spine ingest**

Modify the request model and handler:

```python
from second_brain.spine.models import _WorkloadEvent, WorkloadPayload
from datetime import datetime, timezone

class TelemetryRequest(BaseModel):
    event_type: str
    message: str
    capture_trace_id: str | None = None
    correlation_kind: str | None = None  # NEW
    correlation_id: str | None = None  # NEW
    metadata: dict | None = None

@router.post("/api/telemetry")
async def post_telemetry(req: TelemetryRequest, request: Request) -> dict:
    # Existing logging behavior (App Insights via logger.warning) preserved.
    logger.warning(
        "client_telemetry: %s %s",
        req.event_type, req.message,
        extra={
            "client_capture_trace_id": req.capture_trace_id,
            "client_correlation_kind": req.correlation_kind,
            "client_correlation_id": req.correlation_id,
            "client_metadata": req.metadata,
        },
    )

    # NEW: forward crud_failure events into spine as workload failures
    if req.event_type == "crud_failure":
        spine_repo = request.app.state.spine_repo
        operation = (req.metadata or {}).get("operation", "unknown_crud")
        # Determine which mobile segment based on the operation
        segment_id = _segment_for_crud_operation(operation)
        event = _WorkloadEvent(
            segment_id=segment_id,
            event_type="workload",
            timestamp=datetime.now(timezone.utc),
            payload=WorkloadPayload(
                operation=str(operation),
                outcome="failure",
                duration_ms=0,  # client doesn't measure duration for these
                correlation_kind=req.correlation_kind or "crud",  # type: ignore
                correlation_id=req.correlation_id or req.capture_trace_id,
                error_class="MobileCrudFailure",
            ),
        )
        try:
            await spine_repo.record_event(event)
        except Exception:
            logger.warning("Failed to record mobile crud failure to spine", exc_info=True)

    return {"received": True}


def _segment_for_crud_operation(operation: str) -> str:
    """Route mobile crud failures to the right segment.

    Inbox/conversation operations → mobile_ui
    Status/errands operations     → mobile_capture (the user-facing post-capture flow)
    Capture-flow operations       → mobile_capture
    """
    if any(k in operation for k in ("inbox", "recategorize", "conversation", "bucket")):
        return "mobile_ui"
    return "mobile_capture"
```

Note: `mobile_ui` and `mobile_capture` segments are introduced in **Phase 4**, so before Phase 4 ships, these events arrive at segments not yet in the registry. That's fine — the events accumulate in `spine_events`; they just don't surface on the status board until Phase 4 registers the segments. No data is lost.

- [ ] **Step 3: Tests**

```bash
cd backend && uv run pytest tests/ -k telemetry -v
```

If a `test_telemetry.py` doesn't exist, add a minimal one verifying that a `crud_failure` request results in `spine_repo.record_event` being called with a workload event.

- [ ] **Step 4: Commit + push**

```bash
git add backend/src/second_brain/api/telemetry.py backend/tests/test_telemetry.py
git commit -m "feat(api): telemetry endpoint forwards crud_failure events to spine"
git push
```

---

## Task 10: Web CosmosDiagnosticDetail renderer + dispatcher branch

**Files:**
- Create: `web/components/renderers/CosmosDiagnosticDetail.tsx`
- Modify: `web/app/segment/[id]/page.tsx`

- [ ] **Step 1: Create renderer**

`web/components/renderers/CosmosDiagnosticDetail.tsx`:

```typescript
interface CosmosLog {
  timestamp: string;
  operation_name: string;
  status_code: number;
  duration_ms: number;
  request_charge: number;
  request_length: number;
  response_length: number;
  partition_key_range_id: string;
  client_request_id: string;
  collection_name: string;
}

interface CosmosData {
  schema: "azure_monitor_cosmos";
  diagnostic_logs: CosmosLog[];
  native_url: string;
}

export function CosmosDiagnosticDetail({ data }: { data: CosmosData }) {
  return (
    <div>
      <h2>Cosmos diagnostic logs ({data.diagnostic_logs.length})</h2>
      <p style={{ color: "#888", fontSize: 13 }}>
        Diagnostic logs lag 5–10 minutes; data shown may not be real-time.
      </p>
      {data.diagnostic_logs.length === 0 ? (
        <p style={{ color: "#888" }}>No recent operations.</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ borderBottom: "1px solid #333" }}>
              <th style={{ textAlign: "left", padding: 8 }}>Time</th>
              <th style={{ textAlign: "left", padding: 8 }}>Op</th>
              <th style={{ textAlign: "left", padding: 8 }}>Container</th>
              <th style={{ textAlign: "right", padding: 8 }}>RU</th>
              <th style={{ textAlign: "right", padding: 8 }}>Duration</th>
              <th style={{ textAlign: "right", padding: 8 }}>Status</th>
              <th style={{ textAlign: "left", padding: 8 }}>Request ID</th>
            </tr>
          </thead>
          <tbody>
            {data.diagnostic_logs.map((l, i) => (
              <tr key={i} style={{ borderBottom: "1px solid #1a2028" }}>
                <td style={{ padding: 8, color: "#888" }}>
                  {new Date(l.timestamp).toLocaleTimeString()}
                </td>
                <td style={{ padding: 8 }}>{l.operation_name}</td>
                <td style={{ padding: 8 }}>{l.collection_name}</td>
                <td style={{ padding: 8, textAlign: "right" }}>{l.request_charge.toFixed(1)}</td>
                <td style={{ padding: 8, textAlign: "right" }}>{l.duration_ms}ms</td>
                <td style={{
                  padding: 8,
                  textAlign: "right",
                  color: l.status_code < 300 ? "#3a7d3a" : "#b33b3b",
                }}>{l.status_code}</td>
                <td style={{ padding: 8, fontFamily: "monospace", fontSize: 11 }}>
                  {l.client_request_id?.slice(0, 8) ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Add dispatcher branch**

Modify `web/app/segment/[id]/page.tsx`:

```typescript
import { CosmosDiagnosticDetail } from "@/components/renderers/CosmosDiagnosticDetail";

// ...
{schema === "azure_monitor_app_insights" ? (
  <AppInsightsDetail data={detail.data as never} />
) : schema === "foundry_run" ? (
  <FoundryRunDetail data={detail.data as never} />
) : schema === "azure_monitor_cosmos" ? (
  <CosmosDiagnosticDetail data={detail.data as never} />
) : (
  <p>No renderer registered for schema: <code>{schema}</code></p>
)}
```

- [ ] **Step 3: Type-check + commit + deploy**

```bash
cd web && npm run type-check
git add web/components/renderers/CosmosDiagnosticDetail.tsx web/app/segment/[id]/page.tsx
git commit -m "feat(web): cosmos diagnostic logs renderer + dispatcher branch"
git push
```

---

## Task 11: Mobile — 2 more spine tiles

**Files:**
- Modify: `mobile/app/<status-screen-file>.tsx`

- [ ] **Step 1: Add tiles**

```typescript
<SpineStatusTile segmentId="external_services" />
<SpineStatusTile segmentId="cosmos" />
```

- [ ] **Step 2: Type-check + EAS rebuild**

```bash
cd mobile && npx tsc --noEmit
```

EAS rebuild and verify on device.

- [ ] **Step 3: Commit**

```bash
git add mobile/app/<status-screen-file>.tsx
git commit -m "feat(mobile): add external_services and cosmos spine tiles"
```

---

## Task 12: Phase 3 acceptance verification

- [ ] **Step 1: Backend tests pass:** `cd backend && uv run pytest -x`
- [ ] **Step 2: Web type-check passes:** `cd web && npm run type-check`
- [ ] **Step 3: Mobile type-check passes:** `cd mobile && npx tsc --noEmit`
- [ ] **Step 4: 7 segments visible**

```bash
curl -sS -H "Authorization: Bearer ${API_KEY}" https://brain.willmacdonald.com/api/spine/status \
  | jq '.segments | length'
```

Expected: `7`.

- [ ] **Step 5: Cosmos diagnostic logs flow**

After triggering some Cosmos activity (any capture/CRUD), wait ~10 minutes and:

```bash
curl -sS -H "Authorization: Bearer ${API_KEY}" https://brain.willmacdonald.com/api/spine/segment/cosmos \
  | jq '.data.diagnostic_logs | length'
```

Expected: > 0.

- [ ] **Step 6: Recipe scraping emits workload events**

Trigger a recipe URL capture from the device. Then check the spine events for `external_services`:

```bash
curl -sS -H "Authorization: Bearer ${API_KEY}" "https://brain.willmacdonald.com/api/spine/segment/external_services" \
  | jq '.data'
```

Expected: data populated (App Insights records for `external_services` component).

- [ ] **Step 7: Mobile silent failures now visible in spine**

On the device, intentionally fail an inbox load (e.g., turn off wifi briefly while opening Inbox). Then:

```bash
curl -sS -H "Authorization: Bearer ${API_KEY}" "https://brain.willmacdonald.com/api/spine/correlation/crud/<correlation_id_from_telemetry>" \
  | jq '.events'
```

Note: events for `mobile_ui`/`mobile_capture` segments are stored in `spine_events` even though those segments aren't yet in the registry — Phase 4 will register them and the data will flow into the status board automatically.

- [ ] **Step 8: Cosmos client_request_id flowing through**

Trigger a capture, find its trace ID, then:

```bash
TRACE_ID=<from device toast>
curl -sS -H "Authorization: Bearer ${API_KEY}" "https://brain.willmacdonald.com/api/spine/segment/cosmos?correlation_kind=capture&correlation_id=${TRACE_ID}" \
  | jq '.data.diagnostic_logs[].client_request_id'
```

Expected (after diagnostic log lag): one or more entries matching the trace ID.

- [ ] **Step 9: Tag**

```bash
git tag phase-3-external-cosmos -m "Phase 3 complete: external_services + cosmos + mobile silent-failure instrumentation"
git push --tags
```
