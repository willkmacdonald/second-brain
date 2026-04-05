"""Create Feedback, EvalResults, and GoldenDataset Cosmos DB containers.

Prerequisites:
  - Run `az login` first (uses DefaultAzureCredential)
  - Set COSMOS_ENDPOINT environment variable

Usage:
  python3 backend/scripts/create_eval_containers.py
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

EVAL_CONTAINERS: list[tuple[str, str]] = [
    ("Feedback", "/userId"),
    ("EvalResults", "/userId"),
    ("GoldenDataset", "/userId"),
]


async def create_containers() -> None:
    """Create eval containers in Cosmos DB."""
    endpoint = os.environ.get("COSMOS_ENDPOINT")
    if not endpoint:
        logger.error("COSMOS_ENDPOINT environment variable is not set")
        sys.exit(1)

    credential = DefaultAzureCredential()
    client = CosmosClient(url=endpoint, credential=credential)

    try:
        database = client.get_database_client(DATABASE_NAME)

        for container_name, partition_key in EVAL_CONTAINERS:
            try:
                await database.create_container(
                    id=container_name,
                    partition_key={
                        "paths": [partition_key],
                        "kind": "Hash",
                    },
                )
                logger.info(
                    "Created container '%s' with partition key '%s'",
                    container_name,
                    partition_key,
                )
            except CosmosResourceExistsError:
                logger.info(
                    "Container '%s' already exists",
                    container_name,
                )
    finally:
        await client.close()
        await credential.close()


if __name__ == "__main__":
    asyncio.run(create_containers())
