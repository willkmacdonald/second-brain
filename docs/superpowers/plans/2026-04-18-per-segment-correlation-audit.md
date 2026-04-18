# Per-Segment Correlation Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an MCP tool `audit_correlation` that walks the expected segment chain for a correlation_id (or a sample of recent ones) and reports whether spine events line up with what native sources actually saw.

**Architecture:** New `spine.audit` package in the backend exposes a `CorrelationAuditor` that runs three checks per trace (correlation integrity, mis-attribution, bounded under-reporting). Surfaced via a new `POST /api/spine/audit/correlation` endpoint. Thin MCP wrapper in `mcp/server.py` calls the endpoint over HTTP using the existing API-key auth. No new Cosmos containers — every call is fresh against existing `spine_correlation` + `spine_events` + native (App Insights, Cosmos diagnostic logs) sources.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, asyncio, azure-monitor-query (Log Analytics), azure-cosmos (aio), MCP server (FastMCP, stdio).

**Spec reference:** `docs/superpowers/specs/2026-04-18-per-segment-correlation-audit-design.md`

---

## File Structure

**Backend — new `spine.audit` package:**

| File | Responsibility |
|---|---|
| `backend/src/second_brain/spine/audit/__init__.py` | Package marker + public re-exports |
| `backend/src/second_brain/spine/audit/chains.py` | `EXPECTED_CHAINS` constant + `ExpectedSegment` dataclass |
| `backend/src/second_brain/spine/audit/models.py` | Pydantic response models (`AuditReport`, `TraceAudit`, `Misattribution`, `OrphanReport`, `AuditSummary`, `TimeWindow`) |
| `backend/src/second_brain/spine/audit/native_lookup.py` | Three thin native-source adapters with KQL helpers |
| `backend/src/second_brain/spine/audit/walker.py` | `CorrelationAuditor` — runs the three checks per trace + sample mode |

**Backend — modifications:**

| File | Change |
|---|---|
| `backend/src/second_brain/spine/storage.py` | Add `get_recent_correlation_ids(kind, time_range_seconds, limit)` for sample mode |
| `backend/src/second_brain/spine/api.py` | Add `POST /api/spine/audit/correlation` endpoint |
| `backend/src/second_brain/main.py` | Wire `CorrelationAuditor` into the spine router builder |
| `backend/src/second_brain/observability/kql_templates.py` | Add three new templates: `AUDIT_SPANS_BY_CORRELATION`, `AUDIT_EXCEPTIONS_BY_CORRELATION`, `AUDIT_COSMOS_BY_CORRELATION` |
| `backend/src/second_brain/observability/queries.py` | Add three matching async query functions |

**MCP server — modifications:**

| File | Change |
|---|---|
| `mcp/server.py` | Add `audit_correlation` tool that calls the spine endpoint and returns the parsed response |

**Tests — new:**

| File | Responsibility |
|---|---|
| `backend/tests/test_audit_chains.py` | Unit tests for `EXPECTED_CHAINS` shape + `ExpectedSegment` dataclass |
| `backend/tests/test_audit_walker.py` | Unit tests for `CorrelationAuditor` (12 cases) using synthetic events + mocked native lookup |
| `backend/tests/test_audit_native_lookup.py` | Unit tests for native-lookup adapters (KQL parameterization, response parsing) |
| `backend/tests/test_audit_api.py` | Unit tests for `POST /api/spine/audit/correlation` (request validation, 200 path, 401) |
| `backend/tests/test_audit_integration.py` | Integration test marked `@pytest.mark.integration` — calls the deployed endpoint with a real recent correlation_id |
| `backend/tests/test_audit_mcp_tool.py` | Unit test for the MCP tool wrapper (mocked httpx) |

---

## Conventions

