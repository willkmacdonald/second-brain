"""Workspace-compatible KQL query templates for Log Analytics.

All templates use the workspace schema (traces, requests, dependencies,
exceptions) rather than the portal schema (AppTraces, AppRequests, etc.).

Field mapping applied during migration:
  Portal              -> Workspace
  AppTraces            -> traces
  AppRequests          -> requests
  AppDependencies      -> dependencies
  AppExceptions        -> exceptions
  TimeGenerated        -> timestamp
  SeverityLevel        -> severityLevel
  Message (capital)    -> message (lowercase)
"""

# ---------------------------------------------------------------------------
# Capture Trace -- traces a single capture through its full lifecycle
# ---------------------------------------------------------------------------
# Parameterised with {trace_id} via str.format().

CAPTURE_TRACE = """\
let trace_id = "{trace_id}";
union traces, dependencies, requests, exceptions
| where customDimensions.capture_trace_id == trace_id
    or customDimensions["capture_trace_id"] == trace_id
| project
    timestamp,
    ItemType = case(
        itemType == "trace", "Log",
        itemType == "dependency", "Dependency",
        itemType == "request", "Request",
        itemType == "exception", "Exception",
        itemType
    ),
    severityLevel,
    Message = coalesce(message, name, type),
    Component = tostring(customDimensions.component),
    CaptureTraceId = tostring(customDimensions.capture_trace_id)
| order by timestamp asc
"""

# ---------------------------------------------------------------------------
# Recent Failures -- ERROR-level logs and unhandled exceptions (last 24h)
# ---------------------------------------------------------------------------
# No parameters -- timespan controlled by the query_workspace call.

RECENT_FAILURES = """\
union traces, exceptions
| where severityLevel >= 3
    or itemType == "exception"
| project
    timestamp,
    ItemType = case(
        itemType == "trace", "Log",
        itemType == "exception", "Exception",
        itemType
    ),
    severityLevel,
    Message = coalesce(message, type),
    Component = tostring(customDimensions.component),
    CaptureTraceId = tostring(customDimensions.capture_trace_id)
| order by timestamp desc
| take 50
"""

# ---------------------------------------------------------------------------
# System Health -- consolidated summary for programmatic consumption
# ---------------------------------------------------------------------------
# Returns a single row with key metrics.  The portal version had five
# separate sections; this consolidates them into one query.

SYSTEM_HEALTH = """\
let capture_requests = requests
| where name has "/api/capture";
let capture_count = toscalar(capture_requests | summarize count());
let successful_count = toscalar(
    capture_requests
    | where toint(resultCode) >= 200 and toint(resultCode) < 400
    | summarize count()
);
let client_error_count = toscalar(
    capture_requests
    | where toint(resultCode) >= 400 and toint(resultCode) < 500
    | summarize count()
);
let server_error_count = toscalar(
    capture_requests
    | where toint(resultCode) >= 500
    | summarize count()
);
let error_log_count = toscalar(
    traces
    | where severityLevel >= 3
    | summarize count()
);
let avg_duration = toscalar(
    capture_requests
    | summarize avg(duration)
);
let admin_count = toscalar(
    traces
    | where customDimensions.component == "admin_agent"
    | summarize count()
);
print
    capture_count = capture_count,
    successful_count = successful_count,
    client_error_count = client_error_count,
    server_error_count = server_error_count,
    error_log_count = error_log_count,
    avg_duration_ms = avg_duration,
    admin_processing_count = admin_count
"""

# ---------------------------------------------------------------------------
# System Health Enhanced -- with P95/P99 latency and trend comparison
# ---------------------------------------------------------------------------
# Parameterised with {time_range} via str.format().
# {time_range} must be a KQL duration literal (e.g., "24h", "7d").
# The execute_kql timespan should be 2x {time_range} to cover both periods.

