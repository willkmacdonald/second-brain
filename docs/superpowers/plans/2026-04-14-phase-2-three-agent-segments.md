# Phase 2: Three Agent Segments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Classifier, Admin, and Investigation agents as spine segments. Each emits liveness/readiness/workload events. Foundry correlation via existing `run_id` and `foundryThreadId` (NOT vendor metadata filtering). One new web renderer (`FoundryRunDetail`) reused across all three agents.

**Architecture:** Each agent is wrapped at its existing call site to emit spine events. Workload events carry `run_id`/`thread_id`/`capture_trace_id` as correlation IDs. The pull adapter joins App Insights agent spans (which we already own) by these IDs — Foundry Runs API is consulted only as an enrichment layer if available, never on the critical path.

**Tech Stack:** Same as Phase 1.

**Spec reference:** `docs/superpowers/specs/2026-04-14-per-segment-observability-design.md`

**Phase 1 dependency:** All Phase 1 tasks must be complete and deployed.

---

## File Structure

**Backend — modifications:**

| File | Change |
|---|---|
| `backend/src/second_brain/spine/registry.py` | Add 3 new `EvaluatorConfig` entries (classifier, admin, investigation) |
| `backend/src/second_brain/spine/adapters/foundry_agent.py` | NEW: pull adapter for any Foundry-agent segment, parameterized by `agent_id` |
| `backend/src/second_brain/spine/agent_emitter.py` | NEW: helper to emit workload events from agent wrappers |
| `backend/src/second_brain/agents/classifier.py` | Wrap classify call to emit workload event |
| `backend/src/second_brain/agents/admin.py` | Same (verify file path before editing) |
| `backend/src/second_brain/agents/investigation.py` | Same |
| `backend/src/second_brain/main.py` | Register 3 adapters, start 3 liveness emitters |

**Backend — tests:**

| File | Purpose |
|---|---|
| `backend/tests/test_spine_foundry_adapter.py` | Foundry-agent adapter returns `foundry_run` schema |
| `backend/tests/test_spine_agent_emitter.py` | Helper emits workload event with run_id/thread_id correlation |
| `backend/tests/test_spine_registry_phase2.py` | New segment configs in registry |

**Web — additions:**

| File | Responsibility |
|---|---|
| `web/components/renderers/FoundryRunDetail.tsx` | Renderer for `foundry_run` schema |
| `web/app/segment/[id]/page.tsx` | Add `foundry_run` branch to dispatcher |

**Mobile — additions:**

| File | Change |
|---|---|
| `mobile/app/(tabs)/status.tsx` (or wherever Status screen lives) | Add 3 more `<SpineStatusTile>` instances |

---

## Task 1: Extend EvaluatorConfig registry with 3 agent segments

**Files:**
- Modify: `backend/src/second_brain/spine/registry.py`
- Create: `backend/tests/test_spine_registry_phase2.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_spine_registry_phase2.py`:

```python
"""Phase 2: registry includes the three Foundry agent segments."""

from second_brain.spine.registry import get_default_registry


def test_registry_includes_classifier() -> None:
    cfg = get_default_registry().get("classifier")
    assert cfg.host_segment == "container_app"
    assert cfg.display_name == "Classifier"
    # Workload thresholds for an agent: more lenient on rate (LLM calls fail more)
    assert cfg.yellow_thresholds.get("workload_failure_rate") == 0.20


def test_registry_includes_admin() -> None:
    cfg = get_default_registry().get("admin")
    assert cfg.host_segment == "container_app"


def test_registry_includes_investigation() -> None:
    cfg = get_default_registry().get("investigation")
    assert cfg.host_segment == "container_app"


def test_all_three_agents_have_red_consecutive_failures_threshold() -> None:
    registry = get_default_registry()
    for sid in ("classifier", "admin", "investigation"):
        cfg = registry.get(sid)
        assert cfg.red_thresholds.get("consecutive_failures") == 3
```

- [ ] **Step 2: Run to verify failure**

```bash
cd backend && uv run pytest tests/test_spine_registry_phase2.py -v
```

Expected: FAIL — `KeyError: 'classifier'`.

- [ ] **Step 3: Add 3 entries to `get_default_registry`**

In `backend/src/second_brain/spine/registry.py`, extend the list returned by `get_default_registry()`:

