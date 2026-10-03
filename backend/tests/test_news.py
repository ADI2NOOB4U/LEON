from datetime import datetime, timezone

import pytest

from backend.app.db.database import get_connection, init_db
from backend.app.jobs.scheduler import SchedulerService
from backend.app.memory.memory import memory_service
from backend.app.news.service import NewsService, classify_story


@pytest.fixture(autouse=True)
def clear_news():
    init_db()
    conn = get_connection()
    for table in ("briefing_deliveries", "briefing_stories", "briefings", "news_stories", "news_subscriptions", "scheduled_jobs"):
        conn.execute(f"DELETE FROM {table}")
    conn.execute("DELETE FROM memory")
    conn.commit(); conn.close()


def test_subscription_crud_and_duplicate_protection():
    service = NewsService()
    created = service.create_subscription("AI")
    assert created["topic"] == "ai"
    with pytest.raises(ValueError, match="already exists"):
        service.create_subscription("ai")
    updated = service.update_subscription(created["id"], enabled=0, preference="critical")
    assert updated["enabled"] == 0 and updated["preference"] == "critical"
    assert service.delete_subscription(created["id"])


@pytest.mark.anyio
async def test_collection_deduplicates_and_rejects_unconfigured_hosts():
    service = NewsService()
    async def search(_query):
        return {"text": "Useful story https://openai.com/blog/story and duplicate https://openai.com/blog/story and bad https://evil.example/story"}
    stories = await service.collect("ai", search=search, limit=3)
    assert len(stories) == 1 and stories[0]["source"] == "openai.com"


def test_importance_and_memory_relevance_are_explainable():
    assert classify_story("Active exploitation of a zero-day", "cybersecurity")[0] == "critical"
    memory_service.add("project", "I am building cybersecurity projects", 0.9)
    service = NewsService()
    stored = service.store_stories([{"topic": "cybersecurity", "title": "Security update", "url": "https://cisa.gov/x", "source": "cisa.gov", "published_at": None, "retrieved_at": datetime.now(timezone.utc).isoformat()}])
    relevant = service.relevant(stored)
    assert relevant[0]["category"] == "important"
    assert relevant[0]["relevance"]


def test_briefing_contains_sources_and_delivery_failures_are_preserved():
    service = NewsService()
    story = service.store_stories([{"topic": "ai", "title": "AI launch", "url": "https://openai.com/x", "source": "openai.com", "published_at": None, "retrieved_at": "now"}])[0]
    briefing = service.generate([story], preference="all")
    assert "https://openai.com/x" in briefing["body"]
    class Failing:
        def send(self, *_): raise RuntimeError("offline")
    from backend.app.notifications.service import NotificationService
    import backend.app.news.service as news_module
    old = news_module.notification_service; news_module.notification_service = NotificationService(Failing())
    try:
        failed = service.deliver(briefing)
        assert failed["delivery_status"] == "failed"
    finally:
        news_module.notification_service = old


def test_scheduler_recovers_interrupted_news_jobs_and_avoids_duplicate_schedule():
    service = NewsService(); service.create_subscription("technology")
    scheduler = SchedulerService()
    service.ensure_schedules(scheduler); service.ensure_schedules(scheduler)
    conn = get_connection(); assert conn.execute("SELECT COUNT(*) FROM scheduled_jobs").fetchone()[0] == 1
    conn.execute("UPDATE scheduled_jobs SET status='running'"); conn.commit(); conn.close()
    real = SchedulerService()
    real._recover_interrupted_jobs()
    conn = get_connection(); assert conn.execute("SELECT status FROM scheduled_jobs").fetchone()[0] == "pending"; conn.close()
