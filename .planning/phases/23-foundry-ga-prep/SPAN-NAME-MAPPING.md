# RC to GA span Name mapping

**Purpose:** Phase 24 task groups 23.1/23.2/23.3 update KQL queries to consume new span Names. This document is the source of truth for that translation.
**Sources:**
- Microsoft Agent Framework GA semantic conventions (per design Section "Observability --- Delete": framework emits `invoke_agent` and `execute_tool`)
- Existing RC span Names found in `backend/src/second_brain/observability/queries.py` and `backend/src/second_brain/observability/kql_templates.py`
- PLAN-02 probe runs (streaming_shape probe captured 25 updates; span-level data not directly visible in probe output but framework-emitted span Names are documented in the GA SDK + design doc)
- FOUNDRY-PROBE-FINDINGS.md Probe 1 (streaming_shape): confirmed framework handles tool execution internally during streaming; the adapter does NOT need manual tool call detection

## Span Name table

| RC span Name | GA span Name | Source for the mapping | Notes |
|---|---|---|---|
| `*_agent_run` (e.g. `classifier_agent_run`, `admin_agent_run`, `investigation_agent_run`) | `invoke_agent` | Design Section "Observability --- Delete" + GA framework semantic conventions | Top-level framework-emitted span per `agent.run()` / `agent.run(stream=True)` call. RC versions were custom spans emitted by `AuditAgentMiddleware` in `agents/middleware.py` via `tracer.start_as_current_span(self._span_name)`. GA framework emits `invoke_agent` natively --- custom middleware wrapping is removed (F-14/F-15/F-16/F-17 in calibration report). |
| `tool_*` (e.g. `tool_file_capture`, `tool_recent_errors`, `tool_add_errand_items`) | `execute_tool` | Design Section "Observability --- Delete" + GA framework semantic conventions | Tool-call inner span (child of `invoke_agent`). RC versions were custom spans emitted by `ToolTimingMiddleware` in `agents/middleware.py` via `tracer.start_as_current_span(f"tool_{func_name}")`. GA framework emits `execute_tool` natively with `tool.name` attribute carrying the function name. |
| `capture_text` | No framework equivalent --- **custom span retained** | Custom span in `streaming/adapter.py:175`. Not a framework-emitted span. | This is a custom `tracer.start_as_current_span("capture_text")` wrapping the entire capture flow. Per F-14 in calibration: the custom wrapper is DELETED in Phase 24 because capture-context attributes move to the framework `invoke_agent` span via `AgentMiddleware`. Capture-type info moves to the AppRequests span (already tagged at `api/capture.py`). |
| `capture_voice` | No framework equivalent --- **custom span deleted** | Custom span in `streaming/adapter.py:372`. Same pattern as `capture_text`. | Deleted per F-14. Attributes move to framework `invoke_agent` span via middleware. |
| `capture_follow_up` | No framework equivalent --- **custom span deleted** | Custom span in `streaming/adapter.py:582`. Same pattern. | Deleted per F-14. |
| `investigate` | No framework equivalent --- **custom span deleted** | Custom span in `streaming/investigation_adapter.py:96`. | Deleted per F-15. Attributes move to framework `invoke_agent` span via middleware. |
| `admin_agent_process` | No framework equivalent --- **custom span deleted** | Custom span in `processing/admin_handoff.py:177`. | Deleted per F-16. |
| `admin_agent_batch_process` | No framework equivalent --- **custom span deleted** | Custom span in `processing/admin_handoff.py:441`. | Deleted per F-16. |

Custom spans the codebase emits that are NOT framework-emitted and are NOT changed by RC-to-GA migration:
- HTTP route spans (`/api/capture`, `/api/errands`, `/api/health`, etc.) --- these are AppRequests emitted by the ASGI OTel instrumentation, not agent framework. They filter on `Name has "/api/capture"` in KQL templates. **Unchanged by migration.**
- Cosmos SDK dependency spans (`ContainerProxy.*`, `POST /dbs/*`, `GET /dbs/*`) --- these are AppDependencies emitted by the Azure SDK OTel auto-instrumentation. They filter on `Name startswith "ContainerProxy"` etc. in `COSMOS_BY_CAPTURE_TRACE`. **Unchanged by migration.**
- Spine workload event spans --- separate system per CLAUDE.md, out of scope for migration.

