from backend.app.db.database import get_connection, log_event, now


def create_task(title: str, max_retries: int = 2) -> int:
    timestamp = now()

    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO tasks
        (title, status, created_at, updated_at, progress,
         current_stage, max_retries)
        VALUES (?, 'queued', ?, ?, 0, 'queued', ?)
        """,
        (title, timestamp, timestamp, max_retries),
    )

    task_id = int(cursor.lastrowid)
    conn.commit()
    conn.close()

    log_event(task_id, "queued", "Task created.")
    return task_id


def get_task(task_id: int):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_tasks():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM tasks ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_task_logs(task_id: int):
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT timestamp, stage, message
        FROM task_logs
        WHERE task_id = ?
        ORDER BY id ASC
        """,
        (task_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_next_queued_task():
    conn = get_connection()
    row = conn.execute(
        """
        SELECT *
        FROM tasks
        WHERE status = 'queued'
        ORDER BY id ASC
        LIMIT 1
        """
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def recover_interrupted_tasks() -> int:
    """Make tasks left mid-execution safe to resume after a process restart.

    Completed steps are deliberately left untouched.  A running step has no
    durable commit point around the external tool call, so it is returned to
    pending and may be retried once; this is the safest behavior for the
    existing at-least-once execution model.
    """
    conn = get_connection()
    timestamp = now()
    try:
        conn.execute(
            "UPDATE plan_steps SET status = 'pending' WHERE status = 'running'"
        )
        changed = conn.execute(
            """UPDATE tasks
               SET status = 'queued', current_stage = 'queued', updated_at = ?
               WHERE status IN ('planning', 'executing', 'verifying')""",
            (timestamp,),
        ).rowcount
        conn.commit()
        return changed
    finally:
        conn.close()


def update_task(task_id: int, **fields) -> None:
    allowed = {
        "status",
        "started_at",
        "completed_at",
        "updated_at",
        "result",
        "error",
        "progress",
        "current_stage",
        "retry_count",
        "cancel_requested",
    }

    fields = {
        key: value
        for key, value in fields.items()
        if key in allowed
    }

    if not fields:
        return

    fields["updated_at"] = now()

    assignments = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values()) + [task_id]

    conn = get_connection()
    conn.execute(
        f"UPDATE tasks SET {assignments} WHERE id = ?",
        values,
    )
    conn.commit()
    conn.close()


def set_stage(task_id: int, stage: str, progress: int, message: str):
    update_task(
        task_id,
        status=stage,
        current_stage=stage,
        progress=progress,
    )
    log_event(task_id, stage, message)


def request_cancel(task_id: int) -> bool:
    task = get_task(task_id)

    if not task:
        return False

    if task["status"] in {"completed", "failed", "cancelled"}:
        return False

    update_task(task_id, cancel_requested=1)
    log_event(task_id, "cancellation", "Cancellation requested.")
    return True
