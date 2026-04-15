# Phase 4: Mobile Segments + MCP Migration with 7-Day Parity Gate Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the final two segments (Mobile UI, Mobile capture) backed by Sentry pull + the backend telemetry data already flowing from Phase 3. Build the `MobileTelemetryDetail` web renderer combining Sentry events + telemetry payloads + CRUD failure events. Migrate the MCP tools from direct App Insights queries to spine endpoints, gated by a 7-day parity test that must pass per tool before legacy code is removed.

**Architecture:** Sentry pull adapter wraps Sentry's REST API (filtered per Sentry tag). Mobile capture and Mobile UI use the same adapter with different filter configurations. MobileTelemetryDetail renderer combines three data sources (Sentry + backend telemetry payloads + CRUD failures from Phase 3 spine events) sorted chronologically. MCP migration: each existing tool gets a `--source spine` mode behind a feature flag; parity tests run nightly comparing legacy vs spine output across a canonical query set; tools cut over only after 7 consecutive days of green parity per tool.

**Tech Stack:** Same as prior phases + Sentry REST API (already authenticated via existing org/DSN config).

**Spec reference:** `docs/superpowers/specs/2026-04-14-per-segment-observability-design.md`

**Phase 1+2+3 dependency:** All prior phase tasks must be complete and deployed.

---

## File Structure

**Backend — additions:**

| File | Responsibility |
|---|---|
| `backend/src/second_brain/spine/adapters/sentry.py` | Sentry pull adapter (parameterized by project + tag filter) |
| `backend/src/second_brain/spine/adapters/mobile_telemetry.py` | Reads from `spine_events` for mobile crud_failure data |
| `backend/src/second_brain/spine/adapters/composite.py` | Combines multiple sources for one segment |
| `backend/src/second_brain/mcp_parity/__init__.py` | Parity test framework |
| `backend/src/second_brain/mcp_parity/canonical_queries.py` | Canonical query set per MCP tool |
| `backend/src/second_brain/mcp_parity/runner.py` | Runs both legacy + spine paths and compares |

**Backend — modifications:**

| File | Change |
|---|---|
| `backend/src/second_brain/spine/registry.py` | Add `mobile_ui` and `mobile_capture` segments |
| `backend/src/second_brain/main.py` | Wire 2 sentry adapters + composite adapters; mount parity router |
| `backend/src/second_brain/config.py` | Add `SENTRY_AUTH_TOKEN`, `SENTRY_ORG`, `SENTRY_PROJECT_*` settings |

**Backend — tests:**

| File | Purpose |
|---|---|
| `backend/tests/test_spine_sentry_adapter.py` | Sentry adapter shape |
| `backend/tests/test_spine_mobile_telemetry_adapter.py` | Mobile telemetry adapter reads from spine_events |
| `backend/tests/test_spine_composite_adapter.py` | Composite merges sources |
| `backend/tests/test_mcp_parity_runner.py` | Parity comparator |

**MCP — modifications:**

| File | Change |
|---|---|
| `mcp/server.py` | Add `--source spine` flag per tool; spine path calls `/api/spine/*` via httpx |
| `mcp/parity_check.py` | NEW: standalone script that runs the parity suite |
| `.github/workflows/mcp-parity.yml` | NEW: nightly job that runs parity check + reports |

**Web — additions:**

| File | Responsibility |
|---|---|
| `web/components/renderers/MobileTelemetryDetail.tsx` | Renderer for `mobile_telemetry_combined` schema |
| `web/app/segment/[id]/page.tsx` | Add dispatcher branch |

**Mobile — modifications:**

| File | Change |
|---|---|
| `mobile/lib/sentry.ts` | Set `Sentry.setTag("capture_trace_id", id)` (and `correlation_kind`) at trace-creation sites |
| `mobile/app/<status-screen-file>.tsx` | Add 2 final spine tiles |

---

## Task 1: Mobile-side Sentry tagging for trace correlation

**Files:**
- Modify: `mobile/lib/sentry.ts`
- Modify: `mobile/lib/telemetry.ts` (or wherever `generateTraceId` is called)

- [ ] **Step 1: Read existing Sentry init**

```bash
cat mobile/lib/sentry.ts
```

Verify Sentry SDK is initialized and exposes `Sentry.setTag`/`Sentry.setContext`.

- [ ] **Step 2: Add a tag-setter helper to sentry.ts**

```typescript
import * as Sentry from "@sentry/react-native";

export function tagTrace(captureTraceId: string): void {
  Sentry.setTag("capture_trace_id", captureTraceId);
  Sentry.setTag("correlation_kind", "capture");
  Sentry.setTag("correlation_id", captureTraceId);
}

export function clearTraceTags(): void {
  Sentry.setTag("capture_trace_id", undefined as never);
  Sentry.setTag("correlation_kind", undefined as never);
  Sentry.setTag("correlation_id", undefined as never);
}
```

- [ ] **Step 3: Call `tagTrace` after `generateTraceId`**

In each capture entry point (text capture, voice capture, conversation/follow-up), find where `generateTraceId()` is called and add a `tagTrace(traceId)` call right after.

```bash
grep -rn "generateTraceId" mobile/ --include="*.ts" --include="*.tsx"
```

For each call site, add the tagging:

```typescript
import { tagTrace } from "../lib/sentry";
import { generateTraceId } from "../lib/telemetry";

const traceId = generateTraceId();
tagTrace(traceId);
// ... existing capture logic
```

- [ ] **Step 4: Type-check + commit**

```bash
cd mobile && npx tsc --noEmit
git add mobile/lib/sentry.ts mobile/<call sites>
git commit -m "feat(mobile): tag sentry events with capture_trace_id for spine correlation"
```

EAS rebuild after commit.

---

## Task 2: Sentry config + secrets

**Files:**
- Modify: `backend/src/second_brain/config.py`

- [ ] **Step 1: Add Sentry settings**

In `config.py`, extend the Pydantic Settings class:

```python
class Settings(BaseSettings):
    # ... existing fields
    sentry_auth_token: str | None = None
    sentry_org: str | None = None
    sentry_project_mobile: str | None = None  # if you split by project
    sentry_dsn_mobile: str | None = None  # already exists from Phase 17.3
```

- [ ] **Step 2: Store auth token in Key Vault**

