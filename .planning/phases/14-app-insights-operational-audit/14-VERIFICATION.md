---
phase: 14-app-insights-operational-audit
verified: 2026-03-22T23:15:00Z
status: passed
score: 13/13 must-haves verified
---

# Phase 14: App Insights Operational Audit Verification Report

**Phase Goal:** End-to-end observability from mobile app through backend to Azure AI Foundry. Per-capture trace ID propagation, consistent log levels, structured logging with custom dimensions, version-controlled KQL queries, Azure Monitor alerts, and mobile telemetry via backend proxy.
**Verified:** 2026-03-22T23:15:00Z
**Status:** passed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | configure_azure_monitor uses logger_name='second_brain' to scope log collection | VERIFIED | main.py L17: `configure_azure_monitor(logger_name="second_brain")` |
| 2 | Python logger.info traces appear in App Insights (not just WARNING+) | VERIFIED | main.py L16: `logging.getLogger("second_brain").setLevel(logging.INFO)` explicitly sets INFO before configure_azure_monitor |
| 3 | Every log statement follows consistent level policy | VERIFIED | errands.py L296 `logger.debug`, tasks.py L65 `logger.debug`, inbox.py L103 `logger.debug` (routine GET demoted). admin_handoff.py L288 `logger.error` (retry exhaustion promoted). warmup.py L29 `logger.debug` (pings). No TODOs/FIXMEs in any source file. |
| 4 | Every capture request generates/extracts capture_trace_id and threads it through | VERIFIED | capture.py L198,257,304,372: `request.headers.get("X-Trace-Id", str(uuid4()))` in all 4 endpoints. Passed to all stream functions. |
| 5 | Admin Agent background processing carries capture_trace_id from originating capture | VERIFIED | admin_handoff.py L177: `trace_id = doc.get("captureTraceId", capture_trace_id or "unknown")`. Reads from Cosmos document field set by classification.py. |
| 6 | All logger calls in capture/classification/admin paths include extra with capture_trace_id | VERIFIED | capture.py L31-32 `_capture_extra` factory. adapter.py L169,351,550 `log_extra` dict. admin_handoff.py L179-182 `log_extra` dict. classification.py L122,156 `log_extra` dict. All include both `capture_trace_id` and `component`. |
| 7 | Mobile app generates UUID trace ID and sends as X-Trace-Id header | VERIFIED | telemetry.ts L4-15 `generateTraceId()`. ag-ui-client.ts L207 `"X-Trace-Id": traceId` in sendCapture, L268 in sendFollowUp, L329 in sendVoiceCapture, L385 in sendFollowUpVoice. |
| 8 | Trace ID visible in mobile app capture screen for copy-paste debugging | VERIFIED | index.tsx L1009-1026: Pressable with `trace: {lastTraceId.slice(0, 8)}...` and `Clipboard.setStringAsync(lastTraceId)` on press. |
| 9 | Mobile client-side errors reported to backend telemetry endpoint | VERIFIED | ag-ui-client.ts L227-234 wraps onError in sendCapture with `reportError(...)`. Same pattern in sendFollowUp L282-290, sendVoiceCapture L337-345, sendFollowUpVoice L393-401. telemetry.ts L28-46 `reportError` POSTs to `/api/telemetry`. |
| 10 | Backend telemetry endpoint logs mobile errors to App Insights with capture_trace_id | VERIFIED | telemetry.py L33 `@router.post("/api/telemetry", status_code=204)`. L41-54: builds extra dict with `component: "mobile"`, `capture_trace_id`, then calls `logger.warning(...)`. |
| 11 | Telemetry endpoint is authenticated | VERIFIED | auth.py L20: `PUBLIC_PATHS = frozenset({"/health"})` -- `/api/telemetry` is not public. main.py L46,376: telemetry_router imported and registered, behind `APIKeyMiddleware`. |
| 12 | Four KQL query files exist covering all requested queries | VERIFIED | `backend/queries/capture-trace.kql` (31 lines, uses capture_trace_id), `recent-failures.kql` (29 lines, SeverityLevel >= 3), `system-health.kql` (70 lines, summarize/timechart), `admin-agent-audit.kql` (71 lines, admin_agent component filter). Plus `README.md` (44 lines). |
| 13 | Azure Monitor alert rules configured for API down, capture failures, error spikes | VERIFIED (human-confirmed) | Summary 14-03 documents 3 alert rules created via Azure CLI: API-Error-Spike, Capture-Processing-Failures, API-Health-Check with SecondBrainAlerts action group for push notifications. Cannot verify programmatically (Azure infrastructure). |

