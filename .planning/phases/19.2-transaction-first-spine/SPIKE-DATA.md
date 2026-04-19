# Phase 19.2 Plan 01 — Spike Data (Raw Findings)

**Collected:** 2026-04-18 (during Plan 01 Task 1 execution)
**Target:** Deployed backend at `https://brain.willmacdonald.com`
**Caller-supplied trace IDs (audit keys):**
- Capture chain: `spike-20260418T235549Z` (X-Trace-Id header on POST /api/capture)
- Thread chain: `spike-thread-20260418T235618Z` (passed as `thread_id` in /api/investigate body)

No analysis below — raw evidence only. Categorization lives in SPIKE-MEMO.md.

---

## 1. Capture reproduction (POST /api/capture)

Curl invocation:
```
curl -s -N -X POST https://brain.willmacdonald.com/api/capture \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <api-key-from-wkm-shared-kv/second-brain-api-key>" \
  -H "X-Trace-Id: spike-20260418T235549Z" \
  -H "X-Capture-Source: phase-19.2-spike" \
  --data '{"text": "Pick up milk and eggs from the grocery store tomorrow morning"}'
```

SSE events streamed back (verbatim):
```
data: {"type": "STEP_START", "stepName": "Classifying"}
data: {"type": "STEP_END", "stepName": "Classifying"}
data: {"type": "CLASSIFIED", "value": {"inboxItemId": "e83901c2-f437-404e-a634-53310cc36c33", "bucket": "Admin", "confidence": 0.9}}
data: {"type": "COMPLETE", "threadId": "thread-b8173237-d00b-4edd-b340-5b0ea9712cef", "runId": "run-8cca5a01-3873-471a-bbc7-2d9985396705"}
```

Classification bucket = `Admin` → admin_handoff should run on next `/api/errands` call.

Follow-up `GET /api/errands` call (same `X-Trace-Id` header): returned 200 with active destinations + `processingCount: 1` in response. The inbox item was subsequently deleted (see App Insights trace at 23:56:14 in section 5) — confirming admin processing completed.

---

## 2. Investigate reproduction (POST /api/investigate)

Curl invocation:
```
curl -s -N -X POST https://brain.willmacdonald.com/api/investigate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <api-key>" \
  --data '{"question": "what is the current system status?", "thread_id": "spike-thread-20260418T235618Z"}'
```

SSE events (verbatim):
```
data: {"type": "thinking"}
data: {"type": "error", "message": "Investigation failed. Please try again."}
data: {"type": "done", "thread_id": "spike-thread-20260418T235618Z"}
```

Foundry rejected the thread_id because it didn't start with `thread_` (see App Insights exception in section 5). For the spike this is fine — the `spine_stream_wrapper` `finally` block still runs and attempts `emit_agent_workload` after the inner generator yields+returns (no exception escapes the adapter), so this is a valid test of investigation's emit path.

---

## 3. `spine_events` Cosmos queries (ground truth: what landed?)

Database: `second-brain` | Account: `shared-services-cosmosdb` | Containers: `spine_events`, `spine_correlation`

### 3a. Workload summary by segment (last 60 min)

```
window_minutes: 60

by_segment:
  backend_api:
    count=1089  with_correlation_id=2
    sample_operations=['GET /api/errands', 'GET /api/spine/segment/backend_api',
                       'GET /api/spine/segment/classifier', 'GET /api/spine/status', 'GET /health']
    sample_trace_ids=['spike-20260418T235549Z']
```

**All other 8 segments: count=0 workload events in last 60 min.**

### 3b. Workload summary by segment (last 24h)

```
Total workload events in last 24h: 27639
By segment:
  backend_api: 27639  (with correlation_kind=capture: 3)

Non-backend_api workload rows: 0
```

100% of 24h workload traffic is `backend_api`. Only 3 backend_api rows carry `correlation_kind=capture` — all 3 are from the spike above (the other 27,636 are uncorrelated GET /health probes and GETs on the web UI).

### 3c. All event types (liveness / readiness / workload) in last 10 min

```
Total rows: 364
By (segment, event_type):
  ('admin',              'liveness'): 20
  ('backend_api',        'liveness'): 20
  ('backend_api',        'workload'): 184
  ('classifier',         'liveness'): 20
  ('container_app',      'liveness'): 20
  ('cosmos',             'liveness'): 20
  ('external_services',  'liveness'): 20
  ('investigation',      'liveness'): 20
  ('mobile_capture',     'liveness'): 20
  ('mobile_ui',          'liveness'): 20

Non-backend_api workload rows: 0
Rows with correlation_kind=thread: 0
```

