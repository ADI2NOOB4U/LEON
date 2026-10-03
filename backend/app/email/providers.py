"""Provider-neutral email delivery with an optional Gmail API adapter."""

from __future__ import annotations

import asyncio
import base64
from email.mime.text import MIMEText
from typing import Protocol

from backend.app.config.settings import settings


class EmailProvider(Protocol):
    """A provider capable of sending a plain-text message."""

    async def send(self, to: str, subject: str, body: str) -> str:
        """Send a message and return the provider's opaque message identifier."""


class EmailProviderUnavailable(RuntimeError):
    """Raised when email delivery has not been configured."""


class UnavailableEmailProvider:
    async def send(self, to: str, subject: str, body: str) -> str:
        raise EmailProviderUnavailable("No email provider is configured")


class MockEmailProvider:
    """In-memory provider for tests; it never sends network traffic."""

    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []

    async def send(self, to: str, subject: str, body: str) -> str:
        self.messages.append({"to": to, "subject": subject, "body": body})
        return f"mock-{len(self.messages)}"


class GmailEmailProvider:
    """Gmail API adapter using OAuth credentials supplied through settings."""

    def __init__(
        self, client_id: str, client_secret: str, refresh_token: str, sender: str
    ) -> None:
        if not all((client_id, client_secret, refresh_token, sender)):
            raise EmailProviderUnavailable("Gmail credentials are incomplete")
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._sender = sender

    async def send(self, to: str, subject: str, body: str) -> str:
        return await asyncio.to_thread(self._send_sync, to, subject, body)

    def _send_sync(self, to: str, subject: str, body: str) -> str:
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise EmailProviderUnavailable(
                "Gmail support is unavailable; install backend requirements"
            ) from exc

        credentials = Credentials(
            token=None,
            refresh_token=self._refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self._client_id,
            client_secret=self._client_secret,
        )
        message = MIMEText(body, "plain", "utf-8")
        message["To"] = to
        message["From"] = self._sender
        message["Subject"] = subject
        encoded = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
        response = build("gmail", "v1", credentials=credentials, cache_discovery=False).users().messages().send(
            userId="me", body={"raw": encoded}
        ).execute()
        return str(response["id"])


def create_email_provider() -> EmailProvider:
    """Create the explicitly configured provider without exposing its credentials."""
    provider_name = settings.email_provider.strip().lower()
    if provider_name == "mock":
        return MockEmailProvider()
    if provider_name == "gmail" or (
        not provider_name
        and all(
            (
                settings.gmail_client_id,
                settings.gmail_client_secret,
                settings.gmail_refresh_token,
                settings.gmail_sender,
            )
        )
    ):
        return GmailEmailProvider(
            settings.gmail_client_id,
            settings.gmail_client_secret,
            settings.gmail_refresh_token,
            settings.gmail_sender,
        )
    return UnavailableEmailProvider()
