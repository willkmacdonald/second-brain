# Phase 13: Recipe URL Extraction - Research

**Researched:** 2026-03-20
**Domain:** Web scraping (Playwright), LLM-based content extraction, Admin Agent tool extension
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Backend-side fetch via a new Admin Agent @tool (not mobile client) -- tool handles Playwright launch, page load, and content extraction all in one
- Use headless browser (Playwright) inside the backend Docker container for JS-rendered pages
- 30-second page load timeout
- Block non-essential resources (images, CSS, fonts, media) during page load -- only load HTML/JS needed for content
- Set realistic browser user-agent headers to improve success rate on sites that block scrapers; fail gracefully if still blocked
- Playwright added to the existing container image -- no separate service
- **Always run LLM** -- even when JSON-LD Recipe schema is found, pass through LLM to normalize format and handle store assignment in one step
- LLM extracts recipe name + ingredients together (recipe name used for source attribution)
- **Shopper-friendly format** -- LLM normalizes ingredient text to what you'd look for in-store (e.g., "Diced tomatoes (14 oz can)" not "1 can (14 oz) diced tomatoes")
- Include quantities in ingredient names
- **Include all items** -- no filtering of pantry staples (salt, pepper, oil, water)
- Allow duplicate items -- if "milk" already exists on the list and the recipe also needs milk, add another entry with the recipe quantity
- LLM assigns each ingredient to the appropriate store based on Admin Agent instructions
- Shopping list items from recipes include optional `sourceName` and `sourceUrl` fields (null for regular items)
- Data model: add optional `sourceName: str | None` and `sourceUrl: str | None` to ErrandItem
- Recipe items are interspersed normally in the shopping list -- no special grouping or sections
- **Always-visible subtitle** under recipe items: "from: Chicken Tikka Masala" in subtle secondary text (muted gray, smaller font)
- Tapping the subtitle opens the source URL in the device browser
- Recipe items behave exactly like regular items when checked off -- no special tracking
- **No classifier changes needed** -- user types "admin" prefix + URL, classifier routes to Admin as usual
- Admin Agent always fetches URLs -- if the Admin Agent sees a URL in the input text, it always invokes the fetch tool
- Not a recipe? Just extract what it can. If no recipe content found, report "No recipe found on this page."
- Fetch failure (timeout, 404, blocked): Inbox item stays visible with error status/message
- Not a recipe (page loads but no recipe content): Same pattern -- inbox item stays with error
- Partial extraction: If only some ingredients extracted, add what was found
- Success feedback: Status screen shows summary like "8 items added to 2 stores from Chicken Tikka Masala"
- Retry: User re-pastes URL. No retry button UI. No duplicate URL detection
- 30-second timeout for Playwright page loads

### Claude's Discretion
- Playwright configuration details (browser flags, specific resource types to block)
- JSON-LD parsing implementation details
- Exact LLM prompt for ingredient extraction and store assignment
- How much page content to send to the LLM (truncation strategy)
- Error message wording
- User-agent string choice

### Deferred Ideas (OUT OF SCOPE)
- Automated online ordering (browser automation for Chewy, etc.)
- YouTube recipe extraction (video captions)
- URL routing for other buckets (Ideas, notes, etc.)
- Smart classifier URL routing (auto-detect recipe URLs by domain)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| RCPE-01 | User can paste any recipe webpage URL that gets classified as Admin, and Admin Agent extracts recipe ingredients from the page | New `fetch_recipe_url` Admin Agent @tool using Playwright for page fetch + LLM extraction. Tool returns structured ingredient list. Admin Agent sees URL in input, calls the tool, then calls `add_errand_items` with extracted ingredients. |
| RCPE-02 | Extracted ingredients are added to the appropriate grocery store shopping list | Existing `add_errand_items` tool already handles destination routing via Admin Agent instructions + affinity rules. New tool must return ingredients in a format the Agent can pass to `add_errand_items`. sourceName/sourceUrl fields added to ErrandItem model. |
| RCPE-03 | Shopping list items from recipes show source attribution (recipe name/URL) | New optional `sourceName` and `sourceUrl` fields on ErrandItem Cosmos documents. `add_errand_items` tool extended to accept these fields. Mobile ErrandRow component updated with subtitle + Linking.openURL tap handler. API response model updated. |
</phase_requirements>

