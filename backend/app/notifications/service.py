"""Notification delivery that records task-level audit events."""

from __future__ import annotations

from backend.app.jobs.task_manager import log_event
from backend.app.notifications.providers import NotificationProvider, create_notification_provider


class NotificationService:
    def __init__(self, provider: NotificationProvider | None = None) -> None:
        self._provider = provider or create_notification_provider()

    def notify_task_outcome(self, task: dict, outcome: str) -> bool:
        task_id = task["id"]
        title = f"LEON task {outcome}: {task['title']}"
        body = task.get("result") or task.get("error") or f"Task status: {outcome}"
        try:
            self._provider.send(title, body)
        except Exception:
            log_event(task_id, "notification_failed", f"Task {outcome} notification failed.")
            return False
        log_event(task_id, "notification_sent", f"Task {outcome} notification sent.")
        return True

    def send(self, title: str, body: str) -> None:
        """Deliver a non-task notification through the configured provider."""
        self._provider.send(title, body)


notification_service = NotificationService()
