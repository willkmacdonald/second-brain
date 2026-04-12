# Second Brain — Instrumentation Map

Where telemetry exists, where it doesn't, and what that means for debugging.

Last updated: 2026-04-12

---

## Recommendations

### Address Now (Critical)

**~~1. Mobile crash reporting~~** — RESOLVED (Phase 17.3, 2026-04-11). Sentry React Native SDK installed. Unhandled JS exceptions, native crashes, and OOM events are now reported to Sentry. See "Sentry vs App Insights" section below.

**~~2. React error boundaries~~** — RESOLVED (Phase 17.3, 2026-04-11). `Sentry.ErrorBoundary` wraps the root layout with an `ErrorFallback` recovery UI. Rendering errors are caught, reported to Sentry, and the user sees a "Try Again" screen instead of a blank crash.

### Defer (Nice to Have)

**Screen analytics / session tracking** — Knowing which screens are used would be interesting but isn't blocking debugging. You can infer usage patterns from API request volume in AppRequests.

**Client-side API latency** — Server-side duration is already in AppRequests. The gap is network transit time, which is hard to act on anyway.

**Cosmos RU consumption** — Azure tracks this in Cosmos DB Metrics (separate from App Insights). You can see it in the portal if you ever need it.

**Offline detection** — Would improve UX (show "no connection" instead of "something went wrong") but isn't a telemetry gap per se — if the request never reaches the server, there's nothing to log.

**Silent failures on Inbox/Status screens** — These are CRUD operations that self-heal via re-fetch. Adding telemetry would help spot patterns (e.g., "inbox loads fail every Tuesday") but isn't urgent since the user can just pull-to-refresh.

---

## How to Read This Document

Each section walks through a layer of the system. For every action or component, there's a verdict:

- **TRACKED** — errors and/or success events reach App Insights
- **PARTIAL** — some paths are tracked, others are silent
- **SILENT** — failures are swallowed or shown only to the user on-device
- **AUTOMATIC** — Azure infrastructure tracks this without application code

---

## 1. Mobile App (React Native / Expo)

The mobile app has two telemetry systems:

1. **Sentry** (`mobile/lib/sentry.ts`) — Crash reporting for unhandled JS exceptions, native crashes, OOM events, and React rendering errors. Reports to sentry.io. Disabled in `__DEV__` mode; active in production/preview builds. DSN is baked in at build time via `EXPO_PUBLIC_SENTRY_DSN` in `eas.json`.

2. **Custom telemetry** (`mobile/lib/telemetry.ts`) — POSTs operational events to `POST /api/telemetry` on the backend, which logs them to App Insights. Used for capture-flow errors (network failures, API errors during voice/text capture).

These are complementary, not overlapping: Sentry catches app-level crashes; the custom telemetry tracks operational errors during normal app flow. There is no analytics SDK.

### Capture Flow (Main Tab)

| Action | API Call | Error Reporting | Verdict |
|--------|----------|----------------|---------|
| Text capture submit | `POST /api/capture` (SSE) | `reportError()` to `/api/telemetry` | **TRACKED** |
| Voice capture (on-device recognition) | `POST /api/capture` (SSE) | `reportError()` to `/api/telemetry` | **TRACKED** |
| Voice capture fallback (cloud upload) | `POST /api/capture/voice` (SSE) | `reportError()` to `/api/telemetry` | **TRACKED** |
| Speech recognition error during recording | Falls back to cloud upload | `reportError()` if fallback also fails | **TRACKED** |
| Follow-up text submit | `POST /api/capture/follow-up` (SSE) | `reportError()` to `/api/telemetry` | **TRACKED** |
| Follow-up voice submit | `POST /api/capture/follow-up/voice` (SSE) | `reportError()` to `/api/telemetry` | **TRACKED** |
| HITL bucket selection (low confidence) | `PATCH /api/inbox/{id}/recategorize` | Toast only, no telemetry | **SILENT** |
| Empty voice recording (< 1 second) | None | Silently discarded | **SILENT** |