## Summary

Phase 13 adds a new Admin Agent tool (`fetch_recipe_url`) that uses Playwright to fetch any recipe webpage, extracts the page content, and passes it to the LLM for ingredient extraction with store assignment. The implementation touches three layers: (1) Docker/infrastructure -- adding Playwright + Chromium to the container image, (2) Backend -- new tool, extended data model, modified `add_errand_items`, and updated API response, (3) Mobile -- source attribution subtitle on ErrandRow with tappable URL.

The biggest technical change is adding Playwright and Chromium to the Docker container. This increases the image size substantially (~400-600 MB for Chromium + dependencies) but is a locked decision with future-proofing rationale (browser automation for ordering in later phases). The `playwright install --with-deps chromium` command handles both browser binary and system library installation. The existing `python:3.12-slim-bookworm` multi-stage build needs modification to install system dependencies in the runtime stage.

The LLM extraction approach is straightforward -- the Admin Agent already has routing context (destinations + affinity rules) injected before processing. The new tool fetches the page, extracts visible text (with JSON-LD as supplementary context if present), and returns it to the Agent. The Agent then uses its existing instructions + routing context to assign each ingredient to a destination and call `add_errand_items`.

**Primary recommendation:** Add Playwright as a long-lived browser instance managed in FastAPI's lifespan, create a single new `fetch_recipe_url` @tool that handles the full fetch-and-extract pipeline, extend ErrandItem with optional source fields, and update the mobile ErrandRow for source attribution display.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| playwright | 1.58.0 | Headless Chromium browser automation | Official Microsoft library; best Python async support; handles JS-rendered pages; future-proof for browser automation phases |
| beautifulsoup4 | 4.12+ | HTML parsing for JSON-LD extraction | Standard HTML parser; lightweight; only needed for `<script type="application/ld+json">` tag extraction before passing to LLM |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| lxml | latest | Fast HTML parser backend for BeautifulSoup | Use as BS4 parser for speed; `BeautifulSoup(html, 'lxml')` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Playwright | httpx/aiohttp (plain HTTP) | Would miss JS-rendered content; many recipe sites use React/Next.js; locked decision is Playwright |
| BeautifulSoup | regex for JSON-LD | Fragile; BS4 is tiny dependency and handles edge cases (multiple JSON-LD blocks, malformed HTML) |
| Dedicated recipe-scrapers lib | recipe-scrapers PyPI package | Only works on known sites with specific parsers; LLM approach is universal per CONTEXT.md |

**Installation:**
```bash
uv pip install playwright beautifulsoup4 lxml
playwright install --with-deps chromium
```

## Architecture Patterns

### Recommended Project Structure
```
backend/src/second_brain/
├── tools/
│   ├── admin.py              # Existing: add_errand_items (extended), routing tools
│   └── recipe.py             # NEW: fetch_recipe_url tool + Playwright helpers
├── models/
│   └── documents.py          # Modified: ErrandItem gets sourceName, sourceUrl
├── api/
│   └── errands.py            # Modified: ErrandItemResponse gets sourceName, sourceUrl
├── processing/
│   └── admin_handoff.py      # Modified: success summary for recipe results
└── main.py                   # Modified: Playwright lifecycle + register new tool
```

### Pattern 1: Playwright Browser Lifecycle in FastAPI Lifespan

**What:** Launch Playwright and Chromium once at app startup, store on `app.state`, close at shutdown. Individual page fetches create new browser contexts (cheap, isolated) from the shared browser instance.

**When to use:** Always -- browser launch is expensive (~2-3 seconds). Reusing a single browser instance across requests avoids cold-start penalty per fetch.