Per design Section "Framework-fidelity auditor checklist", spans the auditor expects to see GA-shaped:
- Agent invocation: `invoke_agent` (was `*_agent_run` custom spans)
- Tool execution: `execute_tool` (was `tool_*` custom spans)
- Span attributes: `agent.name`, `tool.name`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens` (GenAI semantic conventions)
- Capture-trace propagation: `capture.trace_id` attribute on agent + tool spans (per D-07a, set by `AgentMiddleware` + `FunctionMiddleware`)

## Span attribute table (preserved across RC to GA)

| Attribute name | Set by | RC source | GA source |
|---|---|---|---|
| `capture.trace_id` (also seen as `capture_trace_id` in some KQL queries) | ContextVar in `api/capture.py` + `observability/span_processor.py` | RC: `CaptureTraceSpanProcessor.on_start()` tags every span with `capture.trace_id` from the `capture_trace_id_var` ContextVar | GA: `AgentMiddleware`/`FunctionMiddleware` on framework `invoke_agent`/`execute_tool` spans (source-level tagging) + `CaptureTraceSpanProcessor` RETAINED for non-framework spans per D-07a (Azure SDK deps, Cosmos AppDependencies, AppExceptions). Attribute name preserved. |
| `agent.name` | Framework | RC: custom `AuditAgentMiddleware` in `agents/middleware.py` sets `span.set_attribute("agent.name", self._agent_name)` on a custom span | GA: framework auto-emits `agent.name` attribute on the `invoke_agent` span. Custom middleware deleted. |
| `tool.name` | Framework | RC: custom `ToolTimingMiddleware` in `agents/middleware.py` sets `span.set_attribute("tool.name", func_name)` on a custom span | GA: framework auto-emits `tool.name` attribute on the `execute_tool` span. Custom middleware deleted. |
| `gen_ai.usage.input_tokens` | Framework instrumentation | RC: `enable_instrumentation()` at `main.py:31` emits via GenAI semantic conventions. No manual token counters found anywhere in `streaming/`, `agents/`, or `processing/`. | GA: framework's `enable_instrumentation()` continues to emit via GenAI semantic conventions. No change needed. |
| `gen_ai.usage.output_tokens` | Framework instrumentation | RC: same as `input_tokens` --- emitted by framework instrumentation. | GA: same mechanism, same attribute name. |

Note D-07a: `CaptureTraceSpanProcessor` is RETAINED, not removed. KQL queries union over `AppRequests`, `AppDependencies`, `AppTraces`, `AppExceptions` filtered on `Properties.capture_trace_id` --- that filter continues to match in GA because the attribute name is preserved across both sources (framework middleware + retained span processor).

## KQL query consumer table

Phase 24 task groups update KQL queries to use GA span Names. Update is in the SAME commit cluster as the agent that emits the new span Names, so the deployed system never sees a query/code mismatch.

### File: `backend/src/second_brain/observability/queries.py`

| Query function | Current span filter (RC) | New span filter (GA) | Phase 24 owner | Lines (approx) |
|---|---|---|---|---|
| `execute_kql` | Generic query executor --- no span Name filter | No change needed | n/a | Lines 45-102 |
| `query_capture_trace` | `tostring(Properties.capture_trace_id) == trace_id` --- unions over AppRequests/AppDependencies/AppTraces/AppExceptions, filters by attribute not by Name | No change needed --- attribute filter is Name-agnostic | n/a | Lines 105-133 |
| `query_recent_failures` | `SeverityLevel >= 3` on AppTraces + all AppExceptions --- no span Name filter | No change needed | n/a | Lines 136-162 |
| `query_system_health` | `Name has "/api/capture"` on AppRequests --- HTTP route Name, not agent span Name | No change needed --- HTTP route Names are unaffected by RC-to-GA migration | n/a | Lines 165-196 |
| `query_admin_audit` | `Properties.component == "admin_agent"` on AppTraces --- filters by component property, not span Name | No change needed | n/a | Lines 199-220 |
| `query_enhanced_system_health` | `Name has "/api/capture"` on AppRequests --- HTTP route Name | No change needed | n/a | Lines 266-317 |
| `query_recent_failures_filtered` | `SeverityLevel >= {severity_filter}` + optional `Properties.component` filter --- no span Name filter | No change needed | n/a | Lines 320-407 |
| `query_usage_patterns` | `Name has "/api/capture"` (period/hour), `Properties.component == "classifier"` (bucket), `Properties.component == "admin_agent"` (destination) --- HTTP route Name or component property | No change needed | n/a | Lines 410-470 |
| `query_backend_api_requests` | No span Name filter --- projects `Name` column but does not filter on agent span Names | No change needed | n/a | Lines 499-542 |
| `query_backend_api_failures` | `SeverityLevel >= 3` + optional `Properties.capture_trace_id` --- no span Name filter | No change needed | n/a | Lines 545-592 |
| `fetch_agent_runs` | **`Name endswith "_agent_run"`** --- RC-era custom span Name pattern from `AuditAgentMiddleware` | **`Name == "invoke_agent"`** --- GA framework-emitted span Name | task group 23.1 (investigation) | Lines 600-645 |
| `fetch_cosmos_diagnostics` | `Name startswith "ContainerProxy"` or `POST /dbs` or `GET /dbs` on AppDependencies --- Cosmos SDK span Names | No change needed --- Cosmos SDK span Names are unaffected | n/a | Lines 652-694 |
| `fetch_audit_spans_for_correlation` | `Properties.correlation_id == cid` or `Properties.capture_trace_id == cid` --- attribute filter, no span Name | No change needed | n/a | Lines 702-721 |
| `fetch_audit_exceptions_for_correlation` | `Properties.correlation_id == cid` or `Properties.capture_trace_id == cid` --- attribute filter | No change needed | n/a | Lines 724-744 |
| `fetch_audit_cosmos_diagnostics_for_correlation` | `activityId_g == cid` on AzureDiagnostics --- server-side ID filter | No change needed | n/a | Lines 746-766 |

**Summary:** Only `fetch_agent_runs` requires a span Name update. All other query functions filter by HTTP route Names (`/api/capture`), component properties, severity levels, or correlation attributes --- none of which change with the RC-to-GA migration.

### File: `backend/src/second_brain/observability/kql_templates.py`

| Template | Current span filter (RC) | New span filter (GA) | Phase 24 owner |
|---|---|---|---|
| `CAPTURE_TRACE` | `Properties.capture_trace_id == trace_id` --- attribute filter on union of all tables | No change needed --- attribute filter is Name-agnostic | n/a |
| `RECENT_FAILURES` | `SeverityLevel >= 3` on AppTraces + AppExceptions | No change needed | n/a |
| `SYSTEM_HEALTH` | `Name has "/api/capture"` on AppRequests --- HTTP route Name | No change needed | n/a |
| `SYSTEM_HEALTH_ENHANCED` | `Name has "/api/capture"` on AppRequests --- HTTP route Name | No change needed | n/a |
| `RECENT_FAILURES_FILTERED` | `SeverityLevel >= {severity_filter}` + optional component filter | No change needed | n/a |
| `LATEST_CAPTURE_TRACE_ID` | `Properties.capture_trace_id` presence check on AppTraces | No change needed | n/a |
| `USAGE_PATTERNS_BY_PERIOD` | `Name has "/api/capture"` on AppRequests --- HTTP route Name | No change needed | n/a |
| `USAGE_PATTERNS_BY_BUCKET` | `Properties.component == "classifier"` on AppTraces --- component property | No change needed | n/a |
| `USAGE_PATTERNS_BY_DESTINATION` | `Properties.component == "admin_agent"` on AppTraces --- component property | No change needed | n/a |
| `ADMIN_AUDIT_LOG` | `Properties.component in ("admin_agent", "admin_handoff")` on AppTraces | No change needed | n/a |
| `ADMIN_AUDIT_SUMMARY` | `Properties.component in ("admin_agent", "admin_handoff")` on AppTraces | No change needed | n/a |
| `BACKEND_API_REQUESTS` | No span Name filter (projects `Name` but does not filter on agent Names) | No change needed | n/a |
| `BACKEND_API_FAILURES` | `SeverityLevel >= 3` + optional `capture_trace_id` filter | No change needed | n/a |
| **`AGENT_RUNS`** | **`Name endswith "_agent_run"`** on AppDependencies (line 378) | **`Name == "invoke_agent"`** on AppDependencies | task group 23.1 (investigation) |
| `COSMOS_DIAGNOSTIC_LOGS` | `Category == "DataPlaneRequests"` on AzureDiagnostics | No change needed | n/a |
| `COSMOS_BY_CAPTURE_TRACE` | `Name startswith "ContainerProxy"` or DB path Names on AppDependencies | No change needed --- Cosmos SDK Names unaffected | n/a |
| `AUDIT_SPANS_BY_CORRELATION` | `Properties.correlation_id` or `Properties.capture_trace_id` attribute filter | No change needed | n/a |
| `AUDIT_EXCEPTIONS_BY_CORRELATION` | `Properties.correlation_id` or `Properties.capture_trace_id` attribute filter | No change needed | n/a |
| `AUDIT_COSMOS_BY_CORRELATION` | `activityId_g == cid` on AzureDiagnostics | No change needed | n/a |

**Summary:** Only `AGENT_RUNS` requires a span Name update (line 378: `Name endswith "_agent_run"` becomes `Name == "invoke_agent"`). All other templates use HTTP route Names, component properties, severity levels, or correlation attributes.

### Update strategy per task group

- **Task group 23.1 --- Investigation:** Updates the `AGENT_RUNS` template (the only KQL template that filters on agent span Names) from `Name endswith "_agent_run"` to `Name == "invoke_agent"`. This is in the same commit cluster as the `agents/investigation.py` rewrite that replaces `AuditAgentMiddleware` custom spans with framework-emitted `invoke_agent` spans. The `fetch_agent_runs` function in `queries.py` (which consumes `AGENT_RUNS`) may also need property projections updated if GA span attributes differ from RC custom attributes (e.g., `Properties.agent_id` may move to `Properties.agent.name`, `Properties.run_id` may change shape). The `AGENT_RUNS` template currently projects `Properties.agent_id`, `Properties.agent_name`, `Properties.run_id`, `Properties.foundry_thread_id`, `Properties.capture_trace_id` --- Phase 24 task group 23.1 verifies each of these against actual GA span attributes.

- **task group 23.2 --- Admin:** No KQL template changes needed. Admin queries (`ADMIN_AUDIT_LOG`, `ADMIN_AUDIT_SUMMARY`, `USAGE_PATTERNS_BY_DESTINATION`) filter on `Properties.component == "admin_agent"`, not on span Names. The `Properties.component` attribute is set by application-level `logger.info(...)` calls, not by the agent framework --- so it is unaffected by the RC-to-GA migration.

- **Task group 23.3 --- Classifier:** No KQL template changes for existing queries. However, task group 23.3 introduces the new `forced_tool_failure` SSE sub-code (per D-07b). Phase 24 task group 23.3 should add a new KQL query or template to track `forced_tool_failure` events --- either as a new `FORCED_TOOL_FAILURE_COUNT` template filtering on AppTraces where `Properties.sse_sub_code == "forced_tool_failure"` (or however the sub-code is logged), or as an extension to `RECENT_FAILURES_FILTERED`. The exact shape depends on how the adapter logs forced_tool_failure events. Classifier queries (`USAGE_PATTERNS_BY_BUCKET`) filter on `Properties.component == "classifier"` which is unaffected.

## Azure Monitor alert rules to review

Per design Section "Risks" row 7 ("Span name change breaks existing KQL / dashboards / alerts"), Azure Monitor alert rules in the `SecondBrainAlerts` action group (per MEMORY.md) reference KQL queries that may filter on span Names. Phase 24 task group 23.3 final pre-push step reviews:

| Alert rule | KQL basis | Span Name filter | Action |
|---|---|---|---|
| API-Error-Spike | Likely queries `AppExceptions` or `AppTraces` with `SeverityLevel >= 3` --- filters on severity, not span Name | No span Name filter expected --- severity-based | No change needed (verify at deploy time) |
| Capture-Processing-Failures | Likely queries `AppRequests` where `Name has "/api/capture"` with error ResultCode | `Name has "/api/capture"` --- HTTP route Name, not agent span Name | No change needed (verify at deploy time) |
| API-Health-Check | Likely pings `/api/health` endpoint or queries `AppRequests` health route | HTTP route Name filter | No change needed (verify at deploy time) |

Operator command to inspect actual alert rule KQL:
```bash
az monitor scheduled-query list --resource-group shared-services-rg -o json \
  | jq '.[] | {name, criteria: .criteria.allOf[0].query}'