```bash
az keyvault secret set --vault-name wkm-shared-kv --name SENTRY-AUTH-TOKEN --value "<your sentry user/internal-integration auth token>"
```

The token needs `event:read` and `org:read` scopes in Sentry. Generate at `sentry.io/settings/account/api/auth-tokens/`.

- [ ] **Step 3: Wire Container App env vars**

Add to the Container App revision template (whether Bicep or `az containerapp update --set-env-vars`):

```bash
az containerapp update -g shared-services-rg -n second-brain-api \
  --set-env-vars \
    SENTRY_AUTH_TOKEN=secretref:sentry-auth-token \
    SENTRY_ORG=<your-org-slug>
```

(Adjust based on existing Key Vault → Container App secret reference pattern.)

- [ ] **Step 4: Commit (config code only — no secrets)**

```bash
git add backend/src/second_brain/config.py
git commit -m "feat(config): add sentry settings for spine adapter"
```

---

## Task 3: Sentry pull adapter

**Files:**
- Create: `backend/src/second_brain/spine/adapters/sentry.py`
- Test: `backend/tests/test_spine_sentry_adapter.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_spine_sentry_adapter.py`:

```python
"""Tests for the Sentry pull adapter."""

from unittest.mock import AsyncMock

import pytest

from second_brain.spine.adapters.sentry import SentryAdapter


@pytest.mark.asyncio
async def test_fetch_detail_returns_sentry_schema() -> None:
    fetcher = AsyncMock(return_value={"events": [], "issues": []})
    adapter = SentryAdapter(
        segment_id="mobile_ui",
        sentry_fetcher=fetcher,
        native_url_template="https://sentry.io/organizations/test/issues",
        tag_filter={"app_segment": "mobile_ui"},
    )
    result = await adapter.fetch_detail()
    assert result["schema"] == "sentry_event"
    assert "events" in result
    assert "issues" in result


@pytest.mark.asyncio
async def test_fetch_detail_with_capture_correlation_filters_by_tag() -> None:
    fetcher = AsyncMock(return_value={"events": [], "issues": []})
    adapter = SentryAdapter(
        segment_id="mobile_ui",
        sentry_fetcher=fetcher,
        native_url_template="x",
        tag_filter={"app_segment": "mobile_ui"},
    )
    await adapter.fetch_detail(correlation_kind="capture", correlation_id="trace-1")
    fetcher.assert_called_once()
    # The fetcher receives merged tag filter: app_segment + capture_trace_id
    kwargs = fetcher.call_args.kwargs
    assert kwargs["tag_filter"]["capture_trace_id"] == "trace-1"
    assert kwargs["tag_filter"]["app_segment"] == "mobile_ui"
```

- [ ] **Step 2: Verify failure**

