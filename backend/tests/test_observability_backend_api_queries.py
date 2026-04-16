"""Unit tests for backend_api detail query primitives (Task 11.5).

Covers query_backend_api_requests() and query_backend_api_failures().
All tests monkeypatch execute_kql to avoid hitting Log Analytics.
The mocking pattern follows test_investigation_queries.py: patch execute_kql
and return a QueryResult directly.
"""

from unittest.mock import AsyncMock, patch

import pytest

from second_brain.observability import queries
from second_brain.observability.models import FailureRecord, QueryResult, RequestRecord

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request_rows(count: int = 2) -> list[dict]:
    return [
        {
            "timestamp": f"2026-04-15T12:00:0{i}Z",
            "Name": "POST /api/capture/text",
            "ResultCode": "200",
            "DurationMs": 42.0 + i,
            "Success": True,
            "CaptureTraceId": f"trace-{i}",
            "OperationId": f"op-{i}",
        }
        for i in range(count)
    ]


def _make_failure_rows(count: int = 2) -> list[dict]:
    return [
        {
            "timestamp": f"2026-04-15T12:00:0{i}Z",
            "ItemType": "Log" if i % 2 == 0 else "Exception",
            "severityLevel": 3,
            "Message": f"error message {i}",
            "Component": "classifier",
            "CaptureTraceId": f"trace-{i}",
        }
        for i in range(count)
    ]


# ---------------------------------------------------------------------------
# query_backend_api_requests
# ---------------------------------------------------------------------------


class TestQueryBackendApiRequests:
    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        return AsyncMock()

    async def test_no_filter_query_contains_apprequests_and_no_trace_filter(
        self, mock_client: AsyncMock
    ) -> None:
        """No trace ID: KQL has AppRequests but no | where filter line.

        Note: the project clause always contains 'capture_trace_id' as a
        column alias — absence check targets the | where filter specifically.
        """
        captured_query: list[str] = []

        async def _fake_execute_kql(client, workspace_id, query, **kwargs):
            captured_query.append(query)
            return QueryResult(tables=[_make_request_rows(2)])

        with patch.object(queries, "execute_kql", side_effect=_fake_execute_kql):
            result = await queries.query_backend_api_requests(mock_client, "ws-id")

        assert len(result) == 2
        assert all(isinstance(r, RequestRecord) for r in result)
        kql = captured_query[0]
        assert "AppRequests" in kql
        # The WHERE filter line must not be present when no trace ID is given.
        # The project clause contains 'capture_trace_id' as a column alias —
        # we check for the absence of the | where filter form specifically.
        assert "| where tostring(Properties.capture_trace_id)" not in kql

    async def test_with_trace_id_includes_filter_line(
        self, mock_client: AsyncMock
    ) -> None:
        """With capture_trace_id, the KQL includes a | where filter with ID quoted."""
        captured_query: list[str] = []

        async def _fake_execute_kql(client, workspace_id, query, **kwargs):
            captured_query.append(query)
            return QueryResult(tables=[_make_request_rows(1)])

        with patch.object(queries, "execute_kql", side_effect=_fake_execute_kql):
            result = await queries.query_backend_api_requests(
                mock_client, "ws-id", capture_trace_id="abc-123"
            )

        assert len(result) == 1
        kql = captured_query[0]
        # The trace ID must appear exactly once and be quoted
        assert kql.count('"abc-123"') == 1
        assert "capture_trace_id" in kql

    async def test_invalid_trace_id_raises_value_error(
        self, mock_client: AsyncMock
    ) -> None:
        """Trace IDs with unsafe characters raise ValueError before querying."""
        with pytest.raises(ValueError, match="Invalid capture_trace_id"):
            await queries.query_backend_api_requests(
                mock_client, "ws-id", capture_trace_id="x; drop table y"
            )

    async def test_trailing_newline_rejected_by_fullmatch(
        self, mock_client: AsyncMock
    ) -> None:
        """Guard uses re.fullmatch so a trailing \\n does not slip past $."""
        with pytest.raises(ValueError, match="Invalid capture_trace_id"):
            await queries.query_backend_api_requests(
                mock_client, "ws-id", capture_trace_id="abc-123\n"
            )

    async def test_returns_typed_request_records(self, mock_client: AsyncMock) -> None:
        """Rows are parsed into RequestRecord with correct field mapping."""
        rows = [
            {
                "timestamp": "2026-04-15T12:00:00Z",
                "Name": "POST /api/capture/text",
                "ResultCode": "201",
                "DurationMs": 55.5,
                "Success": True,
                "CaptureTraceId": "abc-123",
                "OperationId": "op-xyz",
            }
        ]
        with patch.object(
            queries,
            "execute_kql",
            AsyncMock(return_value=QueryResult(tables=[rows])),
        ):
            result = await queries.query_backend_api_requests(mock_client, "ws-id")

        assert len(result) == 1
        rec = result[0]
        assert rec.name == "POST /api/capture/text"
        assert rec.result_code == "201"
        assert rec.duration_ms == 55.5
        assert rec.success is True
        assert rec.capture_trace_id == "abc-123"
        assert rec.operation_id == "op-xyz"

    async def test_empty_result_returns_empty_list(
        self, mock_client: AsyncMock
    ) -> None:
        """Empty KQL result table returns []."""
        with patch.object(
            queries,
            "execute_kql",
            AsyncMock(return_value=QueryResult(tables=[])),
        ):
            result = await queries.query_backend_api_requests(mock_client, "ws-id")

        assert result == []

    async def test_time_range_seconds_forwarded_as_timedelta(
        self, mock_client: AsyncMock
    ) -> None:
        """time_range_seconds is converted to a timedelta for execute_kql."""
        from datetime import timedelta

        captured_kwargs: list[dict] = []

        async def _fake_execute_kql(client, workspace_id, query, **kwargs):
            captured_kwargs.append(kwargs)
            return QueryResult(tables=[])

        with patch.object(queries, "execute_kql", side_effect=_fake_execute_kql):
            await queries.query_backend_api_requests(
                mock_client, "ws-id", time_range_seconds=7200
            )

        assert captured_kwargs[0]["timespan"] == timedelta(seconds=7200)


