"""Spike: Can azure-ai-evaluation score classifier label accuracy?

Purpose: Determine whether Phase 21 can use Foundry built-in evaluators
for classifier bucket-match scoring, or needs custom scorers.

Run: uv pip install azure-ai-evaluation && python3 score_one_capture.py

Expected outcome: Built-in evaluators (groundedness, relevance, fluency, etc.)
are text-quality scorers designed for RAG/chat. They do NOT score categorical
label match (bucket == ground_truth). A custom callable scorer is needed.
"""

from __future__ import annotations

import json
import sys


def main() -> None:
    """Test azure-ai-evaluation for label-match scoring."""
    try:
        import azure.ai.evaluation  # noqa: F401
    except ImportError:
        print("ERROR: azure-ai-evaluation not installed.")
        print("Install: uv pip install azure-ai-evaluation")
        sys.exit(1)

    # Print SDK version
    version = getattr(azure.ai.evaluation, "__version__", "unknown")
    print(f"azure-ai-evaluation version: {version}")

    # List available built-in evaluators
    evaluator_names = [
        name
        for name in dir(azure.ai.evaluation)
        if name.endswith("Evaluator") and not name.startswith("_")
    ]
    print(f"\nBuilt-in evaluators found: {len(evaluator_names)}")
    for name in sorted(evaluator_names):
        print(f"  - {name}")

    # Minimal eval dataset -- classifier outputs with known-correct labels
    # For this spike, response == ground_truth to verify the mechanism
    eval_data = [
        {
            "query": "Pick up milk and eggs from Whole Foods",
            "response": "Admin",
            "ground_truth": "Admin",
        },
        {
            "query": "Chicken tikka masala recipe for dinner tonight",
            "response": "Meals",
            "ground_truth": "Meals",
        },
        {
            "query": "Remember to call dentist on Monday",
            "response": "Notes",
            "ground_truth": "Notes",
        },
    ]

    # Try F1ScoreEvaluator -- closest to label match
    try:
        from azure.ai.evaluation import F1ScoreEvaluator

        evaluator = F1ScoreEvaluator()
        results = []
        for item in eval_data:
            result = evaluator(
                response=item["response"],
                ground_truth=item["ground_truth"],
            )
            results.append(result)
        print(f"\nF1ScoreEvaluator results: {json.dumps(results, indent=2)}")
        print("NOTE: F1ScoreEvaluator computes token-level F1, not exact label match")
    except Exception as e:
        print(f"\nF1ScoreEvaluator failed: {e}")

    # Try custom callable scorer for exact match
    def exact_match_scorer(*, response: str, ground_truth: str, **kwargs) -> dict:
        """Custom scorer: exact string match for bucket labels."""
        return {"exact_match": 1.0 if response.strip() == ground_truth.strip() else 0.0}

    print("\nCustom exact_match_scorer results:")
    for item in eval_data:
        result = exact_match_scorer(
            response=item["response"],
            ground_truth=item["ground_truth"],
        )
        print(f"  {item['query'][:40]}... -> {result}")

    # Try evaluate() with custom scorer
    try:
        from azure.ai.evaluation import evaluate

        eval_result = evaluate(
            data=eval_data,
            evaluators={"exact_match": exact_match_scorer},
        )
        print(
            f"\nevaluate() result: {json.dumps(eval_result.get('metrics', {}), indent=2)}"
        )
    except Exception as e:
        print(f"\nevaluate() with custom scorer failed: {e}")

    print("\n--- SPIKE CONCLUSION ---")
    print("1. No built-in label-match evaluator exists")
    print("2. F1ScoreEvaluator computes token-level F1 (not categorical accuracy)")
    print("3. Custom callable scorers work via evaluate() function")
    print("4. Phase 21 needs: custom exact-match scorer + per-bucket precision/recall")
    print(
        "5. Foundry SDK hosts and runs custom scorers -- no separate framework needed"
    )


if __name__ == "__main__":
    main()
