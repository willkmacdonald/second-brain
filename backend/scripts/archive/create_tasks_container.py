"""Create the Tasks Cosmos DB container.

Prerequisites:
  - Run `az login` first (uses DefaultAzureCredential)
  - Set COSMOS_ENDPOINT environment variable

Usage:
  python3 backend/scripts/create_tasks_container.py
"""

import asyncio
import logging
import os
import sys

from azure.cosmos.aio import CosmosClient
from azure.cosmos.exceptions import CosmosResourceExistsError
from azure.identity.aio import DefaultAzureCredential

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DATABASE_NAME = "second-brain"
CONTAINER_NAME = "Tasks"
PARTITION_KEY = "/userId"


async def create_container() -> None:
    """Create the Tasks container in Cosmos DB."""
    endpoint = os.environ.get("COSMOS_ENDPOINT")
    if not endpoint:
        logger.error("COSMOS_ENDPOINT environment variable is not set")
        sys.exit(1)

    credential = DefaultAzureCredential()
    client = CosmosClient(url=endpoint, credential=credential)

    try:
        database = client.get_database_client(DATABASE_NAME)

        try:
            container = await database.create_container(
                id=CONTAINER_NAME,
                partition_key={"paths": [PARTITION_KEY], "kind": "Hash"},
            )
            logger.info(
                "Created container '%s' with partition key '%s'",
                CONTAINER_NAME,
                PARTITION_KEY,
            )
        except CosmosResourceExistsError:
            logger.info("Container '%s' already exists", CONTAINER_NAME)

    finally:
        await client.close()
        await credential.close()


if __name__ == "__main__":
    asyncio.run(create_container())