Liveness fires correctly for all 9 segments (driven by `spine/background.py::liveness_emitter` which wraps with `IngestEvent(root=…)`). No segment other than backend_api produces workload.

### 3d. Events tagged with spike capture trace

```json
[
  {
    "segment_id": "backend_api",
    "event_type": "workload",
    "correlation_kind": "capture",
    "correlation_id": "spike-20260418T235549Z",
    "operation": "POST /api/capture",
    "outcome": "success",
    "duration_ms": 2,
    "error_class": null,
    "timestamp": "2026-04-18T23:55:49.600930+00:00"
  },
  {
    "segment_id": "backend_api",
    "event_type": "workload",
    "correlation_kind": "capture",
    "correlation_id": "spike-20260418T235549Z",
    "operation": "GET /api/errands",
    "outcome": "success",
    "duration_ms": 1202,
    "error_class": null,
    "timestamp": "2026-04-18T23:56:04.880061+00:00"
  }
]
```

Only the middleware's backend_api rows. Duration=2ms on `/api/capture` because the middleware times `call_next` (request→response boundary); the SSE stream actually runs async AFTER that. No classifier / admin / investigation / external_services / cosmos / mobile workload rows exist for this trace, even though classifier, admin, and investigation all executed during the capture window (proven by logs, see section 5).

### 3e. Events tagged with spike thread trace

```
[]
```

Investigation emitted NO workload event for the thread, even though the investigate handler at `api/investigate.py:84` wraps the SSE generator in `spine_stream_wrapper` with `thread_id=body.thread_id`. The wrapper's `finally` block ran (confirmed by the AttributeError in section 5) — but `record_event` raised before the row landed.

---

## 4. `spine_correlation` Cosmos queries

### 4a. `kind=capture`, `id=spike-20260418T235549Z`

```json
[
  {
    "id": "capture:spike-20260418T235549Z:backend_api:27df3827-5473-4d7d-a1d9-95fe7074a968",
    "correlation_kind": "capture",
    "correlation_id": "spike-20260418T235549Z",
    "segment_id": "backend_api",
    "timestamp": "2026-04-18T23:55:49.600930+00:00",
    "status": "green",
    "headline": "POST /api/capture success",
    "parent_correlation_kind": null,
    "parent_correlation_id": null
  },
  {
    "id": "capture:spike-20260418T235549Z:backend_api:74fe8c67-ce9a-46da-b9d9-94981f0edb8f",
    "correlation_kind": "capture",
    "correlation_id": "spike-20260418T235549Z",
    "segment_id": "backend_api",
    "timestamp": "2026-04-18T23:56:04.880061+00:00",
    "status": "green",
    "headline": "GET /api/errands success"
  }
]
```

Two rows, both backend_api. Classifier / admin / external_services rows MISSING — the upsert in `SpineRepository.record_event` is guarded by `if inner.event_type == "workload" ... if payload.correlation_kind and payload.correlation_id`, which requires the event to land in `spine_events` first. Since the underlying `create_item` call never runs (see section 5 AttributeError), the correlation upsert is never attempted for those segments.

### 4b. `kind=thread`, `id=spike-thread-20260418T235618Z`

```
[]
```

No investigation correlation row either. Same root cause.

---

## 5. App Insights cross-check (native telemetry tagging)

Workspace: `shared-services-logs` (ID `572d91c2-3209-4b92-b431-5ffb7e8ce4ad`)

### 5a. `AppRequests` filtered by the spike trace (15-min window)

```
(empty — no rows returned)
```

**Native App Insights HTTP request spans have NO capture_trace_id tagging**, matching `audit_correlation`'s `instrumentation_warning`. Every POST/GET the backend received during the spike produced an `AppRequests` row, but none carry `OperationId == '<trace>'` or `Properties.capture_trace_id == '<trace>'`. This is Phase 17.4/19.1 territory — OTel span context is not being bridged from request middleware to the auto-instrumented HTTP span.

### 5b. `AppTraces` filtered by the spike trace (15-min window)

Partial sample (14 rows total, all with `Properties.capture_trace_id == 'spike-20260418T235549Z'`):