### Inbox Screen

| Action | API Call | Error Reporting | Verdict |
|--------|----------|----------------|---------|
| Load inbox list | `GET /api/inbox` | Silent — empty list shown | **SILENT** |
| Pull-to-refresh | `GET /api/inbox` | Silent | **SILENT** |
| Pagination (scroll to load more) | `GET /api/inbox?offset=N` | Silent | **SILENT** |
| Tap item (open detail) | None | N/A | N/A |
| Recategorize from detail card | `PATCH /api/inbox/{id}/recategorize` | Silent | **SILENT** |
| Swipe-to-delete | `DELETE /api/inbox/{id}` | Silent — re-fetches on failure | **SILENT** |

### Conversation Screen (Follow-up Resolution)

| Action | API Call | Error Reporting | Verdict |
|--------|----------|----------------|---------|
| Load item details | `GET /api/inbox/{id}` | Toast only, no telemetry | **SILENT** |
| Bucket selection | `PATCH /api/inbox/{id}/recategorize` | Toast only, no telemetry | **SILENT** |

### Status / Errands Screen

| Action | API Call | Error Reporting | Verdict |
|--------|----------|----------------|---------|
| Load errands + tasks | `GET /api/errands` + `GET /api/tasks` | Silent | **SILENT** |
| Focus-based polling (5 polls at 3s intervals) | Same as load | Silent | **SILENT** |
| Processing-count polling | Same as load | Silent | **SILENT** |
| Dismiss admin notification | `POST /api/errands/notifications/{id}/dismiss` | Silent — re-fetches | **SILENT** |
| Delete errand (swipe) | `DELETE /api/errands/{id}` | Silent — re-fetches | **SILENT** |
| Complete task (swipe) | `DELETE /api/tasks/{id}` | Silent — re-fetches | **SILENT** |
| Route unrouted errand | `POST /api/errands/{id}/route` | Silent — re-fetches | **SILENT** |

### What the Mobile App Does NOT Track

- **No screen view analytics** — no visibility into which screens are used
- **No performance monitoring** — no load times, no API latency from the client's perspective
- **No offline detection** — network failures aren't distinguished from server errors
- **No session tracking** — no concept of user sessions or app lifecycle events (background/foreground)

### Trace ID System

Every capture generates a UUID (`X-Trace-Id` header) that persists across follow-ups. This ID:
- Appears in the user's toast (first 8 chars, tap to copy full ID)
- Is sent in the `X-Trace-Id` header on all SSE requests
- Is included in telemetry error reports as `captureTraceId`
- Is stored on Cosmos DB documents as `captureTraceId`
- Can be queried in App Insights via `Properties.capture_trace_id`

This is the single most useful debugging primitive — it connects a specific capture across mobile, backend, classifier, admin agent, and Cosmos.

---

## 2. Backend API (FastAPI on Azure Container Apps)

### Azure Monitor Configuration

```python
# main.py
logging.getLogger("second_brain").setLevel(logging.INFO)
configure_azure_monitor(logger_name="second_brain")
enable_instrumentation()  # agent framework OTel metrics
```

- Logger name `"second_brain"` scopes logging to application code only (filters out Azure SDK noise)
- Severity level: INFO and above exported to App Insights
- OpenTelemetry spans exported via Azure Monitor exporter
- `enable_instrumentation()` tracks gen_ai token counts and operation durations

### API Endpoints

