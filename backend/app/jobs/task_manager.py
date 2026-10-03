from pathlib import Path

from backend.app.db.database import get_connection, log_event, now


def create_task(title: str, max_retries: int = 2, task_type: str = "standard",
                research_source_count: int = 5, notify_on_completion: bool = True) -> int:
    if task_type not in {"standard", "research"}:
        raise ValueError("task_type must be 'standard' or 'research'")
    if not isinstance(research_source_count, int) or not 1 <= research_source_count <= 20:
        raise ValueError("research_source_count must be between 1 and 20")
    timestamp = now()
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO tasks
        (title, task_type, research_source_count, notify_on_completion, status,
         created_at, updated_at, last_activity, progress, current_stage, max_retries)
        VALUES (?, ?, ?, ?, 'queued', ?, ?, ?, 0, 'queued', ?)""",
        (title, task_type, research_source_count, int(notify_on_completion), timestamp, timestamp, timestamp, max_retries),
    )
    task_id = int(cursor.lastrowid)
    conn.commit(); conn.close()
    log_event(task_id, "queued", "Task created.")
    return task_id


def get_task_artifacts(task_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT id, task_id, path, type, size, created_at FROM task_artifacts WHERE task_id = ? ORDER BY id", (task_id,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_task(task_id: int):
    conn = get_connection(); row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone(); conn.close()
    if not row: return None
    task = dict(row); task["artifacts"] = get_task_artifacts(task_id); return task


def get_tasks():
    conn = get_connection(); rows = conn.execute("SELECT id FROM tasks ORDER BY id DESC").fetchall(); conn.close()
    return [get_task(row["id"]) for row in rows]


def register_artifact(task_id: int, path: str, artifact_type: str = "file") -> dict | None:
    file_path = Path(path)
    if not file_path.is_file(): return None
    timestamp = now(); conn = get_connection()
    conn.execute("INSERT OR IGNORE INTO task_artifacts(task_id, path, type, size, created_at) VALUES (?, ?, ?, ?, ?)", (task_id, str(file_path), artifact_type, file_path.stat().st_size, timestamp))
    row = conn.execute("SELECT id, task_id, path, type, size, created_at FROM task_artifacts WHERE task_id = ? AND path = ? AND type = ?", (task_id, str(file_path), artifact_type)).fetchone()
    conn.commit(); conn.close()
    return dict(row) if row else None


def get_task_logs(task_id: int):
    conn = get_connection(); rows = conn.execute("SELECT timestamp, stage, message FROM task_logs WHERE task_id = ? ORDER BY id", (task_id,)).fetchall(); conn.close()
    return [dict(row) for row in rows]


def get_next_queued_task():
    conn = get_connection(); row = conn.execute("SELECT * FROM tasks WHERE status = 'queued' ORDER BY id LIMIT 1").fetchone(); conn.close()
    return dict(row) if row else None


def claim_task(task_id: int) -> bool:
    timestamp = now(); conn = get_connection()
    changed = conn.execute("UPDATE tasks SET status = 'running', current_stage = 'running', updated_at = ?, last_activity = ? WHERE id = ? AND status = 'queued'", (timestamp, timestamp, task_id)).rowcount
    conn.commit(); conn.close(); return changed == 1


def recover_interrupted_tasks() -> int:
    conn = get_connection(); timestamp = now()
    try:
        conn.execute("UPDATE plan_steps SET status = 'pending' WHERE status = 'running'")
        changed = conn.execute("""UPDATE tasks SET status = 'queued', current_stage = 'queued', updated_at = ?, last_activity = ?
            WHERE status IN ('running', 'planning', 'executing', 'verifying')""", (timestamp, timestamp)).rowcount
        conn.commit(); return changed
    finally: conn.close()


def update_task(task_id: int, **fields) -> None:
    allowed = {"status", "started_at", "completed_at", "updated_at", "result", "summary", "error", "progress", "current_stage", "retry_count", "cancel_requested", "last_activity"}
    fields = {key: value for key, value in fields.items() if key in allowed}
    if not fields: return
    timestamp = now(); fields["updated_at"] = timestamp; fields.setdefault("last_activity", timestamp)
    assignments = ", ".join(f"{key} = ?" for key in fields)
    conn = get_connection(); conn.execute(f"UPDATE tasks SET {assignments} WHERE id = ?", [*fields.values(), task_id]); conn.commit(); conn.close()


def set_stage(task_id: int, stage: str, progress: int, message: str):
    update_task(task_id, status="queued" if stage == "queued" else "running", current_stage=stage, progress=progress)
    log_event(task_id, stage, message)


def request_cancel(task_id: int) -> bool:
    task = get_task(task_id)
    if not task or task["status"] in {"completed", "failed", "cancelled"}: return False
    update_task(task_id, cancel_requested=1); log_event(task_id, "cancellation", "Cancellation requested."); return True
