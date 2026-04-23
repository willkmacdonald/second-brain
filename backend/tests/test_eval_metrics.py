"""Tests for the eval metrics computation module.

Covers classifier metrics (precision/recall/accuracy), confidence calibration,
and admin agent routing accuracy.
"""

from __future__ import annotations

import pytest
from second_brain.eval.metrics import (
    compute_admin_metrics,
    compute_classifier_metrics,
    compute_confidence_calibration,
)


# ---------------------------------------------------------------------------
# Test 1: compute_classifier_metrics with mixed results
# ---------------------------------------------------------------------------
def test_classifier_metrics_mixed_results() -> None:
    """4 results: 3 correct, 1 wrong -> accuracy=0.75, correct precision/recall."""
    results = [
        {"predicted": "Admin", "expected": "Admin", "confidence": 0.9, "correct": True},
        {
            "predicted": "People",
            "expected": "People",
            "confidence": 0.8,
            "correct": True,
        },
        {"predicted": "Ideas", "expected": "Ideas", "confidence": 0.7, "correct": True},
        {
            "predicted": "Admin",
            "expected": "Projects",
            "confidence": 0.6,
            "correct": False,
        },
    ]
    metrics = compute_classifier_metrics(results)

    assert metrics["accuracy"] == 0.75
    assert metrics["total"] == 4
    assert metrics["correct"] == 3

    # Admin: TP=1, FP=1 -> precision=0.5; TP=1, FN=0 -> recall=1.0
    assert metrics["precision"]["Admin"] == 0.5
    assert metrics["recall"]["Admin"] == 1.0

    # People: TP=1, FP=0 -> precision=1.0; TP=1, FN=0 -> recall=1.0
    assert metrics["precision"]["People"] == 1.0
    assert metrics["recall"]["People"] == 1.0

    # Ideas: TP=1, FP=0 -> precision=1.0; TP=1, FN=0 -> recall=1.0
    assert metrics["precision"]["Ideas"] == 1.0
    assert metrics["recall"]["Ideas"] == 1.0

    # Projects: TP=0, FP=0 -> precision=0.0; TP=0, FN=1 -> recall=0.0
    assert metrics["precision"]["Projects"] == 0.0
    assert metrics["recall"]["Projects"] == 0.0


# ---------------------------------------------------------------------------
# Test 2: compute_classifier_metrics with empty list
# ---------------------------------------------------------------------------
def test_classifier_metrics_empty() -> None:
    """Empty list returns accuracy=0.0, total=0."""
    metrics = compute_classifier_metrics([])

    assert metrics["accuracy"] == 0.0
    assert metrics["total"] == 0
    assert metrics["correct"] == 0
    assert metrics["precision"] == {}
    assert metrics["recall"] == {}


# ---------------------------------------------------------------------------
# Test 3: compute_classifier_metrics with all correct
# ---------------------------------------------------------------------------
def test_classifier_metrics_all_correct() -> None:
    """All correct returns accuracy=1.0."""
    results = [
        {
            "predicted": "Admin",
            "expected": "Admin",
            "confidence": 0.95,
            "correct": True,
        },
        {
            "predicted": "People",
            "expected": "People",
            "confidence": 0.88,
            "correct": True,
        },
        {
            "predicted": "Ideas",
            "expected": "Ideas",
            "confidence": 0.92,
            "correct": True,
        },
    ]
    metrics = compute_classifier_metrics(results)

    assert metrics["accuracy"] == 1.0
    assert metrics["total"] == 3
    assert metrics["correct"] == 3

    # All precision and recall should be 1.0
    for bucket in ("Admin", "People", "Ideas"):
        assert metrics["precision"][bucket] == 1.0
        assert metrics["recall"][bucket] == 1.0


