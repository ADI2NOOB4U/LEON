from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Awaitable, Callable
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from backend.app.db.database import get_connection, now
from backend.app.memory.memory import memory_service
from backend.app.notifications.service import notification_service
from backend.app.tools.browser_tools import SearchWebTool, validate_http_url

TOPIC_NAMES = {"cybersecurity", "ai", "technology", "india"}
SOURCES = {
    "cybersecurity": ("cisa.gov", "krebsonsecurity.com", "bleepingcomputer.com"),
    "ai": ("openai.com", "anthropic.com", "blog.google"),
    "technology": ("arstechnica.com", "techcrunch.com", "theverge.com"),
    "india": ("thehindu.com", "indianexpress.com", "pib.gov.in"),
}
PREFERENCE_RANK = {"critical": 4, "important": 3, "interesting": 2, "ignore": 1}
ALLOWED_PREFERENCES = {"critical", "important", "all"}
URL_RE = re.compile(r"https?://[^\s<>\"')]+", re.I)


def validate_topic(topic: str) -> str:
    if not isinstance(topic, str):
        raise ValueError("topic must be a string")
    topic = " ".join(topic.strip().split())
    if not topic or len(topic) > 100 or not re.fullmatch(r"[\w][\w .+#/-]*", topic, re.UNICODE):
        raise ValueError("topic must contain 1-100 safe characters")
    return topic.lower()


def classify_story(title: str, topic: str, body: str = "") -> tuple[str, float, str]:
    text = f"{title} {body}".lower()
    critical = ("zero-day", "active exploitation", "breach", "recall", "emergency", "critical vulnerability")
    important = ("security update", "regulation", "launch", "funding", "acquisition", "policy", "outage")
    if any(term in text for term in critical):
        return "critical", 0.95, "Matched a high-impact safety, security, or emergency signal."
    if any(term in text for term in important):
        return "important", 0.75, "Matched a material product, policy, security, or industry change."
    if topic in text or any(term in text for term in topic.split()):
        return "interesting", 0.5, "Relevant to the subscribed topic but no high-impact signal was found."
    return "ignore", 0.1, "No strong importance or topic signal was found."


