"""Recipe scraping emits a workload event per fetch."""

import socket
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from second_brain.tools.recipe import RecipeTools


@pytest.fixture(autouse=True)
def mock_dns_resolution():
    """Prevent live DNS resolution in recipe URL tests."""
    fake_addr = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]
    with patch("second_brain.tools.recipe.socket.getaddrinfo", return_value=fake_addr):
        yield


@pytest.mark.asyncio
async def test_recipe_fetch_success_emits_workload_event() -> None:
    browser = MagicMock()
    repo = AsyncMock()
    tools = RecipeTools(browser, spine_repo=repo)

    with (
        patch.object(tools, "_fetch_jina", new=AsyncMock(return_value="x" * 600)),
        patch("second_brain.tools.recipe._is_safe_url", return_value=True),
    ):
        await tools.fetch_recipe_url(url="https://example.com/recipe")

    repo.record_event.assert_called()
    event = repo.record_event.call_args[0][0]
    # SPIKE-MEMO §5.3 — recipe now emits via emit_agent_workload which wraps
    # in IngestEvent(root=...); read through `.root`.
    assert event.root.segment_id == "external_services"
    assert event.root.payload.outcome == "success"
    assert "jina" in event.root.payload.operation


@pytest.mark.asyncio
async def test_recipe_fetch_all_tiers_failed_emits_failure() -> None:
    browser = MagicMock()
    repo = AsyncMock()
    tools = RecipeTools(browser, spine_repo=repo)

    with (
        patch.object(
            tools,
            "_fetch_jina",
            new=AsyncMock(return_value=""),
        ),
        patch.object(
            tools,
            "_fetch_simple",
            new=AsyncMock(return_value=("", "", "httpx-failed")),
        ),
        patch.object(
            tools,
            "_fetch_playwright",
            new=AsyncMock(return_value=("", "", "playwright-failed")),
        ),
        patch("second_brain.tools.recipe._is_safe_url", return_value=True),
    ):
        await tools.fetch_recipe_url(url="https://example.com/recipe")

    # Should have emitted a failure workload event
    repo.record_event.assert_called()
    event = repo.record_event.call_args[0][0]
    assert event.root.segment_id == "external_services"
    # All tiers returned empty content, so outcome is "failure"
    assert event.root.payload.outcome == "failure"


@pytest.mark.asyncio
async def test_recipe_fetch_no_repo_does_not_crash() -> None:
    """When spine_repo is None, no emission happens and fetch still works."""
    browser = MagicMock()
    tools = RecipeTools(browser)  # no spine_repo

    with (
        patch.object(tools, "_fetch_jina", new=AsyncMock(return_value="x" * 600)),
        patch("second_brain.tools.recipe._is_safe_url", return_value=True),
    ):
        result = await tools.fetch_recipe_url(url="https://example.com/recipe")

    assert "x" * 100 in result