```bash
cd backend && uv run pytest tests/test_spine_sentry_adapter.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement adapter**

Create `backend/src/second_brain/spine/adapters/sentry.py`:

```python
"""Sentry segment adapter — pulls events + issues from Sentry REST API."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from second_brain.spine.models import CorrelationKind

logger = logging.getLogger(__name__)


class SentryAdapter:
    """Pulls Sentry events + issues, filterable by tags.

    Uses the Sentry REST API. The fetcher is injected for testability;
    the production fetcher is a thin wrapper around httpx that hits
    /api/0/projects/{org}/{project}/events/ with a query like
    `?query=<tag_key>:<tag_value> <tag_key>:<tag_value>`.
    """

    def __init__(
        self,
        segment_id: str,
        sentry_fetcher: Callable[..., Awaitable[dict[str, Any]]],
        native_url_template: str,
        tag_filter: dict[str, str],
    ) -> None:
        self.segment_id = segment_id
        self._fetcher = sentry_fetcher
        self.native_url_template = native_url_template
        self._base_tag_filter = dict(tag_filter)

    async def fetch_detail(
        self,
        correlation_kind: CorrelationKind | None = None,
        correlation_id: str | None = None,
        time_range_seconds: int = 3600,
    ) -> dict[str, Any]:
        merged_filter = dict(self._base_tag_filter)
        if correlation_kind == "capture" and correlation_id:
            merged_filter["capture_trace_id"] = correlation_id
        elif correlation_kind == "crud" and correlation_id:
            merged_filter["correlation_id"] = correlation_id

        result = await self._fetcher(
            tag_filter=merged_filter, time_range_seconds=time_range_seconds,
        )
        return {
            "schema": "sentry_event",
            "events": result.get("events", []),
            "issues": result.get("issues", []),
            "tag_filter": merged_filter,
            "native_url": self.native_url_template,
        }


async def make_sentry_fetcher(
    auth_token: str, org: str, project: str,
) -> Callable[..., Awaitable[dict[str, Any]]]:
    """Build a production fetcher closure bound to org/project credentials."""

    async def _fetch(tag_filter: dict[str, str], time_range_seconds: int) -> dict[str, Any]:
        # Sentry query syntax: "key:value key2:value2" space-separated
        query = " ".join(f"{k}:{v}" for k, v in tag_filter.items())
        url = f"https://sentry.io/api/0/projects/{org}/{project}/events/"
        params = {"query": query, "statsPeriod": f"{time_range_seconds}s"}
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    url,
                    params=params,
                    headers={"Authorization": f"Bearer {auth_token}"},
                    timeout=10.0,
                )
                resp.raise_for_status()
                events = resp.json()
            except Exception:
                logger.warning("Sentry fetch failed", exc_info=True)
                events = []
        # Optional: also fetch issues endpoint
        return {"events": events, "issues": []}

    return _fetch
```

- [ ] **Step 4: Tests pass**

```bash
cd backend && uv run pytest tests/test_spine_sentry_adapter.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/second_brain/spine/adapters/sentry.py backend/tests/test_spine_sentry_adapter.py
git commit -m "feat(spine): sentry pull adapter with tag-based filtering"
```

---

## Task 4: Mobile telemetry adapter (reads spine_events for mobile crud failures)

**Files:**
- Create: `backend/src/second_brain/spine/adapters/mobile_telemetry.py`
- Test: `backend/tests/test_spine_mobile_telemetry_adapter.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_spine_mobile_telemetry_adapter.py`:

```python
"""Tests for the mobile telemetry adapter."""

from unittest.mock import AsyncMock

import pytest

from second_brain.spine.adapters.mobile_telemetry import MobileTelemetryAdapter


@pytest.mark.asyncio
async def test_fetch_detail_returns_telemetry_schema() -> None:
    repo = AsyncMock()
    repo.get_recent_events.return_value = []
    adapter = MobileTelemetryAdapter(
        segment_id="mobile_ui",
        repo=repo,
        native_url="https://portal.azure.com/#blade/AppInsightsExtension",
    )
    result = await adapter.fetch_detail()
    assert result["schema"] == "mobile_telemetry"
    assert "telemetry_events" in result


@pytest.mark.asyncio
async def test_fetch_detail_filters_to_segment_workload_failures() -> None:
    repo = AsyncMock()
    repo.get_recent_events.return_value = [
        {"event_type": "workload", "payload": {"outcome": "failure", "operation": "load_inbox"}},
        {"event_type": "workload", "payload": {"outcome": "success", "operation": "load_inbox"}},
        {"event_type": "liveness", "payload": {"instance_id": "i1"}},
    ]
    adapter = MobileTelemetryAdapter(
        segment_id="mobile_ui",
        repo=repo,
        native_url="x",
    )
    result = await adapter.fetch_detail()
    # Only failure workload events shown by default
    assert len(result["telemetry_events"]) == 1
    assert result["telemetry_events"][0]["payload"]["outcome"] == "failure"
```

- [ ] **Step 2: Verify failure**

```bash
cd backend && uv run pytest tests/test_spine_mobile_telemetry_adapter.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement adapter**

Create `backend/src/second_brain/spine/adapters/mobile_telemetry.py`:

```python
"""Mobile telemetry adapter — reads from spine_events for crud_failure data."""

from __future__ import annotations

from typing import Any

from second_brain.spine.models import CorrelationKind
from second_brain.spine.storage import SpineRepository


class MobileTelemetryAdapter:
    """Pulls mobile crud_failure workload events from spine_events.

    These were ingested by the backend telemetry endpoint (Phase 3 Task 9).
    """

    def __init__(
        self,
        segment_id: str,
        repo: SpineRepository,
        native_url: str,
    ) -> None:
        self.segment_id = segment_id
        self._repo = repo
        self.native_url_template = native_url

    async def fetch_detail(
        self,
        correlation_kind: CorrelationKind | None = None,
        correlation_id: str | None = None,
        time_range_seconds: int = 3600,
    ) -> dict[str, Any]:
        events = await self._repo.get_recent_events(
            segment_id=self.segment_id, window_seconds=time_range_seconds,
        )
        # Show only workload failures by default — those are the actionable ones
        failures = [
            e for e in events
            if e["event_type"] == "workload"
            and e["payload"]["outcome"] == "failure"
        ]
        return {
            "schema": "mobile_telemetry",
            "telemetry_events": failures,
            "native_url": self.native_url_template,
        }
```

- [ ] **Step 4: Tests pass + commit**

```bash
cd backend && uv run pytest tests/test_spine_mobile_telemetry_adapter.py -v
git add backend/src/second_brain/spine/adapters/mobile_telemetry.py backend/tests/test_spine_mobile_telemetry_adapter.py
git commit -m "feat(spine): mobile telemetry adapter reads spine_events for crud failures"
```

---

## Task 5: Composite adapter (combines Sentry + mobile telemetry for one segment)

**Files:**
- Create: `backend/src/second_brain/spine/adapters/composite.py`
- Test: `backend/tests/test_spine_composite_adapter.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_spine_composite_adapter.py`:

```python
"""Tests for the composite adapter that combines multiple sources."""

from unittest.mock import AsyncMock

import pytest

from second_brain.spine.adapters.composite import CompositeAdapter


@pytest.mark.asyncio
async def test_composite_returns_combined_schema() -> None:
    a1 = AsyncMock()
    a1.segment_id = "mobile_ui"
    a1.native_url_template = "https://sentry.io"
    a1.fetch_detail.return_value = {
        "schema": "sentry_event",
        "events": [{"id": "e1", "timestamp": "2026-04-14T12:00:00Z"}],
        "native_url": "https://sentry.io",
    }
    a2 = AsyncMock()
    a2.segment_id = "mobile_ui"
    a2.fetch_detail.return_value = {
        "schema": "mobile_telemetry",
        "telemetry_events": [{"payload": {"operation": "load_inbox"}, "timestamp": "2026-04-14T12:01:00Z"}],
        "native_url": "https://portal.azure.com",
    }

    composite = CompositeAdapter(
        segment_id="mobile_ui",
        sources={"sentry": a1, "telemetry": a2},
        native_url="https://sentry.io",
    )

    result = await composite.fetch_detail()
    assert result["schema"] == "mobile_telemetry_combined"
    assert "sources" in result
    assert "sentry" in result["sources"]
    assert "telemetry" in result["sources"]
    assert result["sources"]["sentry"]["schema"] == "sentry_event"
```

- [ ] **Step 2: Verify failure**

```bash
cd backend && uv run pytest tests/test_spine_composite_adapter.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement composite**

Create `backend/src/second_brain/spine/adapters/composite.py`:

```python
"""Composite adapter — fans out to multiple source adapters and combines results.

