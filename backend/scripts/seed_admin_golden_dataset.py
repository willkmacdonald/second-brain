"""Seed GoldenDataset with admin test cases (Phase 24 P1-7).

Idempotent -- re-running upserts the same cases by deterministic id. Reads
cases from a YAML manifest under backend/scripts/admin_golden_seed/.

Usage:
    cd backend && uv run python -m scripts.seed_admin_golden_dataset \
        --cases scripts/admin_golden_seed/cases.yaml

Prerequisites:
    - az login (DefaultAzureCredential)
    - COSMOS_ENDPOINT environment variable exported

Per Phase 24 plan 24-13.5 (P1-7 closure).

The operator MUST curate the cases.yaml manifest before running. The
starter manifest contains 10 placeholder cases -- replace with real
production captures.

Document shape rationale (Plan-execution Rule 1 auto-fix):
    The eval runner at backend/src/second_brain/eval/runner.py:262-267
    hardcodes `userId = "will"` in its Cosmos query and reads case fields
    as `case["inputText"]` (line 286) plus `case["expectedDestination"]`
    (line 306). To ensure runner consumption, this script writes documents
    matching that exact shape:
        - userId = "will" (not "eval-user-admin"; runner only queries "will")
        - inputText (not captureText; runner reads inputText)
        - expectedDestination (camelCase; runner filters on this field)
        - expectedToolName (camelCase; forward-looking for post-hoc tool
          inspection during eval; not currently read by runner but pinned
          in the seed doc for plan 24-20 Gate 6 + future evaluator hooks)
    These deviations from the plan's interfaces text are required for the
    seed script + runner pair to actually function end-to-end.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml
from azure.cosmos.aio import CosmosClient
from azure.identity.aio import DefaultAzureCredential

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Pinned constants -- see module docstring "Document shape rationale" for why.
EVAL_USER_ID = "will"  # eval/runner.py:263 hardcodes WHERE userId = "will"
EVAL_TYPE = "admin_agent"
DATABASE_NAME = "second-brain"
CONTAINER_NAME = "GoldenDataset"


def _case_id(capture_text: str) -> str:
    """Deterministic id from capture text -- keeps upserts idempotent."""
    digest = hashlib.sha1(capture_text.encode("utf-8")).hexdigest()
    return f"admin-eval-{digest[:16]}"


def _load_cases(manifest_path: Path) -> list[dict[str, str]]:
    with manifest_path.open("r") as fh:
        data = yaml.safe_load(fh)
    cases = data.get("cases", [])
    if not isinstance(cases, list) or len(cases) < 10:
        raise ValueError(
            f"cases.yaml must contain at least 10 cases; found {len(cases)}. "
            "Curate >= 10 representative admin captures before seeding."
        )
    for i, case in enumerate(cases):
        for required in ("capture_text", "expected_destination", "expected_tool"):
            if required not in case:
                raise ValueError(f"case[{i}] missing required field {required!r}")
        if case["expected_tool"] not in ("add_errand_items", "add_task_items"):
            raise ValueError(
                f"case[{i}] expected_tool must be 'add_errand_items' or "
                f"'add_task_items'; got {case['expected_tool']!r}"
            )
    return cases


async def seed(manifest_path: Path) -> int:
    cases = _load_cases(manifest_path)

    endpoint = os.environ["COSMOS_ENDPOINT"]
    database_name = os.environ.get("COSMOS_DATABASE", DATABASE_NAME)
    container_name = CONTAINER_NAME

    upserted = 0
    async with DefaultAzureCredential() as credential:
        async with CosmosClient(endpoint, credential=credential) as client:
            db = client.get_database_client(database_name)
            container = db.get_container_client(container_name)

            for case in cases:
                case_id = _case_id(case["capture_text"])
                now = datetime.now(UTC).isoformat()
                doc = {
                    "id": case_id,
                    "userId": EVAL_USER_ID,
                    "evalType": EVAL_TYPE,
                    # Runner reads case["inputText"] -- see module docstring.
                    "inputText": case["capture_text"],
                    "expectedDestination": case["expected_destination"],
                    "expectedToolName": case["expected_tool"],
                    "source": "manual",
                    "tags": ["admin_eval", "phase24_seed"],
                    "createdAt": now,
                    "updatedAt": now,
                }
                await container.upsert_item(body=doc)
                upserted += 1
                logger.info(
                    "Upserted admin case %s (%s -> %s)",
                    case_id,
                    case["capture_text"][:60],
                    case["expected_destination"],
                )

    logger.info("Seeded %d admin cases (manifest=%s)", upserted, manifest_path)
    return upserted


def main() -> int:
    parser = argparse.ArgumentParser(prog="seed_admin_golden_dataset")
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("scripts/admin_golden_seed/cases.yaml"),
        help="Path to YAML cases manifest.",
    )
    args = parser.parse_args()

    if not args.cases.exists():
        print(f"FATAL: manifest not found: {args.cases}", file=sys.stderr)
        return 1

    try:
        count = asyncio.run(seed(args.cases))
        print(json.dumps({"seeded_count": count, "manifest": str(args.cases)}))
        return 0
    except Exception as exc:
        logger.exception("Seeding failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