SYSTEM_HEALTH_ENHANCED = """\
let current_period = requests
| where name has "/api/capture"
| where timestamp > ago({time_range});
let previous_period = requests
| where name has "/api/capture"
| where timestamp between (ago(2 * {time_range}) .. ago({time_range}));
let current_stats = current_period
| summarize
    capture_count = count(),
    successful_count = countif(toint(resultCode) >= 200 and toint(resultCode) < 400),
    error_count = countif(toint(resultCode) >= 500),
    avg_duration_ms = avg(duration),
    p95_duration_ms = percentile(duration, 95),
    p99_duration_ms = percentile(duration, 99);
let previous_stats = previous_period
| summarize
    prev_capture_count = count(),
    prev_error_count = countif(toint(resultCode) >= 500);
let error_log_count = toscalar(
    traces
    | where timestamp > ago({time_range})
    | where severityLevel >= 3
    | summarize count()
);
let admin_count = toscalar(
    traces
    | where timestamp > ago({time_range})
    | where customDimensions.component == "admin_agent"
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
# {component_filter} should be empty string for no filter, or:
#   | where tostring(customDimensions.component) == "component_name"
# {severity_filter} is a KQL severity level int (3=warning, 4=error)
# {limit} is the row limit (default 10)

RECENT_FAILURES_FILTERED = """\
union traces, exceptions
| where severityLevel >= {severity_filter}
    or itemType == "exception"
{component_filter}\
| project
    timestamp,
    ItemType = case(
        itemType == "trace", "Log",
        itemType == "exception", "Exception",
        itemType
    ),
    severityLevel,
    Message = coalesce(message, type),
    Component = tostring(customDimensions.component),
    CaptureTraceId = tostring(customDimensions.capture_trace_id)
| order by timestamp desc
| take {limit}
"""

# ---------------------------------------------------------------------------
# Latest Capture Trace ID -- find the most recent capture trace ID
# ---------------------------------------------------------------------------
# No parameters -- timespan controlled by the query_workspace call.

LATEST_CAPTURE_TRACE_ID = """\
requests
| where name has "/api/capture"
| where toint(resultCode) >= 200 and toint(resultCode) < 400
| top 1 by timestamp desc
| extend trace_id = tostring(customDimensions.capture_trace_id)
| project trace_id, timestamp
"""

# ---------------------------------------------------------------------------
# Usage Patterns -- captures by time period
# ---------------------------------------------------------------------------
# Parameterised with {bin_size} via str.format().
# {bin_size} must be a KQL duration literal (e.g., "1h", "1d").

USAGE_PATTERNS_BY_PERIOD = """\
requests
| where name has "/api/capture"
| summarize capture_count = count() by bin(timestamp, {bin_size})
| order by timestamp asc
"""

# ---------------------------------------------------------------------------
# Usage Patterns -- bucket distribution from classifier
# ---------------------------------------------------------------------------
# No parameters -- timespan controlled by the query_workspace call.

USAGE_PATTERNS_BY_BUCKET = """\
traces
| where customDimensions.component == "classifier"
| where message has "Filed to"
| extend bucket = extract("Filed to (\\\\w+)", 1, message)
| where isnotempty(bucket)
| summarize count_ = count() by bucket
| order by count_ desc
"""

# ---------------------------------------------------------------------------
# Usage Patterns -- destination usage from admin agent
# ---------------------------------------------------------------------------
# No parameters -- timespan controlled by the query_workspace call.

USAGE_PATTERNS_BY_DESTINATION = """\
traces
| where customDimensions.component == "admin_agent"
| where message has "Added"
| extend destination = extract("to ([\\\\w-]+)", 1, message)
| where isnotempty(destination)
| summarize count_ = count() by destination
| order by count_ desc
"""

# ---------------------------------------------------------------------------
# Admin Audit -- activity log (all admin_agent / admin_handoff entries)
# ---------------------------------------------------------------------------

ADMIN_AUDIT_LOG = """\
traces
| where customDimensions.component == "admin_agent"
    or customDimensions.component == "admin_handoff"
| project
    timestamp,
    severityLevel,
    Message = message,
    CaptureTraceId = tostring(customDimensions.capture_trace_id),
    Component = tostring(customDimensions.component)
| order by timestamp desc
"""

# ---------------------------------------------------------------------------
# Admin Audit -- per-capture processing summary
# ---------------------------------------------------------------------------

ADMIN_AUDIT_SUMMARY = """\
traces
| where customDimensions.component in ("admin_agent", "admin_handoff")
| where isnotempty(customDimensions.capture_trace_id)
| summarize
    StartTime = min(timestamp),
    EndTime = max(timestamp),
    LogCount = count(),
    Errors = countif(severityLevel >= 3),
    HasErrandCreation = countif(
        message has "add_errand_items"
        or message has "errand"
        or message has "shopping"
    )
    by CaptureTraceId = tostring(customDimensions.capture_trace_id)
| extend DurationSeconds = datetime_diff('second', EndTime, StartTime)
| order by StartTime desc
"""