**Example:**
```python
# In main.py lifespan
from playwright.async_api import async_playwright

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing setup ...

    # Launch Playwright browser (after admin tools setup)
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=True,
        args=[
            "--disable-dev-shm-usage",  # Use /tmp instead of /dev/shm
            "--disable-gpu",
            "--no-sandbox",  # Required for non-root in container
            "--disable-software-rasterizer",
        ],
    )
    app.state.playwright = pw
    app.state.browser = browser

    yield

    # Cleanup (reverse order)
    await browser.close()
    await pw.stop()
    # ... existing cleanup ...
```

### Pattern 2: New Tool with Page Fetch + Content Extraction

**What:** A single `fetch_recipe_url` @tool that the Admin Agent calls when it sees a URL. The tool handles: page fetch via Playwright, resource blocking, content extraction (visible text + JSON-LD), and returns the content for the Agent to process.

**When to use:** Every time Admin Agent processes a capture containing a URL.

**Example:**
```python
# tools/recipe.py
import json
import logging
import re
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
            Field(description="The recipe webpage URL to fetch and extract content from"),
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
        context = await self._browser.new_context(
            user_agent=USER_AGENT,
        )
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

            # Extract JSON-LD structured data if present
            html = await page.content()
            json_ld = _extract_json_ld_recipe(html)

            # Build response for the agent
            parts = []
            if json_ld:
                parts.append(f"STRUCTURED RECIPE DATA (JSON-LD):\n{json.dumps(json_ld, indent=2)}")

            # Truncate visible text to fit LLM context
            truncated_text = visible_text[:12000] if visible_text else ""
            if truncated_text:
                parts.append(f"PAGE TEXT:\n{truncated_text}")

            if not parts:
                return f"Error: Page at {url} loaded but contained no extractable content."

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
```

### Pattern 3: Extended add_errand_items with Source Attribution

**What:** Extend the existing `add_errand_items` tool to accept optional `sourceName` and `sourceUrl` fields in each item dict, and persist them on the ErrandItem document.

**Example:**
```python
# In tools/admin.py add_errand_items method, after extracting name/destination:
source_name = item_data.get("sourceName")
source_url = item_data.get("sourceUrl")

doc = ErrandItem(
    destination=destination,
    name=name,
    needsRouting=needs_routing,
    sourceName=source_name,   # None for non-recipe items
    sourceUrl=source_url,     # None for non-recipe items
)
```

### Pattern 4: Mobile Source Attribution Display

**What:** Conditionally render a subtitle under recipe-originated errand items showing "from: Recipe Name" in muted gray. Tapping opens the URL in the device browser.

**Example (ErrandRow.tsx):**
```tsx
import { Linking, Pressable } from "react-native";

// In ErrandRow component:
{item.sourceName && (
  <Pressable onPress={() => item.sourceUrl && Linking.openURL(item.sourceUrl)}>
    <Text style={styles.sourceText}>from: {item.sourceName}</Text>
  </Pressable>
)}

// Style:
sourceText: {
  fontSize: 12,
  color: "#888",
  marginTop: 2,
},
```

### Anti-Patterns to Avoid
- **Launching a new browser per fetch:** Browser launch costs ~2-3 seconds. Reuse a single browser instance; create cheap browser contexts per request.
- **Sending full HTML to LLM:** Recipe pages can be 100KB+ of HTML. Send visible text (truncated) + JSON-LD structured data instead.
- **Parsing ingredients in Python code:** The CONTEXT.md locks "always run LLM" -- the Agent handles ingredient parsing, store assignment, and normalization to shopper-friendly format. The tool just provides page content.
- **Blocking `document` or `xhr`/`fetch` resource types:** Many recipe sites load content via XHR (Next.js, React). Only block `image`, `media`, `font`, `stylesheet`.
- **Running Playwright install at runtime:** Browser binary + deps must be baked into the Docker image at build time.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JS-rendered page fetching | Custom HTTP client + JS parser | Playwright headless Chromium | JS rendering is impossibly complex; headless browser handles it natively |
| JSON-LD parsing | Regex extraction | BeautifulSoup + json.loads | JSON-LD can be nested in @graph arrays, have multiple blocks, be malformed |
| Ingredient normalization | Custom NLP pipeline | LLM prompt with structured output | Infinite variety of ingredient formats; LLM handles naturally |
| Recipe detection | Domain allowlist / keyword matching | LLM analysis of page content | Any page could contain a recipe; locked decision says "just extract what it can" |
| Browser anti-detection | Custom fingerprint spoofing | Simple user-agent override + graceful failure | Over-engineering; locked decision says "fail gracefully if still blocked" |