```python
        EvaluatorConfig(
            segment_id="classifier",
            display_name="Classifier",
            liveness_interval_seconds=30,
            host_segment="container_app",
            workload_window_seconds=300,
            yellow_thresholds={
                "workload_failure_rate": 0.20,  # LLM calls flake more than HTTP
                "any_readiness_failed": True,
            },
            red_thresholds={
                "workload_failure_rate": 0.50,
                "consecutive_failures": 3,
            },
        ),
        EvaluatorConfig(
            segment_id="admin",
            display_name="Admin Agent",
            liveness_interval_seconds=30,
            host_segment="container_app",
            workload_window_seconds=300,
            yellow_thresholds={
                "workload_failure_rate": 0.20,
                "any_readiness_failed": True,
            },
            red_thresholds={
                "workload_failure_rate": 0.50,
                "consecutive_failures": 3,
            },
        ),
        EvaluatorConfig(
            segment_id="investigation",
            display_name="Investigation Agent",
            liveness_interval_seconds=30,
            host_segment="container_app",
            workload_window_seconds=300,
            yellow_thresholds={
                "workload_failure_rate": 0.20,
                "any_readiness_failed": True,
            },
            red_thresholds={
                "workload_failure_rate": 0.50,
                "consecutive_failures": 3,
            },
        ),
```

- [ ] **Step 4: Verify tests pass**

```bash
cd backend && uv run pytest tests/test_spine_registry_phase2.py tests/test_spine_registry.py -v
```

Expected: PASS — both old and new tests green.

- [ ] **Step 5: Commit**

```bash
git add backend/src/second_brain/spine/registry.py backend/tests/test_spine_registry_phase2.py
git commit -m "feat(spine): register classifier, admin, investigation segments"
```

---

## Task 2: Agent emitter helper

**Files:**
- Create: `backend/src/second_brain/spine/agent_emitter.py`
- Test: `backend/tests/test_spine_agent_emitter.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_spine_agent_emitter.py`:

```python
"""Tests for the agent workload-emission helper."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from second_brain.spine.agent_emitter import emit_agent_workload


@pytest.mark.asyncio
async def test_emit_agent_workload_with_capture_correlation() -> None:
    repo = AsyncMock()
    await emit_agent_workload(
        repo=repo,
        segment_id="classifier",
        operation="classify",
        outcome="success",
        duration_ms=234,
        capture_trace_id="trace-1",
        run_id="run-abc",
        thread_id="thr-xyz",
    )
    repo.record_event.assert_called_once()
    event = repo.record_event.call_args.args[0]
    assert event.segment_id == "classifier"
    assert event.event_type == "workload"
    # Capture wins as primary correlation when present
    assert event.payload.correlation_kind == "capture"
    assert event.payload.correlation_id == "trace-1"


@pytest.mark.asyncio
async def test_emit_agent_workload_thread_correlation_when_no_capture() -> None:
    repo = AsyncMock()
    await emit_agent_workload(
        repo=repo,
        segment_id="investigation",
        operation="answer_question",
        outcome="success",
        duration_ms=4000,
        capture_trace_id=None,
        run_id="run-abc",
        thread_id="thr-xyz",
    )
    event = repo.record_event.call_args.args[0]
    # Thread is the primary correlation for investigation when no capture
    assert event.payload.correlation_kind == "thread"
    assert event.payload.correlation_id == "thr-xyz"


@pytest.mark.asyncio
async def test_emit_agent_workload_failure_includes_error_class() -> None:
    repo = AsyncMock()
    await emit_agent_workload(
        repo=repo,
        segment_id="classifier",
        operation="classify",
        outcome="failure",
        duration_ms=100,
        capture_trace_id="trace-1",
        run_id="run-abc",
        thread_id=None,
        error_class="HttpResponseError",
    )
    event = repo.record_event.call_args.args[0]
    assert event.payload.error_class == "HttpResponseError"


@pytest.mark.asyncio
async def test_emit_agent_workload_never_raises_on_repo_failure() -> None:
    repo = AsyncMock()
    repo.record_event.side_effect = RuntimeError("cosmos down")
    # Must not propagate — spine failure must never break the caller
    await emit_agent_workload(
        repo=repo,
        segment_id="classifier",
        operation="classify",
        outcome="success",
        duration_ms=10,
        capture_trace_id="trace-1",
        run_id=None,
        thread_id=None,
    )
```

- [ ] **Step 2: Run to verify failure**

```bash
cd backend && uv run pytest tests/test_spine_agent_emitter.py -v
```

