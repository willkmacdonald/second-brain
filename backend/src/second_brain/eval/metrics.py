"""Eval metrics computation for Classifier and Admin Agent quality.

Pure computation functions -- no I/O, no database access. All functions
accept lists of result dicts and return aggregate metric dicts.

Used by the eval runner (Plan 02) and API layer (Plan 04).
"""

from __future__ import annotations

from collections import defaultdict


def compute_classifier_metrics(results: list[dict]) -> dict:
    """Compute accuracy, per-bucket precision, and per-bucket recall.

    Args:
        results: List of dicts with keys ``predicted``, ``expected``,
            ``confidence``, ``correct``.

    Returns:
        Dict with ``accuracy``, ``total``, ``correct``, ``precision``
        (per-bucket), and ``recall`` (per-bucket).
    """
    total = len(results)
    if total == 0:
        return {
            "accuracy": 0.0,
            "total": 0,
            "correct": 0,
            "precision": {},
            "recall": {},
        }

    correct = sum(1 for r in results if r["correct"])
    accuracy = correct / total

    # Collect all bucket labels that appear in predictions or expected
    buckets: set[str] = set()
    for r in results:
        buckets.add(r["predicted"])
        buckets.add(r["expected"])

    precision: dict[str, float] = {}
    recall: dict[str, float] = {}

    for bucket in sorted(buckets):
        tp = sum(
            1 for r in results if r["predicted"] == bucket and r["expected"] == bucket
        )
        fp = sum(
            1 for r in results if r["predicted"] == bucket and r["expected"] != bucket
        )
        fn = sum(
            1 for r in results if r["predicted"] != bucket and r["expected"] == bucket
        )

        precision[bucket] = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall[bucket] = tp / (tp + fn) if (tp + fn) > 0 else 0.0

    return {
        "accuracy": accuracy,
        "total": total,
        "correct": correct,
        "precision": precision,
        "recall": recall,
    }


def compute_confidence_calibration(
    results: list[dict],
    bins: int = 5,
) -> list[dict]:
    """Bin results by confidence and compute per-bin accuracy.

    Args:
        results: List of dicts with keys ``confidence`` and ``correct``.
        bins: Number of equal-width bins across [0.0, 1.0].

    Returns:
        List of dicts with ``bin`` (label), ``count``,
        ``avg_confidence`` (rounded to 3 decimals), and
        ``actual_accuracy`` (rounded to 3 decimals).
        Empty bins are omitted. Empty input returns ``[]``.
    """
    if not results:
        return []

    bin_width = 1.0 / bins
    bin_data: dict[str, list[dict]] = defaultdict(list)

    for r in results:
        conf = r["confidence"]
        # Determine which bin this falls into
        for i in range(bins):
            lo = round(i * bin_width, 4)
            hi = round((i + 1) * bin_width, 4)
            label = f"{lo}-{hi}"

            if i == bins - 1:
                # Last bin is inclusive on both ends: [lo, hi]
                if lo <= conf <= hi:
                    bin_data[label].append(r)
                    break
            else:
                # Other bins: [lo, hi)
                if lo <= conf < hi:
                    bin_data[label].append(r)
                    break

    output: list[dict] = []
    for i in range(bins):
        lo = round(i * bin_width, 4)
        hi = round((i + 1) * bin_width, 4)
        label = f"{lo}-{hi}"

        if label not in bin_data:
            continue

        items = bin_data[label]
        count = len(items)
        avg_conf = round(sum(item["confidence"] for item in items) / count, 3)
        actual_acc = round(sum(1 for item in items if item["correct"]) / count, 3)

        output.append(
            {
                "bin": label,
                "count": count,
                "avg_confidence": avg_conf,
                "actual_accuracy": actual_acc,
            }
        )

    return output


def compute_admin_metrics(results: list[dict]) -> dict:
    """Compute routing accuracy and per-destination breakdown.

    Args:
        results: List of dicts with keys ``predicted_destination``,
            ``expected_destination``, ``correct``.

    Returns:
        Dict with ``routing_accuracy``, ``total``, ``correct``, and
        ``per_destination`` (accuracy per expected destination).
    """
    total = len(results)
    if total == 0:
        return {
            "routing_accuracy": 0.0,
            "total": 0,
            "correct": 0,
            "per_destination": {},
        }

    correct = sum(1 for r in results if r["correct"])
    routing_accuracy = correct / total

    # Per-destination accuracy (keyed by expected_destination)
    dest_results: dict[str, list[bool]] = defaultdict(list)
    for r in results:
        dest_results[r["expected_destination"]].append(r["correct"])

    per_destination: dict[str, float] = {}
    for dest, correctness_list in sorted(dest_results.items()):
        per_destination[dest] = sum(1 for c in correctness_list if c) / len(
            correctness_list
        )

    return {
        "routing_accuracy": routing_accuracy,
        "total": total,
        "correct": correct,
        "per_destination": per_destination,
    }
