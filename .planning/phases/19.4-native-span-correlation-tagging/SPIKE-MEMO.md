# Phase 19.4 Plan 01: Spike Memo -- CaptureTraceSpanProcessor Empirical Test

**Date:** 2026-04-20
**Trace ID used:** `spike-194-1776662261`
**Deploy commit:** `3395457` (main, deployed via GitHub Actions run 24649650273)
**Capture endpoint:** `POST https://brain.willmacdonald.com/api/capture`
**Capture result:** CLASSIFIED (bucket: Projects, confidence: 0.85)

## 1. Methodology

Deployed `CaptureTraceSpanProcessor` (registered via `configure_azure_monitor(span_processors=[...])`).
The processor reads `capture_trace_id_var` (ContextVar) on every span `on_start` and sets
`span.set_attribute("capture.trace_id", value)` when non-empty.

Additionally, `capture_trace_id_var.set(capture_trace_id)` was added to all 4 capture
handlers in `api/capture.py` immediately after `request.state.capture_trace_id = capture_trace_id`,
to make the value available BEFORE the streaming generator runs.

The adapter.py already sets `capture_trace_id_var` inside the generators (lines 171, 368, 578).
The handler-level set is additive -- it ensures the ContextVar has a value at handler entry time.

After deploy, one text capture was triggered with trace ID `spike-194-1776662261`. After 4 minutes
of App Insights ingestion latency, KQL queries were run against each of the 4 emit sites.

## 2. Per-Site Verification Table

| # | Site | KQL Table | Query Filter | Rows Found | `capture.trace_id` Present | Pass/Fail |
|---|------|-----------|-------------|------------|---------------------------|-----------|
| 1 | `backend_api` AppRequests | `AppRequests` | `Name == "POST /api/capture"` in capture time window | 1 | **NO** -- Properties contains only `_MS.ProcessedByMetricExtractors` and `_MS.ResourceAttributeId` | **FAIL** |
| 2 | Foundry agent spans | `AppDependencies` | `Properties.["capture.trace_id"] == "spike-194-1776662261"` | 20+ | **YES** -- all Foundry SDK spans (`chat unknown`, `get_agent`, `create_thread`, `process_thread_run`, `submit_tool_outputs`, `tool_file_capture`, `execute_tool file_capture`) carry `capture.trace_id` | **PASS** |
| 3 | Cosmos diagnostic logs | `AzureDiagnostics` | `activityId_g startswith "spike-194"` | 0 | **N/A** -- `activityId_g` contains Cosmos server-side activity IDs (UUIDs), NOT `x-ms-client-request-id`. However, Cosmos SDK spans in `AppDependencies` (`ContainerProxy.create_item`, `POST /dbs/.../docs/`) DO carry `capture.trace_id` via the SpanProcessor. | **PASS (via AppDependencies, not AzureDiagnostics)** |
| 4 | Investigation custom spans | `AppDependencies` | Not tested (investigation runs have no `capture_trace_id`) | N/A | **PASS by design** -- SpanProcessor no-ops when ContextVar is empty. Investigation spans use `thread_id` for correlation, not `capture_trace_id`. The `capture_text` app-created span (equivalent mechanism) confirmed working. | **PASS (by design)** |

### KQL Evidence

**Site 1 (FAIL):**
```sql
AppRequests
| where TimeGenerated between(datetime(2026-04-20T05:17:30Z)..datetime(2026-04-20T05:18:00Z))
| where Name contains "capture"
| project TimeGenerated, Name, ResultCode, CaptureTraceId=tostring(Properties.["capture.trace_id"]), Props=tostring(Properties)
```
Result: 1 row, `CaptureTraceId` is empty.