Expected: FAIL — `ImportError: cannot import name 'emit_agent_workload'`.

- [ ] **Step 3: Implement emitter**

Create `backend/src/second_brain/spine/agent_emitter.py`:

```python
"""Helper for emitting workload events from agent wrappers.

Correlation kind precedence:
  capture > thread > request > crud
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Literal

from second_brain.spine.models import (
    CorrelationKind,
    WorkloadPayload,
    _WorkloadEvent,
)
from second_brain.spine.storage import SpineRepository

logger = logging.getLogger(__name__)

Outcome = Literal["success", "failure", "degraded"]


async def emit_agent_workload(
    repo: SpineRepository,
    segment_id: str,
    operation: str,
    outcome: Outcome,
    duration_ms: int,
    capture_trace_id: str | None,
    run_id: str | None,
    thread_id: str | None,
    error_class: str | None = None,
) -> None:
    """Emit a single workload event for an agent invocation.

    Choose the most-specific correlation: capture wins when present,
    else thread, else none. run_id is recorded in metadata via
    operation suffix so it remains queryable in App Insights spans
    (which we already own — no Foundry Runs API dependency).
    """
    correlation_kind: CorrelationKind | None
    correlation_id: str | None
    if capture_trace_id:
        correlation_kind = "capture"
        correlation_id = capture_trace_id
    elif thread_id:
        correlation_kind = "thread"
        correlation_id = thread_id
    else:
        correlation_kind = None
        correlation_id = None

    op_suffix = f" run={run_id}" if run_id else ""
    event = _WorkloadEvent(
        segment_id=segment_id,
        event_type="workload",
        timestamp=datetime.now(timezone.utc),
        payload=WorkloadPayload(
            operation=f"{operation}{op_suffix}",
            outcome=outcome,
            duration_ms=duration_ms,
            correlation_kind=correlation_kind,
            correlation_id=correlation_id,
            error_class=error_class,
        ),
    )
    try:
        await repo.record_event(event)
    except Exception:  # noqa: BLE001 — never propagate
        logger.warning("emit_agent_workload failed", exc_info=True)
```

- [ ] **Step 4: Verify tests pass**

```bash
cd backend && uv run pytest tests/test_spine_agent_emitter.py -v
```

Expected: PASS — all 4 tests.

- [ ] **Step 5: Commit**

```bash
git add backend/src/second_brain/spine/agent_emitter.py backend/tests/test_spine_agent_emitter.py
git commit -m "feat(spine): agent workload emitter with capture>thread correlation"
```

---

## Task 3: Foundry-agent pull adapter

**Files:**
- Create: `backend/src/second_brain/spine/adapters/foundry_agent.py`
- Test: `backend/tests/test_spine_foundry_adapter.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_spine_foundry_adapter.py`:

```python
"""Tests for the Foundry-agent pull adapter (joins by run_id/thread_id)."""

from unittest.mock import AsyncMock

import pytest

from second_brain.spine.adapters.foundry_agent import FoundryAgentAdapter


@pytest.mark.asyncio
async def test_fetch_detail_returns_foundry_run_schema() -> None:
    spans_query = AsyncMock(return_value=[])
    adapter = FoundryAgentAdapter(
        segment_id="classifier",
        agent_id="asst_1",
        agent_name="Classifier",
        spans_fetcher=spans_query,
        native_url_template="https://ai.azure.com/build/agents/asst_1",
    )
    result = await adapter.fetch_detail()
    assert result["schema"] == "foundry_run"
    assert result["agent_id"] == "asst_1"
    assert result["agent_name"] == "Classifier"
    assert "agent_runs" in result
    assert result["native_url"] == "https://ai.azure.com/build/agents/asst_1"


@pytest.mark.asyncio
async def test_fetch_detail_with_thread_correlation_filters_spans() -> None:
    spans_query = AsyncMock(return_value=[
        {"thread_id": "thr-1", "run_id": "run-1", "duration_ms": 1234, "outcome": "success"}
    ])
    adapter = FoundryAgentAdapter(
        segment_id="investigation",
        agent_id="asst_2",
        agent_name="Investigation",
        spans_fetcher=spans_query,
        native_url_template="https://ai.azure.com/build/agents/asst_2",
    )
    result = await adapter.fetch_detail(
        correlation_kind="thread", correlation_id="thr-1",
    )
    spans_query.assert_called_once()
    call_kwargs = spans_query.call_args.kwargs
    assert call_kwargs.get("thread_id") == "thr-1"
    assert len(result["agent_runs"]) == 1


@pytest.mark.asyncio
async def test_fetch_detail_with_capture_correlation_passes_capture_filter() -> None:
    spans_query = AsyncMock(return_value=[])
    adapter = FoundryAgentAdapter(
        segment_id="classifier",
        agent_id="asst_1",
        agent_name="Classifier",
        spans_fetcher=spans_query,
        native_url_template="x",
    )
    await adapter.fetch_detail(
        correlation_kind="capture", correlation_id="trace-1",
    )
    call_kwargs = spans_query.call_args.kwargs
    assert call_kwargs.get("capture_trace_id") == "trace-1"
```

