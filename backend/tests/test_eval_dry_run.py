"""Tests for dry-run eval tool handlers.

Covers EvalClassifierTools (file_capture capture, confidence clamping, reset)
and DryRunAdminTools (errand/task capture, routing context, accumulation).
"""

from __future__ import annotations

import asyncio

import pytest
from second_brain.eval.dry_run_tools import DryRunAdminTools, EvalClassifierTools


# ---------------------------------------------------------------------------
# Test 1: EvalClassifierTools.file_capture captures fields
# ---------------------------------------------------------------------------
def test_classifier_file_capture_stores_prediction() -> None:
    """file_capture stores bucket, confidence, status and returns dict."""
    tools = EvalClassifierTools()
    result = asyncio.run(
        tools.file_capture(
            text="buy milk",
            bucket="Admin",
            confidence=0.85,
            status="classified",
            title="Buy milk",
        )
    )
    assert tools.last_bucket == "Admin"
    assert tools.last_confidence == 0.85
    assert tools.last_status == "classified"
    assert result["bucket"] == "Admin"
    assert result["confidence"] == 0.85
    assert result["item_id"] == "eval-dry-run"


# ---------------------------------------------------------------------------
# Test 2: EvalClassifierTools confidence clamped to [0.0, 1.0]
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [(1.5, 1.0), (-0.1, 0.0), (0.5, 0.5), (0.0, 0.0), (1.0, 1.0)],
)
def test_classifier_confidence_clamped(raw: float, expected: float) -> None:
    """Confidence values outside [0.0, 1.0] are clamped."""
    tools = EvalClassifierTools()
    asyncio.run(
        tools.file_capture(
            text="test",
            bucket="Ideas",
            confidence=raw,
            status="classified",
        )
    )
    assert tools.last_confidence == expected


# ---------------------------------------------------------------------------
# Test 3: EvalClassifierTools.reset() clears state
# ---------------------------------------------------------------------------
def test_classifier_reset_clears_state() -> None:
    """reset() sets all last_* fields to None."""
    tools = EvalClassifierTools()
    asyncio.run(
        tools.file_capture(
            text="test",
            bucket="People",
            confidence=0.9,
            status="classified",
        )
    )
    assert tools.last_bucket is not None

    tools.reset()
    assert tools.last_bucket is None
    assert tools.last_confidence is None
    assert tools.last_status is None


# ---------------------------------------------------------------------------
# Test 4: DryRunAdminTools.add_errand_items captures destinations
# ---------------------------------------------------------------------------
def test_admin_add_errand_items_captures_destinations() -> None:
    """add_errand_items records destinations without side effects."""
    tools = DryRunAdminTools(routing_context="test routing context")
    result = asyncio.run(
        tools.add_errand_items(
            items=[
                {"name": "milk", "destination": "jewel"},
                {"name": "dog food", "destination": "pet_store"},
            ]
        )
    )
    assert tools.captured_destinations == ["jewel", "pet_store"]
    assert len(tools.captured_items) == 2
    assert "[DRY RUN]" in result
    assert "2" in result


# ---------------------------------------------------------------------------
# Test 5: DryRunAdminTools.add_task_items returns dry-run message
# ---------------------------------------------------------------------------
def test_admin_add_task_items_dry_run() -> None:
    """add_task_items returns dry-run message without side effects."""
    tools = DryRunAdminTools(routing_context="test routing context")
    result = asyncio.run(
        tools.add_task_items(
            tasks=[
                {"name": "book dentist appointment"},
                {"name": "fill out expense report"},
            ]
        )
    )
    assert "[DRY RUN]" in result
    assert "2" in result
    assert len(tools.captured_tasks) == 2
    assert tools.captured_tasks[0]["name"] == "book dentist appointment"


# ---------------------------------------------------------------------------
# Test 6: DryRunAdminTools.get_routing_context returns fixed string
# ---------------------------------------------------------------------------
def test_admin_get_routing_context_returns_fixed_string() -> None:
    """get_routing_context returns the routing_context passed to constructor."""
    ctx = "Destinations: jewel (Jewel-Osco), cvs (CVS)\nRules: milk -> jewel"
    tools = DryRunAdminTools(routing_context=ctx)
    result = asyncio.run(tools.get_routing_context())
    assert result == ctx


# ---------------------------------------------------------------------------
# Test 7: DryRunAdminTools.captured_destinations accumulates across calls
# ---------------------------------------------------------------------------
def test_admin_captured_destinations_accumulate() -> None:
    """captured_destinations starts empty and accumulates across calls."""
    tools = DryRunAdminTools(routing_context="test")
    assert tools.captured_destinations == []

    asyncio.run(
        tools.add_errand_items(items=[{"name": "eggs", "destination": "jewel"}])
    )
    assert tools.captured_destinations == ["jewel"]

    asyncio.run(
        tools.add_errand_items(items=[{"name": "shampoo", "destination": "cvs"}])
    )
    assert tools.captured_destinations == ["jewel", "cvs"]
