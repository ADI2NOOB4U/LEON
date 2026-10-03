import json

from backend.app.db.database import get_connection, init_db
from backend.app.jobs.task_manager import create_task, get_task
from backend.app.jobs.worker import LeonWorker
from backend.app.tools.base import BaseTool
from backend.app.tools.registry import ToolRegistry


class MockSearch(BaseTool):
    name = "search_web"
    description = "mock"
    permission = "SAFE"

    async def execute(self, query="", **kwargs):
        return {"results": [
            {"title": "One", "url": "https://example.com/a#top"},
            {"title": "One duplicate", "url": "https://EXAMPLE.com/a"},
            {"title": "Two", "url": "https://example.org/b"},
        ]}


class MockExtract(BaseTool):
    name = "extract_page_text"
    description = "mock"
    permission = "SAFE"

    async def execute(self, url="", **kwargs):
        return {"url": url, "text": f"Facts collected from {url}."}


def setup_function():
    init_db()
    conn = get_connection()
    conn.execute("DELETE FROM task_artifacts")
    conn.execute("DELETE FROM task_logs")
    conn.execute("DELETE FROM tasks")
    conn.commit()
    conn.close()


def test_research_task_collects_deduplicated_sources_and_artifact(tmp_path, monkeypatch):
    import backend.app.core.research_agent as research_module
    monkeypatch.setattr(research_module.settings, "data_dir", tmp_path)

    task_id = create_task("What are LEON safety controls?", task_type="research", research_source_count=5)
    registry = ToolRegistry()
    registry.register(MockSearch())
    registry.register(MockExtract())
    worker = LeonWorker(registry=registry)
    worker._execute(get_task(task_id))

    task = get_task(task_id)
    assert task["status"] == "completed"
    assert len(task["artifacts"]) == 1
    assert task["artifacts"][0]["type"] == "research_report"
    assert "## Facts" in task["result"]
    assert "## Synthesis" in task["result"]
    assert task["result"].count("https://example.com/a") == 3  # fact text, citation, source list
    assert "retrieved" in task["result"]


def test_research_source_failures_are_bounded_and_retryable():
    class FailingExtract(MockExtract):
        async def execute(self, url="", **kwargs):
            if "example.org" in url:
                raise TimeoutError("mock timeout")
            return await super().execute(url, **kwargs)

    task_id = create_task("bounded research", max_retries=0, task_type="research", research_source_count=2)
    registry = ToolRegistry()
    registry.register(MockSearch())
    registry.register(FailingExtract())
    LeonWorker(registry=registry)._execute(get_task(task_id))

    task = get_task(task_id)
    assert task["status"] == "completed"
    assert "- Two" not in task["result"]
