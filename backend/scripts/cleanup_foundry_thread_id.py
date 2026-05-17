"""Phase 24 P0-2 post-UAT cleanup: delete foundryThreadId from Inbox docs.

P0-1 OUTCOME context: under the locked Option A design, no replacement
session-handle field was added to InboxDocument. Cross-process
session-handle rehydration was proven not to work on GA Foundry SDK
1.3.0, so the design pivoted to explicit conversationHistory persistence
on the Inbox doc itself. The only RC-era field that needs cleanup is
`foundryThreadId`, retained during the migration window for rollback
safety.

Run this script ONLY after 24-23 UAT confirms GA revision is healthy and
rollback is no longer needed. Until that point, foundryThreadId is dead
data on the doc but harmless -- the GA code reads via
resolve_inbox_conversation_history(), which logs a warning and returns []
for legacy docs (graceful continuity loss per Option A).

Idempotent -- re-running finds zero rows with foundryThreadId defined.

Usage:
    cd backend && COSMOS_ENDPOINT=https://shared-services-cosmosdb.documents.azure.com:443/ \\
        uv run python -m scripts.cleanup_foundry_thread_id

Per Phase 24 plan 24-24 (P0-2 cleanup half + P0-1 OUTCOME finalization).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys

from azure.cosmos.aio import CosmosClient
from azure.identity.aio import DefaultAzureCredential

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


async def cleanup() -> dict[str, int]:
    """Returns counts {seen, cleaned, errors}."""
    endpoint = os.environ["COSMOS_ENDPOINT"]
    database_name = os.environ.get("COSMOS_DATABASE", "second-brain")
    # Container name is "Inbox" (capital I) per the deployed Cosmos schema —
    # the plan body's lowercase "inbox" was a transcription error caught
    # during execution.
    container_name = "Inbox"

    seen = 0
    cleaned = 0
    errors = 0

    async with DefaultAzureCredential() as credential:
        async with CosmosClient(endpoint, credential=credential) as client:
            db = client.get_database_client(database_name)
            container = db.get_container_client(container_name)

            query = "SELECT * FROM c WHERE IS_DEFINED(c.foundryThreadId)"
            async for item in container.query_items(query=query):
                seen += 1
                item_id = item.get("id", "<unknown>")

                try:
                    del item["foundryThreadId"]
                    await container.replace_item(item=item_id, body=item)
                    cleaned += 1
                    has_history = bool(item.get("conversationHistory"))
                    logger.info(
                        "Cleaned %s (conversationHistory %s)",
                        item_id,
                        "present"
                        if has_history
                        else "absent (legacy doc — graceful continuity loss)",
                    )
                except Exception as exc:
                    errors += 1
                    logger.exception("ERROR cleaning %s: %s", item_id, exc)

    summary = {
        "seen": seen,
        "cleaned": cleaned,
        "errors": errors,
    }
    logger.info("Cleanup complete: %s", summary)
    return summary


def main() -> int:
    try:
        summary = asyncio.run(cleanup())
        print(json.dumps(summary))
        return 0 if summary["errors"] == 0 else 1
    except Exception as exc:
        logger.exception("Cleanup failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
