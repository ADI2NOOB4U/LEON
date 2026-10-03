"""Playwright-backed, read-focused browser tools."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode, urlsplit

try:
    from playwright.async_api import async_playwright
except ImportError:  # Keep non-browser LEON features usable until dependencies are installed.
    def async_playwright() -> Any:
        raise RuntimeError(
            "Playwright is not installed. Run: pip install -r backend/requirements.txt"
        )

from backend.app.tools.base import BaseTool
from backend.app.tools.registry import ToolRegistry


def validate_http_url(url: str) -> str:
    """Return a normalized HTTP(S) URL or raise a useful validation error."""
    if not isinstance(url, str) or not url.strip():
        raise ValueError("url must be a non-empty string")

    url = url.strip()
    if any(character.isspace() for character in url) or "\\" in url or "\x00" in url:
        raise ValueError("url must be a valid HTTP or HTTPS URL")

    parsed = urlsplit(url)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("url must be a valid HTTP or HTTPS URL") from exc

    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.hostname
        or (port is not None and not 0 < port < 65536)
    ):
        raise ValueError("url must be a valid HTTP or HTTPS URL")
    return url


class BrowserSession:
    """Keeps the page opened by the explicitly confirmed browser tool."""

    def __init__(self) -> None:
        self._playwright: Any | None = None
        self._browser: Any | None = None
        self._context: Any | None = None
        self._page: Any | None = None

    async def open(self, url: str) -> dict[str, Any]:
        url = validate_http_url(url)
        await self._ensure_page()
        await self._page.goto(url, wait_until="domcontentloaded")
        return {"tool": "open_browser", "url": url, "opened": True}

    async def title(self) -> str:
        if self._page is None:
            raise ValueError("no browser page is open; call open_browser first")
        return await self._page.title()

    async def _ensure_page(self) -> None:
        if self._page is not None:
            return
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
        # Downloads are deliberately disabled: these tools only expose text.
        self._context = await self._browser.new_context(accept_downloads=False)
        self._page = await self._context.new_page()


browser_session = BrowserSession()


async def _read_page_text(url: str) -> str:
    """Read rendered body text in a short-lived, download-disabled browser."""
    url = validate_http_url(url)
    playwright = await async_playwright().start()
    browser = context = None
    try:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(accept_downloads=False)
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded")
        return await page.locator("body").inner_text()
    finally:
        if context is not None:
            await context.close()
        if browser is not None:
            await browser.close()
        await playwright.stop()


class OpenBrowserTool(BaseTool):
    name = "open_browser"
    description = "Open an HTTP or HTTPS URL in LEON's Playwright browser."
    permission = "CONFIRM"

    async def execute(self, url: str = "", **kwargs: Any) -> dict[str, Any]:
        if kwargs:
            raise ValueError("open_browser received unexpected arguments")
        return await browser_session.open(url)


class GetPageTitleTool(BaseTool):
    name = "get_page_title"
    description = "Return the title of the currently open LEON browser page."
    permission = "SAFE"

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        if kwargs:
            raise ValueError("get_page_title does not accept arguments")
        return {"tool": self.name, "title": await browser_session.title()}


class ExtractPageTextTool(BaseTool):
    name = "extract_page_text"
    description = "Read rendered text from an HTTP or HTTPS page without downloads."
    permission = "SAFE"

    async def execute(self, url: str = "", **kwargs: Any) -> dict[str, Any]:
        if kwargs:
            raise ValueError("extract_page_text received unexpected arguments")
        url = validate_http_url(url)
        return {"tool": self.name, "url": url, "text": await _read_page_text(url)}


class SearchWebTool(BaseTool):
    name = "search_web"
    description = "Search the web and return rendered result text without downloads."
    permission = "SAFE"

    async def execute(self, query: str = "", **kwargs: Any) -> dict[str, Any]:
        if kwargs:
            raise ValueError("search_web received unexpected arguments")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")

        query = query.strip()
        search_url = "https://html.duckduckgo.com/html/?" + urlencode({"q": query})
        return {
            "tool": self.name,
            "query": query,
            "search_url": search_url,
            "text": await _read_page_text(search_url),
        }


def register_browser_tools(registry: ToolRegistry) -> ToolRegistry:
    """Register Playwright browser tools with their required permissions."""
    registry.register(OpenBrowserTool())
    registry.register(GetPageTitleTool())
    registry.register(ExtractPageTextTool())
    registry.register(SearchWebTool())
    return registry
