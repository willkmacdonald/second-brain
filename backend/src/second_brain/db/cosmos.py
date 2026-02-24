"""Cosmos DB async singleton client with container accessors.

CosmosManager manages the lifecycle of the async Cosmos client --
initialization at startup, container access during operation, and
cleanup at shutdown. This class is justified per CLAUDE.md guidelines
as it manages a stateful client with lifecycle (connection pool,
startup/shutdown).
"""

import logging

from azure.cosmos.aio import ContainerProxy, CosmosClient
from azure.identity.aio import DefaultAzureCredential

logger = logging.getLogger(__name__)

CONTAINER_NAMES: list[str] = ["Inbox", "People", "Projects", "Ideas", "Admin"]
PARTITION_KEY = "/userId"


class CosmosManager:
    """Manages the async Cosmos DB client singleton.

    Usage:
        manager = CosmosManager(endpoint="https://...", database_name="second-brain")
        await manager.initialize()
        container = manager.get_container("Inbox")
        # ... use container ...
        await manager.close()
    """

    def __init__(self, endpoint: str, database_name: str) -> None:
        """Store config. Client is not yet created -- call initialize()."""
        self._endpoint = endpoint
        self._database_name = database_name
        self._credential: DefaultAzureCredential | None = None
        self._client: CosmosClient | None = None
        self.containers: dict[str, ContainerProxy] = {}

    async def initialize(self) -> None:
        """Create the async Cosmos client and get container references.

        Uses DefaultAzureCredential for Azure AD auth (az login locally,
        managed identity in production).
        """
        self._credential = DefaultAzureCredential()
        self._client = CosmosClient(
            url=self._endpoint,
            credential=self._credential,
        )
        database = self._client.get_database_client(self._database_name)

        for name in CONTAINER_NAMES:
            self.containers[name] = database.get_container_client(name)

        logger.info(
            "Cosmos DB initialized: database=%s, containers=%s",
            self._database_name,
            list(self.containers.keys()),
        )

    async def close(self) -> None:
        """Close the Cosmos client and credential."""
        if self._client is not None:
            await self._client.close()
            logger.info("Cosmos DB client closed")
        if self._credential is not None:
            await self._credential.close()

    def get_container(self, name: str) -> ContainerProxy:
        """Return a container proxy by name.

        Raises:
            ValueError: If the container name is not one of the 5 known containers.
        """
        if name not in self.containers:
            valid = ", ".join(CONTAINER_NAMES)
            msg = f"Unknown container '{name}'. Valid containers: {valid}"
            raise ValueError(msg)
        return self.containers[name]
