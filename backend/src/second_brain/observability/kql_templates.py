"""Workspace-schema KQL query templates for Log Analytics.

All templates query the Log Analytics workspace directly via
`LogsQueryClient.query_workspace()`, which exposes the workspace-style
table and column names (NOT the portal-style aliases).

Schema reference for this workspace:

  Tables:
    AppRequests       (portal alias: requests)
    AppTraces         (portal alias: traces)
    AppDependencies   (portal alias: dependencies)
    AppExceptions     (portal alias: exceptions)

  Common columns:
    TimeGenerated     (portal alias: timestamp)
    Name              (portal alias: name) -- on AppRequests/AppDependencies
    ResultCode        (portal alias: resultCode)
    DurationMs        (portal alias: duration, already in milliseconds)
    Message           (portal alias: message) -- on AppTraces/AppExceptions
    SeverityLevel     (portal alias: severityLevel)
    Properties        (portal alias: customDimensions) -- dynamic type

Time filtering: The `timespan` parameter on
`LogsQueryClient.query_workspace()` acts as an implicit
`where TimeGenerated ...` filter at the API level. Templates therefore
only need explicit `TimeGenerated` filters when splitting the span
into sub-periods (e.g., current vs previous period comparisons).

Output column naming: Each template uses `project`/`extend` to emit
column names that match what the Python parsing layer in `queries.py`
expects (`timestamp`, `ItemType`, `severityLevel`, `Message`,
`Component`, `CaptureTraceId`, etc.). This keeps the Python layer
decoupled from workspace-schema specifics.
"""

# ---------------------------------------------------------------------------
# Capture Trace -- traces a single capture through its full lifecycle
# ---------------------------------------------------------------------------
# Parameterised with {trace_id} via str.format().

CAPTURE_TRACE = """\
let trace_id = "{trace_id}";
union withsource=SourceTable AppRequests, AppDependencies, AppTraces, AppExceptions
| where tostring(Properties.capture_trace_id) == trace_id
| project
    timestamp = TimeGenerated,
    ItemType = case(
        SourceTable == "AppTraces", "Log",
        SourceTable == "AppRequests", "Request",
        SourceTable == "AppDependencies", "Dependency",
        SourceTable == "AppExceptions", "Exception",
        SourceTable
    ),
    severityLevel = SeverityLevel,
    Message = coalesce(OuterMessage, Message, InnermostMessage, ExceptionType, Name),
    OuterMessage,
    OuterType,
    InnermostMessage,
    Details = tostring(Details),
    Component = tostring(Properties.component),
    CaptureTraceId = tostring(Properties.capture_trace_id)
| order by timestamp asc
"""

# ---------------------------------------------------------------------------
# Recent Failures -- ERROR-level logs and unhandled exceptions
# ---------------------------------------------------------------------------
# No parameters -- timespan controlled by the query_workspace call.
# AppExceptions rows are always included; AppTraces rows are filtered
# by SeverityLevel >= 3 (warning or higher).

RECENT_FAILURES = """\
union withsource=SourceTable
    (AppTraces | where SeverityLevel >= 3),
    AppExceptions
| project
    timestamp = TimeGenerated,
    ItemType = case(
        SourceTable == "AppTraces", "Log",
        SourceTable == "AppExceptions", "Exception",
        SourceTable
    ),
    severityLevel = SeverityLevel,
    Message = coalesce(OuterMessage, Message, InnermostMessage, ExceptionType),
    OuterMessage,
    OuterType,
    InnermostMessage,
    Details = tostring(Details),
    Component = tostring(Properties.component),
    CaptureTraceId = tostring(Properties.capture_trace_id)
| order by timestamp desc
| take 50
"""

# ---------------------------------------------------------------------------
# System Health -- consolidated summary for programmatic consumption
# ---------------------------------------------------------------------------
# Returns a single row with key metrics. Timespan controlled by the
# query_workspace call.

