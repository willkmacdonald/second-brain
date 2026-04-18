"""Verify KQL templates project the new AppExceptions native fields.

Phase 19.1 absorption: surface OuterMessage, OuterType, InnermostMessage,
and tostring(Details) instead of dropping them in coalesce(Message, ExceptionType).
"""

from second_brain.observability.kql_templates import (
    AGENT_RUNS,
    CAPTURE_TRACE,
    RECENT_FAILURES,
    RECENT_FAILURES_FILTERED,
)


def test_capture_trace_projects_outer_message() -> None:
    assert "OuterMessage" in CAPTURE_TRACE


def test_capture_trace_projects_outer_type() -> None:
    assert "OuterType" in CAPTURE_TRACE


def test_capture_trace_projects_innermost_message() -> None:
    assert "InnermostMessage" in CAPTURE_TRACE


def test_capture_trace_uses_tostring_for_details() -> None:
    assert "tostring(Details)" in CAPTURE_TRACE


def test_recent_failures_projects_new_fields() -> None:
    assert "OuterMessage" in RECENT_FAILURES
    assert "OuterType" in RECENT_FAILURES
    assert "InnermostMessage" in RECENT_FAILURES
    assert "tostring(Details)" in RECENT_FAILURES


def test_recent_failures_filtered_projects_new_fields() -> None:
    assert "OuterMessage" in RECENT_FAILURES_FILTERED
    assert "OuterType" in RECENT_FAILURES_FILTERED
    assert "InnermostMessage" in RECENT_FAILURES_FILTERED
    assert "tostring(Details)" in RECENT_FAILURES_FILTERED


def test_message_coalesce_elevates_outer_message_first() -> None:
    """coalesce ordering puts OuterMessage first so AppExceptions get rich detail."""
    for tpl in (CAPTURE_TRACE, RECENT_FAILURES, RECENT_FAILURES_FILTERED):
        assert "coalesce(OuterMessage, Message" in tpl


def test_no_resultcode_projection_on_appexceptions() -> None:
    """AppExceptions has no ResultCode column — must not project it."""
    for tpl in (CAPTURE_TRACE, RECENT_FAILURES, RECENT_FAILURES_FILTERED):
        # Specifically: no bare 'ResultCode,' or 'ResultCode\n' in projection list
        # (the existing AppRequests projection on CAPTURE_TRACE is fine)
        lines = tpl.split("\n")
        for line in lines:
            stripped = line.strip()
            # Allow ResultCode in the AppRequests projection block; reject when
            # it appears alongside the new AppExceptions fields.
            if "OuterMessage" in stripped and "ResultCode" in stripped:
                raise AssertionError(
                    "ResultCode must not project alongside "
                    f"AppExceptions fields: {stripped}"
                )


def test_agent_runs_template_filters_compose() -> None:
    rendered = AGENT_RUNS.format(
        agent_filter='| where tostring(Properties.agent_id) == "asst_1"',
        capture_filter="",
        thread_filter='| where tostring(Properties.foundry_thread_id) == "thr-1"',
        limit=20,
    )
    assert "asst_1" in rendered
    assert "thr-1" in rendered
    assert "Properties.foundry_thread_id" in rendered


def test_cosmos_diagnostic_logs_template_filters_compose() -> None:
    from second_brain.observability.kql_templates import COSMOS_DIAGNOSTIC_LOGS

    rendered = COSMOS_DIAGNOSTIC_LOGS.format(
        capture_filter='| where ActivityId == "trace-1"\n',
        limit=50,
    )
    assert "trace-1" in rendered
    assert "CDBDataPlaneRequests" in rendered


def test_cosmos_diagnostic_logs_template_no_filter() -> None:
    from second_brain.observability.kql_templates import COSMOS_DIAGNOSTIC_LOGS

    rendered = COSMOS_DIAGNOSTIC_LOGS.format(capture_filter="", limit=25)
    assert "CDBDataPlaneRequests" in rendered
    assert "take 25" in rendered
    assert "| where ActivityId ==" not in rendered