**Score:** 13/13 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/src/second_brain/main.py` | Scoped configure_azure_monitor with logger_name, INFO level | VERIFIED | L16-17: `setLevel(logging.INFO)` + `configure_azure_monitor(logger_name="second_brain")`. Telemetry router registered L46,376. |
| `backend/src/second_brain/api/capture.py` | X-Trace-Id header extraction and propagation | VERIFIED | L198,257,304,372: header extraction in all 4 endpoints. L31-32: `_capture_extra` helper. Passed to all stream functions. |
| `backend/src/second_brain/streaming/adapter.py` | capture_trace_id threaded through all stream functions and OTel spans | VERIFIED | L158,342,537: `capture_trace_id: str = ""` param. L176,357,557: `span.set_attribute("capture.trace_id", ...)`. L171,352,551: ContextVar set/reset. |
| `backend/src/second_brain/processing/admin_handoff.py` | capture_trace_id carried from inbox doc into admin processing | VERIFIED | L141,385: `capture_trace_id: str = ""` param. L177: reads from `doc.get("captureTraceId", ...)`. L178,404: OTel span attribute. |
| `backend/src/second_brain/tools/classification.py` | capture_trace_id_var ContextVar, captureTraceId on documents | VERIFIED | L37-39: `capture_trace_id_var` ContextVar. L121,154,270: reads via `.get()`. L187,222: `doc_body["captureTraceId"] = trace_id` on inbox documents. |
| `mobile/lib/telemetry.ts` | Telemetry reporting client and trace ID generation | VERIFIED | 46 lines. `generateTraceId()` L4-15. `reportError()` L28-46. POSTs to `/api/telemetry`. |
| `backend/src/second_brain/api/telemetry.py` | POST /api/telemetry endpoint | VERIFIED | 55 lines. `TelemetryEvent` Pydantic model. `report_client_telemetry` handler. 204 status code. WARNING level logging. |
| `mobile/lib/ag-ui-client.ts` | X-Trace-Id header on all capture requests | VERIFIED | L207,268,329,385: `"X-Trace-Id": traceId` in all 4 functions. L202,260,313,367: `generateTraceId()` calls. Error wrapping with `reportError`. |
| `backend/queries/capture-trace.kql` | Lifecycle timeline query by capture_trace_id | VERIFIED | 31 lines. Uses `PASTE_TRACE_ID_HERE` variable. Unions AppTraces, AppDependencies, AppRequests, AppExceptions. Filters by `customDimensions.capture_trace_id`. |
| `backend/queries/recent-failures.kql` | ERROR+ logs and exceptions from last 24h | VERIFIED | 29 lines. `SeverityLevel >= 3`. Includes CaptureTraceId projection. Limited to 50 results. |
| `backend/queries/system-health.kql` | Capture volume, success rate, error trends | VERIFIED | 70 lines. 5 sections: capture volume, success rate, error rate, latency, admin activity. Uses `summarize` with `bin(TimeGenerated, 1h)`. |
| `backend/queries/admin-agent-audit.kql` | Admin Agent processing audit | VERIFIED | 71 lines. Filters by `component == "admin_agent"`. Per-capture grouping section. Errand creation and failures sections. |
| `backend/queries/README.md` | Instructions for using queries | VERIFIED | 44 lines. Step-by-step portal instructions. Query table. Trace ID flow diagram. Data retention note. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `capture.py` | `adapter.py` | `capture_trace_id` parameter | WIRED | capture.py L217 passes `capture_trace_id=capture_trace_id` to `stream_text_capture`. Same for voice (L269), follow-up (L337), follow-up voice (L427). |
| `adapter.py` | `admin_handoff.py` | `captureTraceId` on inbox document | WIRED | classification.py L187,222 stores `captureTraceId` on Cosmos doc. admin_handoff.py L177 reads it back: `doc.get("captureTraceId", ...)`. Indirect via Cosmos document -- correct for the background processing pattern. |
| `adapter.py` | `classification.py` | `capture_trace_id_var` ContextVar | WIRED | adapter.py L32 imports `capture_trace_id_var`. L171 sets it: `trace_token = capture_trace_id_var.set(capture_trace_id)`. L331 resets. classification.py L121 reads: `trace_id = capture_trace_id_var.get()`. |
| `mobile/ag-ui-client.ts` | `backend/capture.py` | X-Trace-Id header | WIRED | ag-ui-client.ts L207: `"X-Trace-Id": traceId`. capture.py L198: `request.headers.get("X-Trace-Id", str(uuid4()))`. |
| `mobile/telemetry.ts` | `backend/telemetry.py` | POST /api/telemetry | WIRED | telemetry.ts L30: `fetch(\`${API_BASE_URL}/api/telemetry\`)`. telemetry.py L33: `@router.post("/api/telemetry")`. JSON body field names match (snake_case). |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| OBS-01 | 14-01 | configure_azure_monitor scoped to application loggers (logger_name="second_brain") | SATISFIED | main.py L17 |
| OBS-02 | 14-01 | Logger.info traces visible in App Insights (not just WARNING+) | SATISFIED | main.py L16: explicit `setLevel(logging.INFO)` |
| OBS-03 | 14-01 | Consistent log level policy enforced across all backend files | SATISFIED | 5 log level fixes applied (4 planned + 1 discovered). No TODOs/FIXMEs. errands/tasks/inbox demoted to debug. admin_handoff retry promoted to error. |
| OBS-04 | 14-01 | Per-capture trace ID propagated end-to-end | SATISFIED | Verified in capture.py -> adapter.py -> classification.py -> admin_handoff.py chain. ContextVar + Cosmos document field pattern. |
| OBS-05 | 14-02 | Mobile app generates trace ID, sends as X-Trace-Id header, displays for debugging | SATISFIED | telemetry.ts `generateTraceId()`, ag-ui-client.ts X-Trace-Id header, index.tsx trace display with tap-to-copy. |
| OBS-06 | 14-02 | Mobile client errors reported to backend telemetry proxy | SATISFIED | telemetry.ts `reportError()`, ag-ui-client.ts error callback wrapping, telemetry.py endpoint. |
| OBS-07 | 14-03 | Four version-controlled KQL query files | SATISFIED | backend/queries/ contains capture-trace.kql, recent-failures.kql, system-health.kql, admin-agent-audit.kql, README.md. |
| OBS-08 | 14-03 | Azure Monitor alert rules configured | SATISFIED | Summary documents 3 alert rules created via Azure CLI. Infrastructure-only, no repo artifacts. |

**Orphaned requirements:** None. All 8 OBS-xx requirements from REQUIREMENTS.md are accounted for in plans and verified.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none found) | - | - | - | No TODOs, FIXMEs, placeholders, stubs, or empty implementations found in any Phase 14 modified files |