**Key insight:** The entire extraction pipeline is intentionally LLM-driven per CONTEXT.md. The tool's job is only to fetch content and hand it to the Agent. The Agent (with its existing instructions + routing context) handles all intelligence: identifying ingredients, normalizing format, assigning stores.

## Common Pitfalls

### Pitfall 1: Docker Image Size Explosion
**What goes wrong:** Adding Playwright + Chromium to `python:3.12-slim-bookworm` increases image size by ~400-600 MB (Chromium binary + system libraries like libnss3, libgbm1, etc.).
**Why it happens:** Chromium has heavy system library dependencies (graphics, audio, fonts).
**How to avoid:** Install only Chromium (not Firefox/WebKit): `playwright install chromium`. Use `--with-deps` to auto-install system libraries. Clean apt cache. Accept the size increase -- it's inherent to having a real browser, and the 8 GB Azure Container Apps limit is well above this.
**Warning signs:** Docker build taking >10 minutes; image pushing slowly to ACR.

### Pitfall 2: Playwright Browser Not Found at Runtime
**What goes wrong:** `playwright install chromium` runs as one user but the app runs as another, so the browser binary path doesn't match.
**Why it happens:** Playwright stores browsers in `~/.cache/ms-playwright/` which is user-specific. The Dockerfile creates user `app` (uid 1001) but install might run as root.
**How to avoid:** Run `playwright install chromium` as the `app` user (after `USER app`), OR set `PLAYWRIGHT_BROWSERS_PATH=/app/.playwright` to a shared location and install before switching users.
**Warning signs:** `BrowserType.launch: Executable doesn't exist` error at runtime.

### Pitfall 3: /dev/shm Too Small in Container
**What goes wrong:** Chromium crashes with "out of memory" because Docker containers default to 64 MB `/dev/shm`.
**Why it happens:** Chromium uses shared memory for inter-process communication.
**How to avoid:** Launch with `--disable-dev-shm-usage` flag (forces /tmp usage instead). This is a standard Docker + Chromium fix and has minimal performance impact.
**Warning signs:** Browser crashes on page load with no clear error message.

### Pitfall 4: Page Content Too Large for LLM Context
**What goes wrong:** Sending the entire page text to the LLM exceeds token limits or wastes tokens on irrelevant content (nav bars, footers, comments, ads).
**Why it happens:** Recipe pages are often 50-100KB of visible text with extensive non-recipe content.
**How to avoid:** Truncate visible text to ~12,000 characters (~3,000 tokens). Include JSON-LD structured data separately (if present) as it's compact and high-signal. The LLM is good at finding recipe content within noisy text.
**Warning signs:** LLM responses truncated or incoherent; high token usage per recipe.

### Pitfall 5: Stale Playwright Browser After Crash
**What goes wrong:** If Chromium crashes (OOM, segfault), the browser instance stored on `app.state` becomes unusable, and all subsequent fetches fail.
**Why it happens:** Browser process died but Python object still exists.
**How to avoid:** Wrap browser operations in try/except. If browser.is_connected() is False, log a warning and return an error from the tool. Consider a health check or lazy re-launch pattern, but for v1, failing gracefully and requiring a container restart is acceptable.
**Warning signs:** All recipe fetches fail after one crash until container redeploys.

### Pitfall 6: Admin Agent Not Calling fetch_recipe_url
**What goes wrong:** Admin Agent receives a URL but doesn't call the new tool -- just tries to process the URL text as-is.
**Why it happens:** Agent instructions in Foundry portal don't mention the new tool or when to use it.
**How to avoid:** Update Admin Agent instructions in the Foundry portal to include: "When the user capture contains a URL, always call fetch_recipe_url first to get the page content before processing."
**Warning signs:** Recipe URLs get filed as plain text errand items instead of extracted ingredients.

