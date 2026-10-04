import asyncio

import httpx
import pytest
from pydantic import SecretStr

from backend.app.config.settings import settings
from backend.app.core.providers.openai_compatible import GeminiProvider
from backend.app.security.cloud_privacy import CloudPrivacyError


def _set_key(monkeypatch, value="test-gemini-key"):
    monkeypatch.setattr(settings, "gemini_api_key", SecretStr(value))


def _response(data, status_code=200):
    class DummyResponse:
        def raise_for_status(self):
            if status_code >= 400:
                request = httpx.Request("POST", "https://generativelanguage.googleapis.com/v1beta/interactions")
                response = httpx.Response(status_code, request=request)
                response.raise_for_status()

        def json(self):
            return data

    return DummyResponse()


def _install_client(monkeypatch, response=None, error=None):
    captured = []

    class DummyAsyncClient:
        def __init__(self, *args, **kwargs):
            captured.append({"client": kwargs})
            self.closed = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_value, traceback):
            self.closed = True
            return False

        async def post(self, url, **kwargs):
            assert not self.closed
            captured.append({"url": url, **kwargs})
            if error:
                raise error
            return response

    monkeypatch.setattr(httpx, "AsyncClient", DummyAsyncClient)
    return captured


def test_interactions_request_is_stateless_and_contains_only_latest_public_text(monkeypatch):
    _set_key(monkeypatch)
    monkeypatch.setattr(settings, "cloud_ai_search_grounding", True)
    result = _response(
        {
            "steps": [
                {"type": "thought", "summary": [{"type": "text", "text": "not for user"}]},
                {
                    "type": "model_output",
                    "content": [
                        {
                            "type": "text",
                            "text": "A public answer.",
                            "annotations": [
                                {
                                    "type": "url_citation",
                                    "url": "https://example.test/source",
                                    "title": "Example source",
                                }
                            ],
                        }
                    ],
                },
            ]
        }
    )
    captured = _install_client(monkeypatch, response=result)
    provider = GeminiProvider()

    answer = asyncio.run(
        provider.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "memory: private workspace facts; .env; "
                        "API_KEY=AIzaFakeCredentialForUnitTest012345; "
                        "camera image; microphone recording"
                    ),
                },
                {"role": "user", "content": "earlier turn"},
                {"role": "assistant", "content": "previous assistant reply"},
                {"role": "user", "content": "What is photosynthesis?"},
            ],
            grounding=True,
        )
    )

    request = captured[1]
    assert request["url"] == "https://generativelanguage.googleapis.com/v1beta/interactions"
    assert request["headers"]["x-goog-api-key"] == "test-gemini-key"
    assert request["json"] == {
        "model": settings.cloud_ai_model,
        "input": "What is photosynthesis?",
        "store": False,
        "tools": [{"type": "google_search"}],
    }
    assert "memory" not in str(request["json"])
    assert ".env" not in str(request["json"])
    assert "AIzaFakeCredentialForUnitTest012345" not in str(request["json"])
    assert "camera image" not in str(request["json"])
    assert "microphone recording" not in str(request["json"])
    assert "earlier turn" not in str(request["json"])
    assert answer == (
        "A public answer.\n\nSources:\n"
        "- Example source: https://example.test/source"
    )


def test_gemini_key_is_redacted_from_provider_output(monkeypatch):
    api_key = "test-gemini-key"
    _set_key(monkeypatch, api_key)
    _install_client(
        monkeypatch,
        response=_response(
            {
                "steps": [
                    {
                        "type": "model_output",
                        "content": [
                            {"type": "text", "text": f"Echoed credential: {api_key}"}
                        ],
                    }
                ]
            }
        ),
    )

    answer = asyncio.run(
        GeminiProvider().chat([{"role": "user", "content": "What is photosynthesis?"}])
    )

    assert api_key not in answer
    assert "[REDACTED]" in answer


@pytest.mark.parametrize(
    "text",
    [
        "Read my .env file.",
        "Summarize this private medical document.",
        "What is in this camera image?",
        "Transcribe this microphone recording.",
        "API_KEY=sk-test-0123456789abcdef",
        "Review my local workspace source code.",
        "Summarize C:\\Users\\me\\Documents\\notes.txt",
    ],
)
def test_sensitive_or_local_content_is_blocked_before_cloud_request(monkeypatch, text):
    _set_key(monkeypatch)
    captured = _install_client(monkeypatch, response=_response({"steps": []}))

    with pytest.raises(CloudPrivacyError):
        asyncio.run(
            GeminiProvider().chat(
                [{"role": "user", "content": text}],
                grounding=True,
            )
        )
    assert len(captured) == 0


def test_binary_media_cannot_be_sent_as_cloud_chat_text(monkeypatch):
    _set_key(monkeypatch)
    captured = _install_client(monkeypatch, response=_response({"steps": []}))

    with pytest.raises(CloudPrivacyError):
        asyncio.run(
            GeminiProvider().chat(
                [{"role": "user", "content": b"camera or microphone bytes"}]
            )
        )
    assert len(captured) == 0


def test_missing_api_key_fails_without_request(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", SecretStr(""))
    captured = _install_client(monkeypatch, response=_response({"steps": []}))

    with pytest.raises(RuntimeError, match="API key is not configured"):
        asyncio.run(GeminiProvider().chat([{"role": "user", "content": "Public question"}]))
    assert len(captured) == 0


@pytest.mark.parametrize("status_code", [401, 403, 429])
def test_auth_and_rate_limit_responses_are_not_hidden(monkeypatch, status_code):
    _set_key(monkeypatch)
    _install_client(monkeypatch, response=_response({}, status_code=status_code))

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(GeminiProvider().chat([{"role": "user", "content": "Public question"}]))


def test_timeout_is_not_hidden(monkeypatch):
    _set_key(monkeypatch)
    _install_client(monkeypatch, error=httpx.ReadTimeout("request timed out"))

    with pytest.raises(httpx.ReadTimeout):
        asyncio.run(GeminiProvider().chat([{"role": "user", "content": "Public question"}]))


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"steps": "not-a-list"},
        {"steps": [{"type": "model_output", "content": None}]},
        {"steps": [{"type": "model_output", "content": [{"type": "image"}]}]},
    ],
)
def test_malformed_interaction_responses_fail_without_echoing_response_body(
    monkeypatch, payload
):
    _set_key(monkeypatch)
    _install_client(monkeypatch, response=_response(payload))

    with pytest.raises(RuntimeError, match="Gemini returned"):
        asyncio.run(GeminiProvider().chat([{"role": "user", "content": "Public question"}]))