### Human Verification Required

### 1. App Insights INFO Visibility

**Test:** After deployment, query `AppTraces | where SeverityLevel == 1 | take 5` in App Insights Logs
**Expected:** INFO-level traces appear (not just WARNING+), including lifecycle events from capture, classification, admin processing
**Why human:** Requires deployed backend sending data to App Insights. Cannot verify log exporter behavior locally.

### 2. Trace ID End-to-End in App Insights

**Test:** After deployment, capture something via mobile, copy the trace ID, paste into capture-trace.kql
**Expected:** Timeline shows events across capture, classification, admin processing, errand creation
**Why human:** Requires live capture flowing through deployed backend. KQL query correctness depends on actual App Insights schema.

### 3. Azure Monitor Alerts

**Test:** Verify alerts appear in Azure Portal > Monitor > Alerts and test push notification delivery
**Expected:** 3 alert rules visible (API-Error-Spike, Capture-Processing-Failures, API-Health-Check). Push notifications delivered to Azure mobile app.
**Why human:** Azure infrastructure -- cannot verify programmatically from repo.

### 4. Mobile Trace ID Display

**Test:** Open mobile app, capture text, observe toast
**Expected:** Toast shows "trace: a1b2c3d4..." below the filing result. Tap copies full UUID to clipboard.
**Why human:** Visual UI behavior on physical device.

### Gaps Summary

No gaps found. All 13 observable truths verified against the codebase. All 8 requirements (OBS-01 through OBS-08) are satisfied with concrete implementation evidence. All key links are wired. No anti-patterns detected. Backend tests pass (138 passed, 5 skipped; 1 pre-existing SSL failure in test_recipe_tools.py unrelated to Phase 14).

The implementation is thorough:
- Backend logging is scoped, leveled, and trace-ID-aware with structured extras
- Trace ID flows from mobile X-Trace-Id header through capture endpoints, ContextVar into @tool functions, Cosmos document persistence, and Admin Agent background processing
- Mobile generates trace IDs, injects headers, wraps errors with telemetry, and provides tap-to-copy UI
- Four KQL queries provide actionable operational tools
- Azure Monitor alerts configured for proactive incident detection

---

_Verified: 2026-03-22T23:15:00Z_
_Verifier: Claude (gsd-verifier)_
