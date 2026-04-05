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