class NewsService:
    def subscriptions(self) -> list[dict[str, Any]]:
        conn = get_connection(); rows = conn.execute("SELECT * FROM news_subscriptions ORDER BY topic").fetchall(); conn.close()
        return [dict(row) for row in rows]

    def create_subscription(self, topic: str, schedule: str = "morning", preference: str = "important") -> dict[str, Any]:
        topic = validate_topic(topic); self._validate_preferences(schedule, preference)
        timestamp = now(); conn = get_connection()
        try:
            cur = conn.execute("INSERT INTO news_subscriptions(topic, enabled, schedule, preference, created_at, updated_at) VALUES (?,1,?,?,?,?)", (topic, schedule, preference, timestamp, timestamp))
            conn.commit(); subscription_id = int(cur.lastrowid)
        except Exception as exc:
            conn.rollback()
            if "UNIQUE" in str(exc).upper(): raise ValueError("subscription already exists") from exc
            raise
        finally: conn.close()
        return self.get_subscription(subscription_id)  # type: ignore[return-value]

    def get_subscription(self, subscription_id: int) -> dict[str, Any] | None:
        conn = get_connection(); row = conn.execute("SELECT * FROM news_subscriptions WHERE id=?", (subscription_id,)).fetchone(); conn.close()
        return dict(row) if row else None

    def update_subscription(self, subscription_id: int, **changes: Any) -> dict[str, Any] | None:
        current = self.get_subscription(subscription_id)
        if not current: return None
        topic = validate_topic(changes.get("topic", current["topic"]))
        schedule = changes.get("schedule", current["schedule"]); preference = changes.get("preference", current["preference"])
        self._validate_preferences(schedule, preference)
        enabled = int(changes.get("enabled", current["enabled"]))
        if enabled not in (0, 1): raise ValueError("enabled must be boolean")
        conn = get_connection()
        try:
            conn.execute("UPDATE news_subscriptions SET topic=?, schedule=?, preference=?, enabled=?, updated_at=? WHERE id=?", (topic, schedule, preference, enabled, now(), subscription_id)); conn.commit()
        except Exception as exc:
            conn.rollback()
            if "UNIQUE" in str(exc).upper(): raise ValueError("subscription already exists") from exc
            raise
        finally: conn.close()
        return self.get_subscription(subscription_id)

    def delete_subscription(self, subscription_id: int) -> bool:
        conn = get_connection(); cur = conn.execute("DELETE FROM news_subscriptions WHERE id=?", (subscription_id,)); conn.commit(); conn.close(); return cur.rowcount > 0

    async def collect(self, topic: str, search: Callable[[str], Awaitable[dict[str, Any]]] | None = None, limit: int = 3) -> list[dict[str, Any]]:
        topic = validate_topic(topic); search = search or SearchWebTool().execute
        domains = SOURCES.get(topic, ())
        queries = [f"site:{domain} {topic} latest" for domain in domains] if domains else [f'"{topic}" latest news']
        output: list[dict[str, Any]] = []
        for query in queries[:max(1, min(limit, 10))]:
            try: result = await search(query)
            except Exception: continue
            for url in URL_RE.findall(str(result.get("text", ""))):
                url = url.rstrip(".,;]")
                try: validate_http_url(url)
                except ValueError: continue
                host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
                if domains and not any(host == d or host.endswith("." + d) for d in domains): continue
                title = self._title_from_result(result.get("text", ""), url, topic)
                output.append({"topic": topic, "title": title, "url": url, "source": host, "published_at": None, "retrieved_at": now()})
        return self._dedupe(output)

    def store_stories(self, stories: list[dict[str, Any]]) -> list[dict[str, Any]]:
        conn = get_connection(); ids = []
        for story in stories:
            category, score, reason = classify_story(story["title"], story["topic"])
            conn.execute("INSERT OR IGNORE INTO news_stories(topic,title,url,source,published_at,retrieved_at,category,score,reason,classified_at) VALUES (?,?,?,?,?,?,?,?,?,?)", (*[story.get(k) for k in ("topic","title","url","source","published_at","retrieved_at")], category, score, reason, now()))
            row = conn.execute("SELECT * FROM news_stories WHERE url=?", (story["url"],)).fetchone()
            if row: ids.append(dict(row))
        conn.commit(); conn.close(); return ids

    def relevant(self, stories: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        for story in stories:
            context = memory_service.retrieve_relevant(f"{story['topic']} {story['title']}", limit=3, max_chars=700)
            story = dict(story); story["relevance"] = context; story["relevance_reason"] = "Matches saved LEON context." if context else "Matches the active subscription topic."
            result.append(story)
        return result

    def generate(self, stories: list[dict[str, Any]], schedule: str = "manual", preference: str = "important") -> dict[str, Any]:
        minimum = 4 if preference == "critical" else 3 if preference == "important" else 1
        selected = [s for s in self.relevant(stories) if PREFERENCE_RANK.get(s.get("category", "ignore"), 1) >= minimum]
        selected.sort(key=lambda s: (float(s.get("score") or 0), s.get("retrieved_at", "")), reverse=True)
        lines = [f"{s['title']} — {s['source']}\nFacts: {s['title']}.\nWhy it matters: {s.get('reason', 'Prioritized for your subscription.')}\nLEON interpretation: {s['relevance_reason']}\nSource: {s['url']}" for s in selected[:10]]
        headline = f"LEON {schedule} briefing" if selected else f"LEON {schedule} briefing — no prioritized stories"
        body = "\n\n".join(lines) or "No stories met the current importance preference."
        conn = get_connection(); cur = conn.execute("INSERT INTO briefings(schedule,headline,body,created_at,delivery_status) VALUES (?,?,?,?,?)", (schedule, headline, body, now(), "pending")); briefing_id = int(cur.lastrowid)
        for story in selected: conn.execute("INSERT OR IGNORE INTO briefing_stories(briefing_id,story_id) VALUES (?,?)", (briefing_id, story["id"]))
        conn.commit(); conn.close(); return self.get_briefing(briefing_id)  # type: ignore[return-value]

    def get_briefing(self, briefing_id: int) -> dict[str, Any] | None:
        conn = get_connection(); row = conn.execute("SELECT * FROM briefings WHERE id=?", (briefing_id,)).fetchone()
        if not row: conn.close(); return None
        item = dict(row); item["stories"] = [dict(x) for x in conn.execute("SELECT s.* FROM news_stories s JOIN briefing_stories b ON b.story_id=s.id WHERE b.briefing_id=? ORDER BY s.score DESC", (briefing_id,)).fetchall()]; item["deliveries"] = [dict(x) for x in conn.execute("SELECT * FROM briefing_deliveries WHERE briefing_id=?", (briefing_id,)).fetchall()]; conn.close(); return item

    def history(self) -> list[dict[str, Any]]:
        conn = get_connection(); ids = [r["id"] for r in conn.execute("SELECT id FROM briefings ORDER BY created_at DESC").fetchall()]; conn.close(); return [self.get_briefing(i) for i in ids]  # type: ignore[list-item]

    def deliver(self, briefing: dict[str, Any], channels: list[str] = ["desktop"]) -> dict[str, Any]:
        failures = []
        for channel in channels:
            error = None
            try:
                if channel == "desktop": notification_service.send(briefing["headline"], briefing["body"])
                elif channel == "push": raise RuntimeError("No push provider is configured")
                elif channel == "email": notification_service.send_email(briefing["headline"], briefing["body"])
                else: raise ValueError("unsupported delivery channel")
                status = "sent"
            except Exception as exc: status, error = "failed", str(exc); failures.append(error)
            conn = get_connection(); conn.execute("INSERT OR REPLACE INTO briefing_deliveries(briefing_id,channel,status,error,created_at) VALUES (?,?,?,?,?)", (briefing["id"], channel, status, error, now())); conn.commit(); conn.close()
        conn = get_connection(); conn.execute("UPDATE briefings SET delivery_status=?, delivery_error=? WHERE id=?", ("failed" if failures else "sent", "; ".join(failures) or None, briefing["id"])); conn.commit(); conn.close()
        return self.get_briefing(briefing["id"])  # type: ignore[return-value]

    async def run(self, schedule: str = "scheduled", subscription_id: int | None = None) -> dict[str, Any]:
        stories = []
        preferences = []
        for sub in self.subscriptions():
            if sub["enabled"] and (subscription_id is None or sub["id"] == subscription_id) and (sub["schedule"] == schedule or schedule == "scheduled"):
                stories.extend(self.store_stories(await self.collect(sub["topic"])))
                preferences.append(sub["preference"])
        preference = "all" if "all" in preferences else "important" if "important" in preferences else "critical"
        briefing = self.generate(stories, schedule, preference)
        return self.deliver(briefing, ["desktop"])

    def ensure_schedules(self, scheduler) -> None:
        """Create one durable recurring job per enabled subscription schedule."""
        for sub in self.subscriptions():
            if not sub["enabled"]: continue
            name = f"news-briefing-{sub['id']}"
            conn = get_connection(); existing = conn.execute("SELECT 1 FROM scheduled_jobs WHERE name=? AND status IN ('pending','running')", (name,)).fetchone(); conn.close()
            if existing: continue
            tz = timezone.utc; hour = 8 if sub["schedule"] == "morning" else 18
            if sub["schedule"].startswith("custom:"):
                clock, _, zone = sub["schedule"][7:].partition("@")
                hour, minute = map(int, clock.split(":"))
                if zone:
                    try: tz = ZoneInfo(zone)
                    except Exception: continue
            else: minute = 0
            local = datetime.now(tz).replace(hour=hour, minute=minute, second=0, microsecond=0)
            if local <= datetime.now(tz): local += timedelta(days=1)
            scheduler.schedule_recurring(name, local, 86400, {"type": "news_briefing", "schedule": sub["schedule"], "subscription_id": sub["id"]})

    @staticmethod
    def _dedupe(stories):
        seen = set(); return [s for s in stories if not (s["url"] in seen or seen.add(s["url"]))]

    @staticmethod
    def _title_from_result(text: str, url: str, topic: str) -> str:
        for line in text.splitlines():
            clean = line.strip()
            if clean and url not in clean and len(clean) > 10: return clean[:240]
        return f"{topic.title()} update from {urlsplit(url).hostname}"

    @staticmethod
    def _validate_preferences(schedule, preference):
        if schedule not in {"morning", "evening"} and not re.fullmatch(r"custom:\d{2}:\d{2}(?:@[A-Za-z_]+/[A-Za-z_]+)?", str(schedule)):
            raise ValueError("schedule must be morning, evening, or custom:HH:MM[@Timezone]")
        if preference not in ALLOWED_PREFERENCES: raise ValueError("preference must be critical, important, or all")


news_service = NewsService()
