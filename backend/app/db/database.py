import sqlite3
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "leon.db"

DATA_DIR.mkdir(parents=True, exist_ok=True)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            created_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            updated_at TEXT,
            result TEXT,
            error TEXT,
            progress INTEGER NOT NULL DEFAULT 0,
            current_stage TEXT NOT NULL DEFAULT 'queued',
            retry_count INTEGER NOT NULL DEFAULT 0,
            max_retries INTEGER NOT NULL DEFAULT 2,
            cancel_requested INTEGER NOT NULL DEFAULT 0
        )
    """)

    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(tasks)").fetchall()
    }

    migrations = {
        "updated_at": "ALTER TABLE tasks ADD COLUMN updated_at TEXT",
        "progress": "ALTER TABLE tasks ADD COLUMN progress INTEGER NOT NULL DEFAULT 0",
        "current_stage": "ALTER TABLE tasks ADD COLUMN current_stage TEXT NOT NULL DEFAULT 'queued'",
        "retry_count": "ALTER TABLE tasks ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0",
        "max_retries": "ALTER TABLE tasks ADD COLUMN max_retries INTEGER NOT NULL DEFAULT 2",
        "cancel_requested": "ALTER TABLE tasks ADD COLUMN cancel_requested INTEGER NOT NULL DEFAULT 0",
    }

    for name, sql in migrations.items():
        if name not in columns:
            conn.execute(sql)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS task_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            stage TEXT NOT NULL,
            message TEXT NOT NULL,
            FOREIGN KEY(task_id) REFERENCES tasks(id)
        )
    """)

    conn.commit()
    conn.close()


def log_event(task_id: int, stage: str, message: str) -> None:
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO task_logs(task_id, timestamp, stage, message)
        VALUES (?, ?, ?, ?)
        """,
        (task_id, now(), stage, message),
    )
    conn.commit()
    conn.close()
