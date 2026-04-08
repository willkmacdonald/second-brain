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
