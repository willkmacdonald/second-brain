"""Export Inbox items for curation and import curated entries as GoldenDatasetDocuments.

Three subcommands:

  export          -- Query Inbox for recent captures, write JSON.
  import          -- Read curated JSON, write GoldenDatasetDocuments.
  foundry-export  -- Export golden dataset as JSONL for Foundry.

Prerequisites:
  - Run ``az login`` first (uses DefaultAzureCredential)
  - Set COSMOS_ENDPOINT environment variable

Usage:
  # Export recent inbox items for curation
  python3 backend/scripts/seed_golden_dataset.py export --limit 100

  # Import curated (approved) entries as golden dataset
  python3 backend/scripts/seed_golden_dataset.py import --file golden_dataset.json

  # Export golden dataset as JSONL for Foundry evaluation upload
  python3 backend/scripts/seed_golden_dataset.py foundry-export --eval-type classifier
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import UTC, datetime
from uuid import uuid4

from azure.cosmos.aio import CosmosClient
from azure.identity.aio import DefaultAzureCredential

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DATABASE_NAME = "second-brain"


# ---------------------------------------------------------------------------
# Export subcommand
# ---------------------------------------------------------------------------


async def export_inbox(limit: int, output: str) -> None:
    """Export recent Inbox items to a JSON file for human curation.

    Each exported item includes ``_review_status`` (default "pending") and
    ``_original_id`` for traceability.  The curator sets ``_review_status``
    to "approved" for entries they want in the golden dataset.
    """
    endpoint = os.environ.get("COSMOS_ENDPOINT")
    if not endpoint:
        logger.error("COSMOS_ENDPOINT environment variable is not set")
        sys.exit(1)

    credential = DefaultAzureCredential()
    client = CosmosClient(url=endpoint, credential=credential)

    try:
        database = client.get_database_client(DATABASE_NAME)
        container = database.get_container_client("Inbox")

        query = (
            "SELECT c.id, c.rawText, c.bucket, c.captureTraceId, "
            "c.title, c.createdAt "
            "FROM c WHERE c.userId = 'will' "
            "ORDER BY c.createdAt DESC "
            "OFFSET 0 LIMIT @limit"
        )
        parameters: list[dict[str, object]] = [{"name": "@limit", "value": limit}]

        items: list[dict] = []
        async for item in container.query_items(
            query=query,
            parameters=parameters,
            partition_key="will",
        ):
            items.append(
                {
                    "inputText": item.get("rawText", ""),
                    "expectedBucket": item.get("bucket", ""),
                    "source": "manual",
                    "tags": [],
                    "_original_id": item.get("id", ""),
                    "_original_bucket": item.get("bucket", ""),
                    "_review_status": "pending",
                }
            )

        with open(output, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)

        logger.info("Exported %d inbox items to %s", len(items), output)

    except Exception:
        logger.exception("Failed to export inbox items")
        sys.exit(1)
    finally:
        await client.close()
        await credential.close()


# ---------------------------------------------------------------------------
# Import subcommand
# ---------------------------------------------------------------------------


async def import_golden(file_path: str) -> None:
    """Import curated JSON entries as GoldenDatasetDocuments.

    Only entries with ``_review_status`` == "approved" are imported.
    Metadata fields (``_review_status``, ``_original_id``, ``_original_bucket``)
    are stripped before writing to Cosmos.
    """
    endpoint = os.environ.get("COSMOS_ENDPOINT")
    if not endpoint:
        logger.error("COSMOS_ENDPOINT environment variable is not set")
        sys.exit(1)

    # Read curated JSON
    try:
        with open(file_path, encoding="utf-8") as f:
            entries: list[dict] = json.load(f)
    except FileNotFoundError:
        logger.error("File not found: %s", file_path)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        logger.error("Invalid JSON in %s: %s", file_path, exc)
        sys.exit(1)

    approved = [e for e in entries if e.get("_review_status") == "approved"]
    skipped = len(entries) - len(approved)

    if not approved:
        logger.info(
            "No approved entries found (%d total, %d skipped). "
            'Mark entries with "_review_status": "approved" before importing.',
            len(entries),
            skipped,
        )
        return

    credential = DefaultAzureCredential()
    client = CosmosClient(url=endpoint, credential=credential)

    try:
        database = client.get_database_client(DATABASE_NAME)
        container = database.get_container_client("GoldenDataset")

        now = datetime.now(UTC).isoformat()
        imported = 0

        for entry in approved:
            doc = {
                "id": str(uuid4()),
                "userId": "will",
                "inputText": entry.get("inputText", ""),
                "expectedBucket": entry.get("expectedBucket", ""),
                "expectedDestination": entry.get("expectedDestination"),
                "source": entry.get("source", "manual"),
                "tags": entry.get("tags", []),
                "createdAt": now,
                "updatedAt": now,
            }
            await container.create_item(body=doc)
            imported += 1

        logger.info(
            "Imported %d golden dataset entries (%d skipped, %d total in file)",
            imported,
            skipped,
            len(entries),
        )

    except Exception:
        logger.exception("Failed to import golden dataset entries")
        sys.exit(1)
    finally:
        await client.close()
        await credential.close()


# ---------------------------------------------------------------------------
# Foundry-export subcommand
# ---------------------------------------------------------------------------


async def foundry_export(eval_type: str, output: str) -> None:
    """Export golden dataset entries as JSONL for Foundry evaluation upload.

    Produces one JSON object per line.  Schema depends on *eval_type*:

    * **classifier** -- ``{"query": ..., "expected_bucket": ...}``
    * **admin_agent** -- ``{"query": ..., "expected_destination": ...}``
      (only entries with a non-null ``expectedDestination`` are included)
    """
    endpoint = os.environ.get("COSMOS_ENDPOINT")
    if not endpoint:
        logger.error("COSMOS_ENDPOINT environment variable is not set")
        sys.exit(1)

    credential = DefaultAzureCredential()
    client = CosmosClient(url=endpoint, credential=credential)

    try:
        database = client.get_database_client(DATABASE_NAME)
        container = database.get_container_client("GoldenDataset")

        query = "SELECT * FROM c WHERE c.userId = @userId"
        parameters: list[dict[str, object]] = [
            {"name": "@userId", "value": "will"},
        ]

        count = 0
        with open(output, "w", encoding="utf-8") as f:
            async for item in container.query_items(
                query=query,
                parameters=parameters,
                partition_key="will",
            ):
                if eval_type == "admin_agent":
                    dest = item.get("expectedDestination")
                    if not dest:
                        continue
                    line = {
                        "query": item.get("inputText", ""),
                        "expected_destination": dest,
                    }
                else:
                    line = {
                        "query": item.get("inputText", ""),
                        "expected_bucket": item.get("expectedBucket", ""),
                    }

                f.write(json.dumps(line, ensure_ascii=False) + "\n")
                count += 1

        logger.info("Exported %d entries to %s", count, output)

    except Exception:
        logger.exception("Failed to export golden dataset as JSONL")
        sys.exit(1)
    finally:
        await client.close()
        await credential.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser with export/import subcommands."""
    parser = argparse.ArgumentParser(
        description="Export Inbox captures and import curated golden dataset entries."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # export
    export_parser = subparsers.add_parser(
        "export", help="Export recent Inbox items to JSON for curation"
    )
    export_parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of items to export (default: 100)",
    )
    export_parser.add_argument(
        "--output",
        type=str,
        default="backend/scripts/golden_dataset_export.json",
        help=(
            "Output JSON file path "
            "(default: backend/scripts/golden_dataset_export.json)"
        ),
    )

    # import
    import_parser = subparsers.add_parser(
        "import", help="Import approved entries from curated JSON"
    )
    import_parser.add_argument(
        "--file",
        type=str,
        required=True,
        help="Path to curated JSON file with approved entries",
    )

    # foundry-export
    foundry_export_parser = subparsers.add_parser(
        "foundry-export",
        help="Export golden dataset entries as JSONL for Foundry evaluation upload",
    )
    foundry_export_parser.add_argument(
        "--eval-type",
        type=str,
        choices=["classifier", "admin_agent"],
        default="classifier",
        help="Eval type determines JSONL schema (default: classifier)",
    )
    foundry_export_parser.add_argument(
        "--output",
        type=str,
        default="backend/scripts/golden_dataset_foundry.jsonl",
        help=(
            "Output JSONL file path "
            "(default: backend/scripts/golden_dataset_foundry.jsonl)"
        ),
    )

    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()

    if args.command == "export":
        asyncio.run(export_inbox(limit=args.limit, output=args.output))
    elif args.command == "import":
        asyncio.run(import_golden(file_path=args.file))
    elif args.command == "foundry-export":
        asyncio.run(foundry_export(eval_type=args.eval_type, output=args.output))