- [ ] **Step 2: Run to verify failure**

```bash
cd backend && uv run pytest tests/test_spine_foundry_adapter.py -v
```

Expected: FAIL — `ImportError`.

- [ ] **Step 3: Implement adapter**

Create `backend/src/second_brain/spine/adapters/foundry_agent.py`:

```python
"""Foundry-agent segment adapter — joins App Insights spans by run_id/thread_id.

Does NOT depend on Foundry Runs API metadata filtering. Uses the IDs we
already generate and store on our own OTel spans.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from second_brain.spine.models import CorrelationKind


class FoundryAgentAdapter:
    """Pulls agent-run details by joining App Insights spans on run_id/thread_id."""

    def __init__(
        self,
        segment_id: str,
        agent_id: str,
        agent_name: str,
        spans_fetcher: Callable[..., Awaitable[list[dict[str, Any]]]],
        native_url_template: str,
    ) -> None:
        self.segment_id = segment_id
        self._agent_id = agent_id
        self._agent_name = agent_name
        self._spans = spans_fetcher
        self.native_url_template = native_url_template

    async def fetch_detail(
        self,
        correlation_kind: CorrelationKind | None = None,
        correlation_id: str | None = None,
        time_range_seconds: int = 3600,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "agent_id": self._agent_id,
            "time_range_seconds": time_range_seconds,
        }
        if correlation_kind == "capture" and correlation_id:
            kwargs["capture_trace_id"] = correlation_id
        elif correlation_kind == "thread" and correlation_id:
            kwargs["thread_id"] = correlation_id

        runs = await self._spans(**kwargs)
        return {
            "schema": "foundry_run",
            "agent_id": self._agent_id,
            "agent_name": self._agent_name,
            "agent_runs": runs,
            "native_url": self.native_url_template,
        }
```

- [ ] **Step 4: Verify tests pass**

```bash
cd backend && uv run pytest tests/test_spine_foundry_adapter.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/second_brain/spine/adapters/foundry_agent.py backend/tests/test_spine_foundry_adapter.py
git commit -m "feat(spine): foundry-agent adapter joins app insights spans by run_id/thread_id"
```

---

## Task 4: Add agent-spans KQL fetcher

**Files:**
- Modify: `backend/src/second_brain/observability/kql_templates.py`
- Modify: `backend/src/second_brain/observability/queries.py`

- [ ] **Step 1: Add new KQL template `AGENT_RUNS_BY_AGENT_ID`**

In `backend/src/second_brain/observability/kql_templates.py` append:

```python
# ---------------------------------------------------------------------------
# Agent Runs by agent_id (Phase 2: Foundry-agent adapter)
# ---------------------------------------------------------------------------
# Returns recent agent_run spans with optional capture_trace_id and thread_id filters.
# {agent_filter} is a KQL conjunct like '| where tostring(Properties.agent_id) == "asst_1"'
# {capture_filter} is similar for capture_trace_id
# {thread_filter} is similar for thread_id
# {limit} is the row limit (default 20)

AGENT_RUNS = """\
AppDependencies
| where Name endswith "_agent_run"
{agent_filter}
{capture_filter}
{thread_filter}
| project
    timestamp = TimeGenerated,
    name = Name,
    duration_ms = DurationMs,
    success = Success,
    result_code = ResultCode,
    agent_id = tostring(Properties.agent_id),
    agent_name = tostring(Properties.agent_name),
    run_id = tostring(Properties.run_id),
    thread_id = tostring(Properties.foundry_thread_id),
    capture_trace_id = tostring(Properties.capture_trace_id),
    operation_id = OperationId
| order by timestamp desc
| take {limit}
"""
```