```

If any alert rule references `_agent_run` or other RC-only span Names, Phase 24 task group 23.3 plan must include an alert-rule update step. Based on the alert rule names and the pattern that all application KQL queries use HTTP route Names or severity filters (not agent span Names), it is **unlikely** that any alert rule needs updating --- but the operator must verify before push.

## Phase 24 verification gate

Phase 24 cumulative framework-fidelity audit checklist row "Tracing" passes when:
- All KQL queries that filter by span Name use GA Names (or are updated to be Name-agnostic via attribute filters)
- No KQL query references `_agent_run` patterns (the only RC span Name pattern found in the codebase)
- The auditor's diff scan finds zero such references
- The `AGENT_RUNS` template uses `Name == "invoke_agent"` (not `Name endswith "_agent_run"`)

Verify pre-push:
```bash
! grep -rE '_agent_run|azure_ai_agent\.' backend/src/second_brain/observability/   # MUST return zero matches at end of Phase 24
```

Post-deploy span verification:
```bash
# Query App Insights for GA span Names after first capture
az monitor app-insights query --app second-brain-insights --analytics-query \
  "AppDependencies | where TimeGenerated > ago(1h) | where Name == 'invoke_agent' or Name == 'execute_tool' | take 5" \
  --resource-group shared-services-rg -o json | jq '.tables[0].rows'
```

If `invoke_agent` / `execute_tool` spans appear after the first post-deploy capture, the GA framework is emitting correctly and the `AGENT_RUNS` template update is confirmed working.
