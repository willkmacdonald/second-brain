"""Recipe URL fetching tools for the Admin Agent.

Uses Playwright headless browser to fetch recipe web pages, extract visible
text and JSON-LD structured data, and return content for LLM-based ingredient
extraction.
"""

import json
import logging
from typing import Annotated

from agent_framework import tool
from bs4 import BeautifulSoup
from playwright.async_api import Browser, Route
from pydantic import Field

logger = logging.getLogger(__name__)

BLOCKED_RESOURCE_TYPES = {"image", "media", "font", "stylesheet"}

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


class RecipeTools:
    """Recipe URL fetching tools bound to a Playwright Browser instance."""

    def __init__(self, browser: Browser) -> None:
        self._browser = browser

    @tool(approval_mode="never_require")
    async def fetch_recipe_url(
        self,
        url: Annotated[
            str,
            Field(
                description="The recipe webpage URL to fetch and extract content from"
            ),
        ],
    ) -> str:
        """Fetch a recipe webpage and extract its content for ingredient parsing.

        Launches a headless browser page, navigates to the URL, blocks
        non-essential resources (images, CSS, fonts, media), and extracts
        the page's visible text content plus any JSON-LD recipe structured
        data. Returns the extracted content for the agent to parse into
        ingredients.

        If the page cannot be loaded or contains no useful content,
        returns an error message.
        """
        logger.warning("fetch_recipe_url called for: %s", url)
        context = await self._browser.new_context(user_agent=USER_AGENT)
        try:
            page = await context.new_page()

            # Block non-essential resources
            async def block_resources(route: Route) -> None:
                if route.request.resource_type in BLOCKED_RESOURCE_TYPES:
                    await route.abort()
                else:
                    await route.continue_()

            await page.route("**/*", block_resources)

            # Navigate with 30-second timeout
            await page.goto(url, timeout=30000, wait_until="domcontentloaded")

            # Extract visible text
            visible_text = await page.evaluate("document.body.innerText")
            logger.warning(
                "fetch_recipe_url text length=%d first_200=%s",
                len(visible_text) if visible_text else 0,
                (visible_text[:200] if visible_text else "(empty)"),
            )

            # Extract JSON-LD structured data if present
            html = await page.content()
            json_ld = _extract_json_ld_recipe(html)
            logger.warning(
                "fetch_recipe_url json_ld=%s html_length=%d",
                "found" if json_ld else "none",
                len(html),
            )

            # Build response for the agent
            parts: list[str] = []
            if json_ld:
                json_str = json.dumps(json_ld, indent=2)
                parts.append(
                    f"STRUCTURED RECIPE DATA (JSON-LD):\n{json_str}"
                )

            # Truncate visible text to fit LLM context (~12k chars = ~3k tokens)
            truncated_text = visible_text[:12000] if visible_text else ""
            if truncated_text:
                parts.append(f"PAGE TEXT:\n{truncated_text}")

            if not parts:
                logger.warning("fetch_recipe_url: no extractable content for %s", url)
                return (
                    f"Error: Page at {url} loaded but contained no extractable content."
                )

            logger.warning(
                "fetch_recipe_url success: %d parts, total_chars=%d",
                len(parts),
                sum(len(p) for p in parts),
            )
            return "\n\n---\n\n".join(parts)

        except Exception as exc:
            logger.warning("fetch_recipe_url failed for %s: %s", url, exc)
            return f"Error fetching {url}: {type(exc).__name__} - {exc}"
        finally:
            await context.close()


def _extract_json_ld_recipe(html: str) -> dict | None:
    """Extract Recipe schema.org JSON-LD from HTML if present."""
    try:
        soup = BeautifulSoup(html, "lxml")
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                # Handle both direct Recipe and @graph arrays
                if isinstance(data, dict):
                    if data.get("@type") == "Recipe":
                        return data
                    if "@graph" in data:
                        for item in data["@graph"]:
                            if isinstance(item, dict) and item.get("@type") == "Recipe":
                                return item
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get("@type") == "Recipe":
                            return item
            except (json.JSONDecodeError, TypeError):
                continue
    except Exception:
        pass
    return None
