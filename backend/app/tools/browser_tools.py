"""Playwright-backed, read-focused browser tools."""

from __future__ import annotations

import asyncio
import sys
import threading
from collections.abc import Coroutine
from typing import Any
from urllib.parse import urlencode

try:
    from playwright.async_api import async_playwright
except ImportError:  # Keep non-browser LEON features usable until dependencies are installed.
    def async_playwright() -> Any:
        raise RuntimeError(
            "Playwright is not installed. Run: pip install -r backend/requirements.txt"
        )

from backend.app.tools.base import BaseTool
from backend.app.tools.registry import ToolRegistry
from backend.app.security.web_security import (
    WebSecurityError,
    assert_safe_outbound_text,
    inspect_untrusted_content,
    validate_public_url,
)


def validate_http_url(url: str) -> str:
    """Return a normalized HTTP(S) URL or raise a useful validation error."""
    try:
        return validate_public_url(url)
    except WebSecurityError as exc:
        raise ValueError(str(exc)) from exc


class BrowserSession:
    """Keeps the page opened by the explicitly confirmed browser tool."""

    def __init__(self) -> None:
        self._playwright: Any | None = None
        self._browser: Any | None = None
        self._context: Any | None = None
        self._page: Any | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None
        self._loop_lock = threading.Lock()

    async def open(self, url: str) -> dict[str, Any]:
        url = validate_http_url(url)
        await self._run(self._open_on_browser_loop(url))
        return {"tool": "open_browser", "url": url, "opened": True}

    async def title(self) -> str:
        return await self._run(self._title_on_browser_loop())

    async def read_page_text(self, url: str) -> str:
        return await self._run(_read_page_text_on_browser_loop(url))

    def _ensure_browser_loop(self) -> asyncio.AbstractEventLoop:
        with self._loop_lock:
            if self._loop is not None and self._loop.is_running():
                return self._loop

            ready = threading.Event()

            def run_loop() -> None:
                # Playwright launches a subprocess, which selector loops cannot support on Windows.
                loop = (
                    asyncio.ProactorEventLoop()
                    if sys.platform == "win32"
                    else asyncio.new_event_loop()
                )
                asyncio.set_event_loop(loop)
                self._loop = loop
                ready.set()
                loop.run_forever()
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.close()

            self._loop_thread = threading.Thread(
                target=run_loop,
                daemon=True,
                name="LEON-Browser",
            )
            self._loop_thread.start()
            if not ready.wait(timeout=5):
                raise RuntimeError("Browser event loop did not start within 5 seconds")
            return self._loop

    async def _run(self, operation: Coroutine[Any, Any, Any]) -> Any:
        loop = self._ensure_browser_loop()
        return await asyncio.wrap_future(
            asyncio.run_coroutine_threadsafe(operation, loop)
        )

    async def _open_on_browser_loop(self, url: str) -> None:
        await self._ensure_page()
        await self._page.goto(url, wait_until="domcontentloaded")

    async def _title_on_browser_loop(self) -> str:
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
        if hasattr(self._context, "route"):
            async def guard(route: Any) -> None:
                try:
                    validate_http_url(route.request.url)
                except ValueError:
                    await route.abort(error_code="blockedbyclient")
                    return
                await route.continue_()
            await self._context.route("**/*", guard)
        self._page = await self._context.new_page()

    async def close(self) -> None:
        loop = self._loop
        thread = self._loop_thread
        if loop is None or thread is None or not loop.is_running():
            return
        await asyncio.wrap_future(
            asyncio.run_coroutine_threadsafe(self._close_on_browser_loop(), loop)
        )
        loop.call_soon_threadsafe(loop.stop)
        await asyncio.to_thread(thread.join, 5)
        with self._loop_lock:
            self._loop = None
            self._loop_thread = None

    async def _close_on_browser_loop(self) -> None:
        if self._context is not None:
            await self._context.close()
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()
        self._context = self._browser = self._playwright = self._page = None


browser_session = BrowserSession()


async def _read_page_text(url: str) -> str:
    """Read rendered body text in a short-lived, download-disabled browser."""
    url = validate_http_url(url)
    return await browser_session.read_page_text(url)


async def _read_page_text_on_browser_loop(url: str) -> str:
    playwright = await async_playwright().start()
    browser = context = None
    try:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(accept_downloads=False)
        if hasattr(context, "route"):
            async def guard(route: Any) -> None:
                # Validate every redirect/resource request, not only the first URL.
                try:
                    validate_http_url(route.request.url)
                except ValueError:
                    await route.abort(error_code="blockedbyclient")
                    return
                await route.continue_()
            await context.route("**/*", guard)
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
    permission = "SAFE"

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
        text = await _read_page_text(url)
        return {"tool": self.name, "url": url, "text": text,
                "trust": inspect_untrusted_content(text)}


class SearchWebTool(BaseTool):
    name = "search_web"
    description = "Search the web and return rendered result text without downloads."
    permission = "SAFE"

    async def execute(self, query: str = "", **kwargs: Any) -> dict[str, Any]:
        if kwargs:
            raise ValueError("search_web received unexpected arguments")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")

        query = assert_safe_outbound_text(query.strip(), "search query")
        search_url = "https://html.duckduckgo.com/html/?" + urlencode({"q": query})
        text = await _read_page_text(search_url)
        return {
            "tool": self.name,
            "query": query,
            "search_url": search_url,
            "text": text,
            "trust": inspect_untrusted_content(text),
        }


def register_browser_tools(registry: ToolRegistry) -> ToolRegistry:
    """Register Playwright browser tools with their required permissions."""
    registry.register(OpenBrowserTool())
    registry.register(GetPageTitleTool())
    registry.register(ExtractPageTextTool())
    registry.register(SearchWebTool())
    return registry