Used for mobile segments where data lives in multiple native systems.
The combined schema lets the renderer present them as a unified timeline
while preserving each source's native shape.
"""

from __future__ import annotations

import asyncio
from typing import Any

from second_brain.spine.adapters.base import SegmentAdapter
from second_brain.spine.models import CorrelationKind


class CompositeAdapter:
    """Fan-out adapter that aggregates results from named sources."""

    def __init__(
        self,
        segment_id: str,
        sources: dict[str, SegmentAdapter],
        native_url: str,
    ) -> None:
        self.segment_id = segment_id
        self._sources = sources
        self.native_url_template = native_url

    async def fetch_detail(
        self,
        correlation_kind: CorrelationKind | None = None,
        correlation_id: str | None = None,
        time_range_seconds: int = 3600,
    ) -> dict[str, Any]:
        names = list(self._sources.keys())
        results = await asyncio.gather(
            *[
                src.fetch_detail(
                    correlation_kind=correlation_kind,
                    correlation_id=correlation_id,
                    time_range_seconds=time_range_seconds,
                )
                for src in self._sources.values()
            ],
            return_exceptions=True,
        )
        sources_out: dict[str, Any] = {}
        partial_failures: list[str] = []
        for name, res in zip(names, results, strict=False):
            if isinstance(res, Exception):
                partial_failures.append(name)
                continue
            sources_out[name] = res
        return {
            "schema": "mobile_telemetry_combined",
            "sources": sources_out,
            "partial_failures": partial_failures,
            "native_url": self.native_url_template,
        }
```

- [ ] **Step 4: Tests pass + commit**

```bash
cd backend && uv run pytest tests/test_spine_composite_adapter.py -v
git add backend/src/second_brain/spine/adapters/composite.py backend/tests/test_spine_composite_adapter.py
git commit -m "feat(spine): composite adapter for multi-source segments"
```

---

## Task 6: Register mobile_ui + mobile_capture segments

**Files:**
- Modify: `backend/src/second_brain/spine/registry.py`
- Create: `backend/tests/test_spine_registry_phase4.py`

- [ ] **Step 1: Write failing test**

```python
"""Phase 4: registry includes mobile_ui and mobile_capture."""

from second_brain.spine.registry import get_default_registry


def test_registry_includes_mobile_ui() -> None:
    cfg = get_default_registry().get("mobile_ui")
    assert cfg.host_segment is None  # mobile is independent of container app
    assert cfg.display_name == "Mobile UI"


def test_registry_includes_mobile_capture() -> None:
    cfg = get_default_registry().get("mobile_capture")
    assert cfg.host_segment is None
```

- [ ] **Step 2: Add segments to `get_default_registry()`**

```python
        EvaluatorConfig(
            segment_id="mobile_ui",
            display_name="Mobile UI",
            liveness_interval_seconds=300,  # liveness from polled Sentry presence
            host_segment=None,
            workload_window_seconds=900,
            yellow_thresholds={
                "workload_failure_rate": 0.10,  # CRUD failures count
            },
            red_thresholds={
                "workload_failure_rate": 0.30,
                "consecutive_failures": 5,
            },
        ),
        EvaluatorConfig(
            segment_id="mobile_capture",
            display_name="Mobile Capture",
            liveness_interval_seconds=300,
            host_segment=None,
            workload_window_seconds=900,
            yellow_thresholds={
                "workload_failure_rate": 0.10,
            },
            red_thresholds={
                "workload_failure_rate": 0.30,
                "consecutive_failures": 3,  # capture failures are higher-severity
            },
        ),
```

- [ ] **Step 3: Tests pass + commit**

```bash
cd backend && uv run pytest tests/test_spine_registry_phase4.py tests/test_spine_registry.py -v
git add backend/src/second_brain/spine/registry.py backend/tests/test_spine_registry_phase4.py
git commit -m "feat(spine): register mobile_ui and mobile_capture segments"
```

---

## Task 7: Wire 2 mobile composite adapters in main.py

**Files:**
- Modify: `backend/src/second_brain/main.py`

- [ ] **Step 1: Add to lifespan**

```python
from second_brain.spine.adapters.sentry import SentryAdapter, make_sentry_fetcher
from second_brain.spine.adapters.mobile_telemetry import MobileTelemetryAdapter
from second_brain.spine.adapters.composite import CompositeAdapter

# Build the Sentry fetcher once
if settings.sentry_auth_token and settings.sentry_org and settings.sentry_project_mobile:
    sentry_fetcher = await make_sentry_fetcher(
        auth_token=settings.sentry_auth_token,
        org=settings.sentry_org,
        project=settings.sentry_project_mobile,
    )

    sentry_ui = SentryAdapter(
        segment_id="mobile_ui",
        sentry_fetcher=sentry_fetcher,
        native_url_template=f"https://sentry.io/organizations/{settings.sentry_org}/projects/{settings.sentry_project_mobile}/?query=app_segment%3Amobile_ui",
        tag_filter={"app_segment": "mobile_ui"},
    )
    sentry_capture = SentryAdapter(
        segment_id="mobile_capture",
        sentry_fetcher=sentry_fetcher,
        native_url_template=f"https://sentry.io/organizations/{settings.sentry_org}/projects/{settings.sentry_project_mobile}/?query=app_segment%3Amobile_capture",
        tag_filter={"app_segment": "mobile_capture"},
    )
else:
    sentry_ui = None
    sentry_capture = None

mobile_telemetry_ui = MobileTelemetryAdapter(
    segment_id="mobile_ui",
    repo=spine_repo,
    native_url="https://portal.azure.com/#blade/AppInsightsExtension",
)
mobile_telemetry_capture = MobileTelemetryAdapter(
    segment_id="mobile_capture",
    repo=spine_repo,
    native_url="https://portal.azure.com/#blade/AppInsightsExtension",
)

mobile_ui_composite = CompositeAdapter(
    segment_id="mobile_ui",
    sources={
        **({"sentry": sentry_ui} if sentry_ui else {}),
        "telemetry": mobile_telemetry_ui,
    },
    native_url=(sentry_ui.native_url_template if sentry_ui else mobile_telemetry_ui.native_url_template),
)
mobile_capture_composite = CompositeAdapter(
    segment_id="mobile_capture",
    sources={
        **({"sentry": sentry_capture} if sentry_capture else {}),
        "telemetry": mobile_telemetry_capture,
    },
    native_url=(sentry_capture.native_url_template if sentry_capture else mobile_telemetry_capture.native_url_template),
)

# Update adapter_registry
adapter_registry = AdapterRegistry([
    backend_api_adapter, classifier_adapter, admin_adapter, investigation_adapter,
    cosmos_adapter,
    # external_services adapter from Phase 3
    mobile_ui_composite, mobile_capture_composite,
])

# 2 more liveness emitters
# NOTE: mobile segments don't have a backend process to heartbeat from.
# Strategy: emit synthetic liveness whenever the backend telemetry endpoint
# receives ANY event from a mobile segment. That way "mobile is alive" =
# "mobile is sending us telemetry."
# Implementation: in the telemetry endpoint (Phase 3 Task 9), additionally
# emit a liveness event for the appropriate mobile segment whenever a
# crud_failure (or any future telemetry) arrives.
```

- [ ] **Step 2: Update telemetry endpoint to emit synthetic mobile liveness**

In `backend/src/second_brain/api/telemetry.py`, after recording the workload event, also emit a liveness event for the same segment:

```python
from second_brain.spine.models import _LivenessEvent, LivenessPayload

# Inside post_telemetry, after the existing workload-event logic:
liveness_event = _LivenessEvent(
    segment_id=segment_id,
    event_type="liveness",
    timestamp=datetime.now(timezone.utc),
    payload=LivenessPayload(instance_id=request.headers.get("user-agent", "unknown")[:64]),
)
try:
    await spine_repo.record_event(liveness_event)
except Exception:
    logger.warning("Failed to emit mobile liveness", exc_info=True)
```

- [ ] **Step 3: Run tests + push**

```bash
cd backend && uv run pytest -x
git add backend/src/second_brain/main.py backend/src/second_brain/api/telemetry.py
git commit -m "feat(spine): wire mobile composite adapters and synthetic liveness"
git push
```

After deploy:

```bash
curl -sS -H "Authorization: Bearer ${API_KEY}" https://brain.willmacdonald.com/api/spine/status \
  | jq '.segments | length'
```

Expected: 9 segments (8 user-facing + container_app).

---

## Task 8: Web MobileTelemetryDetail renderer + dispatcher branch

**Files:**
- Create: `web/components/renderers/MobileTelemetryDetail.tsx`
- Modify: `web/app/segment/[id]/page.tsx`

- [ ] **Step 1: Create renderer**

`web/components/renderers/MobileTelemetryDetail.tsx`:

```typescript
interface SentrySource {
  schema: "sentry_event";
  events: Array<{ id: string; title?: string; timestamp: string; tags?: Record<string, string> }>;
  issues: unknown[];
  native_url: string;
  tag_filter: Record<string, string>;
}

interface TelemetrySource {
  schema: "mobile_telemetry";
  telemetry_events: Array<{ timestamp: string; payload: { operation: string; outcome: string; error_class?: string | null }; }>;
  native_url: string;
}

interface CombinedData {
  schema: "mobile_telemetry_combined";
  sources: {
    sentry?: SentrySource;
    telemetry?: TelemetrySource;
  };
  partial_failures: string[];
  native_url: string;
}

export function MobileTelemetryDetail({ data }: { data: CombinedData }) {
  const sentryEvents = data.sources.sentry?.events ?? [];
  const telemetryEvents = data.sources.telemetry?.telemetry_events ?? [];

  // Build a unified chronological timeline
  type Row = { ts: string; source: "sentry" | "telemetry"; label: string; detail: string };
  const rows: Row[] = [
    ...sentryEvents.map((e) => ({
      ts: e.timestamp,
      source: "sentry" as const,
      label: e.title ?? "Sentry event",
      detail: JSON.stringify(e.tags ?? {}),
    })),
    ...telemetryEvents.map((e) => ({
      ts: e.timestamp,
      source: "telemetry" as const,
      label: e.payload.operation,
      detail: e.payload.error_class ?? e.payload.outcome,
    })),
  ].sort((a, b) => b.ts.localeCompare(a.ts));

  return (
    <div>
      {data.partial_failures.length > 0 && (
        <p style={{ color: "#c89010" }}>
          ⚠ Partial source failures: {data.partial_failures.join(", ")}
        </p>
      )}
      <h2>Combined timeline ({rows.length} events)</h2>
      <p style={{ color: "#888", fontSize: 13 }}>
        Sources: Sentry ({sentryEvents.length}), backend telemetry ({telemetryEvents.length})
      </p>
      {rows.length === 0 ? (
        <p style={{ color: "#888" }}>No recent events.</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ borderBottom: "1px solid #333" }}>
              <th style={{ textAlign: "left", padding: 8 }}>Time</th>
              <th style={{ textAlign: "left", padding: 8 }}>Source</th>
              <th style={{ textAlign: "left", padding: 8 }}>Operation</th>
              <th style={{ textAlign: "left", padding: 8 }}>Detail</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} style={{ borderBottom: "1px solid #1a2028" }}>
                <td style={{ padding: 8, color: "#888" }}>{new Date(r.ts).toLocaleString()}</td>
                <td style={{ padding: 8, color: r.source === "sentry" ? "#c89010" : "#bbb" }}>
                  {r.source}
                </td>
                <td style={{ padding: 8 }}>{r.label}</td>
                <td style={{ padding: 8, fontFamily: "monospace", fontSize: 11 }}>{r.detail}</td>
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

In `web/app/segment/[id]/page.tsx`:

```typescript
import { MobileTelemetryDetail } from "@/components/renderers/MobileTelemetryDetail";

// ...
} : schema === "mobile_telemetry_combined" ? (
  <MobileTelemetryDetail data={detail.data as never} />
) : (
```

- [ ] **Step 3: Type-check + commit**

```bash
cd web && npm run type-check
git add web/components/renderers/MobileTelemetryDetail.tsx web/app/segment/[id]/page.tsx
git commit -m "feat(web): mobile telemetry combined renderer + dispatcher branch"
git push
```

---

## Task 9: Mobile — final 2 spine tiles

**Files:**
- Modify: `mobile/app/<status-screen-file>.tsx`

- [ ] **Step 1: Add 2 final tiles**

```typescript
<SpineStatusTile segmentId="mobile_ui" />
<SpineStatusTile segmentId="mobile_capture" />
```

- [ ] **Step 2: Type-check + EAS rebuild**

```bash
cd mobile && npx tsc --noEmit
```

EAS rebuild and verify all 8 user-facing tiles visible on device.

- [ ] **Step 3: Commit**

```bash
git add mobile/app/<status-screen-file>.tsx
git commit -m "feat(mobile): add mobile_ui and mobile_capture spine tiles"
```

---

## Task 10: MCP parity test framework

**Files:**
- Create: `backend/src/second_brain/mcp_parity/__init__.py`
- Create: `backend/src/second_brain/mcp_parity/canonical_queries.py`
- Create: `backend/src/second_brain/mcp_parity/runner.py`
- Test: `backend/tests/test_mcp_parity_runner.py`

- [ ] **Step 1: Empty `__init__.py`**

```bash
touch backend/src/second_brain/mcp_parity/__init__.py
```

- [ ] **Step 2: Define canonical queries**

`backend/src/second_brain/mcp_parity/canonical_queries.py`:

```python
"""Canonical query set per MCP tool for the parity check.