# ---------------------------------------------------------------------------
# Test 4: compute_confidence_calibration with results across range
# ---------------------------------------------------------------------------
def test_confidence_calibration_across_range() -> None:
    """10 results across confidence range return calibration bins."""
    results = [
        # Bin [0.0-0.2): confidence 0.1, correct
        {"confidence": 0.1, "correct": True},
        {"confidence": 0.15, "correct": False},
        # Bin [0.2-0.4): confidence 0.3, mixed
        {"confidence": 0.3, "correct": True},
        {"confidence": 0.35, "correct": False},
        # Bin [0.4-0.6): empty — should be omitted
        # Bin [0.6-0.8): confidence ~0.7
        {"confidence": 0.65, "correct": True},
        {"confidence": 0.7, "correct": True},
        {"confidence": 0.75, "correct": False},
        # Bin [0.8-1.0]: confidence ~0.9
        {"confidence": 0.85, "correct": True},
        {"confidence": 0.9, "correct": True},
        {"confidence": 1.0, "correct": True},
    ]
    bins = compute_confidence_calibration(results)

    # Should have 4 bins (0.4-0.6 is empty, omitted)
    assert len(bins) == 4

    bin_map = {b["bin"]: b for b in bins}

    # Bin [0.0-0.2): 2 items, avg_conf=(0.1+0.15)/2=0.125, accuracy=1/2=0.5
    assert bin_map["0.0-0.2"]["count"] == 2
    assert bin_map["0.0-0.2"]["avg_confidence"] == 0.125
    assert bin_map["0.0-0.2"]["actual_accuracy"] == 0.5

    # Bin [0.2-0.4): 2 items, avg_conf=(0.3+0.35)/2=0.325, accuracy=1/2=0.5
    assert bin_map["0.2-0.4"]["count"] == 2
    assert bin_map["0.2-0.4"]["avg_confidence"] == 0.325
    assert bin_map["0.2-0.4"]["actual_accuracy"] == 0.5

    # Bin [0.6-0.8): 3 items, avg_conf=(0.65+0.7+0.75)/3=0.7, accuracy=2/3=0.667
    assert bin_map["0.6-0.8"]["count"] == 3
    assert bin_map["0.6-0.8"]["avg_confidence"] == 0.7
    assert bin_map["0.6-0.8"]["actual_accuracy"] == 0.667

    # Bin [0.8-1.0]: 3 items, avg_conf=(0.85+0.9+1.0)/3≈0.917, accuracy=3/3=1.0
    assert bin_map["0.8-1.0"]["count"] == 3
    assert bin_map["0.8-1.0"]["avg_confidence"] == pytest.approx(0.917, abs=0.001)
    assert bin_map["0.8-1.0"]["actual_accuracy"] == 1.0


# ---------------------------------------------------------------------------
# Test 5: compute_confidence_calibration with empty list
# ---------------------------------------------------------------------------
def test_confidence_calibration_empty() -> None:
    """Empty input returns empty list."""
    bins = compute_confidence_calibration([])
    assert bins == []


# ---------------------------------------------------------------------------
# Test 6: compute_admin_metrics with mixed routing results
# ---------------------------------------------------------------------------
def test_admin_metrics_mixed_results() -> None:
    """3 results: 2 correct destination, 1 wrong -> routing_accuracy≈0.667."""
    results = [
        {
            "predicted_destination": "costco",
            "expected_destination": "costco",
            "correct": True,
        },
        {
            "predicted_destination": "target",
            "expected_destination": "target",
            "correct": True,
        },
        {
            "predicted_destination": "costco",
            "expected_destination": "walmart",
            "correct": False,
        },
    ]
    metrics = compute_admin_metrics(results)

    assert metrics["routing_accuracy"] == pytest.approx(2 / 3, abs=0.001)
    assert metrics["total"] == 3
    assert metrics["correct"] == 2

    # Per-destination: costco 1/1=1.0, target 1/1=1.0, walmart 0/1=0.0
    assert metrics["per_destination"]["costco"] == 1.0
    assert metrics["per_destination"]["target"] == 1.0
    assert metrics["per_destination"]["walmart"] == 0.0


# ---------------------------------------------------------------------------
# Test 7: compute_admin_metrics with empty list
# ---------------------------------------------------------------------------
def test_admin_metrics_empty() -> None:
    """Empty list returns routing_accuracy=0.0."""
    metrics = compute_admin_metrics([])

    assert metrics["routing_accuracy"] == 0.0
    assert metrics["total"] == 0
    assert metrics["correct"] == 0
    assert metrics["per_destination"] == {}