```
23:55:49.600  Capture source: phase-19.2-spike, thread_id=...            component=capture
23:55:53.691  Filed to Admin (0.90, status=classified): Pick up milk...  component=classifier
23:55:55.988  Reasoning chunk  (reasoning_text="Filed")                  component=classifier
23:55:55.994  Reasoning chunk  (reasoning_text=" to")                    component=classifier
...  (13 classifier/reasoning rows)
23:56:14.990  Deleted processed inbox item e83901c2-...                  component=admin_agent
23:56:14.990  Admin Agent processed inbox item e83901c2-...: I have
                added the task "Pick up milk and eggs..."                component=admin_agent
```

**Classifier AND admin DID run.** Python logger carries `capture_trace_id` in `extra` on every log line (per Phase 14 logging scope). This proves the emit paths were reached — the failure is specifically in `record_event`, not upstream.

### 5c. `AppDependencies` filtered by the spike trace (15-min window)

2 rows:

```
23:55:49.600  capture_text          | duration=6641ms | OperationId=0381117e2a58…
              Properties: capture.trace_id=spike-20260418T235549Z,
                          capture.outcome=classified, capture.bucket=Admin
23:56:04.793  admin_agent_process   | duration=10198ms | OperationId=ca99edfb788d…
              Properties: capture.trace_id=spike-20260418T235549Z,
                          admin.outcome=processed, admin.tool_invoked=True
```

OTel custom spans (started via `tracer.start_as_current_span(...)` in `streaming/adapter.py` and `processing/admin_handoff.py`) DO carry `capture.trace_id` as a span attribute. But note: the key is `capture.trace_id` (dot notation, span attribute convention), NOT `capture_trace_id`. `AppRequests` does not join on this automatically; Phase 19.1 introduced AppException native-field projection but did not extend that to `AppRequests.Properties`.

### 5d. `AppExceptions` (found the root cause!)

Three `AttributeError` exceptions in the 15-minute spike window, all with the same stack:

```
ExceptionType: AttributeError
OuterMessage:  emit_agent_workload failed
InnermostMessage: emit_agent_workload failed
Method: Unknown
Details (rawStack):
  Traceback (most recent call last):
    File "/app/.venv/lib/python3.12/site-packages/second_brain/spine/agent_emitter.py", line 63, in emit_agent_workload
      await repo.record_event(event)
    File "/app/.venv/lib/python3.12/site-packages/second_brain/spine/storage.py", line 42, in record_event
      event.root
    File "/app/.venv/lib/python3.12/site-packages/pydantic/main.py", line 1026, in __getattr__
      raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}')
  AttributeError: '_WorkloadEvent' object has no attribute 'root'
```

Occurrences:
| Time                          | Triggered by                              | Segment       |
| ----------------------------- | ----------------------------------------- | ------------- |
| 2026-04-18T23:55:56.242289Z   | Classifier stream_wrapper finally         | classifier    |
| 2026-04-18T23:56:14.990996Z   | admin_handoff.py finally                  | admin         |
| 2026-04-18T23:56:18.467932Z   | investigate.py stream_wrapper finally     | investigation |

All three come from the SAME helper (`spine/agent_emitter.py::emit_agent_workload` line 63).

---

## 6. `audit_correlation` MCP-backed endpoint output

### 6a. Targeted run (`correlation_kind=capture, correlation_id=<spike>`)

```json
{
  "correlation_kind": "capture",
  "sample_size_requested": 1,
  "sample_size_returned": 1,
  "time_range_seconds": 3600,
  "traces": [{
    "correlation_kind": "capture",
    "correlation_id": "spike-20260418T235549Z",
    "verdict": "broken",
    "headline": "missing required segments: classifier, mobile_capture",
    "missing_required": ["classifier", "mobile_capture"],
    "present_optional": [],
    "unexpected": [],
    "misattributions": [],
    "orphans": [],
    "trace_window": {
      "start": "2026-04-18T23:55:49.600930Z",
      "end":   "2026-04-18T23:56:04.880061Z"
    },
    "native_links": {
      "backend_api": "https://portal.azure.com/#blade/AppInsightsExtension"
    }
  }],
  "summary": {
    "clean_count": 0,
    "warn_count": 0,
    "broken_count": 1,
    "segments_with_missing_required": {"classifier": 1, "mobile_capture": 1},
    "overall_verdict": "broken",
    "headline": "1 of 1 traces broken"
  },
  "instrumentation_warning": null
}
```