SYSTEM_HEALTH = """\
let capture_requests = AppRequests
| where Name has "/api/capture";
let capture_count = toscalar(capture_requests | summarize count());
let successful_count = toscalar(
    capture_requests
    | where toint(ResultCode) >= 200 and toint(ResultCode) < 400
    | summarize count()
);
let client_error_count = toscalar(
    capture_requests
    | where toint(ResultCode) >= 400 and toint(ResultCode) < 500
    | summarize count()
);
let server_error_count = toscalar(
    capture_requests
    | where toint(ResultCode) >= 500
    | summarize count()
);
let error_log_count = toscalar(
    AppTraces
    | where SeverityLevel >= 3
    | summarize count()
);
let avg_duration = toscalar(
    capture_requests
    | summarize avg(DurationMs)
);
let admin_count = toscalar(
    AppTraces
    | where tostring(Properties.component) == "admin_agent"
    | summarize count()
);
let last_error_time = toscalar(
    union AppTraces, AppExceptions
    | where SeverityLevel >= 3
    | summarize max(TimeGenerated)
);
print
    capture_count = capture_count,
    successful_count = successful_count,
    client_error_count = client_error_count,
    server_error_count = server_error_count,
    error_log_count = error_log_count,
    avg_duration_ms = avg_duration,
    admin_processing_count = admin_count,
    last_error_time = last_error_time
"""

# ---------------------------------------------------------------------------
# System Health Enhanced -- with P95/P99 latency and trend comparison
# ---------------------------------------------------------------------------
# Parameterised with {time_range} via str.format().
# {time_range} must be a KQL duration literal (e.g., "24h", "7d").
# The execute_kql timespan should be 2x {time_range} to cover both periods.

SYSTEM_HEALTH_ENHANCED = """\
let current_period = AppRequests
| where Name has "/api/capture"
| where TimeGenerated > ago({time_range});
let previous_period = AppRequests
| where Name has "/api/capture"
| where TimeGenerated between (ago(2 * {time_range}) .. ago({time_range}));
let current_stats = current_period
| summarize
    capture_count = count(),
    successful_count = countif(toint(ResultCode) >= 200 and toint(ResultCode) < 400),
    error_count = countif(toint(ResultCode) >= 500),
    avg_duration_ms = avg(DurationMs),
    p95_duration_ms = percentile(DurationMs, 95),
    p99_duration_ms = percentile(DurationMs, 99);
let previous_stats = previous_period
| summarize
    prev_capture_count = count(),
    prev_error_count = countif(toint(ResultCode) >= 500);
let error_log_count = toscalar(
    AppTraces
    | where TimeGenerated > ago({time_range})
    | where SeverityLevel >= 3
    | summarize count()
);
let admin_count = toscalar(
    AppTraces
    | where TimeGenerated > ago({time_range})
    | where tostring(Properties.component) == "admin_agent"
    | summarize count()
);
current_stats
| extend prev_capture_count = toscalar(previous_stats | project prev_capture_count)
| extend prev_error_count = toscalar(previous_stats | project prev_error_count)
| extend error_log_count = error_log_count
| extend admin_processing_count = admin_count
"""

# ---------------------------------------------------------------------------
# Recent Failures Filtered -- with component filter, severity, and limit
# ---------------------------------------------------------------------------
# Parameterised with {component_filter}, {severity_filter}, {limit}
# via str.format().
#
# Returns TWO tables:
#   table 0: single row [{total_count: int}] -- total filtered rows BEFORE
#            the take N cap
#   table 1: up to {limit} failure rows
#
# The Python parser in queries.py depends on this exact order. The
# multi-statement form lets the agent report "showing N of M" when
# results are capped, instead of silently dropping rows past the limit.
#
# {component_filter} should be empty string for no filter, or a line like:
#   | where tostring(Properties.component) == "component_name"
# {severity_filter} is a KQL severity level int (Azure scale:
#   2=Warning, 3=Error, 4=Critical). Applied to BOTH AppTraces AND
#   AppExceptions so handled exceptions logged at Warning level are
#   excluded from "errors" results.
# {limit} is the row limit (default 10).

RECENT_FAILURES_FILTERED = """\
let filtered = union withsource=SourceTable
    (AppTraces | where SeverityLevel >= {severity_filter}),
    (AppExceptions | where SeverityLevel >= {severity_filter})
{component_filter}| project
    timestamp = TimeGenerated,
    ItemType = case(
        SourceTable == "AppTraces", "Log",
        SourceTable == "AppExceptions", "Exception",
        SourceTable
    ),
    severityLevel = SeverityLevel,
    Message = coalesce(OuterMessage, Message, InnermostMessage, ExceptionType),
    OuterMessage,
    OuterType,
    InnermostMessage,
    Details = tostring(Details),
    Component = tostring(Properties.component),
    CaptureTraceId = tostring(Properties.capture_trace_id);
filtered | summarize total_count = count();
filtered | order by timestamp desc | take {limit};
"""

