"""Provider-neutral desktop and push notification interfaces."""

from __future__ import annotations

from typing import Protocol

from backend.app.config.settings import settings


class NotificationProvider(Protocol):
    def send(self, title: str, body: str) -> None:
        """Deliver a user-facing notification."""


class PushNotificationProvider(NotificationProvider, Protocol):
    """Interface for future remote push adapters."""


class MockNotificationProvider:
    def __init__(self) -> None:
        self.notifications: list[dict[str, str]] = []

    def send(self, title: str, body: str) -> None:
        self.notifications.append({"title": title, "body": body})


class DesktopNotificationProvider:
    """Desktop adapter; imports the optional backend lazily."""

    def send(self, title: str, body: str) -> None:
        try:
            from plyer import notification
        except ImportError as exc:
            raise RuntimeError("Desktop notifications are unavailable") from exc
        notification.notify(
            title=_truncate_notification_text(title, 63),
            message=_truncate_notification_text(body, 255),
            app_name="LEON",
        )


def _truncate_notification_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


class UnavailableNotificationProvider:
    def send(self, title: str, body: str) -> None:
        raise RuntimeError("No notification provider is configured")


def create_notification_provider() -> NotificationProvider:
    provider_name = settings.notification_provider.strip().lower()
    if provider_name in {"", "desktop"}:
        return DesktopNotificationProvider()
    if provider_name == "mock":
        return MockNotificationProvider()
    return UnavailableNotificationProvider()
