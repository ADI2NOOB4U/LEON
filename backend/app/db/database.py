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
            ,checkpoint TEXT
            ,context TEXT
            ,verification_status TEXT NOT NULL DEFAULT 'pending'
            ,waiting_reason TEXT
            ,approval_granted INTEGER NOT NULL DEFAULT 0
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
        "checkpoint": "ALTER TABLE tasks ADD COLUMN checkpoint TEXT",
        "context": "ALTER TABLE tasks ADD COLUMN context TEXT",
        "verification_status": "ALTER TABLE tasks ADD COLUMN verification_status TEXT NOT NULL DEFAULT 'pending'",
        "waiting_reason": "ALTER TABLE tasks ADD COLUMN waiting_reason TEXT",
        "approval_granted": "ALTER TABLE tasks ADD COLUMN approval_granted INTEGER NOT NULL DEFAULT 0",
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

    # Structured personal memory lives beside (and reuses) the legacy memory
    # store.  JSON keeps the profile extensible without introducing another DB.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            data TEXT NOT NULL DEFAULT '{}',
            settings TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS personal_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_type TEXT NOT NULL,
            category TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            source TEXT NOT NULL,
            confidence TEXT NOT NULL,
            privacy_level TEXT NOT NULL DEFAULT 'NORMAL',
            retention TEXT NOT NULL DEFAULT 'DURABLE',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_confirmed TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            supersedes_id INTEGER,
            UNIQUE(category, key, value, active)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            relationship_type TEXT NOT NULL DEFAULT 'other',
            important_dates TEXT NOT NULL DEFAULT '{}',
            preferences TEXT NOT NULL DEFAULT '{}',
            notes TEXT,
            source TEXT NOT NULL,
            confidence TEXT NOT NULL,
            privacy_level TEXT NOT NULL DEFAULT 'PRIVATE',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS important_dates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            date_value TEXT NOT NULL,
            time_value TEXT,
            date_type TEXT NOT NULL DEFAULT 'custom',
            person_id TEXT,
            notes TEXT,
            source TEXT NOT NULL,
            confidence TEXT NOT NULL,
            privacy_level TEXT NOT NULL DEFAULT 'PRIVATE',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(name, date_value, active)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memory_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            memory_id INTEGER,
            category TEXT,
            key TEXT,
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            description TEXT,
            confidence REAL NOT NULL DEFAULT 1.0,
            metadata TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(name, entity_type)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_relations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT NOT NULL,
            target_name TEXT NOT NULL,
            relation_type TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 1.0,
            created_at TEXT NOT NULL,
            UNIQUE(source_name, target_name, relation_type)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_name TEXT NOT NULL,
            fact_type TEXT NOT NULL,
            statement TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 1.0,
            source TEXT NOT NULL DEFAULT 'user',
            importance REAL NOT NULL DEFAULT 0.5,
            last_verified TEXT,
            stale INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS improvement_profile (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS improvement_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_hash TEXT NOT NULL,
            route TEXT,
            outcome TEXT NOT NULL,
            rating INTEGER,
            comment TEXT,
            verified INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS improvement_proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            title TEXT NOT NULL,
            rationale TEXT NOT NULL,
            change_json TEXT NOT NULL,
            baseline_score REAL NOT NULL DEFAULT 0,
            candidate_score REAL,
            status TEXT NOT NULL DEFAULT 'evaluated',
            created_at TEXT NOT NULL,
            activated_at TEXT,
            rolled_back_at TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS security_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            action TEXT NOT NULL,
            tool TEXT,
            risk TEXT NOT NULL,
            decision TEXT NOT NULL,
            authorized INTEGER NOT NULL DEFAULT 0,
            verified INTEGER NOT NULL DEFAULT 0,
            details TEXT NOT NULL DEFAULT '{}'
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
    if "expected_result" not in plan_step_columns:
        conn.execute("ALTER TABLE plan_steps ADD COLUMN expected_result TEXT")
    if "verification_method" not in plan_step_columns:
        conn.execute("ALTER TABLE plan_steps ADD COLUMN verification_method TEXT NOT NULL DEFAULT 'result'")
    if "permission_level" not in plan_step_columns:
        conn.execute("ALTER TABLE plan_steps ADD COLUMN permission_level TEXT NOT NULL DEFAULT 'SAFE'")
    if "timeout_seconds" not in plan_step_columns:
        conn.execute("ALTER TABLE plan_steps ADD COLUMN timeout_seconds INTEGER NOT NULL DEFAULT 120")
    if "retry_limit" not in plan_step_columns:
        conn.execute("ALTER TABLE plan_steps ADD COLUMN retry_limit INTEGER NOT NULL DEFAULT 0")
    if "depends_on" not in plan_step_columns:
        conn.execute("ALTER TABLE plan_steps ADD COLUMN depends_on TEXT")

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