- [ ] **Step 2: Add `fetch_agent_runs` function in queries.py**

In `backend/src/second_brain/observability/queries.py`, add:

```python
from second_brain.observability.kql_templates import AGENT_RUNS

async def fetch_agent_runs(
    client: LogsQueryClient,
    workspace_id: str,
    agent_id: str,
    time_range_seconds: int = 3600,
    capture_trace_id: str | None = None,
    thread_id: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Fetch recent agent_run spans, optionally filtered by capture or thread.

    Returns raw row dicts (no Pydantic model — adapter returns raw JSON
    to MCP/web for native-shape rendering).
    """
    agent_filter = f'| where tostring(Properties.agent_id) == "{agent_id}"'
    capture_filter = (
        f'| where tostring(Properties.capture_trace_id) == "{capture_trace_id}"'
        if capture_trace_id else ""
    )
    thread_filter = (
        f'| where tostring(Properties.foundry_thread_id) == "{thread_id}"'
        if thread_id else ""
    )
    query = AGENT_RUNS.format(
        agent_filter=agent_filter,
        capture_filter=capture_filter,
        thread_filter=thread_filter,
        limit=limit,
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
    rows: list[dict] = []
    for row in table.rows:
        rows.append({col: val for col, val in zip(table.columns, row, strict=False)})
    return rows
```

(Existing `from datetime import timedelta` already present at top — verify.)

- [ ] **Step 3: Quick test that the formatter produces parseable KQL**

Inline test (or extend `test_kql_projections.py`):

```python
def test_agent_runs_template_filters_compose() -> None:
    from second_brain.observability.kql_templates import AGENT_RUNS

    rendered = AGENT_RUNS.format(
        agent_filter='| where tostring(Properties.agent_id) == "asst_1"',
        capture_filter="",
        thread_filter='| where tostring(Properties.foundry_thread_id) == "thr-1"',
        limit=20,
    )
    assert "asst_1" in rendered
    assert "thr-1" in rendered
    assert "Properties.foundry_thread_id" in rendered
```

Add to `backend/tests/test_kql_projections.py` (created in Phase 1 Task 7).

```bash
cd backend && uv run pytest tests/test_kql_projections.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/src/second_brain/observability/kql_templates.py backend/src/second_brain/observability/queries.py backend/tests/test_kql_projections.py
git commit -m "feat(observability): agent_runs KQL template + fetcher for foundry adapter"
```

---

## Task 5: Wrap Classifier agent calls with workload emission

**Files:**
- Modify: `backend/src/second_brain/agents/classifier.py` (verify path)

- [ ] **Step 1: Locate the classifier call site**

```bash
grep -n "async def classify\|async def run\|agent.run\|agents_client.runs" backend/src/second_brain/agents/classifier.py | head -10
```

Identify the function that performs the classification call (the one wrapped by OTel middleware).

- [ ] **Step 2: Read the surrounding context**

Read 30 lines around the call site to understand how `capture_trace_id`, `run_id`, and `thread_id` are accessible (typically: `capture_trace_id` from a ContextVar, `run_id` from the agent SDK response, `thread_id` from the thread object).

- [ ] **Step 3: Wrap the call with emission**

Replace the existing call structure with:

```python
import time
from second_brain.spine.agent_emitter import emit_agent_workload
from second_brain.spine.storage import SpineRepository

# Existing imports remain. SpineRepository must be threaded in via DI
# (typically attached to app.state and passed through to the agent service).

async def classify(self, text: str, ..., spine_repo: SpineRepository) -> ClassificationResult:
    start = time.perf_counter()
    capture_trace_id = capture_trace_id_var.get()  # existing ContextVar
    run_id: str | None = None
    thread_id: str | None = None
    error_class: str | None = None
    outcome = "success"
    try:
        # ... existing classify logic that yields run_id and thread_id ...
        result = await self._do_classify(text, ...)
        run_id = result.run_id  # adjust to actual attribute name
        thread_id = result.thread_id
        return result
    except Exception as exc:
        outcome = "failure"
        error_class = type(exc).__name__
        raise
    finally:
        duration_ms = int((time.perf_counter() - start) * 1000)
        await emit_agent_workload(
            repo=spine_repo,
            segment_id="classifier",
            operation="classify",
            outcome=outcome,
            duration_ms=duration_ms,
            capture_trace_id=capture_trace_id,
            run_id=run_id,
            thread_id=thread_id,
            error_class=error_class,
        )
```

