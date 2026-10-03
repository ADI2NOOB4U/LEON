"""Confirmation-gated email tools."""

from __future__ import annotations

from email.utils import parseaddr
from typing import Any

from backend.app.config.settings import settings
from backend.app.email.providers import EmailProvider, create_email_provider
from backend.app.jobs.task_manager import get_task, log_event
from backend.app.tools.base import BaseTool
from backend.app.tools.registry import ToolRegistry


def _validate_message(to: str, subject: str, body: str) -> tuple[str, str, str]:
    if not isinstance(to, str) or "\r" in to or "\n" in to:
        raise ValueError("to must be a valid email address")
    _, address = parseaddr(to)
    if not address or address != to.strip() or "@" not in address:
        raise ValueError("to must be a valid email address")
    if not isinstance(subject, str) or not subject.strip() or "\r" in subject or "\n" in subject:
        raise ValueError("subject must be a non-empty single-line string")
    if not isinstance(body, str) or not body.strip():
        raise ValueError("body must be a non-empty string")
    if len(subject) > 500 or len(body) > 100_000:
        raise ValueError("email subject or body is too long")
    return address, subject.strip(), body


class SendEmailTool(BaseTool):
    name = "send_email"
    description = "Send a plain-text email through the configured provider."
    permission = "CONFIRM"

    def __init__(self, provider: EmailProvider | None = None) -> None:
        self._provider = provider or create_email_provider()

    async def execute(
        self, to: str = "", subject: str = "", body: str = "", **kwargs: Any
    ) -> dict[str, Any]:
        if kwargs:
            raise ValueError("send_email received unexpected arguments")
        to, subject, body = _validate_message(to, subject, body)
        message_id = await self._provider.send(to, subject, body)
        return {"tool": self.name, "to": to, "message_id": message_id, "sent": True}


class SendTaskResultTool(BaseTool):
    name = "send_task_result"
    description = "Email a completed task result to the configured task-result recipient."
    permission = "CONFIRM"

    def __init__(self, provider: EmailProvider | None = None, recipient: str | None = None) -> None:
        self._provider = provider or create_email_provider()
        self._recipient = recipient if recipient is not None else settings.email_task_result_to

    async def execute(self, task_id: int = 0, **kwargs: Any) -> dict[str, Any]:
        if kwargs:
            raise ValueError("send_task_result received unexpected arguments")
        if isinstance(task_id, bool) or not isinstance(task_id, int) or task_id < 1:
            raise ValueError("task_id must be a positive integer")
        task = get_task(task_id)
        if not task:
            raise ValueError("Task not found")
        to, _, _ = _validate_message(self._recipient, "Task result", "placeholder")
        subject = f"LEON task #{task_id}: {task['title']}"
        body = task["result"] or task["error"] or f"Task status: {task['status']}"
        try:
            message_id = await self._provider.send(to, subject, body)
        except Exception:
            log_event(task_id, "email_failed", "Task-result email delivery failed.")
            raise
        log_event(task_id, "email_sent", "Task-result email sent.")
        return {"tool": self.name, "task_id": task_id, "to": to, "message_id": message_id, "sent": True}


def register_email_tools(registry: ToolRegistry) -> ToolRegistry:
    """Register confirmation-gated email tools."""
    registry.register(SendEmailTool())
    registry.register(SendTaskResultTool())
    return registry
