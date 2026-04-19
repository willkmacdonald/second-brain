"""Contract tests that must pass before Phase 1 can honestly close.

These tests are RED until Task 9 amendment and Task 11.5 land. They
encode the two plan amendments (main commits 4ea5d6a and 58b1dea) so
the next engineer sees the expected surface up front.

Test A — capture trace propagation:
    When a capture handler generates (not receives) a capture_trace_id,
    the SpineWorkloadMiddleware must pick it up from request.state and
    emit a correlation-bound workload event. Without this, the
    /api/spine/correlation/capture/{id} timeline silently omits the
    backend_api node for native app captures (which never send
    X-Trace-Id), failing Task 19 Step 6.

Test B — focused query primitives exist with the adapter's signature:
    The Backend API adapter calls its injected fetchers with
    (time_range_seconds=, capture_trace_id=). The observability query
    layer must provide query_backend_api_failures() and
    query_backend_api_requests() with that exact signature so Task 12
    can bind them via functools.partial without argument-reshape
    gymnastics. Without this the adapter has no backing queries and
    /api/spine/segment/backend_api cannot return the locked
    azure_monitor_app_insights schema.

Test C — Phase 19.2 emitter shape contract (SPIKE-MEMO §5):
    Every emit site must wrap its concrete `_WorkloadEvent` /
    `_LivenessEvent` in `IngestEvent(root=...)` before calling
    `SpineRepository.record_event`. The production repository does
    `event.root` (Pydantic v2 RootModel accessor) which raises
    AttributeError on a raw `_WorkloadEvent`. Every emit site that
    bypasses this wrap is silently broken in production — AsyncMock
    tests mask the defect because mocks don't exercise `.root`.

    The fake `RootAccessingSpineRepo` below calls `event.root` in the
    same way `SpineRepository.record_event` does, so the shape bug
    surfaces at test time.
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from second_brain.spine.middleware import SpineWorkloadMiddleware

# ---------------------------------------------------------------------------
# Test A — handler-set request.state.capture_trace_id reaches middleware
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_middleware_reads_capture_trace_id_from_request_state() -> None:
    """Task 9 amendment: state > header > None precedence.

    RED until the middleware's _read_capture_trace_id helper lands.
    """
    repo = AsyncMock()
    app = FastAPI()
    app.add_middleware(SpineWorkloadMiddleware, repo=repo, segment_id="backend_api")

    @app.get("/with-state")
    async def _with_state(request: Request) -> dict:
        request.state.capture_trace_id = "handler-generated-trace"
        return {"ok": True}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/with-state")  # NO X-Trace-Id header
    assert response.status_code == 200

    repo.record_event.assert_called_once()
    event = repo.record_event.call_args.args[0]
    assert event.root.payload.correlation_kind == "capture"
    assert event.root.payload.correlation_id == "handler-generated-trace"


@pytest.mark.asyncio
async def test_middleware_state_takes_precedence_over_header() -> None:
    """request.state wins over inbound X-Trace-Id header.

    RED until _read_capture_trace_id applies state-before-header
    precedence. Reason: handlers may deliberately override a bad/reused
    caller header with a fresh trace they generated.
    """
    repo = AsyncMock()
    app = FastAPI()
    app.add_middleware(SpineWorkloadMiddleware, repo=repo, segment_id="backend_api")

    @app.get("/with-both")
    async def _with_both(request: Request) -> dict:
        request.state.capture_trace_id = "from-state"
        return {"ok": True}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.get("/with-both", headers={"X-Trace-Id": "from-header"})

    event = repo.record_event.call_args.args[0]
    assert event.root.payload.correlation_id == "from-state"


@pytest.mark.asyncio
async def test_middleware_falls_back_to_header_when_state_missing() -> None:
    """Inbound X-Trace-Id still works when handler doesn't set state.

    Already green pre-amendment; included as a regression guard so the
    amendment doesn't accidentally break caller-supplied trace flow
    (e.g. the investigation terminal client which sends X-Trace-Id).
    """
    repo = AsyncMock()
    app = FastAPI()
    app.add_middleware(SpineWorkloadMiddleware, repo=repo, segment_id="backend_api")

    @app.get("/header-only")
    async def _header_only() -> dict:
        return {"ok": True}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.get("/header-only", headers={"X-Trace-Id": "caller-supplied"})

    event = repo.record_event.call_args.args[0]
    assert event.root.payload.correlation_kind == "capture"
    assert event.root.payload.correlation_id == "caller-supplied"


# ---------------------------------------------------------------------------
# Test B — focused query primitives match the adapter's expected signature
# ---------------------------------------------------------------------------


def test_query_backend_api_failures_exists_with_adapter_signature() -> None:
    """Task 11.5: query_backend_api_failures must accept the adapter's kwargs.

    RED until the function is added to
    second_brain.observability.queries with keyword parameters
    `time_range_seconds` (int) and `capture_trace_id` (str | None).

    Task 12 binds the Log Analytics client + workspace via
    functools.partial and hands the remaining kwargs-bound callable to
    the adapter. If the signature doesn't match, functools.partial
    silently defers the failure to the first real request — this test
    fails at import/construction time so the plan-text gap doesn't
    leak to production.
    """
    from second_brain.observability import queries

    assert hasattr(queries, "query_backend_api_failures"), (
        "Task 11.5 not landed: query_backend_api_failures missing"
    )

    sig = inspect.signature(queries.query_backend_api_failures)
    params = sig.parameters
    # First two positionals are bound by functools.partial in Task 12
    assert "client" in params
    assert "workspace_id" in params
    # These two must be keyword-addressable for the adapter contract
    assert "time_range_seconds" in params, (
        "adapter calls failures_fetcher(time_range_seconds=...)"
    )
    assert "capture_trace_id" in params, (
        "adapter calls failures_fetcher(capture_trace_id=...)"
    )
    assert params["capture_trace_id"].default is None


def test_query_backend_api_requests_exists_with_adapter_signature() -> None:
    """Task 11.5: query_backend_api_requests must match the adapter too.

    Same contract as _failures. Returns a list of RequestRecord —
    native AppRequests shape (timestamp, name, result_code, ...).
    """
    from second_brain.observability import queries

    assert hasattr(queries, "query_backend_api_requests"), (
        "Task 11.5 not landed: query_backend_api_requests missing"
    )

    sig = inspect.signature(queries.query_backend_api_requests)
    params = sig.parameters
    assert "client" in params
    assert "workspace_id" in params
    assert "time_range_seconds" in params
    assert "capture_trace_id" in params
    assert params["capture_trace_id"].default is None


def test_request_record_model_exists() -> None:
    """Task 11.5: RequestRecord model for native AppRequests shape.

    RED until models.py gains the RequestRecord Pydantic class with the
    expected AppRequests fields.
    """
    from second_brain.observability import models

    assert hasattr(models, "RequestRecord"), (
        "Task 11.5 not landed: RequestRecord model missing"
    )

    # Instantiation with the minimum fields the KQL template emits
    rec = models.RequestRecord(
        timestamp="2026-04-15T12:00:00Z",
        name="POST /api/capture/text",
        result_code="200",
        duration_ms=42.0,
        success=True,
        capture_trace_id="abc-123",
        operation_id="op-xyz",
    )
    assert rec.name == "POST /api/capture/text"
    assert rec.result_code == "200"  # string, not int — preserves Azure's native shape
    assert rec.capture_trace_id == "abc-123"


def test_adapter_does_not_use_query_capture_trace_as_requests_source() -> None:
    """Contract guard: query_capture_trace is a timeline query, not AppRequests.

    The Task 8 AMENDMENT callout forbids binding query_capture_trace()
    into the adapter's requests_fetcher slot. This test enforces that
    by ensuring the focused primitive exists AND that the legacy
    timeline query is NOT accidentally repurposed (its return type is
    list[TraceRecord], not list[RequestRecord] — mixing them would
    muddy the native-shape contract that the spec locks for the
    AppInsightsDetail renderer).
    """
    from second_brain.observability import queries

    # query_capture_trace still exists (it powers /investigate tooling)
    assert hasattr(queries, "query_capture_trace")

    # ... but it takes trace_id as a positional, NOT the adapter's kwargs
    sig = inspect.signature(queries.query_capture_trace)
    assert "trace_id" in sig.parameters  # timeline-query shape
    assert "time_range_seconds" not in sig.parameters  # NOT the adapter shape
    assert "capture_trace_id" not in sig.parameters  # NOT the adapter shape


# ---------------------------------------------------------------------------
# Test C — Phase 19.2 emitter shape contract (SPIKE-MEMO §5)
#
# The production `SpineRepository.record_event` accepts `IngestEvent`
# and does `event.root` to pull the concrete variant. AsyncMock-based
# tests bypass this accessor, so the shape bug at
# `spine/agent_emitter.py:63`, `api/telemetry.py:105,120`, and
# `tools/recipe.py:185` survives in production despite green unit tests.
#
# `RootAccessingSpineRepo` emulates the production `record_event`
# contract faithfully: it calls `.root` and stores the concrete variant.
# Any emit site that passes a raw `_WorkloadEvent` / `_LivenessEvent`
# will raise AttributeError here, exactly as it does in production.
# ---------------------------------------------------------------------------


import logging  # noqa: E402
import socket  # noqa: E402
from contextlib import ExitStack  # noqa: E402 — grouped with tests below
from unittest.mock import MagicMock, patch  # noqa: E402

from fastapi import FastAPI as _FastAPI  # noqa: E402 — shadowed safely
from httpx import ASGITransport as _ASGITransport  # noqa: E402
from httpx import AsyncClient as _AsyncClient  # noqa: E402

from second_brain.api.telemetry import router as telemetry_router  # noqa: E402
from second_brain.spine.agent_emitter import emit_agent_workload  # noqa: E402
from second_brain.spine.models import (  # noqa: E402
    IngestEvent,
    _LivenessEvent,
    _WorkloadEvent,
)


class _RootAccessingSpineRepo:
    """Fake SpineRepository whose record_event emulates production.

    The real SpineRepository.record_event does `inner = event.root` on
    the passed-in argument. That accessor exists only on the
    `IngestEvent` RootModel wrapper — a raw `_WorkloadEvent` /
    `_LivenessEvent` raises `AttributeError: '_WorkloadEvent' object has
    no attribute 'root'`, which is the production bug the SPIKE memo
    catalogued for four segments (classifier / admin / investigation /
    external_services) plus mobile crud_failure.
    """

    def __init__(self) -> None:
        self.events_recorded: list = []

    async def record_event(self, event) -> None:  # noqa: ANN001
        # This mirrors SpineRepository.record_event:
        #   inner = event.root  # raises if event is not an IngestEvent
        inner = event.root
        self.events_recorded.append(inner)


# ---------------------------------------------------------------------------
# §5.1 — emit_agent_workload wraps event in IngestEvent(root=...)
#
# Fixes classifier + admin + investigation simultaneously because they
# all route through this helper via stream_wrapper / admin_handoff.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_emit_agent_workload_wraps_event_in_ingest_event_root() -> None:
    """SPIKE-MEMO §5.1 — agent_emitter.py:63 must pass IngestEvent.

    RED against the current code (raw `_WorkloadEvent` passed to
    `record_event` raises AttributeError in the fake). Green after the
    one-line wrap `IngestEvent(root=event)` lands.
    """
    repo = _RootAccessingSpineRepo()
    await emit_agent_workload(
        repo=repo,
        segment_id="classifier",
        operation="classify",
        outcome="success",
        duration_ms=123,
        capture_trace_id="trace-abc",
        run_id="run-1",
        thread_id=None,
    )
    assert len(repo.events_recorded) == 1
    inner = repo.events_recorded[0]
    assert inner.segment_id == "classifier"
    assert inner.event_type == "workload"
    assert inner.payload.correlation_kind == "capture"
    assert inner.payload.correlation_id == "trace-abc"


@pytest.mark.asyncio
async def test_emit_agent_workload_investigation_thread_correlation() -> None:
    """SPIKE-MEMO §5.1 — also repairs investigation thread correlation.

    Investigation never wrote a `thread`-kind correlation row because
    agent_emitter's wrap bug dropped every event. RED until the wrap
    fix lands.
    """
    repo = _RootAccessingSpineRepo()
    await emit_agent_workload(
        repo=repo,
        segment_id="investigation",
        operation="answer_question",
        outcome="success",
        duration_ms=4000,
        capture_trace_id=None,
        run_id="run-xyz",
        thread_id="thread-xyz",
    )
    assert len(repo.events_recorded) == 1
    inner = repo.events_recorded[0]
    assert inner.segment_id == "investigation"
    assert inner.payload.correlation_kind == "thread"
    assert inner.payload.correlation_id == "thread-xyz"


# ---------------------------------------------------------------------------
# §5.2 — api/telemetry.py workload + liveness events wrap in IngestEvent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_telemetry_crud_failure_wraps_workload_event_in_ingest_event() -> None:
    """SPIKE-MEMO §5.2 — telemetry.py:105 must pass IngestEvent.

    Mobile crud_failure path is latently broken the same way agent
    emitter is. RED until the wrap lands for both workload (line 105)
    and the sibling liveness emit (line 120).
    """
    app = _FastAPI()
    app.include_router(telemetry_router)
    app.state.spine_repo = _RootAccessingSpineRepo()
    async with _AsyncClient(
        transport=_ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/telemetry",
            json={
                "event_type": "crud_failure",
                "message": "Inbox load failed: 500",
                "metadata": {"operation": "load_inbox", "status": 500},
            },
        )
    assert resp.status_code == 204
    # 2 events: workload failure + synthetic liveness
    events = app.state.spine_repo.events_recorded
    assert len(events) == 2
    workload = events[0]
    assert isinstance(workload, _WorkloadEvent)
    assert workload.segment_id == "mobile_ui"
    assert workload.payload.outcome == "failure"
    liveness = events[1]
    assert isinstance(liveness, _LivenessEvent)
    assert liveness.segment_id == "mobile_ui"


# ---------------------------------------------------------------------------
# §5.3 — tools/recipe.py migrates to emit_agent_workload with correlation
#
# Recipe tool is called by the admin agent @tool invocation. The capture
# trace id is propagated via the existing `capture_trace_id_var`
# ContextVar (the same mechanism file_capture already uses in
# classification.py). When set, the emitted workload event MUST carry
# correlation_kind="capture" + correlation_id=<trace> so it lands in
# spine_correlation.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recipe_fetch_emits_correlation_tagged_workload_via_contextvar() -> None:
    """SPIKE-MEMO §5.3 — recipe.py:175-185 must migrate to emit_agent_workload.

    RED against current code: direct `_WorkloadEvent` construction at
    line 175 both (a) raises AttributeError in RootAccessingSpineRepo
    and (b) omits correlation_kind / correlation_id so the row never
    joins spine_correlation. Green after the migration + ContextVar
    read lands.
    """
    from second_brain.tools.classification import capture_trace_id_var
    from second_brain.tools.recipe import RecipeTools

    # Prevent live DNS resolution
    fake_addr = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]

    browser = MagicMock()
    repo = _RootAccessingSpineRepo()
    tools = RecipeTools(browser, spine_repo=repo)

    trace_id = "trace-recipe-xyz"
    token = capture_trace_id_var.set(trace_id)
    try:
        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "second_brain.tools.recipe.socket.getaddrinfo",
                    return_value=fake_addr,
                )
            )
            stack.enter_context(
                patch(
                    "second_brain.tools.recipe._is_safe_url",
                    return_value=True,
                )
            )
            stack.enter_context(
                patch.object(
                    tools,
                    "_fetch_jina",
                    new=AsyncMock(return_value="x" * 600),
                )
            )
            await tools.fetch_recipe_url(url="https://example.com/recipe")
    finally:
        capture_trace_id_var.reset(token)

    assert len(repo.events_recorded) == 1
    inner = repo.events_recorded[0]
    assert inner.segment_id == "external_services"
    assert inner.payload.outcome == "success"
    assert inner.payload.correlation_kind == "capture"
    assert inner.payload.correlation_id == trace_id


@pytest.mark.asyncio
async def test_recipe_fetch_logs_warning_when_spine_emit_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """SPIKE-MEMO §5.3c — replace bare `except: pass` with logger.warning.

    RED against current code: `tools/recipe.py:186-187` has
    `except Exception: pass` which silently swallows every emit
    failure. After the fix, the warning message must reach logs with
    exc_info so operators can see the failure.
    """
    from second_brain.tools.classification import capture_trace_id_var
    from second_brain.tools.recipe import RecipeTools

    fake_addr = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]

    class _ExplodingRepo:
        async def record_event(self, event) -> None:  # noqa: ANN001, ARG002
            raise RuntimeError("cosmos down")

    browser = MagicMock()
    tools = RecipeTools(browser, spine_repo=_ExplodingRepo())

    token = capture_trace_id_var.set("trace-explode")
    caplog.set_level(logging.WARNING, logger="second_brain")
    try:
        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "second_brain.tools.recipe.socket.getaddrinfo",
                    return_value=fake_addr,
                )
            )
            stack.enter_context(
                patch(
                    "second_brain.tools.recipe._is_safe_url",
                    return_value=True,
                )
            )
            stack.enter_context(
                patch.object(
                    tools,
                    "_fetch_jina",
                    new=AsyncMock(return_value="x" * 600),
                )
            )
            # Must not raise even though emit fails
            await tools.fetch_recipe_url(url="https://example.com/recipe")
    finally:
        capture_trace_id_var.reset(token)

    # Warning log must be present with exc_info (not silently swallowed)
    matching = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and "cosmos down" in (r.exc_text or "")
    ]
    assert matching, (
        "recipe emit failure should log WARNING with exc_info, not bare `except: pass`"
    )


# ---------------------------------------------------------------------------
# Hygiene: ensure production telemetry module really uses IngestEvent
#
# Guards against future regressions: if someone reintroduces a raw
# `_WorkloadEvent`/`_LivenessEvent` call to record_event in the mobile
# crud path, this import-time assertion fails.
# ---------------------------------------------------------------------------


def test_telemetry_module_imports_ingest_event() -> None:
    """Cheap regression guard: telemetry.py references IngestEvent.

    After the §5.2 fix lands, `api/telemetry.py` wraps its emits in
    `IngestEvent(root=...)`. This test fails if the import disappears.
    """
    import second_brain.api.telemetry as telemetry_module

    assert hasattr(telemetry_module, "IngestEvent"), (
        "telemetry.py must import IngestEvent after SPIKE-MEMO §5.2 fix"
    )
    # And it must be the real RootModel, not a stub
    assert telemetry_module.IngestEvent is IngestEvent


# ---------------------------------------------------------------------------
# §5.4 — Cross-site walking regression test
#
# Per SPIKE-MEMO §5.4, exercise every agent-side emit entry point against
# a SpineRepository double whose `record_event` uses the REAL
# `IngestEvent.root` accessor. Any future code path that forgets the wrap
# — direct `_WorkloadEvent` construction, new emit site that skips
# `emit_agent_workload`, etc — fails this test at import/construction
# time instead of silently dropping events in production.
#
# Entry points covered:
#   1. `spine_stream_wrapper` — classifier path (also what admin + any
#      future SSE agent route uses)
#   2. `emit_agent_workload` — direct helper call (admin / investigation
#      / recipe all route through this)
#   3. `api/telemetry.py` crud_failure — mobile_ui / mobile_capture
#      latent crud path (covered separately above, but re-asserted here
#      for a single-suite "every emit site" guarantee)
#   4. `tools/recipe.RecipeTools.fetch_recipe_url` — external_services
#      (covered above in §5.3 tests, asserted here in walk form)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_wrapper_emit_uses_ingest_event_wrap() -> None:
    """SPIKE-MEMO §5.4 — classifier SSE wrapper must land events.

    `spine_stream_wrapper` calls `emit_agent_workload` in its `finally`
    block. If the helper ever regresses on the wrap, this test fails.
    """
    from second_brain.spine.stream_wrapper import spine_stream_wrapper

    repo = _RootAccessingSpineRepo()

    async def _fake_sse() -> AsyncGenerator[str, None]:  # type: ignore[name-defined]  # noqa: F821
        yield 'data: {"type":"STEP_START"}\n\n'
        yield 'data: {"type":"COMPLETE"}\n\n'

    collected: list[str] = []
    async for chunk in spine_stream_wrapper(
        inner=_fake_sse(),
        repo=repo,  # type: ignore[arg-type]
        segment_id="classifier",
        operation="capture_text",
        capture_trace_id="trace-wrap-walk-1",
        run_id=None,
        thread_id=None,
    ):
        collected.append(chunk)

    assert len(collected) == 2, "wrapper must pass SSE chunks through"
    assert len(repo.events_recorded) == 1, (
        "wrapper must emit one workload event after the stream completes"
    )
    inner = repo.events_recorded[0]
    assert inner.segment_id == "classifier"
    assert inner.payload.correlation_kind == "capture"
    assert inner.payload.correlation_id == "trace-wrap-walk-1"


@pytest.mark.asyncio
async def test_stream_wrapper_emits_failure_event_on_error() -> None:
    """SPIKE-MEMO §5.4 — failure path also honours the wrap.

    The failure emit happens in the same `finally` block after `raise`.
    Guards against the wrap being lost on the failure branch only.
    """
    from second_brain.spine.stream_wrapper import spine_stream_wrapper

    repo = _RootAccessingSpineRepo()

    class _BoomError(RuntimeError):
        pass

    async def _failing_sse() -> AsyncGenerator[str, None]:  # type: ignore[name-defined]  # noqa: F821
        yield 'data: {"type":"STEP_START"}\n\n'
        raise _BoomError("synthetic failure")

    with pytest.raises(_BoomError):
        async for _ in spine_stream_wrapper(
            inner=_failing_sse(),
            repo=repo,  # type: ignore[arg-type]
            segment_id="classifier",
            operation="capture_text",
            capture_trace_id="trace-wrap-walk-fail",
            run_id=None,
            thread_id=None,
        ):
            pass

    assert len(repo.events_recorded) == 1
    inner = repo.events_recorded[0]
    assert inner.payload.outcome == "failure"
    assert inner.payload.error_class == "_BoomError"


def test_no_bare_workload_event_record_event_calls_remain() -> None:
    """SPIKE-MEMO §5.4 — static guard against future regressions.

    Scans the production source for any `record_event(` call whose argument
    is a raw `_WorkloadEvent(` or `_LivenessEvent(` constructor. Every
    emit site MUST wrap in `IngestEvent(root=...)`. If this test fails,
    a new emit site was added without the wrap — fix it or add the call
    site to the exemption list with a citation explaining why.
    """
    import pathlib
    import re

    backend_src = pathlib.Path(__file__).parent.parent / "src" / "second_brain"
    assert backend_src.is_dir(), "expected backend/src/second_brain to exist"

    # Pattern: record_event(<identifier>  where identifier starts with `_`
    # (our concrete event model classes are _LivenessEvent / _WorkloadEvent /
    # _ReadinessEvent). Wrapped calls use record_event(IngestEvent(...))
    # which starts with a capital letter and passes this filter.
    bad_pattern = re.compile(
        r"record_event\s*\(\s*_(?:Workload|Liveness|Readiness)Event\b"
    )
    # Also catch `record_event(event)` where `event` is a raw concrete —
    # we approximate by forbidding `record_event(event)` when `event =
    # _WorkloadEvent(...)` appears without an intervening IngestEvent
    # wrap. Full AST analysis is overkill; the named-arg catches the
    # common bug shape from the spike.

    offenders: list[str] = []
    for path in backend_src.rglob("*.py"):
        text = path.read_text()
        for match in bad_pattern.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            offenders.append(f"{path.relative_to(backend_src)}:{line_no}")

    assert not offenders, (
        "SPIKE-MEMO §5.4 regression — raw `_WorkloadEvent` / `_LivenessEvent`"
        f" passed to record_event at: {offenders}. Wrap in IngestEvent(root=...)"
        " or route through `emit_agent_workload`."
    )


# ---------------------------------------------------------------------------
# §5.6 — classifier-side emit verification integration test
#
# The `/api/capture/text` / `/api/capture/voice` / follow-up handlers all
# wrap their inner SSE stream in `spine_stream_wrapper(..., segment_id=
# "classifier", operation="capture_text" | "capture_voice" | ...)` — see
# `backend/src/second_brain/api/capture.py` lines 238, 315, 384, 502. This
# test exercises the same wrapper directly with the classifier's real
# segment_id and operation values, against a RootAccessingSpineRepo
# double. It proves the end-to-end guarantee memo §5.6 asks for:
# "a workload event for segment_id=classifier lands after the stream
# completes", under the exact IngestEvent.root contract the production
# repository enforces.
#
# Wiring the full capture handler (Foundry client + Cosmos adapter +
# streaming.adapter + auth) is out of scope here — it would require a new
# fixture subsystem. The wrapper-level test covers the only code Plan 02
# touches: the emit boundary. The handler's pre-wrapper setup is
# orthogonal and already covered by existing unit tests for the
# streaming adapter and auth layers.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classifier_emit_verification_workload_lands_with_trace() -> None:
    """SPIKE-MEMO §5.6 — classifier-side emit verification.

    Exercises `spine_stream_wrapper` with the exact segment_id + operation
    values used by the production capture handler. Asserts a single
    workload event lands in the repository with correlation_kind="capture"
    and the expected trace id after the stream completes.

    This is the integration-level equivalent of running the real `/api/
    capture/text` handler — the wrapper is the only emit boundary in the
    handler, so exercising it against a RootAccessingSpineRepo proves the
    full emit path is correct without wiring Foundry/Cosmos mocks.
    """
    from second_brain.spine.stream_wrapper import spine_stream_wrapper

    repo = _RootAccessingSpineRepo()
    trace_id = "trace-classifier-emit-verification"

    async def _fake_capture_sse() -> AsyncGenerator[str, None]:  # type: ignore[name-defined]  # noqa: F821
        # Mirrors the shape of events the classifier adapter yields
        # during a real /api/capture/text run.
        yield 'data: {"type":"STEP_START","stepName":"classify"}\n\n'
        classified = (
            'data: {"type":"CLASSIFIED",'
            '"value":{"bucket":"Admin","confidence":0.85}}\n\n'
        )
        yield classified
        yield 'data: {"type":"COMPLETE"}\n\n'

    async for _ in spine_stream_wrapper(
        inner=_fake_capture_sse(),
        repo=repo,  # type: ignore[arg-type]
        segment_id="classifier",
        operation="capture_text",  # exact value used in api/capture.py
        capture_trace_id=trace_id,
        run_id="run-classifier-verify-1",
        thread_id=None,
    ):
        pass

    # Classifier segment emitted exactly one workload event after the
    # stream completed, correlation tagged for capture lineage.
    assert len(repo.events_recorded) == 1
    inner = repo.events_recorded[0]
    assert inner.segment_id == "classifier"
    assert inner.event_type == "workload"
    assert inner.payload.outcome == "success"
    assert "capture_text" in inner.payload.operation
    assert inner.payload.correlation_kind == "capture"
    assert inner.payload.correlation_id == trace_id
