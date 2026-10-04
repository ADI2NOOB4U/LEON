import asyncio

import pytest
from fastapi.testclient import TestClient

from backend.app.core.planner import PlannerService
from backend.app.db.database import get_connection, init_db
from backend.app.jobs.task_manager import create_task, get_task
from backend.app.main import app
from backend.app.missions import mission_service
from backend.app.tools.registry import ToolRegistry


client = TestClient(app)


def setup_function():
    init_db()
    conn = get_connection()
    for table in ("plan_steps", "task_plans", "task_logs", "tasks"):
        conn.execute(f"DELETE FROM {table}")
    conn.commit()
    conn.close()


def test_mission_api_creates_plan_and_exposes_lifecycle():
    response = client.post("/api/missions", json={"objective": "Create and verify a report"})
    assert response.status_code == 200
    mission = response.json()
    assert mission["current_stage"] == "ready"
    mission_id = mission["id"]
    plan = client.get(f"/api/missions/{mission_id}/plan")
    assert plan.status_code == 200
    assert plan.json()["steps"]

    paused = client.post(f"/api/missions/{mission_id}/pause")
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"
    resumed = client.post(f"/api/missions/{mission_id}/resume")
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "queued"


def test_mission_command_uses_existing_task_engine():
    response = client.post("/api/command", json={"message": "Build an app, test it, and fix failures"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "mission"
    assert get_task(payload["mission"]["id"])["task_type"] == "mission"


def test_plan_rejects_unknown_tools_and_invalid_dependencies():
    task_id = create_task("mission", task_type="mission")
    planner = PlannerService(registry=ToolRegistry())
    with pytest.raises(ValueError, match="Unknown tool"):
        planner.create_plan(task_id, [{"title": "bad", "description": "bad", "tool_name": "missing"}])
    with pytest.raises(ValueError, match="invalid dependency"):
        planner.create_plan(task_id, [{"title": "bad", "description": "bad", "depends_on": [2]}])


def test_mission_verification_is_mandatory_for_file_step(tmp_path):
    from backend.app.intelligence.mission_verification import verify_step

    path = tmp_path / "result.txt"
    step = {
        "verification_method": "file_exists",
        "arguments": {"path": str(path)},
    }
    assert verify_step(step, {"success": True})[0] is False
    path.write_text("verified", encoding="utf-8")
    assert verify_step(step, {"success": True})[0] is True


def test_mission_approve_and_respond_controls_are_persistent():
    mission = mission_service.create("Await input", max_retries=0)
    mission_service.wait(mission["id"], "Choose an implementation")
    response = client.post(f"/api/missions/{mission['id']}/respond", json={"answer": "Use Python"})
    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    approved = client.post(f"/api/missions/{mission['id']}/approve")
    assert approved.status_code == 200
    assert approved.json()["approval_granted"] == 1
