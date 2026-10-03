import sqlite3
from pathlib import Path
from datetime import datetime, timezone

from backend.app.security.web_security import redact_task_text

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
            task_type TEXT NOT NULL DEFAULT 'standard',
            research_source_count INTEGER NOT NULL DEFAULT 5,
            notify_on_completion INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'queued',
            created_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            updated_at TEXT,
            last_activity TEXT,
            result TEXT,
            summary TEXT,
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
        "task_type": "ALTER TABLE tasks ADD COLUMN task_type TEXT NOT NULL DEFAULT 'standard'",
        "research_source_count": "ALTER TABLE tasks ADD COLUMN research_source_count INTEGER NOT NULL DEFAULT 5",
        "notify_on_completion": "ALTER TABLE tasks ADD COLUMN notify_on_completion INTEGER NOT NULL DEFAULT 1",
        "updated_at": "ALTER TABLE tasks ADD COLUMN updated_at TEXT",
        "progress": "ALTER TABLE tasks ADD COLUMN progress INTEGER NOT NULL DEFAULT 0",
        "current_stage": "ALTER TABLE tasks ADD COLUMN current_stage TEXT NOT NULL DEFAULT 'queued'",
        "retry_count": "ALTER TABLE tasks ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0",
        "max_retries": "ALTER TABLE tasks ADD COLUMN max_retries INTEGER NOT NULL DEFAULT 2",
        "cancel_requested": "ALTER TABLE tasks ADD COLUMN cancel_requested INTEGER NOT NULL DEFAULT 0",
        "last_activity": "ALTER TABLE tasks ADD COLUMN last_activity TEXT",
        "summary": "ALTER TABLE tasks ADD COLUMN summary TEXT",
        "priority": "ALTER TABLE tasks ADD COLUMN priority TEXT NOT NULL DEFAULT 'normal'",
        "wait_for_user_reason": "ALTER TABLE tasks ADD COLUMN wait_for_user_reason TEXT",
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

    conn.execute("""
        CREATE TABLE IF NOT EXISTS task_artifacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            path TEXT NOT NULL,
            type TEXT NOT NULL,
            size INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(task_id, path, type),
            FOREIGN KEY(task_id) REFERENCES tasks(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            content TEXT NOT NULL,
            importance REAL NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS task_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(task_id) REFERENCES tasks(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS plan_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            step_number INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            tool_name TEXT,
            arguments TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            result TEXT,
            UNIQUE(task_id, step_number),
            FOREIGN KEY(task_id) REFERENCES tasks(id)
        )
    """)

    plan_step_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(plan_steps)").fetchall()
    }
    if "description" not in plan_step_columns:
        conn.execute(
            "ALTER TABLE plan_steps ADD COLUMN description TEXT NOT NULL DEFAULT ''"
        )
        conn.execute(
            "UPDATE plan_steps SET description = 'Complete this part of the task: ' || title"
        )
    if "tool_name" not in plan_step_columns:
        conn.execute("ALTER TABLE plan_steps ADD COLUMN tool_name TEXT")
    if "arguments" not in plan_step_columns:
        conn.execute("ALTER TABLE plan_steps ADD COLUMN arguments TEXT")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            run_at TEXT NOT NULL,
            interval_seconds INTEGER,
            payload TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            retry_count INTEGER NOT NULL DEFAULT 0,
            max_retries INTEGER NOT NULL DEFAULT 2,
            last_error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS news_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL COLLATE NOCASE,
            enabled INTEGER NOT NULL DEFAULT 1,
            schedule TEXT NOT NULL DEFAULT 'morning',
            preference TEXT NOT NULL DEFAULT 'important',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(topic)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS news_stories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            source TEXT NOT NULL,
            published_at TEXT,
            retrieved_at TEXT NOT NULL,
            category TEXT,
            score REAL,
            reason TEXT,
            classified_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS briefings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule TEXT NOT NULL,
            headline TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL,
            delivery_status TEXT NOT NULL DEFAULT 'pending',
            delivery_error TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS briefing_stories (
            briefing_id INTEGER NOT NULL,
            story_id INTEGER NOT NULL,
            PRIMARY KEY(briefing_id, story_id),
            FOREIGN KEY(briefing_id) REFERENCES briefings(id),
            FOREIGN KEY(story_id) REFERENCES news_stories(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS briefing_deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            briefing_id INTEGER NOT NULL,
            channel TEXT NOT NULL,
            status TEXT NOT NULL,
            error TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(briefing_id, channel),
            FOREIGN KEY(briefing_id) REFERENCES briefings(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS news_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            title TEXT NOT NULL,
            normalized_title TEXT NOT NULL,
            importance TEXT NOT NULL DEFAULT 'interesting',
            status TEXT NOT NULL DEFAULT 'reported',
            summary TEXT,
            location TEXT,
            source_url TEXT,
            source TEXT,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            last_alerted_at TEXT,
            alerted INTEGER NOT NULL DEFAULT 0,
            UNIQUE(normalized_title)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS event_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            title TEXT,
            publisher TEXT,
            published_at TEXT,
            retrieved_at TEXT NOT NULL,
            source_type TEXT NOT NULL DEFAULT 'report',
            verification_status TEXT NOT NULL DEFAULT 'reported',
            FOREIGN KEY(event_id) REFERENCES news_events(id)
        )
    """)

    conn.commit()
    conn.close()


def log_event(task_id: int, stage: str, message: str) -> None:
    conn = get_connection()
    safe_message = redact_task_text(message)
    conn.execute(
        """
        INSERT INTO task_logs(task_id, timestamp, stage, message)
        VALUES (?, ?, ?, ?)
        """,
        (task_id, now(), stage, safe_message),
    )
    conn.commit()
    conn.close()
