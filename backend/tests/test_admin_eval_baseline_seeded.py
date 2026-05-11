"""Phase 24 P1-7 red test.

Asserts that backend/tests/fixtures/eval-baseline-pre-migration.json has a
real admin baseline with at least 10 cases, status=completed, and a numeric
routing_accuracy. Fails today against the placeholder admin block; turns
green after plan 24-13.5 ships (operator runs seed script + eval, commits
updated baseline).
"""

from __future__ import annotations

import json
from pathlib import Path

BASELINE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "fixtures"
    / "eval-baseline-pre-migration.json"
)


def test_admin_baseline_has_seeded_cases() -> None:
    assert BASELINE_PATH.exists(), f"Baseline missing: {BASELINE_PATH}"
    payload = json.loads(BASELINE_PATH.read_text())

    admin = payload.get("admin")
    assert admin is not None, "Baseline missing admin block"

    total = admin.get("total")
    assert isinstance(total, int) and total >= 10, (
        f"Admin baseline must have at least 10 seeded cases; got total={total}. "
        "Run backend/scripts/seed_admin_golden_dataset.py and re-baseline before "
        "Phase 24 plan 24-20 Gate 6 can produce a meaningful signal."
    )

    status = admin.get("status")
    assert status == "completed", (
        f"Admin baseline status must be 'completed'; got {status!r}. "
        "Run admin eval against deployed RC backend."
    )

    routing_accuracy = admin.get("routing_accuracy")
    assert isinstance(routing_accuracy, (int, float)), (
        f"admin.routing_accuracy must be a number; got {routing_accuracy!r}"
    )
    assert 0.0 <= routing_accuracy <= 1.0, (
        f"admin.routing_accuracy must be in [0.0, 1.0]; got {routing_accuracy}"
    )

    agg = admin.get("aggregateScores", {})
    assert isinstance(agg, dict)
    assert agg.get("total") == total, "aggregateScores.total must equal admin.total"
    per_destination = agg.get("per_destination", {})
    assert isinstance(per_destination, dict) and len(per_destination) > 0, (
        "aggregateScores.per_destination must be non-empty after seeding"
    )
