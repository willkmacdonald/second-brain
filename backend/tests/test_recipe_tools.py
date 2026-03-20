"""Unit tests for RecipeTools (fetch_recipe_url and _extract_json_ld_recipe).

Tests use mocked Playwright browser -- no real browser or network calls.
"""

from unittest.mock import AsyncMock, MagicMock

from second_brain.tools.recipe import RecipeTools, _extract_json_ld_recipe

# ---------------------------------------------------------------------------
# _extract_json_ld_recipe tests (pure function, no mocking needed)
# ---------------------------------------------------------------------------


class TestExtractJsonLdRecipe:
    """Test JSON-LD recipe extraction from HTML."""

    def test_direct_recipe_type(self) -> None:
        """Extract Recipe when @type is directly 'Recipe'."""
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Recipe", "name": "Pasta", "recipeIngredient": ["pasta", "sauce"]}
        </script>
        </head><body></body></html>
        """
        result = _extract_json_ld_recipe(html)
        assert result is not None
        assert result["@type"] == "Recipe"
        assert result["name"] == "Pasta"

    def test_recipe_in_graph(self) -> None:
        """Extract Recipe from @graph array."""
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@graph": [
            {"@type": "WebPage", "name": "Test"},
            {"@type": "Recipe", "name": "Soup", "recipeIngredient": ["water"]}
        ]}
        </script>
        </head><body></body></html>
        """
        result = _extract_json_ld_recipe(html)
        assert result is not None
        assert result["@type"] == "Recipe"
        assert result["name"] == "Soup"

    def test_recipe_in_list(self) -> None:
        """Extract Recipe from a top-level JSON-LD list."""
        html = """
        <html><head>
        <script type="application/ld+json">
        [
            {"@type": "Organization", "name": "Test Corp"},
            {"@type": "Recipe", "name": "Tacos"}
        ]
        </script>
        </head><body></body></html>
        """
        result = _extract_json_ld_recipe(html)
        assert result is not None
        assert result["name"] == "Tacos"

    def test_no_json_ld_scripts(self) -> None:
        """Return None when no JSON-LD scripts exist."""
        html = "<html><head></head><body>Hello</body></html>"
        result = _extract_json_ld_recipe(html)
        assert result is None

    def test_non_recipe_json_ld(self) -> None:
        """Return None when JSON-LD exists but no Recipe type."""
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Organization", "name": "Test Corp"}
        </script>
        </head><body></body></html>
        """
        result = _extract_json_ld_recipe(html)
        assert result is None

    def test_malformed_json(self) -> None:
        """Return None when JSON-LD contains malformed JSON."""
        html = """
        <html><head>
        <script type="application/ld+json">
        {not valid json at all}
        </script>
        </head><body></body></html>
        """
        result = _extract_json_ld_recipe(html)
        assert result is None

    def test_multiple_scripts_picks_recipe(self) -> None:
        """When multiple JSON-LD blocks exist, find the Recipe one."""
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Organization", "name": "Test Corp"}
        </script>
        <script type="application/ld+json">
        {"@type": "Recipe", "name": "Curry"}
        </script>
        </head><body></body></html>
        """
        result = _extract_json_ld_recipe(html)
        assert result is not None
        assert result["name"] == "Curry"


# ---------------------------------------------------------------------------
# fetch_recipe_url tests (mocked Playwright browser)
# ---------------------------------------------------------------------------


def _build_mock_browser(
    *,
    visible_text: str = "Some recipe text",
    html: str = "<html><body>Some recipe text</body></html>",
    goto_side_effect: Exception | None = None,
) -> MagicMock:
    """Build a mock Playwright Browser with page behavior."""
    mock_page = AsyncMock()
    mock_page.route = AsyncMock()
    if goto_side_effect:
        mock_page.goto = AsyncMock(side_effect=goto_side_effect)
    else:
        mock_page.goto = AsyncMock()
    mock_page.evaluate = AsyncMock(return_value=visible_text)
    mock_page.content = AsyncMock(return_value=html)

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_context.close = AsyncMock()

    mock_browser = MagicMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)

    return mock_browser


class TestFetchRecipeUrl:
    """Test the fetch_recipe_url tool method."""

    async def test_successful_fetch_returns_page_text(self) -> None:
        """Successful fetch returns visible text content."""
        browser = _build_mock_browser(visible_text="Chicken Tikka Recipe")
        tools = RecipeTools(browser=browser)

        result = await tools.fetch_recipe_url(url="https://example.com/recipe")

        assert "PAGE TEXT:" in result
        assert "Chicken Tikka Recipe" in result

    async def test_successful_fetch_with_json_ld(self) -> None:
        """Successful fetch includes JSON-LD when present."""
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Recipe", "name": "Test Recipe"}
        </script>
        </head><body>Some text</body></html>
        """
        browser = _build_mock_browser(
            visible_text="Some text",
            html=html,
        )
        tools = RecipeTools(browser=browser)

        result = await tools.fetch_recipe_url(url="https://example.com/recipe")

        assert "STRUCTURED RECIPE DATA (JSON-LD):" in result
        assert "Test Recipe" in result
        assert "PAGE TEXT:" in result

    async def test_fetch_failure_returns_error_string(self) -> None:
        """Navigation failure returns error message string."""
        browser = _build_mock_browser(
            goto_side_effect=TimeoutError("Page load timed out"),
        )
        tools = RecipeTools(browser=browser)

        result = await tools.fetch_recipe_url(url="https://example.com/slow")

        assert "Error fetching" in result
        assert "TimeoutError" in result

    async def test_context_closed_on_success(self) -> None:
        """Browser context is closed after successful fetch."""
        browser = _build_mock_browser()
        tools = RecipeTools(browser=browser)

        await tools.fetch_recipe_url(url="https://example.com/recipe")

        context = browser.new_context.return_value
        context.close.assert_awaited_once()

    async def test_context_closed_on_error(self) -> None:
        """Browser context is closed even when navigation fails."""
        browser = _build_mock_browser(
            goto_side_effect=TimeoutError("timeout"),
        )
        tools = RecipeTools(browser=browser)

        await tools.fetch_recipe_url(url="https://example.com/slow")

        context = browser.new_context.return_value
        context.close.assert_awaited_once()

    async def test_empty_page_returns_error(self) -> None:
        """Page with no visible text and no JSON-LD returns error."""
        browser = _build_mock_browser(
            visible_text="",
            html="<html><body></body></html>",
        )
        tools = RecipeTools(browser=browser)

        result = await tools.fetch_recipe_url(url="https://example.com/empty")

        assert "Error: Page at" in result
        assert "no extractable content" in result

    async def test_text_truncated_to_limit(self) -> None:
        """Visible text longer than 12000 chars is truncated."""
        long_text = "x" * 20000
        browser = _build_mock_browser(visible_text=long_text)
        tools = RecipeTools(browser=browser)

        result = await tools.fetch_recipe_url(url="https://example.com/long")

        # The full text should be truncated; result should not have 20k chars
        # 12000 chars of text + "PAGE TEXT:\n" prefix
        assert len(result) < 15000