If the agent doesn't currently receive `spine_repo`, add it to its constructor and update `main.py` instantiation.

- [ ] **Step 4: Run existing classifier tests**

```bash
cd backend && uv run pytest tests/test_classifier_integration.py -v
```

Expected: still pass. If they don't compile due to the new constructor arg, update fixtures to pass a mocked `SpineRepository`.

- [ ] **Step 5: Commit**

```bash
git add backend/src/second_brain/agents/classifier.py backend/tests/test_classifier_integration.py
git commit -m "feat(spine): emit workload events from classifier agent"
```

---

## Task 6: Wrap Admin agent calls

**Files:**
- Modify: `backend/src/second_brain/agents/admin.py` (verify path)

Mirror Task 5. The admin agent's wrapped call typically lives in `agents/admin.py`. Same pattern:
- Add `spine_repo` arg
- Wrap the agent invocation in try/except/finally
- Emit workload event with `segment_id="admin"`, run_id/thread_id from response, capture_trace_id from ContextVar (admin agent processes inbox items that have a capture_trace_id from the original capture)

- [ ] **Step 1: Locate admin call site**
- [ ] **Step 2: Read context**
- [ ] **Step 3: Wrap with `emit_agent_workload(segment_id="admin", ...)`**
- [ ] **Step 4: Run admin tests:** `cd backend && uv run pytest tests/test_admin_integration.py -v`
- [ ] **Step 5: Commit**

```bash
git add backend/src/second_brain/agents/admin.py backend/tests/test_admin_integration.py
git commit -m "feat(spine): emit workload events from admin agent"
```

---

## Task 7: Wrap Investigation agent calls

**Files:**
- Modify: `backend/src/second_brain/agents/investigation.py` (verify path) OR `backend/src/second_brain/streaming/investigation_adapter.py` (more likely the right surface)

Investigation is thread-shaped, not capture-shaped. Use `thread_id` as the primary correlation when no capture is present (the emitter handles this precedence automatically).

- [ ] **Step 1: Locate investigation invocation**

```bash
grep -n "async def\|agents_client.runs\|investigation_agent" backend/src/second_brain/streaming/investigation_adapter.py
```

- [ ] **Step 2: Wrap with `emit_agent_workload(segment_id="investigation", ...)`**

The investigation agent's wrapped call is the one whose timeout was reduced to 30s in Phase 17.4. Wrap that whole stream in try/except/finally and emit at completion.

- [ ] **Step 3: Run tests**

```bash
cd backend && uv run pytest tests/test_investigation_client.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/second_brain/streaming/investigation_adapter.py backend/tests/test_investigation_client.py
git commit -m "feat(spine): emit workload events from investigation agent"
```

---

## Task 8: Register 3 Foundry adapters + 3 liveness emitters in main.py

**Files:**
- Modify: `backend/src/second_brain/main.py`

- [ ] **Step 1: In the lifespan, after Phase 1 wiring, add:**

```python
from second_brain.spine.adapters.foundry_agent import FoundryAgentAdapter
from second_brain.observability.queries import fetch_agent_runs

# Bind the spans fetcher to the existing log client + workspace id.
# Use the same client/workspace_id used by other observability fetchers.
async def _spans_fetcher(**kwargs):
    return await fetch_agent_runs(
        client=log_client,           # existing LogsQueryClient instance
        workspace_id=workspace_id,    # existing config value
        **kwargs,
    )

# Configuration: agent IDs from existing config / env (already known)
CLASSIFIER_AGENT_ID = settings.classifier_agent_id  # existing setting
ADMIN_AGENT_ID = settings.admin_agent_id            # existing setting
INVESTIGATION_AGENT_ID = settings.investigation_agent_id

classifier_adapter = FoundryAgentAdapter(
    segment_id="classifier",
    agent_id=CLASSIFIER_AGENT_ID,
    agent_name="Classifier",
    spans_fetcher=_spans_fetcher,
    native_url_template=f"https://ai.azure.com/build/agents/{CLASSIFIER_AGENT_ID}",
)
admin_adapter = FoundryAgentAdapter(
    segment_id="admin",
    agent_id=ADMIN_AGENT_ID,
    agent_name="Admin Agent",
    spans_fetcher=_spans_fetcher,
    native_url_template=f"https://ai.azure.com/build/agents/{ADMIN_AGENT_ID}",
)
investigation_adapter = FoundryAgentAdapter(
    segment_id="investigation",
    agent_id=INVESTIGATION_AGENT_ID,
    agent_name="Investigation Agent",
    spans_fetcher=_spans_fetcher,
    native_url_template=f"https://ai.azure.com/build/agents/{INVESTIGATION_AGENT_ID}",
)

# Update adapter_registry to include them
adapter_registry = AdapterRegistry([
    backend_api_adapter,  # from Phase 1
    classifier_adapter,
    admin_adapter,
    investigation_adapter,
])

# Add 3 more liveness emitters
classifier_liveness_task = asyncio.create_task(
    liveness_emitter(spine_repo, segment_id="classifier")
)
admin_liveness_task = asyncio.create_task(
    liveness_emitter(spine_repo, segment_id="admin")
)
investigation_liveness_task = asyncio.create_task(
    liveness_emitter(spine_repo, segment_id="investigation")
)

# Cancel them on shutdown alongside the others
```