| Endpoint | Logging | OTel Spans | Custom Dimensions | Verdict |
|----------|---------|------------|-------------------|---------|
| `POST /api/capture` | INFO: source, thread_id | `capture_text` span with outcome, bucket, confidence | `capture_trace_id`, `component="classifier"` | **TRACKED** |
| `POST /api/capture/voice` | INFO: source | `capture_voice` span | Same as above | **TRACKED** |
| `POST /api/capture/follow-up` | INFO: follow-up round | `capture_follow_up` span | Same as above | **TRACKED** |
| `POST /api/capture/follow-up/voice` | INFO | `capture_follow_up_voice` span | Same as above | **TRACKED** |
| `POST /api/investigate` | INFO: question, thread_id | `investigate` span with tool info | `component="investigation_agent"` | **TRACKED** |
| `POST /api/telemetry` | WARNING: client event type + message | None | `component="mobile"`, `event_type`, `capture_trace_id`, all metadata | **TRACKED** |
| `GET /api/inbox` | None | None (auto-tracked as AppRequest) | None | **AUTOMATIC** |
| `GET /api/errands` | None | None (auto-tracked) | None | **AUTOMATIC** |
| `GET /api/tasks` | None | None (auto-tracked) | None | **AUTOMATIC** |
| `GET /health` | None (intentionally silent) | None | None | **AUTOMATIC** (AppRequests only) |
| Auth failures | WARNING: IP, path, reason | None | None | **TRACKED** |

### Capture Processing Pipeline

This is the most instrumented path in the system. When a capture arrives:

| Step | What's Logged | Level | Custom Dimensions |
|------|--------------|-------|-------------------|
| 1. Request received | "Capture source: {source}, thread_id={id}" | INFO | `capture_trace_id`, `component="capture"` |
| 2. OTel span opened | Span: `capture_text` or `capture_voice` | — | `capture.type`, `capture.thread_id`, `capture.trace_id` |
| 3. Classifier agent called | Agent middleware spans: `classifier_agent_run`, `tool_file_capture` | DEBUG | `agent.name`, `agent.duration_ms` |
| 4. Reasoning chunks | Each LLM thinking chunk logged separately | INFO | `reasoning_text`, `agent_run_id`, `chunk_index`, `component="classifier"` |
| 5. Classification result | "Filed to {bucket} ({confidence}, status={status}): {text}" | INFO | `capture_trace_id`, `component="classifier"` |
| 6. Cosmos write | Implicit (via file_capture tool) | INFO | `capture_trace_id` |
| 7. Safety-net fallback | "Safety-net: agent skipped file_capture, filed as misunderstood" | WARNING | `capture_trace_id`, `component="classifier"` |
| 8. Stream error | Full stack trace | ERROR | `capture_trace_id`, `component="classifier"` |
| 9. Span closed | Outcome attributes set | — | `capture.outcome`, `capture.bucket`, `capture.confidence`, `capture.safety_net` |

### Admin Agent Processing

| Step | What's Logged | Level | Custom Dimensions |
|------|--------------|-------|-------------------|
| Processing started | OTel span: `admin_agent_process` | — | `admin.inbox_item_id` |
| Tool call | OTel span: `tool_{name}` | DEBUG | `tool.name`, `tool.duration_ms` |
| Processing succeeded | Outcome set on span | — | `admin.outcome="success"`, `admin.tool_invoked` |
| Processing failed | Full stack trace, item marked `adminProcessingStatus="failed"` | ERROR | `admin.outcome="failed"` |
| Retry with nudge | Second attempt after stall | — | `admin.retry=true` |

### Investigation Agent

| Step | What's Logged | Level |
|------|--------------|-------|
| Query received | "Investigation query: question={q} thread_id={id}" | INFO |
| Rate limit warning | SSE event only (soft limiter, never blocks) | — |
| Tool call | SSE event: `{"type": "tool_call", "tool": name}` | — |
| Tool error | SSE event + log | WARNING/ERROR |
| Stream timeout (60s) | "Investigation stream timed out after 60s" | WARNING |
| Stream error | Full stack trace | ERROR |

### Error Handling

- **No global exception handler middleware** — FastAPI's default Starlette handler catches unhandled exceptions
- All unhandled exceptions automatically appear in `AppExceptions` table
- Streaming endpoints (capture, investigate) wrap their generators in try/except with:
  - `span.record_exception(exc)` — records to OTel span
  - `logger.error(..., exc_info=True)` — full stack trace to App Insights
  - SSE error event to client — user sees the error

---

## 3. Azure Infrastructure (Automatic Telemetry)

These are tracked by Azure without any application code.

