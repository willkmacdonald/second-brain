"""URL fetching tools for page content extraction.

Three-tier fetch strategy:
1. Jina Reader (r.jina.ai) — returns clean markdown, bypasses bot protection
2. Simple HTTP (httpx) — fast, direct fetch for sites that allow it
3. Playwright headless browser — fallback for JS-rendered pages

Returns extracted text for LLM-based classification and ingredient extraction.
"""

import json
import logging
import re
from typing import Annotated
from urllib.parse import urlparse, urlunparse

import httpx
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

JINA_READER_PREFIX = "https://r.jina.ai/"

# Minimum text length to consider a fetch successful
MIN_CONTENT_LENGTH = 500


class RecipeTools:
    """URL fetching tools bound to a Playwright Browser instance."""

    def __init__(self, browser: Browser) -> None:
        self._browser = browser

    @tool(approval_mode="never_require")
    async def fetch_recipe_url(
        self,
        url: Annotated[
            str,
            Field(
                description="The webpage URL to fetch and extract content from"
            ),
        ],
    ) -> str:
        """Fetch a webpage and extract its content.

        Tries Jina Reader first (clean markdown, bypasses bot protection),
        then simple HTTP, then headless browser as fallback.
        Returns the extracted content for the agent to parse.

        If the page cannot be loaded or contains no useful content,
        returns an error message.
        """
        logger.warning("fetch_recipe_url called for: %s", url)

        # Normalize known problematic URL patterns
        url = _normalize_url(url)
        logger.warning("fetch_recipe_url normalized to: %s", url)

        # Tier 1: Jina Reader (bypasses Cloudflare/bot protection)
        text = await self._fetch_jina(url)

        # Tier 2: Simple HTTP if Jina failed
        html = ""
        source = "jina"
        if not text or len(text) < MIN_CONTENT_LENGTH:
            logger.warning(
                "fetch_recipe_url: Jina insufficient (text_length=%d), "
                "trying httpx",
                len(text) if text else 0,
            )
            http_text, html, source = await self._fetch_simple(url)
            if http_text and len(http_text) > len(text or ""):
                text = http_text

        # Tier 3: Playwright if still insufficient
        if not text or len(text) < MIN_CONTENT_LENGTH:
            logger.warning(
                "fetch_recipe_url: httpx insufficient (text_length=%d), "
                "trying Playwright",
                len(text) if text else 0,
            )
            pw_text, pw_html, source = await self._fetch_playwright(url)
            if pw_text and len(pw_text) > len(text or ""):
                text = pw_text
                html = pw_html

        logger.warning(
            "fetch_recipe_url: final text_length=%d source=%s first_200=%s",
            len(text) if text else 0,
            source,
            (text[:200] if text else "(empty)"),
        )

        # Extract JSON-LD structured data if we have HTML
        json_ld = _extract_json_ld_recipe(html) if html else None

        # Build response for the agent
        parts: list[str] = []
        if json_ld:
            json_str = json.dumps(json_ld, indent=2)
            parts.append(f"STRUCTURED RECIPE DATA (JSON-LD):\n{json_str}")

        # Truncate text to fit LLM context (~12k chars = ~3k tokens)
        truncated_text = text[:12000] if text else ""
        if truncated_text:
            parts.append(f"PAGE TEXT:\n{truncated_text}")

        if not parts:
            logger.warning(
                "fetch_recipe_url: no extractable content for %s", url
            )
            return (
                f"Error: Page at {url} loaded but contained no "
                f"extractable content."
            )

        logger.warning(
            "fetch_recipe_url success: %d parts, total_chars=%d",
            len(parts),
            sum(len(p) for p in parts),
        )
        return "\n\n---\n\n".join(parts)

    async def _fetch_jina(self, url: str) -> str:
        """Fetch via Jina Reader. Returns clean markdown text."""
        try:
            jina_url = f"{JINA_READER_PREFIX}{url}"
            async with httpx.AsyncClient(
                timeout=30.0,
                headers={"Accept": "text/plain"},
            ) as client:
                resp = await client.get(jina_url)
                resp.raise_for_status()
                text = resp.text
                logger.warning(
                    "Jina Reader succeeded for %s: %d chars", url, len(text)
                )
                return text
        except Exception as exc:
            logger.warning("Jina Reader failed for %s: %s", url, exc)
            return ""

    async def _fetch_simple(self, url: str) -> tuple[str, str, str]:
        """Fetch via httpx. Returns (visible_text, html, source_label)."""
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=30.0,
                headers={"User-Agent": USER_AGENT},
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                html = resp.text

            soup = BeautifulSoup(html, "lxml")

            # Remove script/style elements before extracting text
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()

            text = soup.get_text(separator="\n", strip=True)
            return text, html, "httpx"

        except Exception as exc:
            logger.warning("Simple HTTP fetch failed for %s: %s", url, exc)
            return "", "", "httpx-failed"

    async def _fetch_playwright(self, url: str) -> tuple[str, str, str]:
        """Fetch via Playwright headless browser. Returns (visible_text, html, source_label)."""
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

            # Navigate with 30-second timeout, wait for network to settle
            await page.goto(url, timeout=30000, wait_until="networkidle")

            # Wait for body to have meaningful text (up to 10s)
            try:
                await page.wait_for_function(
                    "(document.body.innerText || '').length > 500",
                    timeout=10000,
                )
            except Exception:
                pass  # Continue with whatever we have

            visible_text = await page.evaluate("document.body.innerText")
            html = await page.content()
            return visible_text or "", html or "", "playwright"

        except Exception as exc:
            logger.warning("Playwright fetch failed for %s: %s", url, exc)
            return "", "", "playwright-failed"
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
                            if (
                                isinstance(item, dict)
                                and item.get("@type") == "Recipe"
                            ):
                                return item
                elif isinstance(data, list):
                    for item in data:
                        if (
                            isinstance(item, dict)
                            and item.get("@type") == "Recipe"
                        ):
                            return item
            except (json.JSONDecodeError, TypeError):
                continue
    except Exception:
        pass
    return None


def _normalize_url(url: str) -> str:
    """Rewrite known problematic URL patterns to their canonical form.

    - open.substack.com/pub/{name}/p/{slug} → {name}.substack.com/p/{slug}
      Substack's share URLs use open.substack.com which serves a JS-only
      redirect page. The canonical subdomain URL works with Jina Reader.
    """
    parsed = urlparse(url)

    if parsed.hostname == "open.substack.com":
        match = re.match(r"/pub/([^/]+)/p/(.+)", parsed.path)
        if match:
            publication, slug = match.group(1), match.group(2)
            canonical = parsed._replace(
                netloc=f"{publication}.substack.com",
                path=f"/p/{slug}",
            )
            return urlunparse(canonical)

    return url
