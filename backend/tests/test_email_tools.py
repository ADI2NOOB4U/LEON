import pytest

from backend.app.email.providers import MockEmailProvider, UnavailableEmailProvider, create_email_provider
from backend.app.jobs.task_manager import create_task, get_task_logs, update_task
from backend.app.security.permissions import PermissionManager
from backend.app.tools.email_tools import SendEmailTool, SendTaskResultTool


@pytest.mark.anyio
async def test_send_email_uses_mock_provider_without_network():
    provider = MockEmailProvider()
    result = await SendEmailTool(provider).execute(
        to="person@example.test", subject="Hello", body="Message body"
    )

    assert result == {
        "tool": "send_email",
        "to": "person@example.test",
        "message_id": "mock-1",
        "sent": True,
    }
    assert provider.messages == [{"to": "person@example.test", "subject": "Hello", "body": "Message body"}]


@pytest.mark.anyio
async def test_send_email_rejects_header_injection_and_requires_confirmation():
    tool = SendEmailTool(MockEmailProvider())

    with pytest.raises(ValueError, match="valid email"):
        await tool.execute(to="person@example.test\nBcc: attacker@example.test", subject="Hello", body="body")
    with pytest.raises(ValueError, match="single-line"):
        await tool.execute(to="person@example.test", subject="Hello\r\nBcc: x", body="body")
    assert not PermissionManager().can_execute(tool)


@pytest.mark.anyio
async def test_send_task_result_delivers_and_records_audit_event():
    task_id = create_task("Email my result")
    update_task(task_id, result="Done")
    provider = MockEmailProvider()

    result = await SendTaskResultTool(provider, "owner@example.test").execute(task_id=task_id)

    assert result["message_id"] == "mock-1"
    assert provider.messages[0]["body"] == "Done"
    assert "email_sent" in [entry["stage"] for entry in get_task_logs(task_id)]


@pytest.mark.anyio
async def test_send_task_result_records_failed_delivery():
    class FailingProvider:
        async def send(self, to, subject, body):
            raise RuntimeError("provider unavailable")

    task_id = create_task("Email failure")
    with pytest.raises(RuntimeError, match="provider unavailable"):
        await SendTaskResultTool(FailingProvider(), "owner@example.test").execute(task_id=task_id)

    assert "email_failed" in [entry["stage"] for entry in get_task_logs(task_id)]


def test_unconfigured_provider_does_not_send(monkeypatch):
    import backend.app.email.providers as providers

    monkeypatch.setattr(providers.settings, "email_provider", "")
    monkeypatch.setattr(providers.settings, "gmail_client_id", "")
    monkeypatch.setattr(providers.settings, "gmail_client_secret", "")
    monkeypatch.setattr(providers.settings, "gmail_refresh_token", "")
    monkeypatch.setattr(providers.settings, "gmail_sender", "")

    assert isinstance(create_email_provider(), UnavailableEmailProvider)