### Pitfall 7: Success Summary Not Shown (response_needs_delivery filtering)
**What goes wrong:** Recipe success summary ("8 items added to 2 stores from Chicken Tikka Masala") gets filtered by `_response_needs_delivery()` and the inbox item is silently deleted.
**Why it happens:** The current delivery heuristic checks for specific keywords (conflict, rule, etc.) and considers tool-call confirmations as non-deliverable.
**How to avoid:** Either update `_response_needs_delivery` to detect recipe summaries, OR (simpler) rely on the existing flow where tool-call confirmations trigger inbox deletion -- the user sees the items appear on their shopping lists via the Status screen. The CONTEXT.md says "Success feedback: Status screen shows a summary" which could mean the summary is shown inline on the Status screen polling response, not as a notification.
**Warning signs:** User pastes URL, items appear on lists, but no feedback message is shown.

## Code Examples

### Dockerfile Modification for Playwright

```dockerfile
# ============ Build Stage ============
FROM python:3.12-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /usr/local/bin/uv

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

# Install dependencies
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-install-project --no-dev

COPY src/ ./src/
RUN uv sync --frozen --no-dev --no-editable

# ============ Runtime Stage ============
FROM python:3.12-slim-bookworm AS runtime

# Install Playwright system dependencies for Chromium
# These are the minimal libs Chromium needs to run
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 \
    libasound2 libpango-1.0-0 libcairo2 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Security: non-root user
RUN groupadd -g 1001 app && \
    useradd -u 1001 -g app -m -d /app -s /bin/false app

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/app/.playwright

# Copy venv and source from builder
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/src /app/src

# Install Chromium browser binary as app user
USER app
RUN playwright install chromium

EXPOSE 8000

CMD ["uvicorn", "second_brain.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### ErrandItem Model Extension

```python
# In models/documents.py
class ErrandItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    destination: str
    name: str
    needsRouting: bool = False
    sourceName: str | None = None   # Recipe name for source attribution
    sourceUrl: str | None = None    # Recipe URL for source attribution
```

### API Response Model Extension

```python
# In api/errands.py
class ErrandItemResponse(BaseModel):
    id: str
    name: str
    destination: str
    needsRouting: bool = False
    sourceName: str | None = None   # noqa: N815
    sourceUrl: str | None = None    # noqa: N815
```

### add_errand_items Tool Extension

```python
# In the add_errand_items tool, update the item creation:
source_name = item_data.get("sourceName")
source_url = item_data.get("sourceUrl")

doc = ErrandItem(
    destination=destination,
    name=name,
    needsRouting=needs_routing,
    sourceName=source_name,
    sourceUrl=source_url,
)
```

### Tool Description Update for add_errand_items

```python
items: Annotated[
    list[dict],
    Field(
        description=(
            "List of errand items to add. Each dict must have "
            "'name' (str, lowercase, natural language like '2 lbs ground beef') "
            "and 'destination' (str, the destination slug from routing context). "
            "Set destination to 'unrouted' if no affinity rule matches. "
            "Optionally include 'sourceName' (str, recipe title) and "
            "'sourceUrl' (str, recipe page URL) for items extracted from recipes."
        )
    ),
],
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| recipe-scrapers library (site-specific parsers) | LLM extraction from page content | 2024-2025 (LLM cost reduction) | Works on any site, no site-specific maintenance |
| Full HTML to LLM | Visible text + JSON-LD structured data | 2024+ | Reduces token usage by 80%+; JSON-LD provides high-signal structured context |
| Puppeteer (Node.js) | Playwright (multi-language, better async) | 2020+ | Playwright has native Python async API; same team at Microsoft |
| requests + BeautifulSoup | Playwright headless browser | Always been an option | JS-rendered content is increasingly common; SPA recipe sites need real browser |