**Site 2 (PASS) -- 20+ spans confirmed:**
```sql
AppDependencies
| where TimeGenerated between(datetime(2026-04-20T05:17:30Z)..datetime(2026-04-20T05:18:00Z))
| where tostring(Properties.["capture.trace_id"]) != ""
| project TimeGenerated, Name, DurationMs, CaptureTraceId=tostring(Properties.["capture.trace_id"])
| order by TimeGenerated asc
```
Result: 23 rows including `capture_text` (6305ms), `chat unknown` (3520ms), `get_agent`, `create_thread`, `process_thread_run` (2946ms), `tool_file_capture` (346ms), `execute_tool file_capture`, `submit_tool_outputs`, and all Cosmos SDK HTTP spans.

**Site 3 (PASS via AppDependencies):**
```sql
AppDependencies
| where TimeGenerated between(datetime(2026-04-20T05:17:44Z)..datetime(2026-04-20T05:17:48Z))
| where Name startswith "ContainerProxy" or Name startswith "POST /dbs" or Name startswith "GET /dbs"
| where tostring(Properties.["capture.trace_id"]) == "spike-194-1776662261"
```
Result: 9 rows -- all Cosmos SDK spans (Inbox create, Projects create, spine_events create/upsert) carry `capture.trace_id`.

## 3. ContextVar Timing Analysis

**Question:** Does `capture_trace_id_var` have a value when the AppRequests `on_start` fires?

