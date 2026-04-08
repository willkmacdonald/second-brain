"""Unit tests for investigation query layer: severity map, KQL string
construction, and truncation branching logic.

These tests mock execute_kql so nothing hits Log Analytics. They are
narrowly scoped to pin invariants that have either failed historically
(_SEVERITY_MAP bug, 2026-04-08) or could fail silently in a way code
review wouldn't catch (KQL string construction, two-table parser logic).

Tests for Pydantic validators and computed fields are deliberately
omitted -- they would test the framework, not our logic.
"""

from second_brain.observability import queries


class TestModuleImport:
    """Sanity check that all imports resolve before adding real tests."""

    def test_queries_module_imports(self):
        assert hasattr(queries, "query_recent_failures_filtered")
        assert hasattr(queries, "_SEVERITY_MAP")