**Deprecated/outdated:**
- `playwright install --with-deps` without specifying browser: Installs all 3 browsers unnecessarily. Always specify `chromium`.
- Sync Playwright API in async FastAPI context: Use `async_playwright` and `await` -- sync API would block the event loop.

## Open Questions

1. **Admin Agent Instructions Update**
   - What we know: Agent instructions live in the Foundry portal and are editable without redeployment.
   - What's unclear: The exact instruction text needed to tell the Agent about the new `fetch_recipe_url` tool and when to call it.
   - Recommendation: During implementation, update Foundry portal instructions to include: "When a capture contains a URL, call fetch_recipe_url to get the page content. Then extract recipe name and ingredients. Use add_errand_items with sourceName and sourceUrl fields for recipe-sourced items."

2. **Success Feedback Delivery Mechanism**
   - What we know: CONTEXT.md says "Status screen shows a summary like '8 items added to 2 stores from Chicken Tikka Masala'". The current flow either delivers admin responses as notifications or silently deletes the inbox item.
   - What's unclear: Whether this summary should be an admin notification (kept on inbox item for delivery) or just implied by the items appearing on lists.
   - Recommendation: Extend `_response_needs_delivery()` to recognize recipe success summaries (e.g., check for "items added" + "from" pattern). This provides explicit feedback without changing the flow.

3. **Container Image Size Impact**
   - What we know: Chromium + system deps add ~400-600 MB. Azure Container Apps allows up to 8 GB images on Consumption tier.
   - What's unclear: Exact final image size. Current image is likely ~200-300 MB (slim Python + deps).
   - Recommendation: Acceptable. Build and check. If >1.5 GB total, consider optimizing but don't block on this.

4. **Chromium Browser Stability Under Load**
   - What we know: This is a single-user app. Recipe fetches are infrequent (a few per week).
   - What's unclear: Whether Chromium will stay stable in a container with limited memory over days/weeks.
   - Recommendation: For v1, accept that a container restart fixes browser issues. The existing Container Apps health check will handle this. If stability becomes an issue, add lazy browser re-launch.

## Sources

### Primary (HIGH confidence)
- [Playwright Python Docker docs](https://playwright.dev/python/docs/docker) - Docker installation patterns, base images, `--with-deps` flag
- [Playwright Python Route API](https://playwright.dev/python/docs/api/class-route) - Resource blocking via route interception
- [Playwright Python Browser API](https://playwright.dev/python/docs/api/class-browser) - Browser/context lifecycle management
- [PyPI playwright 1.58.0](https://pypi.org/project/playwright/) - Current version (released 2026-01-30)
- Existing codebase: `tools/admin.py`, `tools/transcription.py`, `models/documents.py`, `main.py`, `Dockerfile` - Established patterns for @tool decorator, class-based tools, lifespan management

### Secondary (MEDIUM confidence)
- [Playwright Chromium Docker Production Guide](https://thomasbourimech.com/blog/en/playwright-chromium-docker-production/) - System dependencies list for slim-bookworm, non-root browser install pattern
- [ScrapeOps Playwright Resource Blocking](https://scrapeops.io/playwright-web-scraping-playbook/nodejs-playwright-blocking-images-resources/) - Resource type enumeration (image, stylesheet, font, media, etc.)
- [Azure Container Apps Limits](https://learn.microsoft.com/en-us/azure/container-apps/containers) - 8 GB container image size limit on Consumption tier

### Tertiary (LOW confidence)
- Web search results on Playwright anti-bot detection patterns - General landscape; specific effectiveness varies by target site. User-agent override is the baseline; deeper evasion is out of scope per CONTEXT.md "fail gracefully" decision.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Playwright is the locked decision; well-documented Python async API; version verified on PyPI
- Architecture: HIGH - Follows established patterns in this codebase (class-based tools, FastAPI lifespan, ErrandItem model); no novel architectural decisions
- Pitfalls: HIGH - Docker + Playwright is well-documented territory; pitfalls are well-known and have standard solutions
- Mobile changes: HIGH - Simple UI addition (subtitle text + Linking.openURL); follows existing ErrandRow pattern

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (Playwright releases monthly; core patterns stable)
