"""Phase 24 P1-3 regression guard.

Asserts that during the migration window (24-03 .. 24-17), the legacy module
`backend/src/second_brain/agents/middleware.py` remains importable. The new
GA middleware lives at `agents/agent_middleware/capture_trace.py` (distinct
package name -- the original plan put it at `agents/middleware/` which would
shadow the legacy module).

This test passes during the migration window. After 24-18 deletes the legacy
module, this test will fail -- that's the trigger to retire the test (or
invert the assertion to negative coverage). 24-18 is responsible for
updating/removing this test as part of its cleanup.
"""

from __future__ import annotations

import importlib


def test_legacy_agents_middleware_module_still_importable() -> None:
    """During the migration window, legacy imports from agents/middleware.py
    must keep resolving. This proves the new agent_middleware/ package did
    not accidentally shadow the module."""
    mod = importlib.import_module("second_brain.agents.middleware")
    # AuditAgentMiddleware + ToolTimingMiddleware are the two RC-era classes
    assert hasattr(mod, "AuditAgentMiddleware"), (
        "Legacy AuditAgentMiddleware must still be importable from "
        "second_brain.agents.middleware during migration. The new GA "
        "middleware lives at second_brain.agents.agent_middleware.capture_trace."
    )
    assert hasattr(mod, "ToolTimingMiddleware"), (
        "Legacy ToolTimingMiddleware must still be importable during migration."
    )


def test_new_ga_middleware_imports_at_distinct_path() -> None:
    """The new GA middleware must live at agent_middleware/, NOT middleware/."""
    mod = importlib.import_module("second_brain.agents.agent_middleware.capture_trace")
    assert hasattr(mod, "CaptureTraceAgentMiddleware")
    assert hasattr(mod, "CaptureTraceFunctionMiddleware")


def test_no_package_shadowing() -> None:
    """Confirm there is no second_brain.agents.middleware package (only the module).

    If a directory `backend/src/second_brain/agents/middleware/` exists, Python
    will prefer the package and shadow the legacy module -- that's the P1-3 defect.
    """
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[1]
    package_dir = project_root / "src" / "second_brain" / "agents" / "middleware"
    assert not package_dir.is_dir(), (
        f"P1-3 violation: found package directory at {package_dir}. "
        "The new GA middleware must live under agents/agent_middleware/ "
        "(not agents/middleware/) until 24-18 deletes the legacy file."
    )
