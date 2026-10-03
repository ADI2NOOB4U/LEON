"""Bounded, read-only research orchestration for research tasks."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit, urlunsplit

from backend.app.config.settings import settings
from backend.app.jobs.task_manager import register_artifact
from backend.app.security.permissions import PermissionManager
from backend.app.tools.registry import ToolRegistry


class ResearchAgent:
    def __init__(self, registry: ToolRegistry, permission_manager: PermissionManager,
                 timeout: float = 30.0) -> None:
        self.registry = registry
        self.permission_manager = permission_manager
        self.timeout = timeout

    async def run(self, task_id: int, query: str, source_count: int,
                  cancelled: Callable[[], bool] | None = None) -> dict[str, Any]:
        if not 1 <= source_count <= 20:
            raise ValueError("source_count must be between 1 and 20")
        search = self._tool("search_web")
        search_result = await self._call(search, query=query)
        candidates = self._candidates(search_result)
        sources: list[dict[str, str]] = []
        failures: list[str] = []
        for candidate in candidates:
            if len(sources) >= source_count:
                break
            if cancelled and cancelled():
                raise asyncio.CancelledError()
            try:
                page = await self._call(self._tool("extract_page_text"), url=candidate["url"])
                text = str(page.get("text", "")).strip()
                if not text:
                    raise ValueError("page returned no text")
                sources.append({
                    "title": candidate.get("title") or self._title(text, candidate["url"]),
                    "url": candidate["url"],
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "summary": self._summary(text),
                })
            except Exception as exc:
                failures.append(f"{candidate['url']}: {exc}")

        if not sources:
            detail = "; ".join(failures) or "search returned no usable HTTP(S) sources"
            raise RuntimeError(f"Research failed: {detail}")
        report = self._report(query, sources, failures)
        artifact_dir = settings.data_dir / "artifacts"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact = artifact_dir / f"research-{task_id}.md"
        artifact.write_text(report, encoding="utf-8")
        registered = register_artifact(task_id, str(artifact), "research_report")
        return {"report": report, "artifact": registered or {"path": str(artifact)},
                "source_count": len(sources), "sources": sources}

    def _tool(self, name: str):
        tool = self.registry.get(name)
        if tool is None:
            raise RuntimeError(f"Required registered tool is unavailable: {name}")
        if not self.permission_manager.can_execute(tool, confirmed=False):
            raise PermissionError(f"Research cannot execute tool '{name}'")
        return tool

    async def _call(self, tool: Any, **kwargs: Any) -> Any:
        return await asyncio.wait_for(self.registry.execute(tool.name, **kwargs), timeout=self.timeout)

    @staticmethod
    def _canonical(url: str) -> str:
        parsed = urlsplit(url.strip())
        return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path or "/", parsed.query, ""))

    @classmethod
    def _candidates(cls, result: Any) -> list[dict[str, str]]:
        raw = result.get("results", []) if isinstance(result, dict) else []
        candidates: list[dict[str, str]] = []
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict) and isinstance(item.get("url"), str):
                    candidates.append({"url": item["url"], "title": str(item.get("title", ""))})
        text = result.get("text", "") if isinstance(result, dict) else ""
        for url in re.findall(r"https?://[^\s<>\]\)\"']+", str(text)):
            candidates.append({"url": url.rstrip(".,;"), "title": ""})
        seen: set[str] = set()
        unique = []
        for candidate in candidates:
            try:
                key = cls._canonical(candidate["url"])
                if urlsplit(key).scheme not in {"http", "https"} or not urlsplit(key).netloc or key in seen:
                    continue
            except ValueError:
                continue
            seen.add(key)
            candidate["url"] = key
            unique.append(candidate)
        return unique

    @staticmethod
    def _title(text: str, url: str) -> str:
        first = next((line.strip() for line in text.splitlines() if line.strip()), "")
        return first[:120] or urlsplit(url).netloc

    @staticmethod
    def _summary(text: str) -> str:
        clean = re.sub(r"\s+", " ", text).strip()
        return (clean[:300].rsplit(" ", 1)[0] + "…") if len(clean) > 300 else clean

    @staticmethod
    def _report(query: str, sources: list[dict[str, str]], failures: list[str]) -> str:
        lines = [f"# Research report: {query}", "", "## Facts", ""]
        for source in sources:
            lines.append(f"- **{source['title']}** — {source['summary']} ([source]({source['url']}))")
        lines += ["", "## Synthesis", "", "The collected sources provide the evidence above. "
                  "This synthesis is an interpretation of those source summaries, not a directly quoted fact."]
        if failures:
            if sources:
                lines += ["", "## Collection notes", "", f"{len(failures)} additional source(s) were skipped because they could not be retrieved."]
            else:
                lines += ["", "## Collection notes", "", "No usable sources were retrieved from the search results."]
        lines += ["", "## Sources", ""]
        for source in sources:
            lines.append(f"- {source['title']} — {source['url']} (retrieved {source['retrieved_at']})")
        return "\n".join(lines) + "\n"
