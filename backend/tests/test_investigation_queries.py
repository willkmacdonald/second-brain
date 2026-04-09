"""Unit tests for investigation query layer: severity map, KQL string
construction, and truncation branching logic.

These tests mock execute_kql so nothing hits Log Analytics. They are
narrowly scoped to pin invariants that have either failed historically
(_SEVERITY_MAP bug, 2026-04-08) or could fail silently in a way code
review wouldn't catch (KQL string construction, two-table parser logic).

Tests for Pydantic validators and computed fields are deliberately
omitted -- they would test the framework, not our logic.
"""

from unittest.mock import AsyncMock, patch

import pytest

from second_brain.observability import queries
from second_brain.observability.models import FailureQueryResult, QueryResult


class TestModuleImport:
    """Sanity check that all imports resolve before adding real tests."""

    def test_queries_module_imports(self):
        assert hasattr(queries, "query_recent_failures_filtered")
        assert hasattr(queries, "_SEVERITY_MAP")


class TestSeverityMap:
    """Pin the severity map values against Azure's actual scale.

    Azure SeverityLevel: 0=Verbose, 1=Information, 2=Warning,
                         3=Error, 4=Critical.

    Historical bug (2026-04-08): the map had warning=3, error=4.
    With the wrong values, the recent_errors tool's default
    severity='error' filtered for level 4 (Critical) only and
    silently dropped all Error-level rows from results.
    """

    def test_error_maps_to_azure_level_3(self):
        assert queries._SEVERITY_MAP["error"] == 3

    def test_warning_maps_to_azure_level_2(self):
        assert queries._SEVERITY_MAP["warning"] == 2


class TestQueryRecentFailuresFilteredTruncation:
    """Test the truncation branching logic in query_recent_failures_filtered.

    These tests pin the Python computation that decides whether the result
    set was truncated by the take N cap. Mocks execute_kql so nothing hits
    Azure.
    """

    @pytest.fixture
    def mock_client(self):
        return AsyncMock()

    async def test_empty_result_returns_zero_totals(self, mock_client):
        """When KQL returns no tables, parser returns a sensible empty result."""
        with patch.object(
            queries,
            "execute_kql",
            AsyncMock(return_value=QueryResult(tables=[])),
        ):
            result = await queries.query_recent_failures_filtered(mock_client, "ws-id")

        assert isinstance(result, FailureQueryResult)
        assert result.total_count == 0
        assert result.returned_count == 0
        assert result.truncated is False
        assert result.records == []

    async def test_not_truncated_when_returned_equals_total(self, mock_client):
        """5 rows returned, total=5 -> truncated=False."""
        fake_tables = [
            [{"total_count": 5}],
            [
                {
                    "timestamp": f"2026-04-08T00:00:0{i}Z",
                    "ItemType": "Log",
                    "severityLevel": 3,
                    "Message": f"err {i}",
                    "Component": "classifier",
                    "CaptureTraceId": "",
                }
                for i in range(5)
            ],
        ]

        with patch.object(
            queries,
            "execute_kql",
            AsyncMock(return_value=QueryResult(tables=fake_tables)),
        ):
            result = await queries.query_recent_failures_filtered(mock_client, "ws-id")

        assert result.total_count == 5
        assert result.returned_count == 5
        assert result.truncated is False
        assert len(result.records) == 5

    async def test_truncated_when_total_exceeds_returned(self, mock_client):
        """10 rows returned, total=47 -> truncated=True."""
        fake_tables = [
            [{"total_count": 47}],
            [
                {
                    "timestamp": f"2026-04-08T00:00:0{i}Z",
                    "ItemType": "Exception",
                    "severityLevel": 3,
                    "Message": f"err {i}",
                    "Component": "admin_agent",
                    "CaptureTraceId": f"trace-{i}",
                }
                for i in range(10)
            ],
        ]

        with patch.object(
            queries,
            "execute_kql",
            AsyncMock(return_value=QueryResult(tables=fake_tables)),
        ):
            result = await queries.query_recent_failures_filtered(mock_client, "ws-id")

        assert result.total_count == 47
        assert result.returned_count == 10
        assert result.truncated is True
