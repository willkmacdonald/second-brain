"""Azure Blob Storage manager for voice recording uploads.

BlobStorageManager manages the lifecycle of the async Blob Storage client —
initialization at startup, upload/delete during operation, and cleanup at
shutdown. Follows the same singleton pattern as CosmosManager.
"""

import logging
from uuid import uuid4

from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob import ContentSettings
from azure.storage.blob.aio import BlobServiceClient

logger = logging.getLogger(__name__)

VOICE_CONTAINER = "voice-recordings"


class BlobStorageManager:
    """Manages async Azure Blob Storage client for voice recordings.

    Usage:
        manager = BlobStorageManager(account_url="https://mystorageaccount.blob.core.windows.net")
        await manager.initialize()
        url = await manager.upload_audio(audio_bytes, "recording.m4a")
        await manager.delete_audio(url)
        await manager.close()
    """

    def __init__(self, account_url: str) -> None:
        """Store config. Client is not yet created — call initialize()."""
        self._account_url = account_url
        self._credential: DefaultAzureCredential | None = None
        self._client: BlobServiceClient | None = None

    async def initialize(self) -> None:
        """Create the async Blob Storage client with Azure AD auth."""
        self._credential = DefaultAzureCredential()
        self._client = BlobServiceClient(
            account_url=self._account_url,
            credential=self._credential,
        )
        logger.info(
            "Blob Storage initialized: account_url=%s, container=%s",
            self._account_url,
            VOICE_CONTAINER,
        )

    async def upload_audio(
        self,
        audio_bytes: bytes,
        filename: str,
        user_id: str = "will",
    ) -> str:
        """Upload audio bytes to Blob Storage and return the blob URL.

        Args:
            audio_bytes: Raw audio file bytes.
            filename: Original filename (used for extension fallback).
            user_id: User ID for blob path prefix.

        Returns:
            Full URL of the uploaded blob.
        """
        if self._client is None:
            msg = "BlobStorageManager not initialized — call initialize() first"
            raise RuntimeError(msg)

        blob_name = f"{user_id}/{uuid4()}.m4a"
        container_client = self._client.get_container_client(VOICE_CONTAINER)
        blob_client = container_client.get_blob_client(blob_name)

        await blob_client.upload_blob(
            audio_bytes,
            content_settings=ContentSettings(content_type="audio/m4a"),
            overwrite=True,
        )

        logger.info("Uploaded audio blob: %s (%d bytes)", blob_name, len(audio_bytes))
        return blob_client.url

    async def delete_audio(self, blob_url: str) -> None:
        """Delete a blob by its full URL.

        Non-fatal — logs warning on failure since orphaned blobs are harmless.
        """
        if self._client is None:
            logger.warning("BlobStorageManager not initialized, skipping delete")
            return

        try:
            # Extract blob name from URL: https://account.blob.core.windows.net/container/path
            # Split on container name to get the blob path
            container_and_blob = blob_url.split(f"{VOICE_CONTAINER}/", 1)
            if len(container_and_blob) < 2:
                logger.warning("Could not parse blob name from URL: %s", blob_url)
                return

            blob_name = container_and_blob[1]
            container_client = self._client.get_container_client(VOICE_CONTAINER)
            blob_client = container_client.get_blob_client(blob_name)
            await blob_client.delete_blob()
            logger.info("Deleted audio blob: %s", blob_name)
        except Exception:
            logger.warning("Failed to delete blob: %s", blob_url, exc_info=True)

    async def close(self) -> None:
        """Close the Blob Storage client and credential."""
        if self._client is not None:
            await self._client.close()
            logger.info("Blob Storage client closed")
        if self._credential is not None:
            await self._credential.close()
