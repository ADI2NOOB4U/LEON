"""Notification delivery that records task-level audit events."""

from __future__ import annotations

import asyncio

from backend.app.config.settings import settings
from backend.app.email.providers import EmailProvider, create_email_provider
from backend.app.jobs.task_manager import log_event
from backend.app.notifications.providers import NotificationProvider, create_notification_provider


class NotificationService:
    def __init__(
        self,
        provider: NotificationProvider | None = None,
        email_provider: EmailProvider | None = None,
        email_recipient: str | None = None,
    ) -> None:
        self._provider = provider or create_notification_provider()
        self._email_provider = email_provider
        self._email_recipient = (
            settings.email_task_result_to if email_recipient is None else email_recipient
        )
        if self._email_provider is None and self._email_recipient:
            self._email_provider = create_email_provider()

    def notify_task_outcome(self, task: dict, outcome: str) -> bool:
        task_id = task["id"]
        title = f"LEON task {outcome}: {task['title']}"
        body = task.get("result") or task.get("error") or f"Task status: {outcome}"
        try:
            self._provider.send(title, body)
        except Exception:
            log_event(task_id, "notification_failed", f"Task {outcome} notification failed.")
            sent = False
        else:
            log_event(task_id, "notification_sent", f"Task {outcome} notification sent.")
            sent = True
        self._send_optional_email(task, outcome, body)
        return sent

    def _send_optional_email(self, task: dict, outcome: str, body: str) -> None:
        if not self._email_provider or not self._email_recipient:
            return
        try:
            asyncio.run(
                self._email_provider.send(
                    self._email_recipient,
                    f"LEON task {outcome}: {task['title']}",
                    body,
                )
            )
        except Exception:
            log_event(task["id"], "email_failed", "Task-result email delivery failed.")
        else:
            log_event(task["id"], "email_sent", "Task-result email sent.")

    def send(self, title: str, body: str) -> None:
        """Deliver a non-task notification through the configured provider."""
        self._provider.send(title, body)


notification_service = NotificationService()