### App Insights Auto-Instrumentation

| Table | What's Captured | Notes |
|-------|----------------|-------|
| `AppRequests` | All HTTP requests to the FastAPI app (method, path, status code, duration) | Automatic via OpenTelemetry FastAPI instrumentation |
| `AppExceptions` | Unhandled Python exceptions with full stack traces | Automatic |
| `AppDependencies` | Outbound HTTP calls (Cosmos DB, Foundry API, Key Vault) | Automatic via `azure-core-tracing-opentelemetry` |
| `AppTraces` | All `logger.info/warning/error/critical()` calls with custom dimensions | Automatic via Azure Monitor logging handler |

### Azure Monitor Alerts (3 Rules)

| Alert | Condition | Severity | Evaluation Window |
|-------|-----------|----------|-------------------|
| API-Error-Spike | > 3 ERROR-level traces in 5 minutes | Warning (2) | Every 5 min |
| Capture-Processing-Failures | > 2 admin agent failures in 15 minutes | Warning (2) | Every 15 min |
| API-Health-Check | > 5 HTTP 5xx responses in 10 minutes | Important (1) | Every 10 min |

All alerts deliver push notifications to Azure mobile app (will@willmacdonald.com). Auto-mitigate is enabled (alerts auto-resolve when condition clears).

### Container Apps

| What's Tracked | Where |
|----------------|-------|
| Pod restart count | Container App Metrics (Azure Portal) |
| Replica scaling events | Container App Activity Log |
| CPU / memory utilization | Container App Metrics |
| Revision deployment status | GitHub Actions deploy summary |

**CI/CD health check after deploy:** 15 polls at 12-second intervals against `/health`, validates HTTP 200 + `status: "ok"`. Deployment fails if health check fails.

### What Azure Tracks That Isn't in App Insights

| Service | Where It's Tracked | NOT in App Insights |
|---------|-------------------|---------------------|
| Key Vault access (secret reads) | Azure Activity Log | Correct — separate audit trail |
| Container App restarts | Container App Metrics | Correct — different monitoring plane |
| Cosmos DB RU consumption | Cosmos DB Metrics | Only HTTP-level calls appear as AppDependencies |

---

## 4. Azure AI Foundry Agents

Three agents are instrumented with custom middleware (`AuditAgentMiddleware` + `ToolTimingMiddleware`):

| Agent | Middleware | What's Tracked |
|-------|-----------|----------------|
| Classifier | Both | Agent run span + per-tool spans with classification metadata (bucket, confidence, status) |
| Admin Agent | Both | Agent run span + per-tool spans |
| Investigation Agent | Both | Agent run span + per-tool spans |

The `enable_instrumentation()` call from the agent framework SDK additionally tracks:
- `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens` per agent call
- `gen_ai.operation.duration`

**NOT tracked:** Full prompt content or full response content from the LLM. Only token counts and durations.

---

## 5. Sentry vs App Insights

Sentry and App Insights are **separate systems** — they don't overlap:

| System | What It Covers | Where to Look |
|--------|---------------|---------------|
| **Sentry** | Mobile app crashes (JS exceptions, native crashes, OOM, React render errors) | sentry.io dashboard |
| **App Insights** | Backend logs, API requests, traces, errors from the FastAPI server on Container Apps | Azure Portal / `/investigate` |

The Investigation Agent's tools (`recent_errors`, `trace_lifecycle`, `system_health`, `usage_patterns`) query **App Insights only** — they won't see Sentry data.

- **Mobile app crash?** → Check the Sentry dashboard.
- **Backend 500 or processing error?** → Use `/investigate` as usual.

Down the road you could bridge them (Sentry has integrations that can forward to Azure), but right now they're two independent observability surfaces for two different parts of the system.

---

## 6. The Gaps

### Critical Gaps (Things That Fail Silently)

