import asyncio
from types import SimpleNamespace

import pytest

from backend.app.tools import browser_tools
from backend.app.tools.registry import ToolRegistry


class FakePage:
    def __init__(self):
        self.gotos = []

    async def goto(self, url, wait_until):
        self.gotos.append((url, wait_until))

    async def title(self):
        return "LEON test page"

    def locator(self, selector):
        assert selector == "body"
        return SimpleNamespace(inner_text=self.inner_text)

    async def inner_text(self):
        return "Rendered page text"


class FakeContext:
    def __init__(self, page):
        self.page = page
        self.closed = False

    async def new_page(self):
        return self.page

    async def close(self):
        self.closed = True


class FakeBrowser:
    def __init__(self, context):
        self.context = context
        self.closed = False

    async def new_context(self, *, accept_downloads):
        assert accept_downloads is False
        return self.context

    async def close(self):
        self.closed = True


class FakePlaywright:
    def __init__(self, browser):
        self.chromium = SimpleNamespace(launch=self.launch)
        self.browser = browser
        self.stopped = False

    async def launch(self, *, headless):
        assert headless is True
        return self.browser

    async def stop(self):
        self.stopped = True


class FakePlaywrightFactory:
    def __init__(self, playwright):
        self.playwright = playwright

    async def start(self):
        return self.playwright


@pytest.mark.anyio
async def test_open_browser_and_get_page_title_use_playwright(monkeypatch):
    page = FakePage()
    playwright = FakePlaywright(FakeBrowser(FakeContext(page)))
    monkeypatch.setattr(browser_tools, "async_playwright", lambda: FakePlaywrightFactory(playwright))
    session = browser_tools.BrowserSession()
    monkeypatch.setattr(browser_tools, "browser_session", session)

    try:
        opened = await browser_tools.OpenBrowserTool().execute(url="https://example.com/docs")
        title = await browser_tools.GetPageTitleTool().execute()
    finally:
        await session.close()

    assert opened == {"tool": "open_browser", "url": "https://example.com/docs", "opened": True}
    assert title == {"tool": "get_page_title", "title": "LEON test page"}
    assert page.gotos == [("https://example.com/docs", "domcontentloaded")]


def test_browser_session_survives_multiple_caller_event_loops(monkeypatch):
    page = FakePage()
    playwright = FakePlaywright(FakeBrowser(FakeContext(page)))
    starts = 0

    class Factory:
        async def start(self):
            nonlocal starts
            starts += 1
            return playwright

    monkeypatch.setattr(browser_tools, "async_playwright", Factory)
    session = browser_tools.BrowserSession()

    try:
        asyncio.run(session.open("https://example.com/first"))
        assert asyncio.run(session.title()) == "LEON test page"
        asyncio.run(session.open("https://example.com/second"))
    finally:
        asyncio.run(session.close())

    assert starts == 1
    assert page.gotos == [
        ("https://example.com/first", "domcontentloaded"),
        ("https://example.com/second", "domcontentloaded"),
    ]


@pytest.mark.anyio
async def test_extract_page_text_uses_isolated_download_disabled_browser(monkeypatch):
    page = FakePage()
    context = FakeContext(page)
    browser = FakeBrowser(context)
    playwright = FakePlaywright(browser)
    monkeypatch.setattr(browser_tools, "async_playwright", lambda: FakePlaywrightFactory(playwright))

    session = browser_tools.BrowserSession()
    monkeypatch.setattr(browser_tools, "browser_session", session)
    try:
        result = await browser_tools.ExtractPageTextTool().execute(url="https://example.com")
    finally:
        await session.close()

    assert result["text"] == "Rendered page text"
    assert context.closed and browser.closed and playwright.stopped


@pytest.mark.anyio
async def test_search_web_encodes_query_and_returns_text(monkeypatch):
    monkeypatch.setattr(browser_tools, "_read_page_text", lambda url: _text(url))

    result = await browser_tools.SearchWebTool().execute(query="leon tools & safety")

    assert result["search_url"] == "https://html.duckduckgo.com/html/?q=leon+tools+%26+safety"
    assert result["text"] == "search text"


async def _text(url):
    assert url.startswith("https://html.duckduckgo.com/html/?q=")
    return "search text"


@pytest.mark.anyio
@pytest.mark.parametrize("url", ["file:///tmp/a", "https://example.com\nhttps://bad.invalid", "https://example.com:99999"])
async def test_browser_tools_reject_invalid_urls(url):
    with pytest.raises(ValueError):
        await browser_tools.OpenBrowserTool().execute(url=url)


def test_browser_tools_register_with_permissions():
    registry = ToolRegistry()
    browser_tools.register_browser_tools(registry)

    assert [tool.name for tool in registry.list()] == [
        "open_browser", "get_page_title", "extract_page_text", "search_web"
    ]
    assert registry.get("open_browser").permission == "SAFE"
    assert registry.get("get_page_title").permission == "SAFE"


def test_public_read_navigation_is_safe_but_external_side_effects_confirm():
    registry = ToolRegistry()
    browser_tools.register_browser_tools(registry)

    assert registry.get("open_browser").permission == "SAFE"
    assert registry.get("extract_page_text").permission == "SAFE"

    from backend.app.tools.system_tools import OpenUrlTool
    assert OpenUrlTool.permission == "CONFIRM"