If your `Settings` class doesn't yet expose all 3 agent IDs, add them. Investigation agent ID is `asst_5feSWWTMA8rBSUyQo6aSCsEJ` per project memory.

- [ ] **Step 2: Update Phase 17.4 health check to feed readiness events**

The existing active health check (`backend/src/second_brain/api/health.py`) already pings Foundry. Wrap each successful/failed ping in a readiness event:

```python
from second_brain.spine.models import _ReadinessEvent, ReadinessPayload, ReadinessCheck

async def _ping_and_record(segment_id: str, agent_id: str, repo: SpineRepository) -> None:
    try:
        await foundry_client.agents_client.get_agent(agent_id, timeout=5)
        check = ReadinessCheck(name="foundry", status="ok")
    except Exception as exc:
        check = ReadinessCheck(name="foundry", status="failing", detail=str(exc)[:200])
    event = _ReadinessEvent(
        segment_id=segment_id,
        event_type="readiness",
        timestamp=datetime.now(timezone.utc),
        payload=ReadinessPayload(checks=[check]),
    )
    try:
        await repo.record_event(event)
    except Exception:
        logger.warning("Readiness event record failed", exc_info=True)
```

Wire this into the existing health-check schedule for each of the 3 agents.

- [ ] **Step 3: Run all backend tests**

```bash
cd backend && uv run pytest -x
```

Expected: PASS.

- [ ] **Step 4: Commit + push**

```bash
git add backend/src/second_brain/main.py backend/src/second_brain/api/health.py
git commit -m "feat(spine): wire 3 agent adapters and liveness emitters"
git push
```

After deploy, verify:

```bash
curl -sS -H "Authorization: Bearer ${API_KEY}" https://brain.willmacdonald.com/api/spine/status | jq '.segments[].id'
```

Expected: 5 segments — `backend_api`, `classifier`, `admin`, `investigation`, `container_app`.

---

## Task 9: Web FoundryRunDetail renderer + dispatcher branch

**Files:**
- Create: `web/components/renderers/FoundryRunDetail.tsx`
- Modify: `web/app/segment/[id]/page.tsx`

- [ ] **Step 1: Create the renderer**

`web/components/renderers/FoundryRunDetail.tsx`:

```typescript
interface FoundryRun {
  timestamp: string;
  name: string;
  duration_ms: number;
  success: boolean;
  result_code: string;
  agent_id: string;
  agent_name: string;
  run_id: string;
  thread_id: string;
  capture_trace_id: string;
  operation_id: string;
}

interface FoundryRunData {
  schema: "foundry_run";
  agent_id: string;
  agent_name: string;
  agent_runs: FoundryRun[];
  native_url: string;
}

export function FoundryRunDetail({ data }: { data: FoundryRunData }) {
  return (
    <div>
      <h2>{data.agent_name} runs ({data.agent_runs.length})</h2>
      <p style={{ color: "#888", fontSize: 13 }}>Agent ID: <code>{data.agent_id}</code></p>
      {data.agent_runs.length === 0 ? (
        <p style={{ color: "#888" }}>No recent runs.</p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0 }}>
          {data.agent_runs.map((r, i) => (
            <li key={i} style={{ background: "#1a2028", padding: 12, marginBottom: 8, borderRadius: 6 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <div>
                  <strong>{r.name}</strong>
                  <span style={{ marginLeft: 12, color: r.success ? "#3a7d3a" : "#b33b3b", fontSize: 12 }}>
                    {r.success ? "✓" : "✗"} {r.result_code}
                  </span>
                </div>
                <span style={{ color: "#888", fontSize: 12 }}>{r.duration_ms}ms</span>
              </div>
              <div style={{ color: "#888", fontSize: 12, marginTop: 4 }}>
                {new Date(r.timestamp).toLocaleString()}
              </div>
              <div style={{ color: "#666", fontSize: 11, marginTop: 4, fontFamily: "monospace" }}>
                run={r.run_id}
                {r.thread_id && <> · thread={r.thread_id}</>}
                {r.capture_trace_id && <> · trace={r.capture_trace_id.slice(0, 8)}</>}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Add dispatcher branch**

Modify `web/app/segment/[id]/page.tsx`. Add import and conditional branch:

```typescript
import { FoundryRunDetail } from "@/components/renderers/FoundryRunDetail";