# ---------------------------------------------------------------------------
# Latest Capture Trace ID -- find the most recent capture trace ID
# ---------------------------------------------------------------------------
# No parameters -- timespan controlled by the query_workspace call.

LATEST_CAPTURE_TRACE_ID = """\
AppTraces
| where isnotempty(tostring(Properties.capture_trace_id))
| extend trace_id = tostring(Properties.capture_trace_id)
| summarize timestamp = min(TimeGenerated) by trace_id
| top 1 by timestamp desc
| project trace_id, timestamp
"""

# ---------------------------------------------------------------------------
# Usage Patterns -- captures by time period
# ---------------------------------------------------------------------------
# Parameterised with {bin_size} via str.format().
# {bin_size} must be a KQL duration literal (e.g., "1h", "1d").

USAGE_PATTERNS_BY_PERIOD = """\
AppRequests
| where Name has "/api/capture"
| summarize capture_count = count() by timestamp = bin(TimeGenerated, {bin_size})
| order by timestamp asc
"""

# ---------------------------------------------------------------------------
# Usage Patterns -- bucket distribution from classifier
# ---------------------------------------------------------------------------
# No parameters -- timespan controlled by the query_workspace call.

USAGE_PATTERNS_BY_BUCKET = """\
AppTraces
| where tostring(Properties.component) == "classifier"
| where Message has "Filed to"
| extend bucket = extract("Filed to (\\\\w+)", 1, Message)
| where isnotempty(bucket)
| summarize count_ = count() by bucket
| order by count_ desc
"""

# ---------------------------------------------------------------------------
# Usage Patterns -- destination usage from admin agent
# ---------------------------------------------------------------------------
# No parameters -- timespan controlled by the query_workspace call.

USAGE_PATTERNS_BY_DESTINATION = """\
AppTraces
| where tostring(Properties.component) == "admin_agent"
| where Message has "Added"
| extend destination = extract("to ([\\\\w-]+)", 1, Message)
| where isnotempty(destination)
| summarize count_ = count() by destination
| order by count_ desc
"""

# ---------------------------------------------------------------------------
# Admin Audit -- activity log (all admin_agent / admin_handoff entries)
# ---------------------------------------------------------------------------

ADMIN_AUDIT_LOG = """\
AppTraces
| where tostring(Properties.component) == "admin_agent"
    or tostring(Properties.component) == "admin_handoff"
| project
    timestamp = TimeGenerated,
    severityLevel = SeverityLevel,
    Message,
    CaptureTraceId = tostring(Properties.capture_trace_id),
    Component = tostring(Properties.component)
| order by timestamp desc
"""

# ---------------------------------------------------------------------------
# Admin Audit -- per-capture processing summary
# ---------------------------------------------------------------------------

ADMIN_AUDIT_SUMMARY = """\
AppTraces
| where tostring(Properties.component) in ("admin_agent", "admin_handoff")
| where isnotempty(tostring(Properties.capture_trace_id))
| summarize
    StartTime = min(TimeGenerated),
    EndTime = max(TimeGenerated),
    LogCount = count(),
    Errors = countif(SeverityLevel >= 3),
    HasErrandCreation = countif(
        Message has "add_errand_items"
        or Message has "errand"
        or Message has "shopping"
    )
    by CaptureTraceId = tostring(Properties.capture_trace_id)
| extend DurationSeconds = datetime_diff('second', EndTime, StartTime)
| order by StartTime desc
"""

# ---------------------------------------------------------------------------
# Backend API Requests -- AppRequests rows for the backend_api segment
# ---------------------------------------------------------------------------
# Parameterised with {capture_trace_filter} via str.format().
# {capture_trace_filter} is either "" (no filter) or a line like:
#   | where tostring(Properties.capture_trace_id) == "trace-id-here"
# Timespan controlled by the query_workspace call.

BACKEND_API_REQUESTS = """\
AppRequests
{capture_trace_filter}| project
    timestamp = TimeGenerated,
    Name,
    ResultCode,
    DurationMs,
    Success,
    CaptureTraceId = tostring(Properties.capture_trace_id),
    OperationId = tostring(OperationId)
| order by timestamp desc
| take 200
"""