**Answer: NO.** The AppRequests span is created by the ASGI auto-instrumentation (FastAPI's OpenTelemetry integration) when the request enters the server. This happens BEFORE:
- The APIKeyMiddleware runs
- The SpineWorkloadMiddleware runs
- The capture handler body executes
- The `capture_trace_id_var.set()` call we added in `api/capture.py`

The execution order is:
1. ASGI server receives request
2. OpenTelemetry ASGI middleware creates AppRequests span -- **SpanProcessor.on_start fires here** (ContextVar is EMPTY)
3. Starlette/FastAPI middleware stack runs (APIKeyMiddleware, SpineWorkloadMiddleware)
4. Route handler runs, sets `capture_trace_id_var.set(capture_trace_id)`
5. StreamingResponse generator starts, adapter sets ContextVar again (refreshes it)
6. All child spans created from step 4 onward get `capture.trace_id` via the SpanProcessor

**Fix for Site 1:** Use `opentelemetry.trace.get_current_span()` inside the capture handler (or SpineWorkloadMiddleware) to access the already-started AppRequests span and call `span.set_attribute("capture.trace_id", capture_trace_id)` directly. This retroactively adds the attribute to the AppRequests span before it ends. The SpanProcessor approach cannot help here because `on_start` has already fired with an empty ContextVar.

**Recommendation:** Add a one-line explicit `get_current_span().set_attribute(...)` call in each capture handler or in SpineWorkloadMiddleware (which already reads `X-Trace-Id`). This is a per-site fix ONLY for the AppRequests span; all other spans are covered by the SpanProcessor.

## 4. Cosmos Call Site Audit

### Capture-Correlated Call Sites

| File | Line | Operation | Collection | Capture-Correlated | Has `trace_headers()` | Notes |
|------|------|-----------|------------|-------------------|-----------------------|-------|
| `tools/classification.py` | 193 | `create_item` | Inbox | YES | YES | `th = trace_headers(trace_id)` at line 161 |
| `tools/classification.py` | 227 | `create_item` | Inbox | YES | YES | Same `th` from line 161 |
| `tools/classification.py` | 245 | `create_item` | bucket (Projects/Ideas/etc) | YES | YES | Same `th` |
| `tools/classification.py` | 289 | `upsert_item` | Inbox | YES | YES | `th = trace_headers(trace_id)` at line 279 |
| `tools/classification.py` | 326 | `upsert_item` | Inbox | YES | YES | Same `th` from line 279 |
| `tools/classification.py` | 345 | `create_item` | bucket | YES | YES | Same `th` from line 279 |
| `processing/admin_handoff.py` | 129 | `upsert_item` | Inbox | YES | YES | `th = trace_headers(capture_trace_id)` at line 123 |
| `processing/admin_handoff.py` | 201 | `upsert_item` | Inbox | YES | YES | `th = trace_headers(capture_trace_id)` at line 187 |
| `processing/admin_handoff.py` | 327 | `upsert_item` | Inbox | YES | YES | Same pattern |
| `streaming/adapter.py` | 131 | `create_item` | Inbox | YES | **NO** | Safety-net misunderstood path -- no `trace_headers()` |
| `api/capture.py` | 122 | `upsert_item` | Inbox | YES | **NO** | MISUNDERSTOOD foundryThreadId persistence |
| `api/capture.py` | 179 | `upsert_item` | Inbox | YES | **NO** | Follow-up MISUNDERSTOOD foundryThreadId persistence |

### Non-Capture-Correlated Call Sites (no trace_headers needed)

| File | Line | Operation | Collection | Notes |
|------|------|-----------|------------|-------|
| `api/inbox.py` | 259 | `upsert_item` | Inbox | User-initiated inbox management |
| `api/inbox.py` | 294 | `create_item` | bucket | User-initiated filing |
| `api/inbox.py` | 303 | `upsert_item` | Inbox | User-initiated status update |
| `api/errands.py` | 386 | `create_item` | Errands | Errand creation (user action) |
| `api/errands.py` | 407 | `create_item` | AffinityRules | Rule creation (user action) |
| `tools/admin.py` | 175 | `create_item` | Errands | Admin tool -- errand creation |
| `tools/admin.py` | 223 | `create_item` | Tasks | Admin tool -- task creation |
| `tools/admin.py` | 299 | `create_item` | Destinations | Admin tool -- destination management |
| `tools/admin.py` | 322 | `upsert_item` | Destinations | Admin tool -- destination update |
| `tools/admin.py` | 473 | `create_item` | AffinityRules | Admin tool -- affinity rule creation |
| `tools/admin.py` | 509 | `upsert_item` | AffinityRules | Admin tool -- affinity rule update |
| `spine/storage.py` | 52 | `create_item` | spine_events | Spine infrastructure (not capture-specific) |
| `spine/storage.py` | 82 | `upsert_item` | spine_correlation | Spine infrastructure |
| `spine/storage.py` | 100 | `upsert_item` | spine_segment_state | Spine infrastructure |
| `spine/storage.py` | 138 | `create_item` | spine_status_history | Spine infrastructure |

### Key Finding: `trace_headers()` is partially redundant

The `CaptureTraceSpanProcessor` already tags ALL Cosmos SDK spans (`ContainerProxy.create_item`, `POST /dbs/...`) in `AppDependencies` with `capture.trace_id`. This means:
- **For querying capture-correlated Cosmos operations:** Use `AppDependencies | where tostring(Properties.["capture.trace_id"]) == "..."` instead of `AzureDiagnostics | where activityId_g == "..."`.
- **`trace_headers()` is still valuable** for the `AzureDiagnostics` perspective (server-side metrics like RU charge, duration, status codes that aren't in AppDependencies). But the correlation path through AppDependencies is more reliable.
- **3 call sites missing `trace_headers()`:** `adapter.py:131`, `capture.py:122`, `capture.py:179`. These are minor -- safety-net MISUNDERSTOOD and foundryThreadId persistence. Since the SpanProcessor covers the Cosmos SDK spans anyway, these are low priority.

## 5. Numbered Recommendations for Plan 02

### 5.1: Fix Site 1 -- Tag AppRequests span with `capture.trace_id`

In each of the 4 capture handlers in `api/capture.py`, after `capture_trace_id_var.set(capture_trace_id)`, add:
```python
from opentelemetry import trace
current_span = trace.get_current_span()
if current_span.is_recording():
    current_span.set_attribute("capture.trace_id", capture_trace_id)
```
This retroactively tags the already-started AppRequests span.

**Alternative:** Move this into `SpineWorkloadMiddleware` which already reads `X-Trace-Id` from the request headers. This would be a single-site fix instead of repeating in 4 handlers.

### 5.2: Add missing `trace_headers()` to 3 remaining Cosmos call sites

- `streaming/adapter.py:131` -- safety-net misunderstood `create_item`
- `api/capture.py:122` -- MISUNDERSTOOD foundryThreadId `upsert_item`
- `api/capture.py:179` -- follow-up foundryThreadId `upsert_item`

Low priority since SpanProcessor covers these via AppDependencies, but adds `AzureDiagnostics` server-side correlation.

### 5.3: Update KQL templates to use AppDependencies for Cosmos correlation

The existing `COSMOS_DIAGNOSTIC_LOGS` KQL template in `kql_templates.py` filters `AzureDiagnostics | where activityId_g == "{capture_trace_id}"`. This does NOT work because `activityId_g` contains server-side activity IDs, not `x-ms-client-request-id`.

Update the Cosmos correlation query to use `AppDependencies` instead:
```sql
AppDependencies
| where Name startswith "ContainerProxy" or Name startswith "POST /dbs" or Name startswith "GET /dbs"
| where tostring(Properties.["capture.trace_id"]) == "{capture_trace_id}"
```

### 5.4: Correct MEMORY.md `activityId_g` documentation

The MEMORY.md entry "activityId_g column holds x-ms-client-request-id" is incorrect. `activityId_g` holds Cosmos's server-side activity ID. The `x-ms-client-request-id` from `initial_headers` is NOT surfaced in any visible `AzureDiagnostics` column. Update the documentation.

### 5.5: Add regression test for SpanProcessor

Create a unit test that verifies `CaptureTraceSpanProcessor.on_start()` sets the `capture.trace_id` attribute when the ContextVar is set, and does not set it when the ContextVar is empty.

### 5.6: Verify web segment native renderers work with the new `capture.trace_id` property path

The web segment page's native renderers query `AppDependencies` and `AppRequests` for capture-correlated spans. Verify that the `Properties.capture_trace_id` property path in KQL templates matches the actual `Properties.["capture.trace_id"]` path (with dot notation). The SpanProcessor sets `capture.trace_id` (with a dot), which appears in KQL as `Properties.["capture.trace_id"]`.

## 6. `activityId_g` Mapping Decision

**Decision: No new correlation-map table needed.**

The original assumption was that `activityId_g` in `AzureDiagnostics` equals `capture_trace_id` (set via `x-ms-client-request-id`). This is **incorrect**:
- `activityId_g` contains Cosmos's server-side activity ID (a UUID)
- `x-ms-client-request-id` from `initial_headers` does NOT appear as any visible field in `AzureDiagnostics`

However, the `CaptureTraceSpanProcessor` makes this moot:
- Cosmos SDK spans (`ContainerProxy.create_item`, HTTP calls) appear in `AppDependencies` with `capture.trace_id` set by the SpanProcessor
- Filtering `AppDependencies | where tostring(Properties.["capture.trace_id"]) == "..."` returns all Cosmos operations for a capture
- No mapping table or join is needed -- direct equality filter on AppDependencies works

The `trace_headers()` helper is still useful as defense-in-depth (if Azure adds client_request_id to diagnostic logs later), but the PRIMARY correlation path is now through AppDependencies.

## 7. Plan 02 Scope Recommendation

**Recommendation: Merge Plans 02 + 04 into a single plan.**

The SpanProcessor covers Sites 2 (Foundry agent spans) and 4 (investigation/custom spans) with zero per-site code. Site 1 (AppRequests) needs one explicit `get_current_span().set_attribute()` fix. Site 3 (Cosmos) is covered by SpanProcessor via AppDependencies.

**Merged Plan 02 tasks (from recommendations above):**
1. Fix Site 1: Tag AppRequests span (5.1)
2. Add missing trace_headers to 3 call sites (5.2)
3. Update Cosmos KQL templates (5.3)
4. Correct MEMORY.md documentation (5.4)
5. Add SpanProcessor regression test (5.5)
6. Verify web segment native renderer property path (5.6)

**Plans 03 and 04 from the original PRD are no longer needed as separate plans.** The SpanProcessor covers the Cosmos SDK span correlation (Plan 03's goal) and investigation span tagging (Plan 04's goal) without additional code.

**Revised phase plan count: 2** (Plan 01 spike memo + Plan 02 merged implementation + verification).