- **Async everywhere.** All native-source queries and Cosmos calls use the async client (`LogsQueryClient.query_workspace`, `azure.cosmos.aio`). Match the existing spine pattern (`storage.py`, `evaluator.py`).
- **Pydantic v2.** Use `BaseModel`, `Field(...)`, `Literal[...]`, `model_dump(mode="json")`. Match `spine/models.py`.
- **Tests:** unit tests use the existing `mock_cosmos_manager` fixture pattern from `backend/tests/conftest.py`. Integration tests use the `@pytest.mark.integration` marker (NOT `@pytest.mark.live` — that marker doesn't exist; see `backend/pyproject.toml`).
- **Type hints required** on every function/method. Match the existing codebase style.
- **No new dependencies.** Everything reuses existing libraries. If you find yourself wanting `pytest-mock`, use `unittest.mock.AsyncMock` instead — it's what the rest of the suite uses.
- **Run tests from the backend directory:** `cd backend && uv run pytest tests/test_<file>.py -v`. The MCP tests run from the repo root: `uv run pytest backend/tests/test_audit_mcp_tool.py -v`.

---

## Task 1: `EXPECTED_CHAINS` and `ExpectedSegment`

**Files:**
- Create: `backend/src/second_brain/spine/audit/__init__.py`
- Create: `backend/src/second_brain/spine/audit/chains.py`
- Create: `backend/tests/test_audit_chains.py`

- [ ] **Step 1: Create the package marker**

Write to `backend/src/second_brain/spine/audit/__init__.py`:

```python
"""Per-segment correlation audit package.

See docs/superpowers/specs/2026-04-18-per-segment-correlation-audit-design.md.
"""
```

- [ ] **Step 2: Write the failing test**

Write to `backend/tests/test_audit_chains.py`:

```python
"""Tests for EXPECTED_CHAINS shape and ExpectedSegment dataclass."""

from __future__ import annotations

import pytest

from second_brain.spine.audit.chains import (
    EXPECTED_CHAINS,
    ExpectedSegment,
    get_expected_chain,
    required_segments,
)


def test_expected_segment_is_frozen_dataclass():
    seg = ExpectedSegment("backend_api", required=True)
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        seg.required = False  # type: ignore[misc]


def test_all_four_kinds_have_chains():
    assert set(EXPECTED_CHAINS) == {"capture", "thread", "request", "crud"}


def test_capture_chain_required_segments():
    chain = EXPECTED_CHAINS["capture"]
    required = [s.segment_id for s in chain if s.required]
    assert required == ["mobile_capture", "backend_api", "classifier"]


def test_capture_chain_optional_segments():
    chain = EXPECTED_CHAINS["capture"]
    optional = [s.segment_id for s in chain if not s.required]
    assert set(optional) == {"admin", "external_services", "cosmos"}


def test_thread_chain():
    chain = EXPECTED_CHAINS["thread"]
    assert [s.segment_id for s in chain if s.required] == [
        "investigation",
        "backend_api",
    ]
    assert [s.segment_id for s in chain if not s.required] == ["cosmos"]


def test_request_chain_cosmos_required():
    """Per spec section 'Expected Segment Chains', cosmos required for request."""
    chain = EXPECTED_CHAINS["request"]
    assert [s.segment_id for s in chain if s.required] == [
        "backend_api",
        "cosmos",
    ]


def test_crud_chain_cosmos_required():
    """Per spec section 'Expected Segment Chains', cosmos required for crud."""
    chain = EXPECTED_CHAINS["crud"]
    required = [s.segment_id for s in chain if s.required]
    assert required == ["mobile_ui", "backend_api", "cosmos"]


def test_get_expected_chain_returns_chain():
    assert get_expected_chain("capture") == EXPECTED_CHAINS["capture"]


def test_required_segments_helper():
    assert required_segments("crud") == ["mobile_ui", "backend_api", "cosmos"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_audit_chains.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'second_brain.spine.audit.chains'`.

- [ ] **Step 4: Write the implementation**

Write to `backend/src/second_brain/spine/audit/chains.py`:

```python
"""Expected segment chains per correlation_kind.

Hardcoded in code (not config) — same principle as the evaluator registry.
When adding a new segment or routing path, update EXPECTED_CHAINS here.
"""

from __future__ import annotations

from dataclasses import dataclass

from second_brain.spine.models import CorrelationKind


@dataclass(frozen=True, slots=True)
class ExpectedSegment:
    """One segment in an expected correlation chain."""

    segment_id: str
    required: bool


EXPECTED_CHAINS: dict[CorrelationKind, list[ExpectedSegment]] = {
    "capture": [
        ExpectedSegment("mobile_capture", required=True),
        ExpectedSegment("backend_api", required=True),
        ExpectedSegment("classifier", required=True),
        ExpectedSegment("admin", required=False),
        ExpectedSegment("external_services", required=False),
        ExpectedSegment("cosmos", required=False),
    ],
    "thread": [
        ExpectedSegment("investigation", required=True),
        ExpectedSegment("backend_api", required=True),
        ExpectedSegment("cosmos", required=False),
    ],
    "request": [
        ExpectedSegment("backend_api", required=True),
        ExpectedSegment("cosmos", required=True),
    ],
    "crud": [
        ExpectedSegment("mobile_ui", required=True),
        ExpectedSegment("backend_api", required=True),
        ExpectedSegment("cosmos", required=True),
    ],
}


def get_expected_chain(kind: CorrelationKind) -> list[ExpectedSegment]:
    """Return the expected segment chain for a correlation kind."""
    return EXPECTED_CHAINS[kind]


def required_segments(kind: CorrelationKind) -> list[str]:
    """Return only the required segment_ids in chain order."""
    return [s.segment_id for s in EXPECTED_CHAINS[kind] if s.required]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_audit_chains.py -v`
Expected: 9 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/src/second_brain/spine/audit/__init__.py \
        backend/src/second_brain/spine/audit/chains.py \
        backend/tests/test_audit_chains.py
git commit -m "feat(audit): expected correlation chains per kind"
```

---

## Task 2: Audit response models

**Files:**
- Create: `backend/src/second_brain/spine/audit/models.py`
- Modify: `backend/tests/test_audit_chains.py` (no — new test file)
- Test: `backend/tests/test_audit_models.py`

- [ ] **Step 1: Write the failing test**

Write to `backend/tests/test_audit_models.py`:

```python
"""Tests for audit Pydantic models — round-trip + verdict helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from second_brain.spine.audit.models import (
    AuditReport,
    AuditSummary,
    Misattribution,
    OrphanReport,
    TimeWindow,
    TraceAudit,
    roll_up_trace_verdict,
)


def test_trace_audit_minimal_round_trip():
    audit = TraceAudit(
        correlation_kind="capture",
        correlation_id="abc-123",
        verdict="clean",
        headline="all green",
        missing_required=[],
        present_optional=[],
        unexpected=[],
        misattributions=[],
        orphans=[],
        trace_window=TimeWindow(
            start=datetime(2026, 4, 18, 12, 0, 0, tzinfo=UTC),
            end=datetime(2026, 4, 18, 12, 0, 30, tzinfo=UTC),
        ),
        native_links={},
    )
    payload = audit.model_dump(mode="json")
    assert payload["correlation_id"] == "abc-123"
    assert payload["verdict"] == "clean"


def test_misattribution_round_trip():
    m = Misattribution(
        segment_id="classifier",
        check="outcome",
        spine_value="success",
        native_value="exception observed",
        reason="spine reports success but App Insights has 1 exception",
    )
    payload = m.model_dump(mode="json")
    assert payload["check"] == "outcome"


def test_orphan_report_round_trip():
    o = OrphanReport(
        segment_id="backend_api",
        orphan_count=3,
        sample_operations=["POST /api/capture", "GET /api/inbox"],
    )
    payload = o.model_dump(mode="json")
    assert payload["orphan_count"] == 3
    assert len(payload["sample_operations"]) == 2


def test_roll_up_clean():
    verdict = roll_up_trace_verdict(
        missing_required=[],
        misattributions=[],
        orphans=[],
        unexpected=[],
    )
    assert verdict == "clean"


def test_roll_up_warn_on_unexpected():
    verdict = roll_up_trace_verdict(
        missing_required=[],
        misattributions=[],
        orphans=[],
        unexpected=["classifier"],
    )
    assert verdict == "warn"


def test_roll_up_warn_on_orphans():
    verdict = roll_up_trace_verdict(
        missing_required=[],
        misattributions=[],
        orphans=[
            OrphanReport(
                segment_id="backend_api", orphan_count=1, sample_operations=["GET /x"]
            )
        ],
        unexpected=[],
    )
    assert verdict == "warn"


def test_roll_up_warn_on_non_outcome_misattribution():
    misattr = Misattribution(
        segment_id="classifier",
        check="operation",
        spine_value="classify_capture",
        native_value="(no matching span)",
        reason="no native span had a matching operation name",
    )
    verdict = roll_up_trace_verdict(
        missing_required=[],
        misattributions=[misattr],
        orphans=[],
        unexpected=[],
    )
    assert verdict == "warn"


def test_roll_up_broken_on_missing_required():
    verdict = roll_up_trace_verdict(
        missing_required=["classifier"],
        misattributions=[],
        orphans=[],
        unexpected=[],
    )
    assert verdict == "broken"


def test_roll_up_broken_on_outcome_misattribution():
    misattr = Misattribution(
        segment_id="classifier",
        check="outcome",
        spine_value="success",
        native_value="2 exceptions in window",
        reason="outcome disagreement",
    )
    verdict = roll_up_trace_verdict(
        missing_required=[],
        misattributions=[misattr],
        orphans=[],
        unexpected=[],
    )
    assert verdict == "broken"


def test_audit_summary_overall_verdict_precedence():
    summary = AuditSummary(
        clean_count=2,
        warn_count=1,
        broken_count=0,
        segments_with_missing_required={},
        segments_with_misattribution={},
        segments_with_orphans={"backend_api": 1},
        overall_verdict="warn",
        headline="1 of 3 traces have orphan operations",
    )
    payload = summary.model_dump(mode="json")
    assert payload["overall_verdict"] == "warn"


def test_audit_report_round_trip():
    report = AuditReport(
        correlation_kind="capture",
        sample_size_requested=5,
        sample_size_returned=3,
        time_range_seconds=86400,
        traces=[],
        summary=AuditSummary(
            clean_count=0,
            warn_count=0,
            broken_count=0,
            segments_with_missing_required={},
            segments_with_misattribution={},
            segments_with_orphans={},
            overall_verdict="clean",
            headline="no traces sampled",
        ),
        instrumentation_warning=None,
    )
    payload = report.model_dump(mode="json")
    assert payload["sample_size_returned"] == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_audit_models.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

Write to `backend/src/second_brain/spine/audit/models.py`:

```python
"""Pydantic models for the audit_correlation MCP tool / spine endpoint.

Verdict precedence per trace:
  - broken: any missing_required OR any misattribution.check == "outcome"
  - warn:   any unexpected OR any non-outcome misattribution OR any orphans
  - clean:  none of the above

Per report: broken > warn > clean across the trace list.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from second_brain.spine.models import CorrelationKind

Verdict = Literal["clean", "warn", "broken"]
MisattributionCheck = Literal["outcome", "operation", "time_window"]


class TimeWindow(BaseModel):
    """Earliest -> latest spine_event timestamp for a single trace."""

    start: datetime
    end: datetime


class Misattribution(BaseModel):
    """One sub-check failure during the mis-attribution check."""

    segment_id: str
    check: MisattributionCheck
    spine_value: str
    native_value: str
    reason: str


class OrphanReport(BaseModel):
    """Per-segment count of native operations with no matching spine event."""

    segment_id: str
    orphan_count: int
    sample_operations: list[str] = Field(default_factory=list)


class TraceAudit(BaseModel):
    """Per-trace audit result."""

    correlation_kind: CorrelationKind
    correlation_id: str
    verdict: Verdict
    headline: str

    missing_required: list[str] = Field(default_factory=list)
    present_optional: list[str] = Field(default_factory=list)
    unexpected: list[str] = Field(default_factory=list)

    misattributions: list[Misattribution] = Field(default_factory=list)
    orphans: list[OrphanReport] = Field(default_factory=list)

    trace_window: TimeWindow
    native_links: dict[str, str] = Field(default_factory=dict)


class AuditSummary(BaseModel):
    """Roll-up across all sampled traces."""

    clean_count: int
    warn_count: int
    broken_count: int

    segments_with_missing_required: dict[str, int] = Field(default_factory=dict)
    segments_with_misattribution: dict[str, int] = Field(default_factory=dict)
    segments_with_orphans: dict[str, int] = Field(default_factory=dict)

    overall_verdict: Verdict
    headline: str


class AuditReport(BaseModel):
    """Top-level response from POST /api/spine/audit/correlation."""

    correlation_kind: CorrelationKind
    sample_size_requested: int
    sample_size_returned: int
    time_range_seconds: int

    traces: list[TraceAudit] = Field(default_factory=list)
    summary: AuditSummary
    instrumentation_warning: str | None = None


def roll_up_trace_verdict(
    *,
    missing_required: list[str],
    misattributions: list[Misattribution],
    orphans: list[OrphanReport],
    unexpected: list[str],
) -> Verdict:
    """Apply the per-trace verdict precedence rules."""
    if missing_required:
        return "broken"
    if any(m.check == "outcome" for m in misattributions):
        return "broken"
    if unexpected or orphans or misattributions:
        return "warn"
    return "clean"


def roll_up_report_verdict(traces: list[TraceAudit]) -> Verdict:
    """Apply the per-report verdict precedence rules."""
    if any(t.verdict == "broken" for t in traces):
        return "broken"
    if any(t.verdict == "warn" for t in traces):
        return "warn"
    return "clean"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_audit_models.py -v`
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/src/second_brain/spine/audit/models.py \
        backend/tests/test_audit_models.py
git commit -m "feat(audit): response models + verdict roll-up rules"
```

---

## Task 3: Native-lookup KQL templates and query functions

This task adds the three KQL templates the audit walker uses to read native sources, plus the matching async query functions.

**Files:**
- Modify: `backend/src/second_brain/observability/kql_templates.py` (append three templates)
- Modify: `backend/src/second_brain/observability/queries.py` (append three async functions)
- Test: `backend/tests/test_audit_native_queries.py`

- [ ] **Step 1: Write the failing test**

Write to `backend/tests/test_audit_native_queries.py`:

```python
"""Tests for the audit native-lookup KQL helpers (parameterization, parsing)."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from azure.monitor.query import LogsQueryStatus

from second_brain.observability.queries import (
    fetch_audit_cosmos_diagnostics_for_correlation,
    fetch_audit_exceptions_for_correlation,
    fetch_audit_spans_for_correlation,
)


def _mock_response(rows: list[dict], columns: list[str]):
    """Return a fake LogsQueryResult-shaped object with one table."""
    table = type(
        "T",
        (),
        {
            "columns": columns,
            "rows": [tuple(r.get(c) for c in columns) for r in rows],
        },
    )()
    return type(
        "R",
        (),
        {
            "status": LogsQueryStatus.SUCCESS,
            "tables": [table],
            "partial_data": None,
            "partial_error": None,
        },
    )()


@pytest.mark.asyncio
async def test_fetch_audit_spans_returns_dicts():
    client = AsyncMock()
    client.query_workspace.return_value = _mock_response(
        rows=[
            {
                "timestamp": "2026-04-18T12:00:00Z",
                "Name": "POST /api/capture",
                "Component": "backend_api",
                "DurationMs": 123.4,
                "ResultCode": "200",
                "CorrelationId": "abc-123",
                "CorrelationKind": "capture",
            }
        ],
        columns=[
            "timestamp",
            "Name",
            "Component",
            "DurationMs",
            "ResultCode",
            "CorrelationId",
            "CorrelationKind",
        ],
    )
    spans = await fetch_audit_spans_for_correlation(
        client,
        workspace_id="ws-123",
        correlation_id="abc-123",
        time_range_seconds=3600,
    )
    assert spans == [
        {
            "timestamp": "2026-04-18T12:00:00Z",
            "Name": "POST /api/capture",
            "Component": "backend_api",
            "DurationMs": 123.4,
            "ResultCode": "200",
            "CorrelationId": "abc-123",
            "CorrelationKind": "capture",
        }
    ]
    sent_query = client.query_workspace.call_args.kwargs["query"]
    assert "abc-123" in sent_query


@pytest.mark.asyncio
async def test_fetch_audit_spans_empty_table_returns_empty_list():
    client = AsyncMock()
    client.query_workspace.return_value = _mock_response(rows=[], columns=["timestamp"])
    assert (
        await fetch_audit_spans_for_correlation(
            client,
            workspace_id="ws-123",
            correlation_id="abc-123",
            time_range_seconds=3600,
        )
        == []
    )


@pytest.mark.asyncio
async def test_fetch_audit_exceptions_round_trip():
    client = AsyncMock()
    client.query_workspace.return_value = _mock_response(
        rows=[
            {
                "timestamp": "2026-04-18T12:00:05Z",
                "Component": "classifier",
                "ExceptionType": "HttpResponseError",
                "OuterMessage": "boom",
                "CorrelationId": "abc-123",
            }
        ],
        columns=[
            "timestamp",
            "Component",
            "ExceptionType",
            "OuterMessage",
            "CorrelationId",
        ],
    )
    exceptions = await fetch_audit_exceptions_for_correlation(
        client,
        workspace_id="ws-123",
        correlation_id="abc-123",
        time_range_seconds=3600,
    )
    assert exceptions[0]["ExceptionType"] == "HttpResponseError"


@pytest.mark.asyncio
async def test_fetch_audit_cosmos_diagnostics_round_trip():
    client = AsyncMock()
    client.query_workspace.return_value = _mock_response(
        rows=[
            {
                "timestamp": "2026-04-18T12:00:00Z",
                "OperationName": "Read",
                "statusCode_s": "200",
                "duration_s": "10.2",
                "activityId_g": "abc-123",
            }
        ],
        columns=[
            "timestamp",
            "OperationName",
            "statusCode_s",
            "duration_s",
            "activityId_g",
        ],
    )
    rows = await fetch_audit_cosmos_diagnostics_for_correlation(
        client,
        workspace_id="ws-123",
        correlation_id="abc-123",
        time_range_seconds=3600,
    )
    assert rows[0]["activityId_g"] == "abc-123"


@pytest.mark.asyncio
async def test_timespan_passed_to_client():
    """Verify the timespan derived from time_range_seconds reaches the client."""
    client = AsyncMock()
    client.query_workspace.return_value = _mock_response(rows=[], columns=["timestamp"])
    await fetch_audit_spans_for_correlation(
        client,
        workspace_id="ws-123",
        correlation_id="abc-123",
        time_range_seconds=600,
    )
    timespan = client.query_workspace.call_args.kwargs["timespan"]
    assert timespan == timedelta(seconds=600)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_audit_native_queries.py -v`
Expected: FAIL with `ImportError: cannot import name 'fetch_audit_spans_for_correlation'`.

- [ ] **Step 3: Append KQL templates**

Append to `backend/src/second_brain/observability/kql_templates.py`:

```python


# ---------------------------------------------------------------------------
# Audit native-lookup templates (per-segment correlation audit, 2026-04-18)
# ---------------------------------------------------------------------------
# All three accept a single {correlation_id} parameter via str.format().
# Timespan is controlled by the query_workspace call (caller-provided).

AUDIT_SPANS_BY_CORRELATION = """\
let cid = "{correlation_id}";
union AppRequests, AppDependencies
| where tostring(Properties.correlation_id) == cid
   or tostring(Properties.capture_trace_id) == cid
| project
    timestamp = TimeGenerated,
    Name,
    Component = tostring(Properties.component),
    DurationMs,
    ResultCode = tostring(ResultCode),
    CorrelationId = coalesce(
        tostring(Properties.correlation_id),
        tostring(Properties.capture_trace_id)
    ),
    CorrelationKind = tostring(Properties.correlation_kind)
| order by timestamp asc
"""

AUDIT_EXCEPTIONS_BY_CORRELATION = """\
let cid = "{correlation_id}";
AppExceptions
| where tostring(Properties.correlation_id) == cid
   or tostring(Properties.capture_trace_id) == cid
| project
    timestamp = TimeGenerated,
    Component = tostring(Properties.component),
    ExceptionType,
    OuterMessage,
    OuterType,
    InnermostMessage,
    Details = tostring(Details),
    CorrelationId = coalesce(
        tostring(Properties.correlation_id),
        tostring(Properties.capture_trace_id)
    )
| order by timestamp asc
"""

AUDIT_COSMOS_BY_CORRELATION = """\
let cid = "{correlation_id}";
AzureDiagnostics
| where Category == "DataPlaneRequests"
| where activityId_g == cid
| project
    timestamp = TimeGenerated,
    OperationName,
    statusCode_s,
    duration_s,
    activityId_g,
    collectionName_s
| order by timestamp asc
"""
```

- [ ] **Step 4: Append the three async query functions**

Append to `backend/src/second_brain/observability/queries.py`:

```python


# ---------------------------------------------------------------------------
# Audit native-lookup query functions (per-segment correlation audit)
# ---------------------------------------------------------------------------


async def fetch_audit_spans_for_correlation(
    client: LogsQueryClient,
    workspace_id: str,
    correlation_id: str,
    time_range_seconds: int,
) -> list[dict]:
    """Return App Insights AppRequests + AppDependencies tagged with correlation_id."""
    from second_brain.observability.kql_templates import AUDIT_SPANS_BY_CORRELATION

    query = AUDIT_SPANS_BY_CORRELATION.format(correlation_id=correlation_id)
    result = await execute_kql(
        client,
        workspace_id,
        query,
        timespan=timedelta(seconds=time_range_seconds),
    )
    if not result.tables or not result.tables[0]:
        return []
    return list(result.tables[0])


async def fetch_audit_exceptions_for_correlation(
    client: LogsQueryClient,
    workspace_id: str,
    correlation_id: str,
    time_range_seconds: int,
) -> list[dict]:
    """Return App Insights AppExceptions tagged with correlation_id."""
    from second_brain.observability.kql_templates import (
        AUDIT_EXCEPTIONS_BY_CORRELATION,
    )

    query = AUDIT_EXCEPTIONS_BY_CORRELATION.format(correlation_id=correlation_id)
    result = await execute_kql(
        client,
        workspace_id,
        query,
        timespan=timedelta(seconds=time_range_seconds),
    )
    if not result.tables or not result.tables[0]:
        return []
    return list(result.tables[0])


async def fetch_audit_cosmos_diagnostics_for_correlation(
    client: LogsQueryClient,
    workspace_id: str,
    correlation_id: str,
    time_range_seconds: int,
) -> list[dict]:
    """Return Cosmos diagnostic-log rows whose activityId_g matches correlation_id."""
    from second_brain.observability.kql_templates import AUDIT_COSMOS_BY_CORRELATION

    query = AUDIT_COSMOS_BY_CORRELATION.format(correlation_id=correlation_id)
    result = await execute_kql(
        client,
        workspace_id,
        query,
        timespan=timedelta(seconds=time_range_seconds),
    )
    if not result.tables or not result.tables[0]:
        return []
    return list(result.tables[0])
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_audit_native_queries.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/src/second_brain/observability/kql_templates.py \
        backend/src/second_brain/observability/queries.py \
        backend/tests/test_audit_native_queries.py
git commit -m "feat(audit): native-lookup KQL templates + query helpers"
```

---

## Task 4: `native_lookup.py` adapter facade

A thin facade that bundles the three query functions behind one object so the walker has a single dependency to mock.

**Files:**
- Create: `backend/src/second_brain/spine/audit/native_lookup.py`
- Test: `backend/tests/test_audit_native_lookup_facade.py`

- [ ] **Step 1: Write the failing test**

Write to `backend/tests/test_audit_native_lookup_facade.py`:

```python
"""Tests for the NativeLookup facade — wiring of the three fetchers."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from second_brain.spine.audit.native_lookup import NativeLookup


@pytest.mark.asyncio
async def test_facade_dispatches_to_each_fetcher():
    spans_fetcher = AsyncMock(return_value=[{"Name": "GET /x"}])
    exceptions_fetcher = AsyncMock(return_value=[{"ExceptionType": "Boom"}])
    cosmos_fetcher = AsyncMock(return_value=[{"OperationName": "Read"}])

    lookup = NativeLookup(
        spans_fetcher=spans_fetcher,
        exceptions_fetcher=exceptions_fetcher,
        cosmos_fetcher=cosmos_fetcher,
    )

    spans = await lookup.spans("abc-123", time_range_seconds=600)
    exceptions = await lookup.exceptions("abc-123", time_range_seconds=600)
    cosmos_rows = await lookup.cosmos("abc-123", time_range_seconds=600)

    assert spans == [{"Name": "GET /x"}]
    assert exceptions == [{"ExceptionType": "Boom"}]
    assert cosmos_rows == [{"OperationName": "Read"}]

    spans_fetcher.assert_called_once_with(
        correlation_id="abc-123", time_range_seconds=600
    )


@pytest.mark.asyncio
async def test_facade_returns_empty_when_lookup_unconfigured():
    """When no fetchers are wired (e.g. logs_client unavailable), return [].

    Lets the audit endpoint stay up even if Log Analytics isn't configured.
    """
    lookup = NativeLookup(
        spans_fetcher=None,
        exceptions_fetcher=None,
        cosmos_fetcher=None,
    )
    assert await lookup.spans("abc", time_range_seconds=600) == []
    assert await lookup.exceptions("abc", time_range_seconds=600) == []
    assert await lookup.cosmos("abc", time_range_seconds=600) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_audit_native_lookup_facade.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

Write to `backend/src/second_brain/spine/audit/native_lookup.py`:

```python
"""Facade for native-source lookups used by the audit walker.

Bundles the three async fetchers behind one object so the walker has a single
dependency to inject and tests have a single mock surface. When a fetcher is
None (e.g. LogsQueryClient unavailable at app startup), the corresponding
method returns an empty list — keeps the audit endpoint from 500-ing in
degraded environments.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

NativeFetcher = Callable[..., Awaitable[list[dict[str, Any]]]]


class NativeLookup:
    """Thin facade around the three native-source query helpers."""

    def __init__(
        self,
        *,
        spans_fetcher: NativeFetcher | None,
        exceptions_fetcher: NativeFetcher | None,
        cosmos_fetcher: NativeFetcher | None,
    ) -> None:
        self._spans = spans_fetcher
        self._exceptions = exceptions_fetcher
        self._cosmos = cosmos_fetcher

    async def spans(
        self, correlation_id: str, *, time_range_seconds: int
    ) -> list[dict[str, Any]]:
        if self._spans is None:
            return []
        return await self._spans(
            correlation_id=correlation_id,
            time_range_seconds=time_range_seconds,
        )

    async def exceptions(
        self, correlation_id: str, *, time_range_seconds: int
    ) -> list[dict[str, Any]]:
        if self._exceptions is None:
            return []
        return await self._exceptions(
            correlation_id=correlation_id,
            time_range_seconds=time_range_seconds,
        )

    async def cosmos(
        self, correlation_id: str, *, time_range_seconds: int
    ) -> list[dict[str, Any]]:
        if self._cosmos is None:
            return []
        return await self._cosmos(
            correlation_id=correlation_id,
            time_range_seconds=time_range_seconds,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_audit_native_lookup_facade.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/src/second_brain/spine/audit/native_lookup.py \
        backend/tests/test_audit_native_lookup_facade.py
git commit -m "feat(audit): NativeLookup facade for the three query helpers"
```

---

## Task 5: `SpineRepository.get_recent_correlation_ids` for sample mode

The walker's sample mode needs the N most-recent correlation_ids of a given kind. Add a repository method.

**Files:**
- Modify: `backend/src/second_brain/spine/storage.py`
- Test: `backend/tests/test_spine_storage_sample_correlation_ids.py`

- [ ] **Step 1: Write the failing test**

Write to `backend/tests/test_spine_storage_sample_correlation_ids.py`:

```python
"""Tests for SpineRepository.get_recent_correlation_ids."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from second_brain.spine.storage import SpineRepository


def _async_iter(items):
    async def _gen():
        for i in items:
            yield i

    return _gen()


@pytest.mark.asyncio
async def test_returns_unique_recent_ids_in_descending_order():
    correlation = MagicMock()
    correlation.query_items = MagicMock(
        return_value=_async_iter(
            [
                {
                    "correlation_id": "id-1",
                    "timestamp": "2026-04-18T12:00:00+00:00",
                },
                {
                    "correlation_id": "id-2",
                    "timestamp": "2026-04-18T12:01:00+00:00",
                },
                {
                    "correlation_id": "id-1",  # duplicate from a different segment
                    "timestamp": "2026-04-18T12:02:00+00:00",
                },
            ]
        )
    )

    repo = SpineRepository(
        events_container=MagicMock(),
        segment_state_container=MagicMock(),
        status_history_container=MagicMock(),
        correlation_container=correlation,
    )

    ids = await repo.get_recent_correlation_ids(
        kind="capture", time_range_seconds=86400, limit=10
    )

    # Most recent first, deduplicated, kind-filtered (caller passes kind).
    assert ids == ["id-1", "id-2"]


@pytest.mark.asyncio
async def test_respects_limit():
    rows = [
        {
            "correlation_id": f"id-{i}",
            "timestamp": f"2026-04-18T12:{i:02d}:00+00:00",
        }
        for i in range(10)
    ]
    correlation = MagicMock()
    correlation.query_items = MagicMock(return_value=_async_iter(rows))

    repo = SpineRepository(
        events_container=MagicMock(),
        segment_state_container=MagicMock(),
        status_history_container=MagicMock(),
        correlation_container=correlation,
    )

    ids = await repo.get_recent_correlation_ids(
        kind="capture", time_range_seconds=86400, limit=3
    )
    assert len(ids) == 3
    assert ids[0] == "id-9"  # most recent first


@pytest.mark.asyncio
async def test_query_uses_kind_and_cutoff():
    correlation = MagicMock()
    correlation.query_items = MagicMock(return_value=_async_iter([]))

    repo = SpineRepository(
        events_container=MagicMock(),
        segment_state_container=MagicMock(),
        status_history_container=MagicMock(),
        correlation_container=correlation,
    )

    await repo.get_recent_correlation_ids(
        kind="thread", time_range_seconds=3600, limit=5
    )

    call = correlation.query_items.call_args
    parameters = {p["name"]: p["value"] for p in call.kwargs["parameters"]}
    assert parameters["@kind"] == "thread"
    assert "@cutoff" in parameters
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_spine_storage_sample_correlation_ids.py -v`
Expected: FAIL with `AttributeError: 'SpineRepository' object has no attribute 'get_recent_correlation_ids'`.

- [ ] **Step 3: Add the method to `SpineRepository`**

Edit `backend/src/second_brain/spine/storage.py`. Append after `get_correlation_events`:

```python
    async def get_recent_correlation_ids(
        self,
        kind: CorrelationKind,
        time_range_seconds: int,
        limit: int,
    ) -> list[str]:
        """Return up to `limit` most-recent unique correlation_ids of `kind`.

        Sorted newest-first. Deduplicated across segments (the same
        correlation_id appears once per (correlation_id, segment_id) tuple in
        the underlying container).
        """
        cutoff = (datetime.now(UTC) - timedelta(seconds=time_range_seconds)).isoformat()

        # Pull rows newest-first; dedupe in Python (Cosmos GROUP BY is restricted
        # in cross-partition queries and we already constrain the result with TTL).
        seen: dict[str, str] = {}
        async for item in self._correlation.query_items(
            query=(
                "SELECT c.correlation_id, c.timestamp FROM c"
                " WHERE c.correlation_kind = @kind AND c.timestamp >= @cutoff"
                " ORDER BY c.timestamp DESC"
            ),
            parameters=[
                {"name": "@kind", "value": kind},
                {"name": "@cutoff", "value": cutoff},
            ],
        ):
            cid = item["correlation_id"]
            if cid not in seen:
                seen[cid] = item["timestamp"]
            if len(seen) >= limit:
                break

        return list(seen.keys())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_spine_storage_sample_correlation_ids.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/src/second_brain/spine/storage.py \
        backend/tests/test_spine_storage_sample_correlation_ids.py
git commit -m "feat(audit): repository helper for sampling recent correlation_ids"
```

---

## Task 6: `CorrelationAuditor` — Check 1 (correlation integrity)

The walker is built up across three tasks (one per check) so each task can be small. Task 6 wires the class skeleton + Check 1.

**Files:**
- Create: `backend/src/second_brain/spine/audit/walker.py`
- Test: `backend/tests/test_audit_walker_integrity.py`

- [ ] **Step 1: Write the failing test**

Write to `backend/tests/test_audit_walker_integrity.py`:

```python
"""Tests for CorrelationAuditor — Check 1 (correlation integrity)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from second_brain.spine.audit.walker import CorrelationAuditor

NOW = datetime(2026, 4, 18, 12, 5, 0, tzinfo=UTC)


def _corr_record(segment_id: str, ts: str = "2026-04-18T12:00:00+00:00"):
    return {
        "correlation_kind": "capture",
        "correlation_id": "abc-123",
        "segment_id": segment_id,
        "timestamp": ts,
        "status": "green",
        "headline": f"{segment_id} ok",
    }


@pytest.mark.asyncio
async def test_clean_chain_no_misattribution_no_orphans():
    repo = AsyncMock()
    repo.get_correlation_events.return_value = [
        _corr_record("mobile_capture"),
        _corr_record("backend_api"),
        _corr_record("classifier"),
    ]
    repo.get_recent_events.return_value = []

    lookup = AsyncMock()
    lookup.spans.return_value = []
    lookup.exceptions.return_value = []
    lookup.cosmos.return_value = []

    auditor = CorrelationAuditor(repo=repo, lookup=lookup, now=lambda: NOW)
    result = await auditor.audit("capture", "abc-123", time_range_seconds=3600)

    assert result.verdict == "clean"
    assert result.missing_required == []
    assert result.unexpected == []


@pytest.mark.asyncio
async def test_missing_required_classifier_marks_broken():
    repo = AsyncMock()
    repo.get_correlation_events.return_value = [
        _corr_record("mobile_capture"),
        _corr_record("backend_api"),
        # classifier missing
    ]
    repo.get_recent_events.return_value = []

    lookup = AsyncMock()
    lookup.spans.return_value = []
    lookup.exceptions.return_value = []
    lookup.cosmos.return_value = []

    auditor = CorrelationAuditor(repo=repo, lookup=lookup, now=lambda: NOW)
    result = await auditor.audit("capture", "abc-123", time_range_seconds=3600)

    assert result.verdict == "broken"
    assert "classifier" in result.missing_required


@pytest.mark.asyncio
async def test_unexpected_segment_marks_warn():
    repo = AsyncMock()
    repo.get_correlation_events.return_value = [
        _corr_record("mobile_capture"),
        _corr_record("backend_api"),
        _corr_record("classifier"),
        _corr_record("some_unknown_segment"),
    ]
    repo.get_recent_events.return_value = []

    lookup = AsyncMock()
    lookup.spans.return_value = []
    lookup.exceptions.return_value = []
    lookup.cosmos.return_value = []

    auditor = CorrelationAuditor(repo=repo, lookup=lookup, now=lambda: NOW)
    result = await auditor.audit("capture", "abc-123", time_range_seconds=3600)

    assert "some_unknown_segment" in result.unexpected
    assert result.verdict == "warn"


@pytest.mark.asyncio
async def test_present_optional_listed():
    repo = AsyncMock()
    repo.get_correlation_events.return_value = [
        _corr_record("mobile_capture"),
        _corr_record("backend_api"),
        _corr_record("classifier"),
        _corr_record("admin"),
    ]
    repo.get_recent_events.return_value = []

    lookup = AsyncMock()
    lookup.spans.return_value = []
    lookup.exceptions.return_value = []
    lookup.cosmos.return_value = []

    auditor = CorrelationAuditor(repo=repo, lookup=lookup, now=lambda: NOW)
    result = await auditor.audit("capture", "abc-123", time_range_seconds=3600)

    assert "admin" in result.present_optional
    assert result.verdict == "clean"


@pytest.mark.asyncio
async def test_trace_window_spans_correlation_records():
    repo = AsyncMock()
    repo.get_correlation_events.return_value = [
        _corr_record("mobile_capture", ts="2026-04-18T12:00:00+00:00"),
        _corr_record("backend_api", ts="2026-04-18T12:00:30+00:00"),
        _corr_record("classifier", ts="2026-04-18T12:00:45+00:00"),
    ]
    repo.get_recent_events.return_value = []
    lookup = AsyncMock()
    lookup.spans.return_value = []
    lookup.exceptions.return_value = []
    lookup.cosmos.return_value = []

    auditor = CorrelationAuditor(repo=repo, lookup=lookup, now=lambda: NOW)
    result = await auditor.audit("capture", "abc-123", time_range_seconds=3600)

    assert result.trace_window.start == datetime(2026, 4, 18, 12, 0, 0, tzinfo=UTC)
    assert result.trace_window.end == datetime(2026, 4, 18, 12, 0, 45, tzinfo=UTC)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_audit_walker_integrity.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'second_brain.spine.audit.walker'`.

- [ ] **Step 3: Write the implementation**

Write to `backend/src/second_brain/spine/audit/walker.py`:

```python
"""Correlation audit walker.

Public surface:
  - CorrelationAuditor.audit(kind, id, time_range_seconds) -> TraceAudit
  - CorrelationAuditor.audit_sample(kind, sample_size, time_range_seconds) -> AuditReport

Implements three checks per trace:
  1. Correlation integrity   — required vs. optional vs. unexpected segments
  2. Mis-attribution         — outcome / operation / time-window agreement
  3. Bounded under-reporting — orphaned native operations in the trace window

See docs/superpowers/specs/2026-04-18-per-segment-correlation-audit-design.md.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from second_brain.spine.audit.chains import EXPECTED_CHAINS, ExpectedSegment
from second_brain.spine.audit.models import (
    AuditReport,
    AuditSummary,
    Misattribution,
    OrphanReport,
    TimeWindow,
    TraceAudit,
    roll_up_report_verdict,
    roll_up_trace_verdict,
)
from second_brain.spine.audit.native_lookup import NativeLookup
from second_brain.spine.models import CorrelationKind, parse_cosmos_ts
from second_brain.spine.storage import SpineRepository

NATIVE_LINK_TEMPLATES: dict[str, str] = {
    "backend_api": "https://portal.azure.com/#blade/AppInsightsExtension",
    "classifier": "https://ai.azure.com/build/agents",
    "admin": "https://ai.azure.com/build/agents",
    "investigation": "https://ai.azure.com/build/agents",
    "external_services": "https://portal.azure.com/#blade/AppInsightsExtension",
    "cosmos": "https://portal.azure.com/#blade/Microsoft_Azure_DocumentDB",
    "mobile_ui": "https://sentry.io",
    "mobile_capture": "https://sentry.io",
    "container_app": "https://portal.azure.com/#blade/AppInsightsExtension",
}


class CorrelationAuditor:
    """Walks the expected chain for one correlation_id and audits it."""

    def __init__(
        self,
        *,
        repo: SpineRepository,
        lookup: NativeLookup,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._repo = repo
        self._lookup = lookup
        self._now = now or (lambda: datetime.now(UTC))

    async def audit(
        self,
        kind: CorrelationKind,
        correlation_id: str,
        *,
        time_range_seconds: int,
    ) -> TraceAudit:
        """Audit a single correlation_id."""
        # ---- Pull spine records for this trace ----
        records = await self._repo.get_correlation_events(kind, correlation_id)
        segments_seen: dict[str, list[dict[str, Any]]] = {}
        for r in records:
            segments_seen.setdefault(r["segment_id"], []).append(r)

        chain = EXPECTED_CHAINS[kind]
        chain_ids = {s.segment_id for s in chain}
        required = {s.segment_id for s in chain if s.required}
        optional = {s.segment_id for s in chain if not s.required}

        # ---- Check 1: correlation integrity ----
        missing_required = sorted(required - segments_seen.keys())
        present_optional = sorted(optional & segments_seen.keys())
        unexpected = sorted(set(segments_seen.keys()) - chain_ids)

        # ---- Trace window from spine record timestamps ----
        timestamps = [parse_cosmos_ts(r["timestamp"]) for r in records]
        if timestamps:
            window = TimeWindow(start=min(timestamps), end=max(timestamps))
        else:
            now = self._now()
            window = TimeWindow(start=now, end=now)

        # ---- Check 2 + Check 3 (Tasks 7 + 8 fill these in) ----
        misattributions: list[Misattribution] = []
        orphans: list[OrphanReport] = []

        verdict = roll_up_trace_verdict(
            missing_required=missing_required,
            misattributions=misattributions,
            orphans=orphans,
            unexpected=unexpected,
        )

        return TraceAudit(
            correlation_kind=kind,
            correlation_id=correlation_id,
            verdict=verdict,
            headline=_headline_for_trace(
                verdict, missing_required, misattributions, orphans, unexpected
            ),
            missing_required=missing_required,
            present_optional=present_optional,
            unexpected=unexpected,
            misattributions=misattributions,
            orphans=orphans,
            trace_window=window,
            native_links=_native_links_for(segments_seen.keys()),
        )

    async def audit_sample(
        self,
        kind: CorrelationKind,
        sample_size: int,
        time_range_seconds: int,
    ) -> AuditReport:
        """Sample the most-recent correlation_ids and audit each."""
        ids = await self._repo.get_recent_correlation_ids(
            kind=kind,
            time_range_seconds=time_range_seconds,
            limit=sample_size,
        )
        traces = [
            await self.audit(kind, cid, time_range_seconds=time_range_seconds)
            for cid in ids
        ]
        return AuditReport(
            correlation_kind=kind,
            sample_size_requested=sample_size,
            sample_size_returned=len(traces),
            time_range_seconds=time_range_seconds,
            traces=traces,
            summary=_build_summary(traces),
            instrumentation_warning=None,
        )


def _native_links_for(segment_ids) -> dict[str, str]:
    return {
        seg: NATIVE_LINK_TEMPLATES[seg]
        for seg in segment_ids
        if seg in NATIVE_LINK_TEMPLATES
    }


def _headline_for_trace(
    verdict: str,
    missing_required: list[str],
    misattributions: list[Misattribution],
    orphans: list[OrphanReport],
    unexpected: list[str],
) -> str:
    if missing_required:
        return f"missing required segments: {', '.join(missing_required)}"
    if any(m.check == "outcome" for m in misattributions):
        seg = next(m.segment_id for m in misattributions if m.check == "outcome")
        return f"outcome disagreement on {seg}"
    if unexpected:
        return f"unexpected segments emitted: {', '.join(unexpected)}"
    if orphans:
        total = sum(o.orphan_count for o in orphans)
        return f"{total} orphaned native operation(s)"
    if misattributions:
        return f"{len(misattributions)} non-outcome misattribution(s)"
    return "all expected segments present, no discrepancies"


def _build_summary(traces: list[TraceAudit]) -> AuditSummary:
    clean = sum(1 for t in traces if t.verdict == "clean")
    warn = sum(1 for t in traces if t.verdict == "warn")
    broken = sum(1 for t in traces if t.verdict == "broken")

    missing: dict[str, int] = {}
    misattr: dict[str, int] = {}
    orphan_segs: dict[str, int] = {}
    for t in traces:
        for seg in t.missing_required:
            missing[seg] = missing.get(seg, 0) + 1
        for m in t.misattributions:
            misattr[m.segment_id] = misattr.get(m.segment_id, 0) + 1
        for o in t.orphans:
            orphan_segs[o.segment_id] = orphan_segs.get(o.segment_id, 0) + 1

    overall = roll_up_report_verdict(traces)
    headline = _summary_headline(overall, broken, warn, len(traces))

    return AuditSummary(
        clean_count=clean,
        warn_count=warn,
        broken_count=broken,
        segments_with_missing_required=missing,
        segments_with_misattribution=misattr,
        segments_with_orphans=orphan_segs,
        overall_verdict=overall,
        headline=headline,
    )


def _summary_headline(
    overall: str, broken: int, warn: int, total: int
) -> str:
    if total == 0:
        return "no traces sampled"
    if overall == "broken":
        return f"{broken} of {total} traces broken"
    if overall == "warn":
        return f"{warn} of {total} traces have warnings"
    return f"all {total} traces clean"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_audit_walker_integrity.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/src/second_brain/spine/audit/walker.py \
        backend/tests/test_audit_walker_integrity.py
git commit -m "feat(audit): walker skeleton + Check 1 (correlation integrity)"
```

---

## Task 7: `CorrelationAuditor` — Check 2 (mis-attribution)

**Files:**
- Modify: `backend/src/second_brain/spine/audit/walker.py`
- Test: `backend/tests/test_audit_walker_misattribution.py`

- [ ] **Step 1: Write the failing test**

Write to `backend/tests/test_audit_walker_misattribution.py`:

```python
"""Tests for CorrelationAuditor — Check 2 (mis-attribution sub-checks)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from second_brain.spine.audit.walker import CorrelationAuditor

NOW = datetime(2026, 4, 18, 12, 5, 0, tzinfo=UTC)


def _corr_record(segment_id: str, ts: str = "2026-04-18T12:00:30+00:00"):
    return {
        "correlation_kind": "capture",
        "correlation_id": "abc-123",
        "segment_id": segment_id,
        "timestamp": ts,
        "status": "green",
        "headline": f"{segment_id} ok",
    }


def _workload_event(segment_id: str, outcome: str, operation: str = "do_thing"):
    return {
        "id": f"{segment_id}-evt",
        "segment_id": segment_id,
        "event_type": "workload",
        "timestamp": "2026-04-18T12:00:30+00:00",
        "payload": {
            "operation": operation,
            "outcome": outcome,
            "duration_ms": 100,
            "correlation_kind": "capture",
            "correlation_id": "abc-123",
        },
    }


@pytest.mark.asyncio
async def test_outcome_disagreement_marks_broken():
    """Spine says success but App Insights has an exception in window."""
    repo = AsyncMock()
    repo.get_correlation_events.return_value = [
        _corr_record("mobile_capture"),
        _corr_record("backend_api"),
        _corr_record("classifier"),
    ]
    repo.get_recent_events.side_effect = (
        lambda segment_id, window_seconds: {
            "classifier": [_workload_event("classifier", outcome="success")],
        }.get(segment_id, [])
    )

    lookup = AsyncMock()
    lookup.spans.return_value = []
    lookup.exceptions.return_value = [
        {
            "Component": "classifier",
            "ExceptionType": "HttpResponseError",
            "OuterMessage": "boom",
        }
    ]
    lookup.cosmos.return_value = []

    auditor = CorrelationAuditor(repo=repo, lookup=lookup, now=lambda: NOW)
    result = await auditor.audit("capture", "abc-123", time_range_seconds=3600)

    assert result.verdict == "broken"
    outcome_misattr = [m for m in result.misattributions if m.check == "outcome"]
    assert any(m.segment_id == "classifier" for m in outcome_misattr)


@pytest.mark.asyncio
async def test_outcome_disagreement_failure_with_no_exceptions():
    """Spine says failure but App Insights has zero exceptions."""
    repo = AsyncMock()
    repo.get_correlation_events.return_value = [
        _corr_record("mobile_capture"),
        _corr_record("backend_api"),
        _corr_record("classifier"),
    ]
    repo.get_recent_events.side_effect = (
        lambda segment_id, window_seconds: {
            "classifier": [_workload_event("classifier", outcome="failure")],
        }.get(segment_id, [])
    )

    lookup = AsyncMock()
    lookup.spans.return_value = [
        {"Component": "classifier", "Name": "do_thing", "DurationMs": 100}
    ]
    lookup.exceptions.return_value = []
    lookup.cosmos.return_value = []

    auditor = CorrelationAuditor(repo=repo, lookup=lookup, now=lambda: NOW)
    result = await auditor.audit("capture", "abc-123", time_range_seconds=3600)

    assert result.verdict == "broken"
    assert any(m.check == "outcome" for m in result.misattributions)


@pytest.mark.asyncio
async def test_operation_name_mismatch_marks_warn():
    repo = AsyncMock()
    repo.get_correlation_events.return_value = [
        _corr_record("mobile_capture"),
        _corr_record("backend_api"),
        _corr_record("classifier"),
    ]
    repo.get_recent_events.side_effect = (
        lambda segment_id, window_seconds: {
            "classifier": [
                _workload_event("classifier", outcome="success", operation="zzz_unique")
            ],
        }.get(segment_id, [])
    )

    lookup = AsyncMock()
    # Native span exists but doesn't mention the spine-claimed operation.
    lookup.spans.return_value = [
        {
            "Component": "classifier",
            "Name": "POST /something/else",
            "DurationMs": 100,
        }
    ]
    lookup.exceptions.return_value = []
    lookup.cosmos.return_value = []

    auditor = CorrelationAuditor(repo=repo, lookup=lookup, now=lambda: NOW)
    result = await auditor.audit("capture", "abc-123", time_range_seconds=3600)

    assert any(m.check == "operation" for m in result.misattributions)
    assert result.verdict == "warn"


@pytest.mark.asyncio
async def test_no_native_data_skips_misattribution_silently():
    """If the lookup returns nothing for a segment we can't compare — don't flag."""
    repo = AsyncMock()
    repo.get_correlation_events.return_value = [
        _corr_record("mobile_capture"),
        _corr_record("backend_api"),
        _corr_record("classifier"),
    ]
    repo.get_recent_events.side_effect = (
        lambda segment_id, window_seconds: {
            "classifier": [_workload_event("classifier", outcome="success")],
        }.get(segment_id, [])
    )

    lookup = AsyncMock()
    lookup.spans.return_value = []
    lookup.exceptions.return_value = []
    lookup.cosmos.return_value = []

    auditor = CorrelationAuditor(repo=repo, lookup=lookup, now=lambda: NOW)
    result = await auditor.audit("capture", "abc-123", time_range_seconds=3600)

    # Spine claims success; native shows nothing. We don't flag the *outcome*
    # because we have no native evidence either way. Operation/time_window
    # checks are also skipped when there are no spans.
    assert result.misattributions == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_audit_walker_misattribution.py -v`
Expected: 4 failed (no misattribution logic yet).

- [ ] **Step 3: Implement Check 2 in `walker.py`**

Edit `backend/src/second_brain/spine/audit/walker.py`. Replace the `# ---- Check 2 + Check 3` block in `audit()` with:

```python
        # ---- Check 2: mis-attribution (outcome / operation / time_window) ----
        # Pull native sources once for the whole trace.
        spans = await self._lookup.spans(
            correlation_id, time_range_seconds=time_range_seconds
        )
        exceptions = await self._lookup.exceptions(
            correlation_id, time_range_seconds=time_range_seconds
        )
        cosmos_rows = await self._lookup.cosmos(
            correlation_id, time_range_seconds=time_range_seconds
        )

        misattributions: list[Misattribution] = []
        for segment_id in segments_seen.keys() & chain_ids:
            workload_events = await self._workload_events_for(
                segment_id=segment_id,
                correlation_id=correlation_id,
                time_range_seconds=time_range_seconds,
            )
            misattributions.extend(
                _check_misattribution(
                    segment_id=segment_id,
                    workload_events=workload_events,
                    spans=spans,
                    exceptions=exceptions,
                    cosmos_rows=cosmos_rows,
                )
            )

        # ---- Check 3 (Task 8 fills this in) ----
        orphans: list[OrphanReport] = []
```

Then append these helper functions to the bottom of the file:

```python
async def _workload_events_for_unused() -> None:  # placeholder marker
    pass


def _check_misattribution(
    *,
    segment_id: str,
    workload_events: list[dict[str, Any]],
    spans: list[dict[str, Any]],
    exceptions: list[dict[str, Any]],
    cosmos_rows: list[dict[str, Any]],
) -> list[Misattribution]:
    """Run outcome / operation / time-window sub-checks for one segment."""
    findings: list[Misattribution] = []

    # Filter native rows to this segment when possible (Component column).
    seg_spans = [
        s for s in spans if str(s.get("Component", "")).lower() == segment_id.lower()
    ] or spans
    seg_exceptions = [
        e
        for e in exceptions
        if str(e.get("Component", "")).lower() == segment_id.lower()
    ] or exceptions

    # Cosmos has no Component column; treat any cosmos row as relevant only
    # when this segment_id == "cosmos".
    seg_cosmos = cosmos_rows if segment_id == "cosmos" else []

    has_native_evidence = bool(seg_spans or seg_exceptions or seg_cosmos)
    if not has_native_evidence:
        # No native data to compare against — silent on all three sub-checks.
        return findings

    spine_outcomes = {e["payload"]["outcome"] for e in workload_events}

    # Outcome agreement
    if "success" in spine_outcomes and seg_exceptions:
        findings.append(
            Misattribution(
                segment_id=segment_id,
                check="outcome",
                spine_value="success",
                native_value=f"{len(seg_exceptions)} exception(s) in window",
                reason=(
                    "spine reports success but native sources have"
                    f" {len(seg_exceptions)} exception(s) for this trace"
                ),
            )
        )
    if "failure" in spine_outcomes and not seg_exceptions:
        findings.append(
            Misattribution(
                segment_id=segment_id,
                check="outcome",
                spine_value="failure",
                native_value="0 exceptions in window",
                reason=(
                    "spine reports failure but native sources have no"
                    " exceptions for this trace"
                ),
            )
        )

    # Operation name plausibility (loose: spine.operation appears in any span Name)
    spine_ops = {e["payload"]["operation"] for e in workload_events}
    if seg_spans and spine_ops:
        native_names = " ".join(str(s.get("Name", "")) for s in seg_spans).lower()
        unmatched = [op for op in spine_ops if op.lower() not in native_names]
        if unmatched and len(unmatched) == len(spine_ops):
            findings.append(
                Misattribution(
                    segment_id=segment_id,
                    check="operation",
                    spine_value=", ".join(sorted(spine_ops)),
                    native_value="(no matching span Name)",
                    reason=(
                        "spine operation name(s) not found in any native span"
                        " Name for this trace"
                    ),
                )
            )

    return findings
```

Add the `_workload_events_for` instance method on `CorrelationAuditor` (above `audit_sample`):

```python
    async def _workload_events_for(
        self,
        *,
        segment_id: str,
        correlation_id: str,
        time_range_seconds: int,
    ) -> list[dict[str, Any]]:
        """Return workload events for this segment+correlation in the window."""
        events = await self._repo.get_recent_events(
            segment_id=segment_id, window_seconds=time_range_seconds
        )
        return [
            e
            for e in events
            if e.get("event_type") == "workload"
            and e.get("payload", {}).get("correlation_id") == correlation_id
        ]
```

Remove the `_workload_events_for_unused` placeholder.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_audit_walker_integrity.py tests/test_audit_walker_misattribution.py -v`
Expected: 9 passed (5 from Task 6 + 4 from Task 7).

- [ ] **Step 5: Commit**

```bash
git add backend/src/second_brain/spine/audit/walker.py \
        backend/tests/test_audit_walker_misattribution.py
git commit -m "feat(audit): walker Check 2 (outcome + operation sub-checks)"
```

---

## Task 8: `CorrelationAuditor` — Check 3 (orphans) + sample-mode tests

**Files:**
- Modify: `backend/src/second_brain/spine/audit/walker.py`
- Test: `backend/tests/test_audit_walker_orphans.py`
- Test: `backend/tests/test_audit_walker_sample.py`

- [ ] **Step 1: Write the orphan test**

Write to `backend/tests/test_audit_walker_orphans.py`:

```python
"""Tests for CorrelationAuditor — Check 3 (bounded under-reporting)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from second_brain.spine.audit.walker import CorrelationAuditor

NOW = datetime(2026, 4, 18, 12, 5, 0, tzinfo=UTC)


def _corr_record(segment_id: str):
    return {
        "correlation_kind": "capture",
        "correlation_id": "abc-123",
        "segment_id": segment_id,
        "timestamp": "2026-04-18T12:00:30+00:00",
        "status": "green",
        "headline": f"{segment_id} ok",
    }


def _workload(segment_id: str, operation: str):
    return {
        "id": f"{segment_id}-evt",
        "segment_id": segment_id,
        "event_type": "workload",
        "timestamp": "2026-04-18T12:00:30+00:00",
        "payload": {
            "operation": operation,
            "outcome": "success",
            "duration_ms": 100,
            "correlation_kind": "capture",
            "correlation_id": "abc-123",
        },
    }


@pytest.mark.asyncio
async def test_orphan_native_operation_marks_warn():
    """Native source has 2 spans for backend_api; spine has 1 workload event."""
    repo = AsyncMock()
    repo.get_correlation_events.return_value = [
        _corr_record("mobile_capture"),
        _corr_record("backend_api"),
        _corr_record("classifier"),
    ]
    repo.get_recent_events.side_effect = (
        lambda segment_id, window_seconds: {
            "backend_api": [_workload("backend_api", operation="POST /api/capture")],
            "classifier": [_workload("classifier", operation="classify")],
        }.get(segment_id, [])
    )

    lookup = AsyncMock()
    lookup.spans.return_value = [
        {"Component": "backend_api", "Name": "POST /api/capture"},
        {"Component": "backend_api", "Name": "GET /api/inbox"},  # orphan
        {"Component": "classifier", "Name": "classify"},
    ]
    lookup.exceptions.return_value = []
    lookup.cosmos.return_value = []

    auditor = CorrelationAuditor(repo=repo, lookup=lookup, now=lambda: NOW)
    result = await auditor.audit("capture", "abc-123", time_range_seconds=3600)

    backend_orphans = [o for o in result.orphans if o.segment_id == "backend_api"]
    assert backend_orphans
    assert backend_orphans[0].orphan_count == 1
    assert "GET /api/inbox" in backend_orphans[0].sample_operations
    assert result.verdict == "warn"


@pytest.mark.asyncio
async def test_no_orphans_when_spine_covers_native():
    repo = AsyncMock()
    repo.get_correlation_events.return_value = [
        _corr_record("mobile_capture"),
        _corr_record("backend_api"),
        _corr_record("classifier"),
    ]
    repo.get_recent_events.side_effect = (
        lambda segment_id, window_seconds: {
            "backend_api": [_workload("backend_api", operation="POST /api/capture")],
            "classifier": [_workload("classifier", operation="classify")],
        }.get(segment_id, [])
    )
    lookup = AsyncMock()
    lookup.spans.return_value = [
        {"Component": "backend_api", "Name": "POST /api/capture"},
        {"Component": "classifier", "Name": "classify"},
    ]
    lookup.exceptions.return_value = []
    lookup.cosmos.return_value = []

    auditor = CorrelationAuditor(repo=repo, lookup=lookup, now=lambda: NOW)
    result = await auditor.audit("capture", "abc-123", time_range_seconds=3600)

    assert result.orphans == []
    assert result.verdict == "clean"
```

- [ ] **Step 2: Implement Check 3 in `walker.py`**

Edit `backend/src/second_brain/spine/audit/walker.py`. Replace `orphans: list[OrphanReport] = []` in `audit()` with:

```python
        # ---- Check 3: bounded under-reporting (orphans) ----
        orphans: list[OrphanReport] = []
        for segment_id in segments_seen.keys() & chain_ids:
            workload_events = await self._workload_events_for(
                segment_id=segment_id,
                correlation_id=correlation_id,
                time_range_seconds=time_range_seconds,
            )
            orphan_report = _detect_orphans(
                segment_id=segment_id,
                workload_events=workload_events,
                spans=spans,
            )
            if orphan_report and orphan_report.orphan_count > 0:
                orphans.append(orphan_report)
```

Append this helper to the bottom of the file:

```python
def _detect_orphans(
    *,
    segment_id: str,
    workload_events: list[dict[str, Any]],
    spans: list[dict[str, Any]],
) -> OrphanReport | None:
    """Return an OrphanReport if the segment has more native spans than workload events.

    Orphans are spans tagged with this trace's correlation_id whose Name is not
    plausibly covered by any spine workload event for this segment.
    """
    seg_spans = [
        s for s in spans if str(s.get("Component", "")).lower() == segment_id.lower()
    ]
    if not seg_spans:
        return None

    spine_ops_blob = " ".join(
        str(e["payload"]["operation"]) for e in workload_events
    ).lower()

    orphan_names: list[str] = []
    for span in seg_spans:
        name = str(span.get("Name", ""))
        if not name:
            continue
        if name.lower() not in spine_ops_blob:
            orphan_names.append(name)

    if not orphan_names:
        return None
    return OrphanReport(
        segment_id=segment_id,
        orphan_count=len(orphan_names),
        sample_operations=orphan_names[:3],
    )
```

- [ ] **Step 3: Run orphan test**

Run: `cd backend && uv run pytest tests/test_audit_walker_orphans.py -v`
Expected: 2 passed.

- [ ] **Step 4: Write the sample-mode test**

Write to `backend/tests/test_audit_walker_sample.py`:

```python
"""Tests for CorrelationAuditor.audit_sample — sample-mode + summary roll-up."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from second_brain.spine.audit.walker import CorrelationAuditor


def _corr_record(segment_id: str, correlation_id: str = "abc-1"):
    return {
        "correlation_kind": "capture",
        "correlation_id": correlation_id,
        "segment_id": segment_id,
        "timestamp": "2026-04-18T12:00:00+00:00",
        "status": "green",
        "headline": f"{segment_id} ok",
    }


@pytest.mark.asyncio
async def test_audit_sample_returns_one_audit_per_id():
    repo = AsyncMock()
    repo.get_recent_correlation_ids.return_value = ["abc-1", "abc-2", "abc-3"]
    repo.get_correlation_events.side_effect = lambda kind, cid: [
        _corr_record("mobile_capture", cid),
        _corr_record("backend_api", cid),
        _corr_record("classifier", cid),
    ]
    repo.get_recent_events.return_value = []

    lookup = AsyncMock()
    lookup.spans.return_value = []
    lookup.exceptions.return_value = []
    lookup.cosmos.return_value = []

    auditor = CorrelationAuditor(repo=repo, lookup=lookup)
    report = await auditor.audit_sample(
        kind="capture", sample_size=3, time_range_seconds=86400
    )

    assert report.sample_size_requested == 3
    assert report.sample_size_returned == 3
    assert len(report.traces) == 3
    assert report.summary.overall_verdict == "clean"


@pytest.mark.asyncio
async def test_audit_sample_returns_fewer_when_not_enough_traces():
    repo = AsyncMock()
    repo.get_recent_correlation_ids.return_value = ["abc-1"]
    repo.get_correlation_events.side_effect = lambda kind, cid: [
        _corr_record("mobile_capture", cid),
        _corr_record("backend_api", cid),
        _corr_record("classifier", cid),
    ]
    repo.get_recent_events.return_value = []

    lookup = AsyncMock()
    lookup.spans.return_value = []
    lookup.exceptions.return_value = []
    lookup.cosmos.return_value = []

    auditor = CorrelationAuditor(repo=repo, lookup=lookup)
    report = await auditor.audit_sample(
        kind="capture", sample_size=5, time_range_seconds=86400
    )

    assert report.sample_size_requested == 5
    assert report.sample_size_returned == 1


@pytest.mark.asyncio
async def test_audit_sample_summary_aggregates_missing_required():
    repo = AsyncMock()
    repo.get_recent_correlation_ids.return_value = ["abc-1", "abc-2"]
    # Both traces missing classifier.
    repo.get_correlation_events.side_effect = lambda kind, cid: [
        _corr_record("mobile_capture", cid),
        _corr_record("backend_api", cid),
    ]
    repo.get_recent_events.return_value = []

    lookup = AsyncMock()
    lookup.spans.return_value = []
    lookup.exceptions.return_value = []
    lookup.cosmos.return_value = []

    auditor = CorrelationAuditor(repo=repo, lookup=lookup)
    report = await auditor.audit_sample(
        kind="capture", sample_size=2, time_range_seconds=86400
    )

    assert report.summary.overall_verdict == "broken"
    assert report.summary.broken_count == 2
    assert report.summary.segments_with_missing_required == {"classifier": 2}
```

- [ ] **Step 5: Run all walker tests**

Run: `cd backend && uv run pytest tests/test_audit_walker_integrity.py tests/test_audit_walker_misattribution.py tests/test_audit_walker_orphans.py tests/test_audit_walker_sample.py -v`
Expected: 14 passed (5 + 4 + 2 + 3).

- [ ] **Step 6: Commit**

```bash
git add backend/src/second_brain/spine/audit/walker.py \
        backend/tests/test_audit_walker_orphans.py \
        backend/tests/test_audit_walker_sample.py
git commit -m "feat(audit): walker Check 3 (orphans) + sample mode"
```

---

## Task 9: HTTP endpoint `POST /api/spine/audit/correlation`

**Files:**
- Modify: `backend/src/second_brain/spine/api.py`
- Modify: `backend/src/second_brain/main.py`
- Test: `backend/tests/test_audit_api.py`

- [ ] **Step 1: Write the failing test**

Write to `backend/tests/test_audit_api.py`:

```python
"""Tests for POST /api/spine/audit/correlation."""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from second_brain.spine.api import build_spine_router
from second_brain.spine.auth import spine_auth

TEST_API_KEY = "test-api-key-12345"


def _make_app(auditor):
    repo = AsyncMock()
    evaluator = AsyncMock()
    adapter_registry = AsyncMock()
    segment_registry = AsyncMock()

    app = FastAPI()
    app.state.api_key = TEST_API_KEY
    router = build_spine_router(
        repo=repo,
        evaluator=evaluator,
        adapter_registry=adapter_registry,
        segment_registry=segment_registry,
        auth_dependency=spine_auth,
        auditor=auditor,
    )
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_audit_endpoint_requires_auth():
    auditor = AsyncMock()
    app = _make_app(auditor)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post(
            "/api/spine/audit/correlation",
            json={"correlation_kind": "capture", "correlation_id": "abc-1"},
        )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_audit_endpoint_single_id_calls_auditor_audit():
    from second_brain.spine.audit.models import (
        AuditReport,
        AuditSummary,
        TimeWindow,
        TraceAudit,
    )
    from datetime import UTC, datetime

    trace_audit = TraceAudit(
        correlation_kind="capture",
        correlation_id="abc-1",
        verdict="clean",
        headline="all good",
        trace_window=TimeWindow(
            start=datetime(2026, 4, 18, tzinfo=UTC),
            end=datetime(2026, 4, 18, tzinfo=UTC),
        ),
    )
    auditor = AsyncMock()
    auditor.audit.return_value = trace_audit
    auditor.audit_sample.return_value = AuditReport(
        correlation_kind="capture",
        sample_size_requested=1,
        sample_size_returned=1,
        time_range_seconds=86400,
        traces=[trace_audit],
        summary=AuditSummary(
            clean_count=1,
            warn_count=0,
            broken_count=0,
            segments_with_missing_required={},
            segments_with_misattribution={},
            segments_with_orphans={},
            overall_verdict="clean",
            headline="all 1 traces clean",
        ),
    )

    app = _make_app(auditor)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post(
            "/api/spine/audit/correlation",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "correlation_kind": "capture",
                "correlation_id": "abc-1",
                "time_range_seconds": 86400,
            },
        )

    assert r.status_code == 200
    auditor.audit.assert_called_once()
    auditor.audit_sample.assert_not_called()
    body = r.json()
    assert body["sample_size_returned"] == 1
    assert body["traces"][0]["correlation_id"] == "abc-1"


@pytest.mark.asyncio
async def test_audit_endpoint_sample_mode_calls_audit_sample():
    from second_brain.spine.audit.models import AuditReport, AuditSummary

    auditor = AsyncMock()
    auditor.audit_sample.return_value = AuditReport(
        correlation_kind="capture",
        sample_size_requested=5,
        sample_size_returned=0,
        time_range_seconds=86400,
        traces=[],
        summary=AuditSummary(
            clean_count=0,
            warn_count=0,
            broken_count=0,
            segments_with_missing_required={},
            segments_with_misattribution={},
            segments_with_orphans={},
            overall_verdict="clean",
            headline="no traces sampled",
        ),
    )

    app = _make_app(auditor)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post(
            "/api/spine/audit/correlation",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "correlation_kind": "capture",
                "sample_size": 5,
            },
        )

    assert r.status_code == 200
    auditor.audit_sample.assert_called_once()
    auditor.audit.assert_not_called()


@pytest.mark.asyncio
async def test_audit_endpoint_validates_sample_size_bounds():
    auditor = AsyncMock()
    app = _make_app(auditor)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post(
            "/api/spine/audit/correlation",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={"correlation_kind": "capture", "sample_size": 100},
        )
    assert r.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_audit_api.py -v`
Expected: FAIL with `TypeError: build_spine_router() got an unexpected keyword argument 'auditor'`.

- [ ] **Step 3: Add the request model + endpoint**

Edit `backend/src/second_brain/spine/api.py`. At the top, after the existing imports, add:

```python
from pydantic import BaseModel, Field

from second_brain.spine.audit.models import AuditReport
from second_brain.spine.audit.walker import CorrelationAuditor
```

Define a request model below the imports (above `build_spine_router`):

```python
class AuditRequest(BaseModel):
    """Request body for POST /api/spine/audit/correlation."""

    correlation_kind: CorrelationKind
    correlation_id: str | None = None
    sample_size: int = Field(5, ge=1, le=20)
    time_range_seconds: int = Field(86400, ge=60, le=604800)  # 1min - 7d
```

Update `build_spine_router`'s signature to accept the auditor:

```python
def build_spine_router(
    repo: SpineRepository,
    evaluator: StatusEvaluator,
    adapter_registry: AdapterRegistry,
    segment_registry: SegmentRegistry,
    auth_dependency: Callable[..., Awaitable[None]],
    auditor: CorrelationAuditor | None = None,
) -> APIRouter:
```

Add the endpoint at the end of the function, just before `return router`:

```python
    @router.post(
        "/audit/correlation",
        response_model=AuditReport,
        dependencies=[Depends(auth_dependency)],
    )
    async def audit_correlation(req: AuditRequest) -> AuditReport:
        if auditor is None:
            raise HTTPException(503, "Audit not configured")
        if req.correlation_id:
            trace = await auditor.audit(
                kind=req.correlation_kind,
                correlation_id=req.correlation_id,
                time_range_seconds=req.time_range_seconds,
            )
            from second_brain.spine.audit.walker import _build_summary

            summary = _build_summary([trace])
            return AuditReport(
                correlation_kind=req.correlation_kind,
                sample_size_requested=1,
                sample_size_returned=1,
                time_range_seconds=req.time_range_seconds,
                traces=[trace],
                summary=summary,
            )
        return await auditor.audit_sample(
            kind=req.correlation_kind,
            sample_size=req.sample_size,
            time_range_seconds=req.time_range_seconds,
        )
```

- [ ] **Step 4: Wire the auditor into `main.py`**

Edit `backend/src/second_brain/main.py`. Find the `build_spine_router(` call (around line 354) and the spine setup block. Right above the `build_spine_router(...)` call, construct the auditor:

```python
            from functools import partial as _partial

            from second_brain.observability.queries import (
                fetch_audit_cosmos_diagnostics_for_correlation,
                fetch_audit_exceptions_for_correlation,
                fetch_audit_spans_for_correlation,
            )
            from second_brain.spine.audit.native_lookup import NativeLookup
            from second_brain.spine.audit.walker import CorrelationAuditor

            if app.state.logs_client is not None and settings.log_analytics_workspace_id:
                audit_lookup = NativeLookup(
                    spans_fetcher=_partial(
                        fetch_audit_spans_for_correlation,
                        app.state.logs_client,
                        settings.log_analytics_workspace_id,
                    ),
                    exceptions_fetcher=_partial(
                        fetch_audit_exceptions_for_correlation,
                        app.state.logs_client,
                        settings.log_analytics_workspace_id,
                    ),
                    cosmos_fetcher=_partial(
                        fetch_audit_cosmos_diagnostics_for_correlation,
                        app.state.logs_client,
                        settings.log_analytics_workspace_id,
                    ),
                )
            else:
                audit_lookup = NativeLookup(
                    spans_fetcher=None,
                    exceptions_fetcher=None,
                    cosmos_fetcher=None,
                )
            spine_auditor = CorrelationAuditor(repo=spine_repo, lookup=audit_lookup)
```

Then update the `build_spine_router(` call to pass `auditor=spine_auditor`:

```python
            build_spine_router(
                repo=spine_repo,
                evaluator=spine_evaluator,
                adapter_registry=adapter_registry,
                segment_registry=spine_registry,
                auth_dependency=spine_auth,
                auditor=spine_auditor,
            )
```

(If the existing call uses positional arguments, leave them positional and just append `auditor=spine_auditor` as a kwarg.)

- [ ] **Step 5: Run tests**

Run: `cd backend && uv run pytest tests/test_audit_api.py -v`
Expected: 4 passed.

Also run the full spine test suite to confirm no regressions: `cd backend && uv run pytest tests/test_spine_*.py tests/test_audit_*.py -v`. All passing.

- [ ] **Step 6: Commit**

```bash
git add backend/src/second_brain/spine/api.py \
        backend/src/second_brain/main.py \
        backend/tests/test_audit_api.py
git commit -m "feat(audit): POST /api/spine/audit/correlation endpoint"
```

---

## Task 10: MCP tool wrapper `audit_correlation`

**Files:**
- Modify: `mcp/server.py`
- Test: `backend/tests/test_audit_mcp_tool.py`

- [ ] **Step 1: Write the failing test**

Write to `backend/tests/test_audit_mcp_tool.py`:

```python
"""Tests for the audit_correlation MCP tool wrapper."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_audit_correlation_calls_spine_endpoint():
    """The MCP tool POSTs to /api/spine/audit/correlation and returns the body."""
    expected_response = {
        "correlation_kind": "capture",
        "sample_size_requested": 5,
        "sample_size_returned": 1,
        "time_range_seconds": 86400,
        "traces": [],
        "summary": {
            "clean_count": 0,
            "warn_count": 0,
            "broken_count": 0,
            "segments_with_missing_required": {},
            "segments_with_misattribution": {},
            "segments_with_orphans": {},
            "overall_verdict": "clean",
            "headline": "no traces sampled",
        },
        "instrumentation_warning": None,
    }

    with patch("mcp.server._spine_post", new=AsyncMock(return_value=expected_response)):
        # Import inside the patch so the tool sees the patched helper.
        from mcp.server import audit_correlation  # noqa: WPS433

        result = await audit_correlation(
            correlation_kind="capture",
            correlation_id=None,
            sample_size=5,
            time_range_seconds=86400,
            ctx=None,
        )
    assert result == expected_response


@pytest.mark.asyncio
async def test_audit_correlation_returns_error_on_exception():
    with patch(
        "mcp.server._spine_post",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        from mcp.server import audit_correlation  # noqa: WPS433

        result = await audit_correlation(
            correlation_kind="capture",
            correlation_id="abc-1",
            sample_size=5,
            time_range_seconds=86400,
            ctx=None,
        )
    assert result == {"error": True, "message": "boom", "type": "RuntimeError"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_audit_mcp_tool.py -v`
Expected: FAIL with `ImportError: cannot import name 'audit_correlation'`.

- [ ] **Step 3: Add `_spine_post` helper + tool to `mcp/server.py`**

Edit `mcp/server.py`. Below the existing `_spine_call` function (around line 93), add a POST helper:

```python
async def _spine_post(path: str, json_body: dict[str, Any]) -> dict[str, Any]:
    """POST to the spine API and return the JSON response."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{SPINE_BASE_URL}{path}",
            json=json_body,
            headers={"Authorization": f"Bearer {SPINE_API_KEY}"},
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]
```

Then add the tool at the bottom of the file, just before the `if __name__ == "__main__":` block:

```python
# ---------------------------------------------------------------------------
# Tool 7: audit_correlation
# ---------------------------------------------------------------------------


@mcp.tool()
async def audit_correlation(
    correlation_kind: str,
    correlation_id: str | None = None,
    sample_size: int = 5,
    time_range_seconds: int = 86400,
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Audit whether spine events for a correlation_id (or a sample of recent
    ones) line up with what native sources actually saw.

    Use when the user asks whether observability is working, whether a specific
    trace was captured correctly, or whether segments are accurately reflecting
    their domain. Returns per-trace verdicts plus an aggregate roll-up.

    Args:
        correlation_kind: One of 'capture', 'thread', 'request', 'crud'.
        correlation_id: Audit a specific ID. If null, samples the N most-recent
            correlation_ids of this kind from the last `time_range_seconds`.
        sample_size: Number of traces to sample when correlation_id is null
            (1-20). Ignored otherwise.
        time_range_seconds: Window for sampling and native-source lookups
            (60 to 604800 = 1 minute to 7 days).
    """
    try:
        body: dict[str, Any] = {
            "correlation_kind": correlation_kind,
            "sample_size": sample_size,
            "time_range_seconds": time_range_seconds,
        }
        if correlation_id:
            body["correlation_id"] = correlation_id
        return await _spine_post("/api/spine/audit/correlation", body)
    except Exception as exc:
        logger.error("audit_correlation failed: %s", exc, exc_info=True)
        return {"error": True, "message": str(exc), "type": type(exc).__name__}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_audit_mcp_tool.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add mcp/server.py backend/tests/test_audit_mcp_tool.py
git commit -m "feat(mcp): audit_correlation tool"
```

---

## Task 11: Instrumentation-warning sanity check

If a `required=True` segment has zero matching native spans for *every* sampled trace, the report includes a top-level warning that the audit itself may be broken. Distinguishes "this trace is broken" from "the audit is broken."

**Files:**
- Modify: `backend/src/second_brain/spine/audit/walker.py`
- Test: `backend/tests/test_audit_instrumentation_warning.py`

- [ ] **Step 1: Write the failing test**

Write to `backend/tests/test_audit_instrumentation_warning.py`:

```python
"""Tests for the instrumentation_warning sanity check on AuditReport."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from second_brain.spine.audit.walker import CorrelationAuditor


def _corr_record(segment_id: str, correlation_id: str = "abc-1"):
    return {
        "correlation_kind": "capture",
        "correlation_id": correlation_id,
        "segment_id": segment_id,
        "timestamp": "2026-04-18T12:00:00+00:00",
        "status": "green",
        "headline": f"{segment_id} ok",
    }


@pytest.mark.asyncio
async def test_instrumentation_warning_when_required_segment_has_zero_native_spans_in_all_traces():
    """When backend_api appears in every trace's spine chain but native lookup
    returns zero spans for backend_api in every trace, the report flags a
    likely instrumentation regression (e.g., correlation_id tagging dropped).
    """
    repo = AsyncMock()
    repo.get_recent_correlation_ids.return_value = ["abc-1", "abc-2"]
    repo.get_correlation_events.side_effect = lambda kind, cid: [
        _corr_record("mobile_capture", cid),
        _corr_record("backend_api", cid),
        _corr_record("classifier", cid),
    ]
    repo.get_recent_events.return_value = []

    lookup = AsyncMock()
    # Native lookup returns spans for mobile_capture + classifier but never
    # backend_api — that's the instrumentation regression we want to surface.
    lookup.spans.return_value = [
        {"Component": "mobile_capture", "Name": "capture_button_press"},
        {"Component": "classifier", "Name": "classify"},
    ]
    lookup.exceptions.return_value = []
    lookup.cosmos.return_value = []

    auditor = CorrelationAuditor(repo=repo, lookup=lookup)
    report = await auditor.audit_sample(
        kind="capture", sample_size=2, time_range_seconds=86400
    )

    assert report.instrumentation_warning is not None
    assert "backend_api" in report.instrumentation_warning


@pytest.mark.asyncio
async def test_no_instrumentation_warning_when_at_least_one_trace_has_native_data():
    repo = AsyncMock()
    repo.get_recent_correlation_ids.return_value = ["abc-1", "abc-2"]
    repo.get_correlation_events.side_effect = lambda kind, cid: [
        _corr_record("mobile_capture", cid),
        _corr_record("backend_api", cid),
        _corr_record("classifier", cid),
    ]
    repo.get_recent_events.return_value = []

    lookup = AsyncMock()
    # backend_api has native data, just no exceptions → no warning expected.
    lookup.spans.return_value = [
        {"Component": "backend_api", "Name": "POST /api/capture"},
        {"Component": "classifier", "Name": "classify"},
    ]
    lookup.exceptions.return_value = []
    lookup.cosmos.return_value = []

    auditor = CorrelationAuditor(repo=repo, lookup=lookup)
    report = await auditor.audit_sample(
        kind="capture", sample_size=2, time_range_seconds=86400
    )
    assert report.instrumentation_warning is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_audit_instrumentation_warning.py -v`
Expected: FAIL — `instrumentation_warning` always None.

- [ ] **Step 3: Update `audit_sample` to compute the warning**

Edit `backend/src/second_brain/spine/audit/walker.py`. The audit walker also needs to track per-segment "did native lookup return any data for this segment in this trace." The cleanest way is to attach the native-lookup data to the trace audit so `audit_sample` can roll it up.

Add a private field on `TraceAudit`-like data — but rather than mutating the model, return the per-segment native-presence map alongside the trace audit from the internal call. Refactor:

Add a helper at the top of the file (just below NATIVE_LINK_TEMPLATES):

```python
# Tracks per-trace which segments had any native data returned by the lookup.
# Keyed by correlation_id → set of segment_ids with non-empty native results.
SegmentNativeMap = dict[str, set[str]]
```

Change `audit()` to internally compute the map and stash it on the auditor's last-call state (small private attribute). Actually — simpler — change `audit_sample()` to call native lookup itself first per-trace and pass the results down. But that duplicates work. Cleanest implementation:

Change `audit()` to return a tuple `(TraceAudit, set[str])` from a new internal `_audit_with_native_presence`, and keep `audit()` as a thin wrapper. Then `audit_sample` can collect the presence sets.

Replace the existing `audit()` method with:

```python
    async def audit(
        self,
        kind: CorrelationKind,
        correlation_id: str,
        *,
        time_range_seconds: int,
    ) -> TraceAudit:
        """Audit a single correlation_id."""
        trace, _ = await self._audit_with_native_presence(
            kind, correlation_id, time_range_seconds=time_range_seconds
        )
        return trace

    async def _audit_with_native_presence(
        self,
        kind: CorrelationKind,
        correlation_id: str,
        *,
        time_range_seconds: int,
    ) -> tuple[TraceAudit, set[str]]:
        """Internal: returns the audit + which segments had any native data."""
        records = await self._repo.get_correlation_events(kind, correlation_id)
        segments_seen: dict[str, list[dict[str, Any]]] = {}
        for r in records:
            segments_seen.setdefault(r["segment_id"], []).append(r)

        chain = EXPECTED_CHAINS[kind]
        chain_ids = {s.segment_id for s in chain}
        required = {s.segment_id for s in chain if s.required}
        optional = {s.segment_id for s in chain if not s.required}

        missing_required = sorted(required - segments_seen.keys())
        present_optional = sorted(optional & segments_seen.keys())
        unexpected = sorted(set(segments_seen.keys()) - chain_ids)

        timestamps = [parse_cosmos_ts(r["timestamp"]) for r in records]
        if timestamps:
            window = TimeWindow(start=min(timestamps), end=max(timestamps))
        else:
            now = self._now()
            window = TimeWindow(start=now, end=now)

        spans = await self._lookup.spans(
            correlation_id, time_range_seconds=time_range_seconds
        )
        exceptions = await self._lookup.exceptions(
            correlation_id, time_range_seconds=time_range_seconds
        )
        cosmos_rows = await self._lookup.cosmos(
            correlation_id, time_range_seconds=time_range_seconds
        )

        misattributions: list[Misattribution] = []
        orphans: list[OrphanReport] = []
        native_present: set[str] = set()

        for segment_id in segments_seen.keys() & chain_ids:
            workload_events = await self._workload_events_for(
                segment_id=segment_id,
                correlation_id=correlation_id,
                time_range_seconds=time_range_seconds,
            )
            if _segment_has_native_data(segment_id, spans, exceptions, cosmos_rows):
                native_present.add(segment_id)
            misattributions.extend(
                _check_misattribution(
                    segment_id=segment_id,
                    workload_events=workload_events,
                    spans=spans,
                    exceptions=exceptions,
                    cosmos_rows=cosmos_rows,
                )
            )
            orphan_report = _detect_orphans(
                segment_id=segment_id,
                workload_events=workload_events,
                spans=spans,
            )
            if orphan_report and orphan_report.orphan_count > 0:
                orphans.append(orphan_report)

        verdict = roll_up_trace_verdict(
            missing_required=missing_required,
            misattributions=misattributions,
            orphans=orphans,
            unexpected=unexpected,
        )

        trace = TraceAudit(
            correlation_kind=kind,
            correlation_id=correlation_id,
            verdict=verdict,
            headline=_headline_for_trace(
                verdict, missing_required, misattributions, orphans, unexpected
            ),
            missing_required=missing_required,
            present_optional=present_optional,
            unexpected=unexpected,
            misattributions=misattributions,
            orphans=orphans,
            trace_window=window,
            native_links=_native_links_for(segments_seen.keys()),
        )
        return trace, native_present
```

Replace the `audit_sample` method with:

```python
    async def audit_sample(
        self,
        kind: CorrelationKind,
        sample_size: int,
        time_range_seconds: int,
    ) -> AuditReport:
        ids = await self._repo.get_recent_correlation_ids(
            kind=kind,
            time_range_seconds=time_range_seconds,
            limit=sample_size,
        )
        traces: list[TraceAudit] = []
        per_trace_native: list[set[str]] = []
        for cid in ids:
            trace, native_present = await self._audit_with_native_presence(
                kind, cid, time_range_seconds=time_range_seconds
            )
            traces.append(trace)
            per_trace_native.append(native_present)

        warning = _instrumentation_warning(kind, traces, per_trace_native)
        return AuditReport(
            correlation_kind=kind,
            sample_size_requested=sample_size,
            sample_size_returned=len(traces),
            time_range_seconds=time_range_seconds,
            traces=traces,
            summary=_build_summary(traces),
            instrumentation_warning=warning,
        )
```

Add these helpers to the bottom of the file:

```python
def _segment_has_native_data(
    segment_id: str,
    spans: list[dict[str, Any]],
    exceptions: list[dict[str, Any]],
    cosmos_rows: list[dict[str, Any]],
) -> bool:
    """Return True if any native source returned a row attributable to segment_id."""
    if any(
        str(s.get("Component", "")).lower() == segment_id.lower() for s in spans
    ):
        return True
    if any(
        str(e.get("Component", "")).lower() == segment_id.lower() for e in exceptions
    ):
        return True
    if segment_id == "cosmos" and cosmos_rows:
        return True
    return False


def _instrumentation_warning(
    kind: CorrelationKind,
    traces: list[TraceAudit],
    per_trace_native: list[set[str]],
) -> str | None:
    """Return a warning if any required segment had zero native data across all traces."""
    if not traces:
        return None

    required = {s.segment_id for s in EXPECTED_CHAINS[kind] if s.required}
    # Only consider segments that were actually present in every trace's spine
    # chain — otherwise we'd flag legitimately-missing required segments as an
    # instrumentation issue.
    appeared_everywhere = set(required)
    for trace in traces:
        appeared_everywhere &= set(
            trace.present_optional
            + [s for s in required if s not in trace.missing_required]
        )

    silent_segments: list[str] = []
    for seg in sorted(appeared_everywhere):
        if all(seg not in present for present in per_trace_native):
            silent_segments.append(seg)

    if not silent_segments:
        return None
    return (
        f"{', '.join(silent_segments)} appears to have lost correlation_id"
        " tagging — every sampled trace had spine events for this segment but"
        " zero matching native records"
    )
```

- [ ] **Step 4: Run all walker tests**

Run: `cd backend && uv run pytest tests/test_audit_walker_*.py tests/test_audit_instrumentation_warning.py -v`
Expected: 16 passed (5 + 4 + 2 + 3 + 2).

- [ ] **Step 5: Commit**

```bash
git add backend/src/second_brain/spine/audit/walker.py \
        backend/tests/test_audit_instrumentation_warning.py
git commit -m "feat(audit): instrumentation_warning sanity check (R2)"
```

---

## Task 12: Integration test against deployed backend

A live test marked `@pytest.mark.integration` that calls the deployed `https://brain.willmacdonald.com` endpoint with a real recent capture trace ID. Asserts response shape — does NOT assert verdict (the live system's verdict is the answer the user is interested in, not something to gate CI on).

**Files:**
- Test: `backend/tests/test_audit_integration.py`

- [ ] **Step 1: Write the integration test**

Write to `backend/tests/test_audit_integration.py`:

```python
"""Integration test for the audit endpoint against the deployed backend.

Marked @pytest.mark.integration — skipped by default. Run with:
  uv run pytest backend/tests/test_audit_integration.py -m integration -v

Requires:
  - SPINE_API_KEY in env (or in backend/.env)
  - SPINE_BASE_URL (defaults to https://brain.willmacdonald.com)
"""

from __future__ import annotations

import os

import httpx
import pytest

SPINE_BASE_URL = os.environ.get("SPINE_BASE_URL", "https://brain.willmacdonald.com")
SPINE_API_KEY = os.environ.get("SPINE_API_KEY", "")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sample_capture_returns_well_formed_report():
    """Sample mode returns a structurally-valid AuditReport."""
    if not SPINE_API_KEY:
        pytest.skip("SPINE_API_KEY not set")

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{SPINE_BASE_URL}/api/spine/audit/correlation",
            headers={"Authorization": f"Bearer {SPINE_API_KEY}"},
            json={
                "correlation_kind": "capture",
                "sample_size": 3,
                "time_range_seconds": 86400,
            },
        )
    resp.raise_for_status()
    body = resp.json()

    # Shape assertions only — values reflect live system state.
    assert body["correlation_kind"] == "capture"
    assert body["sample_size_requested"] == 3
    assert "traces" in body
    assert "summary" in body
    assert body["summary"]["overall_verdict"] in {"clean", "warn", "broken"}
    for trace in body["traces"]:
        assert trace["verdict"] in {"clean", "warn", "broken"}
        assert "trace_window" in trace
        assert "native_links" in trace
```

- [ ] **Step 2: Verify test SKIPS without API key**

Run: `cd backend && uv run pytest tests/test_audit_integration.py -v`
Expected: 1 skipped (assuming `SPINE_API_KEY` is not in your shell env — that's normal).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_audit_integration.py
git commit -m "test(audit): integration test against deployed endpoint"
```

The integration test runs after deployment — see Task 13.

---

## Task 13: Deploy and live-verify

This task is operational, not code-changing. It exercises the deployed system end-to-end through the MCP tool and the integration test.

- [ ] **Step 1: Push to main**

```bash
git push origin main
```

- [ ] **Step 2: Wait for CI/CD to deploy**

GitHub Actions builds the image, pushes to ACR, and rolls Container App. ~5-8 minutes. Watch:

```bash
gh run watch
```

When the latest run shows green, the new revision is live.

- [ ] **Step 3: Run the integration test against the deployed backend**

```bash
cd backend
SPINE_API_KEY=$(az keyvault secret show --vault-name wkm-shared-kv --name second-brain-api-key --query value -o tsv) \
  uv run pytest tests/test_audit_integration.py -m integration -v
```

Expected: 1 passed. If 4xx/5xx, check the Container App logs in App Insights (`AppExceptions` table; component=`spine`).

- [ ] **Step 4: Restart Claude Code so MCP picks up the new tool**

Quit Claude Code and restart it. The MCP server is loaded once per process.

- [ ] **Step 5: Exercise the tool through the agent**

In a Claude Code session:

```
/investigate are spine segments accurately reflecting capture flows right now?
```

The agent should call `audit_correlation` with `correlation_kind="capture"` and a small `sample_size`. Expect a structured report. Verify the report includes a summary headline and per-trace verdicts.

- [ ] **Step 6: Single-ID mode sanity check**

Find a recent capture trace_id (the agent will know how to look one up via `trace_lifecycle`), then ask:

```
audit that specific capture
```

Expect a single-trace report. Inspect the trace's `missing_required`, `unexpected`, `misattributions`, and `orphans` fields. Anything unexpected is a real-system finding to investigate.

- [ ] **Step 7: No commit** — this is a verification task. If issues surface, file follow-up tasks rather than amending the audit code reactively.

---

## Self-Review

**Spec coverage:**
- [x] Tool surface (Section: Tool Surface) → Task 10
- [x] Expected segment chains (Section: Expected Segment Chains) → Task 1
- [x] Three checks per trace (Section: The Three Checks Per Trace) → Tasks 6, 7, 8
- [x] Output shape (Section: Output Shape) → Task 2
- [x] Verdict roll-up rules → Task 2 (`roll_up_trace_verdict`, `roll_up_report_verdict`)
- [x] Backend endpoint `POST /api/spine/audit/correlation` → Task 9
- [x] `spine.audit` package layout → Tasks 1, 2, 4, 6
- [x] Native-source query helpers → Task 3
- [x] `NativeLookup` facade → Task 4
- [x] `SpineRepository.get_recent_correlation_ids` → Task 5
- [x] MCP tool wrapper → Task 10
- [x] R1 (lag handling): `time_range_seconds` validation 60-604800, padding via per-trace window — covered in Task 9 (validator) + Task 11 (instrumentation warning)
- [x] R2 (instrumentation warning) → Task 11
- [x] R5 (narrow tool description) → Task 10 docstring scoped to "audit whether spine events line up"
- [x] R6 (sample_size cap at 20) → Task 9 validator
- [x] Tests at three layers (unit walker / native lookup / end-to-end) → Tasks 6-8 / Task 3 / Task 12
- [x] Live verification → Task 13

R3 (chain drift) and R4 (sample masks tail) are documented in the spec as accepted risks with no code change required.

**Placeholder scan:** No "TBD" / "TODO" / vague "add appropriate error handling" anywhere. Every code step shows the actual code; every test step shows the actual assertions.

**Type consistency:** `CorrelationKind` is imported from `second_brain.spine.models` in every audit module. `Verdict`, `MisattributionCheck`, `Misattribution`, `OrphanReport`, `TraceAudit`, `AuditReport`, `AuditSummary`, `TimeWindow` defined once in `audit/models.py` and re-used throughout. `EXPECTED_CHAINS` defined once in `audit/chains.py`. `CorrelationAuditor` constructor signature stable across Tasks 6, 7, 8, 11. `build_spine_router` gains one keyword arg `auditor: CorrelationAuditor | None = None` in Task 9; the `main.py` wiring in Task 9 passes it as a kwarg. `_spine_post` added in Task 10 mirrors the existing `_spine_call` style.

**Scope:** Single feature, single MCP tool, ~one phase of work. Appropriate for one plan.
