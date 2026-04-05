"""LogsQueryClient lifecycle management for App Insights queries."""

import logging

from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential
from azure.monitor.query.aio import LogsQueryClient

logger = logging.getLogger(__name__)


def create_logs_client(
    credential: AsyncDefaultAzureCredential,
) -> LogsQueryClient:
    """Create a LogsQueryClient using an existing async credential.

    The credential is owned by the FastAPI lifespan -- this function does NOT
    create or close it.
    """
    client = LogsQueryClient(credential=credential)
    logger.info("LogsQueryClient created")
    return client


async def close_logs_client(client: LogsQueryClient) -> None:
    """Close the LogsQueryClient during shutdown."""
    await client.close()
    logger.info("LogsQueryClient closed")