### 6b. Sample mode (`correlation_kind=capture, sample_size=5, time_range_seconds=3600`)

```json
{
  "sample_size_requested": 5,
  "sample_size_returned": 1,
  "traces": [{ /* same as 6a */ }],
  "summary": {
    "broken_count": 1,
    "segments_with_missing_required": {"classifier": 1, "mobile_capture": 1},
    "overall_verdict": "broken"
  },
  "instrumentation_warning": "backend_api appears to have lost correlation_id tagging — every sampled trace had spine events for this segment but zero matching native records"
}
```

Note: `sample_size_returned=1` because only one trace (ours) was joinable in the last hour. The rest of the backend_api rows have no correlation_id. The `instrumentation_warning` is the same warning produced by the 2026-04-18 first audit run (documented in `project_followup_audit_first_findings.md`).

---

## 7. Known emit-site inventory (code reads, verified against deployed behaviour)

| Segment            | File:line                                              | Wraps in `IngestEvent(root=…)`?        | Landed in spine_events today?                                    |
| ------------------ | ------------------------------------------------------ | -------------------------------------- | ---------------------------------------------------------------- |
| backend_api        | `spine/middleware.py:70,95`                            | YES (lines 70 & 95)                    | YES (27,639 rows/24h)                                            |
| classifier         | `spine/stream_wrapper.py:41` → `agent_emitter.py:63`   | NO (passes raw `_WorkloadEvent`)       | NO — AttributeError at storage.py:42 every call                  |
| admin              | `processing/admin_handoff.py:397` → `agent_emitter.py:63` | NO (same helper)                    | NO — AttributeError every call                                   |
| investigation      | `api/investigate.py:87` → `agent_emitter.py:63`        | NO (same helper)                       | NO — AttributeError every call                                   |
| external_services  | `tools/recipe.py:185`                                  | NO (passes raw `_WorkloadEvent`, `except: pass` swallows) | NOT EXERCISED in spike (no recipe URL in text); but code path is latently broken the same way |
| mobile_ui          | `api/telemetry.py:105,120` (crud_failure only)         | NO (both callsites pass raw events)    | NOT EXERCISED in spike; by design normal captures don't emit     |
| mobile_capture     | `api/telemetry.py:105,120` (crud_failure only)         | NO                                     | NOT EXERCISED; by design normal captures don't emit              |
| cosmos             | n/a — pulled by `CosmosAdapter` from AzureDiagnostics  | n/a                                    | n/a (native/pull)                                                |
| container_app      | n/a — pulled by `ContainerAppAdapter` from AI logs     | n/a                                    | n/a (native/pull)                                                |

Liveness for all 9 (including cosmos + container_app) is emitted by `spine/background.py::liveness_emitter` which DOES wrap with `IngestEvent(root=…)` — that's why every segment has ~20 liveness events/10min.

---

## 8. Cross-check: what the Python signature of `record_event` expects

From `backend/src/second_brain/spine/storage.py:37-43`:

```python
async def record_event(self, event: IngestEvent) -> None:
    """Append an ingest event and (for workloads with correlation)
    a correlation record.
    """
    inner = (
        event.root  # <-- requires IngestEvent (pydantic RootModel), not bare _WorkloadEvent
    )
```

`IngestEvent` is `RootModel[Annotated[_LivenessEvent | _ReadinessEvent | _WorkloadEvent, Field(discriminator="event_type")]]` (from `spine/models.py:79`). Its `.root` attribute is Pydantic v2's RootModel accessor. Bare `_WorkloadEvent` / `_LivenessEvent` are `BaseModel` subclasses — they have no `.root`, hence the `AttributeError`.

---

## 9. Pointers to related prior art

- `project_followup_audit_first_findings.md` (2026-04-18 first audit run)
  - Flagged classifier as "suspicious-pending-verification"
  - Flagged backend_api correlation-id tagging as the strongest real gap
  - Flagged mobile_capture as architecture-limit-not-regression
  - The spike CONFIRMS classifier is broken (not suspicious), CONFIRMS the backend_api correlation gap, CONFIRMS mobile is architecture-limit
- `project_followup_duplicate_api_key_secrets.md` — `sb-api-key` and `second-brain-api-key` both exist; spike used the second

---

*End of raw data. Categorization + recommendations live in SPIKE-MEMO.md.*
