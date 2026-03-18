"""Seed initial destinations into the Destinations Cosmos DB container.

Creates the Destinations and AffinityRules containers (via Azure CLI management
plane) and upserts initial DestinationDocuments for all known destinations.

The data plane create_container API returns 403 Forbidden with AAD tokens, so
container creation uses `az cosmosdb sql container create` instead.

Prerequisites:
  - Run `az login` first
  - Set COSMOS_ENDPOINT environment variable
  - Set COSMOS_ACCOUNT_NAME environment variable (e.g., "second-brain-cosmos")
  - Set COSMOS_RESOURCE_GROUP environment variable (e.g., "shared-services-rg")

Usage:
  COSMOS_ENDPOINT=https://... \
  COSMOS_ACCOUNT_NAME=second-brain-cosmos \
  COSMOS_RESOURCE_GROUP=shared-services-rg \
  python3 backend/scripts/seed_destinations.py
"""

import asyncio
import logging
import os
import subprocess
import sys

from azure.cosmos.aio import CosmosClient
from azure.identity.aio import DefaultAzureCredential

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DATABASE_NAME = "second-brain"
PARTITION_KEY = "/userId"

# Containers to create via Azure CLI management plane
CONTAINERS_TO_CREATE = ["Destinations", "AffinityRules"]

# Initial destinations to seed -- current hardcoded list plus CONTEXT.md destinations
INITIAL_DESTINATIONS: list[dict[str, str]] = [
    {"slug": "jewel", "displayName": "Jewel-Osco", "type": "physical"},
    {"slug": "cvs", "displayName": "CVS", "type": "physical"},
    {"slug": "pet_store", "displayName": "PetSmart", "type": "physical"},
    {"slug": "agora", "displayName": "Agora", "type": "physical"},
    {"slug": "gangnam_market", "displayName": "Gangnam Market", "type": "physical"},
    {"slug": "nicks_fishmarket", "displayName": "Nick's Fishmarket", "type": "physical"},
    {"slug": "chewy", "displayName": "Chewy", "type": "online"},
    {"slug": "other", "displayName": "Other", "type": "physical"},
]


def create_container_via_cli(
    account_name: str, resource_group: str, container_name: str
) -> bool:
    """Create a Cosmos DB SQL container using the Azure CLI management plane.

    Returns True if container was created or already exists, False on failure.
    """
    cmd = [
        "az",
        "cosmosdb",
        "sql",
        "container",
        "create",
        "--account-name",
        account_name,
        "--resource-group",
        resource_group,
        "--database-name",
        DATABASE_NAME,
        "--name",
        container_name,
        "--partition-key-path",
        PARTITION_KEY,
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=False, timeout=60
        )
        if result.returncode == 0:
            logger.info("Created container '%s'", container_name)
            return True

        # Container already exists (conflict error)
        if "Conflict" in result.stderr or "already exists" in result.stderr.lower():
            logger.info("Container '%s' already exists", container_name)
            return True

        # Check stdout for conflict too (az cli sometimes puts errors there)
        output = result.stdout + result.stderr
        if "Conflict" in output or "already exists" in output.lower():
            logger.info("Container '%s' already exists", container_name)
            return True

        logger.error(
            "Failed to create container '%s': %s",
            container_name,
            result.stderr.strip() or result.stdout.strip(),
        )
        return False

    except subprocess.TimeoutExpired:
        logger.error("Timed out creating container '%s'", container_name)
        return False
    except FileNotFoundError:
        logger.error(
            "Azure CLI not found. Install it or run: brew install azure-cli"
        )
        return False


async def seed() -> None:
    """Create containers and seed initial destinations."""
    endpoint = os.environ.get("COSMOS_ENDPOINT")
    account_name = os.environ.get("COSMOS_ACCOUNT_NAME")
    resource_group = os.environ.get("COSMOS_RESOURCE_GROUP")

    if not endpoint:
        logger.error("COSMOS_ENDPOINT environment variable is not set")
        sys.exit(1)
    if not account_name:
        logger.error("COSMOS_ACCOUNT_NAME environment variable is not set")
        sys.exit(1)
    if not resource_group:
        logger.error("COSMOS_RESOURCE_GROUP environment variable is not set")
        sys.exit(1)

    # Step 1: Create containers via Azure CLI management plane
    logger.info("--- Creating Cosmos containers ---")
    for container_name in CONTAINERS_TO_CREATE:
        success = create_container_via_cli(account_name, resource_group, container_name)
        if not success:
            logger.error(
                "Cannot proceed without '%s' container. Exiting.", container_name
            )
            sys.exit(1)

    # Step 2: Seed destinations via data plane
    logger.info("--- Seeding destinations ---")
    credential = DefaultAzureCredential()
    client = CosmosClient(url=endpoint, credential=credential)

    try:
        database = client.get_database_client(DATABASE_NAME)
        destinations_container = database.get_container_client("Destinations")

        seeded_count = 0
        for dest in INITIAL_DESTINATIONS:
            doc = {
                "id": dest["slug"],  # Use slug as id for idempotent upserts
                "userId": "will",
                "slug": dest["slug"],
                "displayName": dest["displayName"],
                "type": dest["type"],
            }
            await destinations_container.upsert_item(doc)
            seeded_count += 1
            logger.info(
                "  %s -> %s (%s)",
                dest["slug"],
                dest["displayName"],
                dest["type"],
            )

        # Print summary
        logger.info("--- Seed Summary ---")
        logger.info("  Destinations seeded: %d", seeded_count)
        logger.info("  AffinityRules container: created (empty -- rules come from voice captures)")
        logger.info("  Existing Errands container: unchanged")

    finally:
        await client.close()
        await credential.close()


if __name__ == "__main__":
    asyncio.run(seed())