# ---------------------------------------------------------------------------
# query_backend_api_failures
# ---------------------------------------------------------------------------


class TestQueryBackendApiFailures:
    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        return AsyncMock()

    async def test_no_filter_returns_failure_records(
        self, mock_client: AsyncMock
    ) -> None:
        """No trace ID: returns FailureRecord objects from both ItemTypes."""
        rows = _make_failure_rows(2)
        with patch.object(
            queries,
            "execute_kql",
            AsyncMock(return_value=QueryResult(tables=[rows])),
        ):
            result = await queries.query_backend_api_failures(mock_client, "ws-id")

        assert len(result) == 2
        assert all(isinstance(r, FailureRecord) for r in result)
        # ItemTypes alternate between Log and Exception
        assert result[0].item_type == "Log"
        assert result[1].item_type == "Exception"

    async def test_with_trace_id_includes_filter_line(
        self, mock_client: AsyncMock
    ) -> None:
        """With capture_trace_id, the KQL includes a | where filter with ID quoted."""
        captured_query: list[str] = []

        async def _fake_execute_kql(client, workspace_id, query, **kwargs):
            captured_query.append(query)
            return QueryResult(tables=[_make_failure_rows(1)])

        with patch.object(queries, "execute_kql", side_effect=_fake_execute_kql):
            await queries.query_backend_api_failures(
                mock_client, "ws-id", capture_trace_id="abc-123"
            )

        kql = captured_query[0]
        assert kql.count('"abc-123"') == 1
        assert "capture_trace_id" in kql

    async def test_invalid_trace_id_raises_value_error(
        self, mock_client: AsyncMock
    ) -> None:
        """Trace IDs with unsafe characters raise ValueError before querying."""
        with pytest.raises(ValueError, match="Invalid capture_trace_id"):
            await queries.query_backend_api_failures(
                mock_client, "ws-id", capture_trace_id="x; drop table y"
            )

    async def test_trailing_newline_rejected_by_fullmatch(
        self, mock_client: AsyncMock
    ) -> None:
        """Guard uses re.fullmatch so a trailing \\n does not slip past $."""
        with pytest.raises(ValueError, match="Invalid capture_trace_id"):
            await queries.query_backend_api_failures(
                mock_client, "ws-id", capture_trace_id="abc-123\n"
            )

    async def test_empty_result_returns_empty_list(
        self, mock_client: AsyncMock
    ) -> None:
        """Empty KQL result table returns []."""
        with patch.object(
            queries,
            "execute_kql",
            AsyncMock(return_value=QueryResult(tables=[])),
        ):
            result = await queries.query_backend_api_failures(mock_client, "ws-id")

        assert result == []

    async def test_field_mapping_is_correct(self, mock_client: AsyncMock) -> None:
        """FailureRecord fields map correctly from KQL column names."""
        rows = [
            {
                "timestamp": "2026-04-15T12:00:00Z",
                "ItemType": "Exception",
                "severityLevel": 4,
                "Message": "Unhandled exception",
                "Component": "admin_agent",
                "CaptureTraceId": "trace-xyz",
            }
        ]
        with patch.object(
            queries,
            "execute_kql",
            AsyncMock(return_value=QueryResult(tables=[rows])),
        ):
            result = await queries.query_backend_api_failures(mock_client, "ws-id")

        assert len(result) == 1
        rec = result[0]
        assert rec.item_type == "Exception"
        assert rec.severity_level == 4
        assert rec.message == "Unhandled exception"
        assert rec.component == "admin_agent"
        assert rec.capture_trace_id == "trace-xyz"
        # Enrichment fields absent from this minimal test row default to None.
        # See test_enrichment_fields_survive_when_kql_provides_them for the
        # positive assertion that these fields ARE read when present.
        assert rec.outer_type is None
        assert rec.outer_message is None
        assert rec.innermost_message is None
        assert rec.details is None

    async def test_enrichment_fields_survive_when_kql_provides_them(
        self, mock_client: AsyncMock
    ) -> None:
        """OuterMessage/OuterType/InnermostMessage/Details from KQL reach FailureRecord.

        The BACKEND_API_FAILURES KQL template projects all four enrichment
        columns. The Python constructor MUST read them — without this, the
        Task 16 AppInsightsDetail renderer's "Inner cause" and "Stack details"
        expandable sections are permanently empty on production data.
        Regression guard for the Task 11.5 mapping omission discovered during
        Phase 1 Task 16 pre-dispatch review.
        """
        rows = [
            {
                "timestamp": "2026-04-15T12:00:00Z",
                "ItemType": "Exception",
                "severityLevel": 4,
                "Message": "ValidationError",
                "Component": "capture_pipeline",
                "CaptureTraceId": "trace-enrich",
                "OuterType": "pydantic.ValidationError",
                "OuterMessage": "1 validation error for CaptureRequest",
                "InnermostMessage": "field required: text",
                "Details": "Traceback (most recent call last):\n  File ...",
            }
        ]
        with patch.object(
            queries,
            "execute_kql",
            AsyncMock(return_value=QueryResult(tables=[rows])),
        ):
            result = await queries.query_backend_api_failures(mock_client, "ws-id")

        assert len(result) == 1
        rec = result[0]
        assert rec.outer_type == "pydantic.ValidationError"
        assert rec.outer_message == "1 validation error for CaptureRequest"
        assert rec.innermost_message == "field required: text"
        assert rec.details == "Traceback (most recent call last):\n  File ..."

    async def test_empty_capture_trace_id_normalized_to_none(
        self, mock_client: AsyncMock
    ) -> None:
        """Empty string CaptureTraceId from KQL is normalized to None by validator."""
        rows = [
            {
                "timestamp": "2026-04-15T12:00:00Z",
                "ItemType": "Log",
                "severityLevel": 3,
                "Message": "some error",
                "Component": "",
                "CaptureTraceId": "",
            }
        ]
        with patch.object(
            queries,
            "execute_kql",
            AsyncMock(return_value=QueryResult(tables=[rows])),
        ):
            result = await queries.query_backend_api_failures(mock_client, "ws-id")

        rec = result[0]
        assert rec.capture_trace_id is None
        assert rec.component is None