# ---------------------------------------------------------------------------
# Backend API Failures -- AppExceptions + severity>=3 AppTraces,
# optionally filtered to a single capture trace
# ---------------------------------------------------------------------------
# Parameterised with {capture_trace_filter} via str.format().
# Timespan controlled by the query_workspace call.

# ---------------------------------------------------------------------------
# Agent Runs by agent_id (Phase 2: Foundry-agent adapter)
# ---------------------------------------------------------------------------
# Returns recent agent_run spans with optional capture_trace_id and thread_id
# filters. {agent_filter}, {capture_filter}, {thread_filter} are KQL conjuncts.
# {limit} is the row limit (default 20).

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


BACKEND_API_FAILURES = """\
union withsource=SourceTable
    (AppTraces | where SeverityLevel >= 3),
    AppExceptions
{capture_trace_filter}| project
    timestamp = TimeGenerated,
    ItemType = case(
        SourceTable == "AppTraces", "Log",
        SourceTable == "AppExceptions", "Exception",
        SourceTable
    ),
    severityLevel = SeverityLevel,
    Message = coalesce(Message, ExceptionType),
    Component = tostring(Properties.component),
    CaptureTraceId = tostring(Properties.capture_trace_id),
    OuterType = tostring(Properties.outer_type),
    OuterMessage = tostring(Properties.outer_message),
    InnermostMessage = tostring(Properties.innermost_message),
    Details = tostring(Properties.details)
| order by timestamp desc
| take 200
"""

# ---------------------------------------------------------------------------
# Cosmos diagnostic logs (Phase 3: cosmos adapter)
# ---------------------------------------------------------------------------
# Returns recent Cosmos operations from Azure Monitor diagnostic logs.
# Diagnostic logs flow with 5-10 minute lag.
#
# Data lands in AzureDiagnostics (Azure diagnostics mode), NOT the
# resource-specific CDBDataPlaneRequests table. Column names use
# _s (string), _d (double), _g (GUID) suffixes.
#
# NOTE: activityId_g is the Cosmos SERVER-SIDE activity ID (a UUID),
# NOT the x-ms-client-request-id set by trace_headers(). For
# capture-correlated Cosmos queries, use COSMOS_BY_CAPTURE_TRACE
# which queries AppDependencies where CaptureTraceSpanProcessor
# injects the capture.trace_id attribute.
#
# {capture_filter} is optional -- empty string for no filter.
# {limit} is row limit.

COSMOS_DIAGNOSTIC_LOGS = """\
AzureDiagnostics
| where Category == "DataPlaneRequests"
{capture_filter}| project
    timestamp = TimeGenerated,
    operation_name = OperationName,
    status_code = toint(statusCode_s),
    duration_ms = todouble(duration_s),
    request_charge = todouble(requestCharge_s),
    request_length = todouble(requestLength_s),
    response_length = todouble(responseLength_s),
    client_request_id = tostring(activityId_g),
    collection_name = collectionName_s
| order by timestamp desc
| take {limit}
"""

# ---------------------------------------------------------------------------
# Cosmos operations by capture_trace_id (Phase 19.4: correlation tagging)
# ---------------------------------------------------------------------------
# Returns Cosmos SDK spans from AppDependencies, correlated by
# capture.trace_id injected by CaptureTraceSpanProcessor.
# This is the PRIMARY path for capture-correlated Cosmos queries --
# more reliable than AzureDiagnostics because activityId_g does NOT
# contain the client-provided trace ID.
#
# Parameterised with {capture_trace_id} and {limit} via str.format().

COSMOS_BY_CAPTURE_TRACE = """\
AppDependencies
| where Name startswith "ContainerProxy"
    or Name startswith "POST /dbs"
    or Name startswith "GET /dbs"
| where tostring(Properties.["capture.trace_id"])
    == "{capture_trace_id}"
| project
    timestamp = TimeGenerated,
    operation_name = Name,
    duration_ms = DurationMs,
    success = Success,
    result_code = ResultCode,
    capture_trace_id = tostring(Properties.["capture.trace_id"]),
    collection_name = tostring(Properties.db_cosmosdb_container)
| order by timestamp desc
| take {limit}
"""


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
