"""Integration tests for Admin Agent and AdminTools.

These tests require real Azure services. They are skipped when
environment variables are not set.

Run manually: pytest tests/test_admin_integration.py -v -m integration
"""

import os

import pytest

_has_foundry = bool(
    os.environ.get("AZURE_AI_PROJECT_ENDPOINT")
    and os.environ.get("AZURE_AI_ADMIN_AGENT_ID")
)
_has_cosmos = bool(os.environ.get("COSMOS_ENDPOINT"))


@pytest.mark.integration
@pytest.mark.skipif(
    not _has_foundry,
    reason="Requires AZURE_AI_PROJECT_ENDPOINT and AZURE_AI_ADMIN_AGENT_ID",
)
async def test_admin_agent_exists_in_foundry():
    """Admin Agent can be fetched from Foundry by stored agent_id."""
    from agent_framework.azure import AzureAIAgentClient
    from azure.identity.aio import DefaultAzureCredential

    credential = DefaultAzureCredential()
    try:
        client = AzureAIAgentClient(
            credential=credential,
            project_endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
            model_deployment_name="gpt-4o",
        )
        agent = await client.agents_client.get_agent(
            os.environ["AZURE_AI_ADMIN_AGENT_ID"]
        )
        assert agent.id == os.environ["AZURE_AI_ADMIN_AGENT_ID"]
        assert agent.name == "AdminAgent"
    finally:
        await credential.close()


@pytest.mark.integration
@pytest.mark.skipif(not _has_cosmos, reason="Requires COSMOS_ENDPOINT")
async def test_add_shopping_list_items_writes_to_cosmos():
    """AdminTools.add_shopping_list_items writes items to real Cosmos DB."""
    from azure.identity.aio import DefaultAzureCredential

    from second_brain.db.cosmos import CosmosManager
    from second_brain.tools.admin import AdminTools

    credential = DefaultAzureCredential()
    created_items: list[tuple[str, str]] = []  # (store, item_id)

    manager = CosmosManager(
        endpoint=os.environ["COSMOS_ENDPOINT"],
        database_name="second-brain",
    )

    try:
        await manager.initialize()
        admin_tools = AdminTools(cosmos_manager=manager)

        result = await admin_tools.add_shopping_list_items(
            items=[
                {"name": "test_integration_milk", "store": "jewel"},
                {"name": "test_integration_bandages", "store": "cvs"},
            ]
        )

        assert "Added 2 items" in result
        assert "jewel" in result
        assert "cvs" in result

        # Verify items exist -- use store as partition key (NOT "will")
        container = manager.get_container("ShoppingLists")
        async for item in container.query_items(
            query="SELECT * FROM c WHERE STARTSWITH(c.name, 'test_integration_')",
            partition_key="jewel",
        ):
            created_items.append(("jewel", item["id"]))

        async for item in container.query_items(
            query="SELECT * FROM c WHERE STARTSWITH(c.name, 'test_integration_')",
            partition_key="cvs",
        ):
            created_items.append(("cvs", item["id"]))

        assert len(created_items) >= 2

    finally:
        # Cleanup: delete test items
        if manager.containers:
            container = manager.get_container("ShoppingLists")
            for store, item_id in created_items:
                try:
                    await container.delete_item(
                        item=item_id, partition_key=store
                    )
                except Exception:
                    pass
        await manager.close()
        await credential.close()
