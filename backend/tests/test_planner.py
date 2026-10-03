import pytest
from fastapi.testclient import TestClient

from backend.app.core.planner import planner_service
from backend.app.db.database import get_connection, init_db
from backend.app.jobs.task_manager import create_task
from backend.app.main import app


client = TestClient(app)


def setup_function():
    init_db()
    conn = get_connection()
    conn.execute("DELETE FROM plan_steps")
    conn.execute("DELETE FROM task_plans")
    conn.execute("DELETE FROM task_logs")
    conn.execute("DELETE FROM tasks")
    conn.commit()
    conn.close()


def test_create_and_get_plan_through_api():
    task_id = create_task("Prepare report")

    response = client.post(
        f"/api/tasks/{task_id}/plan",
        json={"steps": ["Gather inputs", "Draft report", "Review report"]},
    )

    assert response.status_code == 200
    plan = response.json()
    assert plan["task_id"] == task_id
    assert [step["step_number"] for step in plan["steps"]] == [1, 2, 3]
    assert [step["status"] for step in plan["steps"]] == ["pending"] * 3
    assert client.get(f"/api/tasks/{task_id}/plan").json() == plan


def test_update_step_and_recreate_plan_are_deterministic():
    task_id = create_task("Prepare report")
    plan = planner_service.create_plan(task_id, ["First", "Second"])

    updated = planner_service.update_step(
        plan["steps"][0]["id"], "completed", "Inputs collected"
    )
    assert updated["status"] == "completed"
    assert updated["result"] == "Inputs collected"

    replacement = planner_service.create_plan(task_id, ["Replacement"])
    assert replacement["id"] == plan["id"]
    assert [(step["step_number"], step["title"], step["status"])
            for step in replacement["steps"]] == [(1, "Replacement", "pending")]

    with pytest.raises(ValueError):
        planner_service.update_step(replacement["steps"][0]["id"], "unknown")


def test_plan_validates_task_and_steps():
    assert client.get("/api/tasks/999999/plan").status_code == 404
    assert client.post("/api/tasks/999999/plan", json={"steps": ["x"]}).status_code == 404

    task_id = create_task("Prepare report")
    assert client.post(f"/api/tasks/{task_id}/plan", json={"steps": []}).status_code == 422
    assert client.post(f"/api/tasks/{task_id}/plan", json={"steps": ["   "]}).status_code == 422


def test_mock_plan_is_generated_and_persisted_without_execution(monkeypatch):
    monkeypatch.setattr(planner_service.router, "provider_name", "mock")
    task_id = create_task("Organize project notes")

    response = client.post(f"/api/tasks/{task_id}/plan")

    assert response.status_code == 200
    plan = response.json()
    assert len(plan["steps"]) == 3
    assert all(step["title"] and step["description"] for step in plan["steps"])
    assert [step["status"] for step in plan["steps"]] == ["pending"] * 3
    assert client.get(f"/api/tasks/{task_id}/plan").json() == plan


def test_invalid_model_json_is_retried_once_and_validated(monkeypatch):
    from backend.app.core.planner import planner_service

    task_id = create_task("Prepare a report")

    class Responses:
        provider_name = "ollama"

        def __init__(self):
            self.responses = [
                '{"steps":[{"title":"Draft","description":"Write it","extra":true}]}',
                '{"steps":[{"title":"Draft","description":"Write the report"}]}'
            ]
            self.calls = 0

        async def chat(self, messages):
            self.calls += 1
            return self.responses.pop(0)

    router = Responses()
    monkeypatch.setattr(planner_service, "router", router)

    response = client.post(f"/api/tasks/{task_id}/plan")

    assert response.status_code == 200
    assert router.calls == 2
    assert response.json()["steps"][0]["description"] == "Write the report"


def test_invalid_model_json_fails_after_one_retry(monkeypatch):
    from backend.app.core.planner import planner_service

    task_id = create_task("Prepare a report")

    class InvalidResponses:
        provider_name = "ollama"
        calls = 0

        async def chat(self, messages):
            self.calls += 1
            return '{"steps": [], "unexpected": true}'

    router = InvalidResponses()
    monkeypatch.setattr(planner_service, "router", router)

    response = client.post(f"/api/tasks/{task_id}/plan")

    assert response.status_code == 502
    assert router.calls == 2
    assert planner_service.get_plan(task_id) is None


def test_database_migrates_existing_plan_step_descriptions(tmp_path, monkeypatch):
    from backend.app.db import database

    monkeypatch.setattr(database, "DB_PATH", tmp_path / "legacy.db")
    conn = database.get_connection()
    conn.execute(
        """
        CREATE TABLE plan_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            step_number INTEGER NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            result TEXT,
            UNIQUE(task_id, step_number)
        )
        """
    )
    conn.execute(
        "INSERT INTO plan_steps(task_id, step_number, title) VALUES (1, 1, 'Legacy step')"
    )
    conn.commit()
    conn.close()

    database.init_db()

    conn = database.get_connection()
    migrated_step = conn.execute(
        "SELECT description FROM plan_steps WHERE task_id = 1"
    ).fetchone()
    conn.close()

    assert migrated_step["description"] == "Complete this part of the task: Legacy step"