Start small. Expand as we learn what regressions slip through.
Each entry is (tool_name, args_dict). The runner calls the tool
both via legacy direct-App-Insights path and via spine path,
then compares.
"""

from typing import Any

CANONICAL_QUERIES: list[tuple[str, dict[str, Any]]] = [
    # recent_errors
    ("recent_errors", {"time_range": "1h"}),
    ("recent_errors", {"time_range": "24h"}),
    ("recent_errors", {"time_range": "1h", "component": "classifier"}),

    # system_health
    ("system_health", {"time_range": "1h"}),
    ("system_health", {"time_range": "24h"}),

    # trace_lifecycle — needs a trace_id; runner must inject a recent one
    ("trace_lifecycle", {"trace_id": "__LATEST__"}),

    # usage_patterns
    ("usage_patterns", {"time_range": "24h", "group_by": "bucket"}),
    ("usage_patterns", {"time_range": "24h", "group_by": "destination"}),
    ("usage_patterns", {"time_range": "7d", "group_by": "day"}),

    # admin_audit
    ("admin_audit", {}),

    # run_kql — fixed safe query
    ("run_kql", {"query": "AppRequests | take 5", "time_range": "1h"}),
]
```

- [ ] **Step 3: Implement runner**

`backend/src/second_brain/mcp_parity/runner.py`:

```python
"""Runs each canonical query against legacy + spine paths and compares."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ParityResult:
    """Outcome of one parity comparison."""

    tool_name: str
    args: dict[str, Any]
    legacy_ok: bool
    spine_ok: bool
    matched: bool
    diff_summary: str
    timestamp: datetime