// ...
{schema === "azure_monitor_app_insights" ? (
  <AppInsightsDetail data={detail.data as never} />
) : schema === "foundry_run" ? (
  <FoundryRunDetail data={detail.data as never} />
) : (
  <p>No renderer registered for schema: <code>{schema}</code></p>
)}
```

- [ ] **Step 3: Type-check + commit**

```bash
cd web && npm run type-check
```

Expected: no errors.

```bash
git add web/components/renderers/FoundryRunDetail.tsx web/app/segment/[id]/page.tsx
git commit -m "feat(web): foundry run renderer + dispatcher branch"
```

- [ ] **Step 4: Push, deploy, verify**

After CI deploys, open the web spine and click each agent's tile. Verify recent runs render with `run_id`, `thread_id`, `capture_trace_id`, durations, and success indicators.

---

## Task 10: Mobile — 3 more spine tiles

**Files:**
- Modify: `mobile/app/<status-screen-file>.tsx`

- [ ] **Step 1: Add 3 new tile mounts**

```typescript
<SpineStatusTile segmentId="backend_api" />
<SpineStatusTile segmentId="classifier" />
<SpineStatusTile segmentId="admin" />
<SpineStatusTile segmentId="investigation" />
```

- [ ] **Step 2: Type-check + EAS rebuild**

```bash
cd mobile && npx tsc --noEmit
```

Then EAS rebuild as in Phase 1 Task 18.

- [ ] **Step 3: Verify on device**

All 4 spine tiles visible. Tap each → opens correct web detail page.

- [ ] **Step 4: Commit**

```bash
git add mobile/app/<status-screen-file>.tsx
git commit -m "feat(mobile): add classifier, admin, investigation spine tiles"
```

---

## Task 11: Phase 2 acceptance verification

- [ ] **Step 1: Backend tests pass:** `cd backend && uv run pytest -x`
- [ ] **Step 2: Web type-check passes:** `cd web && npm run type-check`
- [ ] **Step 3: Mobile type-check passes:** `cd mobile && npx tsc --noEmit`
- [ ] **Step 4: Status endpoint shows 5 segments**

```bash
curl -sS -H "Authorization: Bearer ${API_KEY}" https://brain.willmacdonald.com/api/spine/status \
  | jq '.segments | length'
```

Expected: `5`.

- [ ] **Step 5: Each agent segment returns a `foundry_run` schema response**

```bash
for s in classifier admin investigation; do
  echo "=== $s ==="
  curl -sS -H "Authorization: Bearer ${API_KEY}" "https://brain.willmacdonald.com/api/spine/segment/$s" \
    | jq '.data.schema'
done
```

Expected: 3 lines of `"foundry_run"`.

- [ ] **Step 6: Trigger a capture on the device, then query its correlation**

After capturing a voice/text note on mobile, find the trace ID and:

```bash
TRACE_ID=<from device toast>
curl -sS -H "Authorization: Bearer ${API_KEY}" "https://brain.willmacdonald.com/api/spine/correlation/capture/${TRACE_ID}" \
  | jq '.events[].segment_id'
```

Expected: at least `backend_api` and `classifier` appear (admin only if classifier routed to Admin bucket).

- [ ] **Step 7: Web FoundryRunDetail renders with real data** for each agent

- [ ] **Step 8: Tag**

```bash
git tag phase-2-agent-segments -m "Phase 2 complete: classifier, admin, investigation segments"
git push --tags
```
