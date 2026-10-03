from pathlib import Path

from backend.app.core.planner import planner_service
from backend.app.db.database import get_connection, init_db
from backend.app.jobs.task_manager import (
    claim_task,
    create_task,
    get_task,
    recover_interrupted_tasks,
    register_artifact,
    update_task,
)
from backend.app.jobs.worker import LeonWorker


def setup_function():
    init_db()
    conn = get_connection()
    for table in ("task_artifacts", "plan_steps", "task_plans", "task_logs", "tasks"):
        conn.execute(f"DELETE FROM {table}")
    conn.commit()
    conn.close()


def test_claim_is_atomic_and_persists_heartbeat():
    task_id = create_task("claim me")
    assert claim_task(task_id) is True
    assert claim_task(task_id) is False
    task = get_task(task_id)
    assert task["status"] == "running"
    assert task["last_activity"]


def test_recovery_keeps_completed_steps_and_worker_skips_them():
    task_id = create_task("resume me", max_retries=0)
    planner_service.create_plan(task_id, ["first", "second"])
    plan = planner_service.get_plan(task_id)
    planner_service.update_step(plan["steps"][0]["id"], "completed", "done")
    planner_service.update_step(plan["steps"][1]["id"], "running")
    update_task(task_id, status="running", current_stage="executing")

    assert recover_interrupted_tasks() == 1

    class RecordingExecutor:
        def __init__(self):
            self.titles = []

        def execute(self, step):
            self.titles.append(step["title"])
            return "done"

    executor = RecordingExecutor()
    LeonWorker(executor)._execute(get_task(task_id))
    assert executor.titles == ["second"]
    task = get_task(task_id)
    assert task["status"] == "completed"
    assert task["summary"] == task["result"]


def test_artifact_registry_is_idempotent_and_exposed_on_task(tmp_path: Path):
    task_id = create_task("artifact task")
    output = tmp_path / "output.txt"
    output.write_text("artifact", encoding="utf-8")

    first = register_artifact(task_id, str(output))
    second = register_artifact(task_id, str(output))
    assert first == second
    assert get_task(task_id)["artifacts"] == [first]
    assert first["type"] == "file"
    assert first["size"] == 8
