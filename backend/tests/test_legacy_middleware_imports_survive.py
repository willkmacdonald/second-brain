"""Phase 24 P1-3 regression guard (post-24-18 state).

After plan 24-18 deletes backend/src/second_brain/agents/middleware.py,
this test asserts:
- The new GA middleware imports at second_brain.agents.agent_middleware.capture_trace.
- No file or directory exists at second_brain/agents/middleware{,.py}.

The legacy-importable sub-test from 24-03 is retired here per P1-3 spec
(the legacy module is gone -- its import would now correctly raise ImportError).
"""

from __future__ import annotations

import importlib


def test_new_ga_middleware_imports_at_distinct_path() -> None:
    """The new GA middleware must live at agent_middleware/, NOT middleware/."""
    mod = importlib.import_module("second_brain.agents.agent_middleware.capture_trace")
    assert hasattr(mod, "CaptureTraceAgentMiddleware")
    assert hasattr(mod, "CaptureTraceFunctionMiddleware")


def test_legacy_middleware_module_is_gone() -> None:
    """Post-24-18: confirm the legacy agents/middleware.py is deleted AND
    no replacement package exists at the same path. The new GA middleware
    lives at agents/agent_middleware/.
    """
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[1]
    legacy_module = project_root / "src" / "second_brain" / "agents" / "middleware.py"
    legacy_package = project_root / "src" / "second_brain" / "agents" / "middleware"
    assert not legacy_module.exists(), (
        f"Legacy module still present at {legacy_module}. "
        "Plan 24-18 should have deleted it."
    )
    assert not legacy_package.is_dir(), (
        f"P1-3 invariant: no package at {legacy_package} (would shadow "
        "if the legacy module were ever resurrected). The GA path is "
        "agents/agent_middleware/."
    )
