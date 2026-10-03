from backend.app.db.database import get_connection, now
from backend.app.jobs.task_manager import get_task
from backend.app.models.schemas import PlanStepStatus


class PlannerService:
    """Deterministic persistence and status management for task plans."""

    def create_plan(self, task_id: int, steps: list[str]) -> dict:
        if not get_task(task_id):
            raise ValueError("Task not found")
        if not steps:
            raise ValueError("A plan must contain at least one step")

        timestamp = now()
        conn = get_connection()
        try:
            existing = conn.execute(
                "SELECT id FROM task_plans WHERE task_id = ?", (task_id,)
            ).fetchone()
            if existing:
                plan_id = int(existing["id"])
                conn.execute("DELETE FROM plan_steps WHERE task_id = ?", (task_id,))
                conn.execute(
                    "UPDATE task_plans SET updated_at = ? WHERE id = ?",
                    (timestamp, plan_id),
                )
            else:
                cursor = conn.execute(
                    "INSERT INTO task_plans(task_id, created_at, updated_at) VALUES (?, ?, ?)",
                    (task_id, timestamp, timestamp),
                )
                plan_id = int(cursor.lastrowid)

            conn.executemany(
                "INSERT INTO plan_steps(task_id, step_number, title, status) VALUES (?, ?, ?, 'pending')",
                [(task_id, number, title) for number, title in enumerate(steps, 1)],
            )
            conn.commit()
        finally:
            conn.close()

        return self.get_plan(task_id)

    def get_plan(self, task_id: int) -> dict | None:
        conn = get_connection()
        plan = conn.execute(
            "SELECT * FROM task_plans WHERE task_id = ?", (task_id,)
        ).fetchone()
        if not plan:
            conn.close()
            return None
        steps = conn.execute(
            "SELECT id, task_id, step_number, title, status, result FROM plan_steps WHERE task_id = ? ORDER BY step_number ASC",
            (task_id,),
        ).fetchall()
        conn.close()
        result = dict(plan)
        result["steps"] = [dict(step) for step in steps]
        return result

    def update_step(
        self, step_id: int, status: PlanStepStatus | str, result: str | None = None
    ) -> dict | None:
        status = PlanStepStatus(status).value
        conn = get_connection()
        conn.execute(
            "UPDATE plan_steps SET status = ?, result = ? WHERE id = ?",
            (status, result, step_id),
        )
        conn.commit()
        step = conn.execute(
            "SELECT id, task_id, step_number, title, status, result FROM plan_steps WHERE id = ?",
            (step_id,),
        ).fetchone()
        conn.close()
        return dict(step) if step else None


planner_service = PlannerService()