async def run_parity(
    legacy_tool: Callable[..., Awaitable[Any]],
    spine_tool: Callable[..., Awaitable[Any]],
    tool_name: str,
    args: dict[str, Any],
) -> ParityResult:
    """Call both, compare the JSON-serializable shapes."""
    now = datetime.now(timezone.utc)
    legacy_result: Any = None
    spine_result: Any = None
    legacy_ok = False
    spine_ok = False
    try:
        legacy_result = await legacy_tool(**args)
        legacy_ok = True
    except Exception as exc:
        logger.warning("Legacy %s failed: %s", tool_name, exc)
    try:
        spine_result = await spine_tool(**args)
        spine_ok = True
    except Exception as exc:
        logger.warning("Spine %s failed: %s", tool_name, exc)

    matched = False
    diff_summary = ""
    if legacy_ok and spine_ok:
        matched, diff_summary = _compare_shapes(legacy_result, spine_result)
    elif legacy_ok != spine_ok:
        diff_summary = f"only one path returned: legacy_ok={legacy_ok} spine_ok={spine_ok}"

    return ParityResult(
        tool_name=tool_name,
        args=args,
        legacy_ok=legacy_ok,
        spine_ok=spine_ok,
        matched=matched,
        diff_summary=diff_summary,
        timestamp=now,
    )


def _compare_shapes(a: Any, b: Any) -> tuple[bool, str]:
    """Compare two shapes for parity.

    Strategy: serialize both to canonical JSON, compare ignoring keys
    that are intrinsically time-dependent (timestamps, etc.).
    """
    try:
        a_json = json.dumps(_normalize(a), sort_keys=True)
        b_json = json.dumps(_normalize(b), sort_keys=True)
    except (TypeError, ValueError) as exc:
        return False, f"serialization error: {exc}"
    if a_json == b_json:
        return True, ""
    return False, _diff_summary(a, b)


def _normalize(value: Any) -> Any:
    """Normalize timestamps and other ephemeral fields out of comparison."""
    if isinstance(value, dict):
        return {
            k: _normalize(v) for k, v in value.items()
            if k not in {"timestamp", "generated_at", "last_updated", "freshness_seconds", "query_latency_ms"}
        }
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    return value


def _diff_summary(a: Any, b: Any) -> str:
    """Brief description of the first divergence."""
    if type(a) is not type(b):
        return f"type mismatch: {type(a).__name__} vs {type(b).__name__}"
    if isinstance(a, dict):
        keys_a = set(a.keys())
        keys_b = set(b.keys())
        if keys_a != keys_b:
            return f"key mismatch: only_in_a={keys_a - keys_b} only_in_b={keys_b - keys_a}"
        for k in keys_a:
            if a[k] != b[k]:
                return f"value mismatch at key '{k}'"
    if isinstance(a, list):
        if len(a) != len(b):
            return f"length mismatch: {len(a)} vs {len(b)}"
    return "shapes differ"
```

- [ ] **Step 4: Test the runner**

`backend/tests/test_mcp_parity_runner.py`:

```python
"""Tests for the MCP parity runner."""

from unittest.mock import AsyncMock

import pytest

from second_brain.mcp_parity.runner import run_parity


@pytest.mark.asyncio
async def test_identical_results_match() -> None:
    legacy = AsyncMock(return_value={"errors": [], "count": 0})
    spine = AsyncMock(return_value={"errors": [], "count": 0})
    result = await run_parity(legacy, spine, "recent_errors", {"time_range": "1h"})
    assert result.matched is True
    assert result.legacy_ok and result.spine_ok


@pytest.mark.asyncio
async def test_different_counts_do_not_match() -> None:
    legacy = AsyncMock(return_value={"errors": [], "count": 0})
    spine = AsyncMock(return_value={"errors": [], "count": 1})
    result = await run_parity(legacy, spine, "recent_errors", {"time_range": "1h"})
    assert result.matched is False
    assert "value mismatch" in result.diff_summary


@pytest.mark.asyncio
async def test_legacy_failure_only_recorded() -> None:
    legacy = AsyncMock(side_effect=RuntimeError("kql failed"))
    spine = AsyncMock(return_value={"errors": [], "count": 0})
    result = await run_parity(legacy, spine, "recent_errors", {})
    assert result.legacy_ok is False
    assert result.spine_ok is True
    assert result.matched is False


@pytest.mark.asyncio
async def test_timestamps_normalized_out_of_comparison() -> None:
    legacy = AsyncMock(return_value={"timestamp": "2026-04-14T12:00:00Z", "data": [1, 2, 3]})
    spine = AsyncMock(return_value={"timestamp": "2026-04-14T12:00:01Z", "data": [1, 2, 3]})
    result = await run_parity(legacy, spine, "x", {})
    assert result.matched is True