| Gap | Impact | Where It Hurts |
|-----|--------|----------------|
| ~~**Mobile app crashes**~~ | ~~Unhandled JS exceptions vanish completely~~ | RESOLVED — Sentry (Phase 17.3) |
| **Inbox/Status screen API failures** | User sees empty screen, no telemetry | You won't know if users can't load their inbox |
| **HITL bucket selection failures** | User sees toast, no telemetry | If recategorization is broken, you won't know |
| **Delete/route operation failures** | Silent re-fetch, no telemetry | Data operations could fail repeatedly |
| **Mobile offline state** | Not detected or reported | Can't distinguish "server down" from "phone has no signal" |

### Moderate Gaps (Would Help Debugging)

| Gap | Impact |
|-----|--------|
| **No client-side API latency** | You see server-side duration in AppRequests, but not the user's experienced latency (includes network) |
| **No screen view tracking** | Can't tell which features are used or unused |
| **No session/lifecycle tracking** | Can't tell how often the app is opened, or if it's foregrounded during a capture |
| **Cosmos DB operation details** | Only HTTP-level tracking — no RU consumption or partition key routing visibility |
| ~~**No React error boundaries**~~ | RESOLVED — `Sentry.ErrorBoundary` + `ErrorFallback` (Phase 17.3) |

### Non-Gaps (Things That Look Missing But Aren't)

| Concern | Why It's Fine |
|---------|--------------|
| "Are Foundry agent errors tracked?" | Yes — all three agents have middleware spans, and the streaming adapters log errors at ERROR level with stack traces |
| "Are API auth failures tracked?" | Yes — `APIKeyMiddleware` logs every failed auth attempt at WARNING level |
| "Is the health endpoint tracked?" | Yes — automatically as AppRequests. It's intentionally silent in application logs to avoid noise |
| "Are Cosmos writes tracked?" | Partially — application code logs success/failure, and Azure tracks the HTTP call as a dependency |

---

## 7. Querying the Telemetry

### Via `/investigate` (Terminal Client)

The Investigation Agent can query App Insights directly. Available tools:

| Tool | What It Queries |
|------|----------------|
| `system_health` | Capture count, success rate, error count, avg/p95/p99 latency, trend comparison |
| `recent_errors` | Last N errors (SeverityLevel >= 3) with component, message, trace ID |
| `trace_lifecycle` | Full lifecycle of a single capture by trace ID (requests, dependencies, traces, exceptions) |
| `usage_patterns` | Captures grouped by time period, bucket, or destination |

### Via Azure Portal (Log Analytics)

KQL queries are version-controlled in `backend/queries/`:
- `capture-trace.kql` — full lifecycle by trace ID
- `recent-failures.kql` — last 50 errors
- `system-health.kql` — multi-section health overview
- `admin-agent-audit.kql` — admin agent processing audit

### Via Azure Monitor Alerts

Three alert rules fire push notifications to your phone (see Section 3).

---

## 8. Summary: What You Can and Can't Debug

| Scenario | Can You Debug It? | How |
|----------|-------------------|-----|
| "A capture failed" | **Yes** | Trace ID from toast → `/investigate trace lifecycle for {id}` |
| "The classifier is wrong" | **Yes** | Trace ID → see classification reasoning in App Insights |
| "Admin agent didn't process" | **Yes** | Check `recent_errors` or trace lifecycle — admin processing spans are fully instrumented |
| "The app crashed on my phone" | **Yes** | Check Sentry dashboard — JS exceptions, native crashes, and render errors are all reported with stack traces and device info |
| "Users can't load their inbox" | **Partially** | You'd see the GET /api/inbox request in AppRequests (if it reached the server). If the phone has no signal, you see nothing. |
| "Recategorization is broken" | **Partially** | You'd see the PATCH request in AppRequests if it reached the server. The mobile app won't tell you. |
| "The app is slow" | **Partially** | Server-side latency is in AppRequests. Client-side network latency is not tracked. |
| "Nobody is using the app" | **Partially** | You can infer from capture volume in AppRequests. No direct app open/session data. |
| "Cosmos is slow" | **Partially** | HTTP-level dependency tracking shows duration. No RU consumption data in App Insights. |
