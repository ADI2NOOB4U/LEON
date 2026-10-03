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