```

```bash
cd backend && uv run pytest tests/test_mcp_parity_runner.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/second_brain/mcp_parity/ backend/tests/test_mcp_parity_runner.py
git commit -m "feat(mcp): parity test framework with normalized comparison"
```

---

## Task 11: Add `--source spine` mode to MCP tools

**Files:**
- Modify: `mcp/server.py`

- [ ] **Step 1: Add a feature flag and HTTP client to the MCP server**

In `mcp/server.py`, near the top:

```python
import os
import httpx

SPINE_BASE_URL = os.environ.get("SPINE_BASE_URL", "https://brain.willmacdonald.com")
SPINE_API_KEY = os.environ.get("SPINE_API_KEY", "")  # same key used elsewhere

def _spine_enabled_for(tool: str) -> bool:
    """Per-tool feature flag — enables spine path during parity period."""
    flag = os.environ.get(f"MCP_SPINE_{tool.upper()}", "off").lower()
    return flag in {"on", "true", "1"}

async def _spine_call(path: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{SPINE_BASE_URL}{path}",
            params=params,
            headers={"Authorization": f"Bearer {SPINE_API_KEY}"},
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()
```

- [ ] **Step 2: Wrap each tool to optionally use spine**

For each existing tool function in `mcp/server.py`, restructure to:

```python
@mcp.tool()
async def recent_errors(time_range: str = "24h", component: str | None = None) -> dict:
    """..."""
    if _spine_enabled_for("recent_errors"):
        # Spine path: GET /api/spine/segment/backend_api with filters
        # then transform into the legacy MCP shape
        body = await _spine_call(
            "/api/spine/segment/backend_api",
            params={"time_range_seconds": _to_seconds(time_range)},
        )
        return _transform_app_insights_to_recent_errors_shape(body, component=component)
    # Legacy path: existing direct App Insights query
    return await _legacy_recent_errors(time_range=time_range, component=component)
```

Apply the pattern to all 6 tools: `recent_errors`, `system_health`, `trace_lifecycle`, `usage_patterns`, `admin_audit`, `run_kql`.

For `run_kql`, the spine path option is debatable (raw KQL has no spine equivalent). Keep `run_kql` legacy-only for v1 and document that decision in the file.

- [ ] **Step 3: Implement transformation helpers**

Each spine response shape is the segment-detail native shape; the MCP tool needs to project it back to its legacy result shape (small, mostly-mechanical transforms). Write each `_transform_*` function such that — for unchanged underlying data — its output equals the legacy function's output (modulo timestamps, which the parity runner normalizes).

- [ ] **Step 4: Add a parity-runner subcommand**

Create `mcp/parity_check.py`:

```python
"""Standalone parity check — runs canonical queries through both paths."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone

# Import both paths from mcp/server.py
from mcp.server import (
    recent_errors as mcp_recent_errors,
    system_health as mcp_system_health,
    trace_lifecycle as mcp_trace_lifecycle,
    usage_patterns as mcp_usage_patterns,
    admin_audit as mcp_admin_audit,
    _spine_call,
)

# Import canonical queries from backend's mcp_parity package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend", "src"))
from second_brain.mcp_parity.canonical_queries import CANONICAL_QUERIES
from second_brain.mcp_parity.runner import run_parity


TOOLS = {
    "recent_errors": mcp_recent_errors,
    "system_health": mcp_system_health,
    "trace_lifecycle": mcp_trace_lifecycle,
    "usage_patterns": mcp_usage_patterns,
    "admin_audit": mcp_admin_audit,
}


async def _resolve_latest_trace_id() -> str:
    """trace_lifecycle parity needs a real trace_id — pull most recent from spine."""
    body = await _spine_call("/api/spine/segment/backend_api")
    excs = body.get("data", {}).get("app_exceptions", []) or body.get("data", {}).get("app_requests", [])
    for row in excs:
        cap = row.get("capture_trace_id")
        if cap:
            return cap
    raise RuntimeError("No recent trace_id found for parity check")


async def main() -> int:
    results = []
    latest_trace = None
    for tool_name, args in CANONICAL_QUERIES:
        if tool_name not in TOOLS:
            continue  # run_kql skipped
        # Resolve __LATEST__ placeholder
        if args.get("trace_id") == "__LATEST__":
            if latest_trace is None:
                latest_trace = await _resolve_latest_trace_id()
            args = {**args, "trace_id": latest_trace}

        # Run with spine flag OFF for legacy
        os.environ[f"MCP_SPINE_{tool_name.upper()}"] = "off"
        legacy_fn = TOOLS[tool_name]

        # Run with spine flag ON for spine
        async def spine_fn(**kw, _name=tool_name):
            os.environ[f"MCP_SPINE_{_name.upper()}"] = "on"
            try:
                return await TOOLS[_name](**kw)
            finally:
                os.environ[f"MCP_SPINE_{_name.upper()}"] = "off"

        result = await run_parity(legacy_fn, spine_fn, tool_name, args)
        results.append(result)

    # Print JSON report
    report = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "results": [
            {
                "tool": r.tool_name,
                "args": r.args,
                "legacy_ok": r.legacy_ok,
                "spine_ok": r.spine_ok,
                "matched": r.matched,
                "diff_summary": r.diff_summary,
            }
            for r in results
        ],
        "summary": {
            "total": len(results),
            "matched": sum(1 for r in results if r.matched),
            "diverged": sum(1 for r in results if not r.matched),
        },
    }
    print(json.dumps(report, indent=2))
    return 0 if all(r.matched for r in results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

- [ ] **Step 5: Commit**

```bash
git add mcp/server.py mcp/parity_check.py
git commit -m "feat(mcp): per-tool spine-source feature flag + parity check script"
```

---

## Task 12: GitHub Actions nightly parity job

**Files:**
- Create: `.github/workflows/mcp-parity.yml`

- [ ] **Step 1: Add the workflow**

```yaml
name: MCP Parity Check

on:
  schedule:
    - cron: '0 8 * * *'  # daily at 08:00 UTC
  workflow_dispatch:

jobs:
  parity:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - uses: astral-sh/setup-uv@v3
        with:
          version: 0.5.4
      - name: Install MCP deps
        working-directory: mcp
        run: uv sync
      - uses: azure/login@v2
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
      - name: Get spine API key
        id: kv
        run: |
          KEY=$(az keyvault secret show --vault-name wkm-shared-kv --name SECOND-BRAIN-API-KEY --query value -o tsv)
          echo "::add-mask::$KEY"
          echo "key=$KEY" >> $GITHUB_OUTPUT
      - name: Run parity check
        env:
          SPINE_BASE_URL: https://brain.willmacdonald.com
          SPINE_API_KEY: ${{ steps.kv.outputs.key }}
        working-directory: mcp
        run: uv run python parity_check.py | tee parity_report.json
      - name: Upload parity report
        uses: actions/upload-artifact@v4
        with:
          name: parity-report-${{ github.run_id }}
          path: mcp/parity_report.json
      - name: Append to parity history
        run: |
          mkdir -p .planning/mcp_parity_history
          cp mcp/parity_report.json ".planning/mcp_parity_history/$(date -u +%Y-%m-%d).json"
          git config user.email "actions@github.com"
          git config user.name "github-actions"
          git add .planning/mcp_parity_history/
          git commit -m "chore(mcp-parity): nightly report $(date -u +%Y-%m-%d)" || true
          git push || true
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/mcp-parity.yml
git commit -m "ci(mcp): nightly parity check workflow"
```

---

## Task 13: Per-tool cutover (after 7 days of green parity)

This is a **gated** task. Do not perform until 7 consecutive nightly parity reports show `matched: true` for the tool being cut over.

For each tool in `recent_errors`, `system_health`, `trace_lifecycle`, `usage_patterns`, `admin_audit`:

- [ ] **Step 1: Verify 7 days of green parity**

```bash
ls .planning/mcp_parity_history/ | tail -7 | while read f; do
  echo "=== $f ==="
  jq '.results[] | select(.tool == "<TOOL_NAME>") | {matched, diff_summary}' ".planning/mcp_parity_history/$f"
done
```

Expected: every entry shows `"matched": true` for the tool being cut over.

- [ ] **Step 2: Switch the default**

In `mcp/server.py`, change the per-tool `_spine_enabled_for("<TOOL_NAME>")` default from `"off"` to `"on"`:

```python
def _spine_enabled_for(tool: str) -> bool:
    defaults = {
        "recent_errors": "on",   # cut over YYYY-MM-DD after 7-day parity
        # add more tools as they cut over
    }
    flag = os.environ.get(f"MCP_SPINE_{tool.upper()}", defaults.get(tool, "off")).lower()
    return flag in {"on", "true", "1"}
```

- [ ] **Step 3: Remove the legacy implementation for that tool**

Delete `_legacy_<tool>` function and any unused App-Insights-direct imports.

- [ ] **Step 4: Run the parity check one more time** to confirm cutover didn't break anything (it should still work because the flag's "on" default is correct)

```bash
SPINE_BASE_URL=https://brain.willmacdonald.com SPINE_API_KEY=$KEY \
  uv run python mcp/parity_check.py
```

Expected: the cut-over tool reports `legacy_ok: false` (legacy code removed) but spine still works. Update the parity check to skip cut-over tools, OR leave the assertion at "spine path works" only for cut-over tools.

- [ ] **Step 5: Commit per cutover**

```bash
git add mcp/server.py
git commit -m "refactor(mcp): cut over <tool_name> to spine after 7d parity"
```

Repeat for each tool over the parity-test window. Final cutover removes all `_legacy_*` functions and the `_spine_enabled_for` shim entirely.

---

## Task 14: Phase 4 acceptance verification

- [ ] **Step 1: All backend tests pass:** `cd backend && uv run pytest -x`
- [ ] **Step 2: Web type-check passes:** `cd web && npm run type-check`
- [ ] **Step 3: Mobile type-check passes:** `cd mobile && npx tsc --noEmit`
- [ ] **Step 4: 9 segments visible** (8 user-facing + container_app):

```bash
curl -sS -H "Authorization: Bearer ${API_KEY}" https://brain.willmacdonald.com/api/spine/status \
  | jq '.segments | length'
```

Expected: `9`.

- [ ] **Step 5: Mobile composite tile data flows**

After triggering an inbox load failure on the device:

```bash
curl -sS -H "Authorization: Bearer ${API_KEY}" "https://brain.willmacdonald.com/api/spine/segment/mobile_ui" \
  | jq '.data.sources.telemetry.telemetry_events | length'
```

Expected: > 0.

- [ ] **Step 6: Sentry events flow** (after triggering a deliberate Sentry event):

```bash
curl -sS -H "Authorization: Bearer ${API_KEY}" "https://brain.willmacdonald.com/api/spine/segment/mobile_ui" \
  | jq '.data.sources.sentry.events | length'
```

Expected: > 0 (after a few minutes for Sentry to index).

- [ ] **Step 7: Cross-segment trace correlation**

Trigger a capture from the device that fails mid-flight (e.g., quickly turn on airplane mode):

```bash
TRACE_ID=<from device toast>
curl -sS -H "Authorization: Bearer ${API_KEY}" "https://brain.willmacdonald.com/api/spine/correlation/capture/${TRACE_ID}" \
  | jq '.events[].segment_id'
```

Expected: events from `mobile_capture`, `backend_api`, `classifier` (and possibly `cosmos` after diagnostic-log lag).

- [ ] **Step 8: Parity test runs and reports**

Manually trigger the GitHub Actions workflow `mcp-parity.yml`. Verify it completes and produces a JSON report. Initial reports may show divergences — that's OK; this is the parity-watching window.

- [ ] **Step 9: Tag**

```bash
git tag phase-4-mobile-and-mcp -m "Phase 4 complete: 8 segments live, MCP parity gate active"
git push --tags
```

After 7 days of green parity per tool, perform Task 13 cutovers tool-by-tool.

---

## Self-Review Checklist for Phase 4

- [x] Sentry tagging on mobile correctly sets capture_trace_id as a tag (queryable), not context (not queryable)
- [x] Backend telemetry endpoint forwards crud_failure events to spine ingest as workload events
- [x] Composite adapter handles partial failures (returns succeeded sources, lists failures)
- [x] MCP parity comparator normalizes timestamps (the only intentionally divergent fields)
- [x] MCP cutover is gated, per-tool, with 7 days of green parity required
- [x] After Phase 4 completion, the spine has 8 user-facing segments + container_app rollup node, matching the spec
- [x] Cross-segment trace correlation works end-to-end (mobile → backend → classifier → cosmos), demonstrable via `/api/spine/correlation/capture/{id}`
