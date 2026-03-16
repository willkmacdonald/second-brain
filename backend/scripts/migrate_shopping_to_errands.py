"""One-time migration script: ShoppingLists -> Errands (Phase 12.2).

Copies all items from the ShoppingLists Cosmos DB container into a new
Errands container, mapping the 'store' field to 'destination'. After
verifying item counts match, deletes the old ShoppingLists container.

Prerequisites:
  - Run `az login` first (uses DefaultAzureCredential)
  - Set COSMOS_ENDPOINT environment variable
  - Run BEFORE deploying the renamed backend code

Usage:
  python3 backend/scripts/migrate_shopping_to_errands.py
"""

import asyncio
import logging
import os
import sys

from azure.cosmos.aio import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from azure.identity.aio import DefaultAzureCredential

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DATABASE_NAME = "second-brain"
SOURCE_CONTAINER = "ShoppingLists"
TARGET_CONTAINER = "Errands"
PARTITION_KEY = "/destination"
KNOWN_DESTINATIONS = ["jewel", "cvs", "pet_store", "other"]


async def migrate() -> None:
    """Migrate items from ShoppingLists to Errands container."""
    endpoint = os.environ.get("COSMOS_ENDPOINT")
    if not endpoint:
        logger.error("COSMOS_ENDPOINT environment variable is not set")
        sys.exit(1)

    credential = DefaultAzureCredential()
    client = CosmosClient(url=endpoint, credential=credential)

    try:
        database = client.get_database_client(DATABASE_NAME)

        # Check if source container exists
        try:
            source = database.get_container_client(SOURCE_CONTAINER)
            # Verify it exists by reading its properties
            await source.read()
        except CosmosResourceNotFoundError:
            logger.info(
                "ShoppingLists container does not exist -- already migrated"
            )
            return

        # Create target container
        target = await database.create_container_if_not_exists(
            id=TARGET_CONTAINER,
            partition_key={"paths": [PARTITION_KEY], "kind": "Hash"},
        )
        logger.info("Errands container ready")

        # Migrate items per destination
        total_migrated = 0
        per_destination: dict[str, int] = {}

        for destination in KNOWN_DESTINATIONS:
            count = 0
            try:
                query = "SELECT * FROM c"
                items = source.query_items(
                    query=query,
                    partition_key=destination,
                )
                async for item in items:
                    try:
                        new_doc = {
                            "id": item["id"],
                            "name": item["name"],
                            "destination": item.get("store", destination),
                        }
                        await target.upsert_item(new_doc)
                        count += 1
                    except Exception:
                        logger.exception(
                            "Failed to copy item %s from %s",
                            item.get("id", "unknown"),
                            destination,
                        )
            except Exception:
                logger.exception(
                    "Failed to query %s partition", destination
                )

            per_destination[destination] = count
            total_migrated += count
            if count > 0:
                logger.info(
                    "  %s: %d item%s migrated",
                    destination,
                    count,
                    "s" if count != 1 else "",
                )

        # Verify counts
        verify_count = 0
        for destination in KNOWN_DESTINATIONS:
            query = "SELECT VALUE COUNT(1) FROM c"
            results = target.query_items(
                query=query,
                partition_key=destination,
            )
            async for result in results:
                verify_count += result

        logger.info("Migration total: %d items", total_migrated)
        logger.info("Verification count: %d items in Errands", verify_count)

        if verify_count != total_migrated:
            logger.error(
                "Verification FAILED: migrated %d but found %d -- "
                "NOT deleting ShoppingLists container",
                total_migrated,
                verify_count,
            )
            sys.exit(1)

        # Delete old container
        await database.delete_container(SOURCE_CONTAINER)
        logger.info("Deleted ShoppingLists container")

        # Print summary
        logger.info("--- Migration Summary ---")
        for destination, count in per_destination.items():
            logger.info("  %s: %d", destination, count)
        logger.info("  Total: %d", total_migrated)
        logger.info("  Verification: PASSED")
        logger.info("  Old container: DELETED")

    finally:
        await client.close()
        await credential.close()


if __name__ == "__main__":
    asyncio.run(migrate())
