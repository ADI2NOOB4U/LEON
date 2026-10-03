import asyncio
import base64
import io
import threading
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app.config.settings import Settings, settings
from backend.app.voice.service import FishAudioTTS, LeonVoiceService, VoiceServiceError


class FakeAgent:
    def __init__(self):
        self.messages = []

    async def chat(self, message):
        self.messages.append(message)
        return "Hello from LEON."


class FakeWhisperModel:
    def __init__(self):
        self.options = []
        self.thread_id = None

    def transcribe(self, audio_path, **options):
        self.thread_id = threading.get_ident()
        self.options.append(options)
        assert Path(audio_path).read_bytes() == b"mock recording"

        class Segment:
            text = "What is the weather?"

        return iter([Segment()]), object()


class FakePiperVoice:
    def __init__(self):
        self.messages = []
        self.thread_id = None

    def synthesize_wav(self, text, wav_file):
        self.thread_id = threading.get_ident()
        self.messages.append(text)
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)
        wav_file.writeframes(b"\x00\x00" * 8)


def test_voice_turn_transcribes_calls_agent_and_returns_speech(monkeypatch):
    event_loop_thread = threading.get_ident()
    agent = FakeAgent()
    whisper = FakeWhisperModel()
    piper = FakePiperVoice()
    service = LeonVoiceService(agent)
    monkeypatch.setattr(service, "_load_stt_model", lambda: whisper)
    monkeypatch.setattr(service, "_load_tts_voice", lambda: piper)

    result = asyncio.run(service.process(b"mock recording", ".webm"))

    assert result["transcript"] == "What is the weather?"
    assert result["assistant"] == "Hello from LEON."
    assert agent.messages == ["What is the weather?"]
    assert piper.messages == ["Hello from LEON."]
    assert whisper.options == [{"vad_filter": True}]
    assert whisper.thread_id != event_loop_thread
    assert piper.thread_id != event_loop_thread
    speech = base64.b64decode(result["audio_base64"])
    with wave.open(io.BytesIO(speech), "rb") as wav_file:
        assert wav_file.getframerate() == 16000
    assert result["audio_content_type"] == "audio/wav"


def test_voice_turn_reports_missing_local_stt_model(tmp_path):
    service = LeonVoiceService(
        FakeAgent(),
        stt_model_path=tmp_path / "missing-model",
        tts_model_path=tmp_path / "missing-voice.onnx",
    )

    with pytest.raises(VoiceServiceError, match="local faster-whisper model is missing"):
        asyncio.run(service.process(b"mock recording", ".webm"))


def test_voice_turn_keeps_text_when_piper_is_unavailable(monkeypatch):
    agent = FakeAgent()
    service = LeonVoiceService(agent)
    monkeypatch.setattr(service, "_load_stt_model", lambda: FakeWhisperModel())

    def missing_voice():
        raise VoiceServiceError("The local Piper voice is missing.")

    monkeypatch.setattr(service, "_load_tts_voice", missing_voice)
    result = asyncio.run(service.process(b"mock recording", ".webm"))

    assert result["transcript"] == "What is the weather?"
    assert result["assistant"] == "Hello from LEON."
    assert result["audio_base64"] == ""
    assert result["audio_error"] == "The local Piper voice is missing."


def test_fish_audio_tts_uses_server_credentials_and_current_api(monkeypatch):
    request = {}

    def fake_post(url, **kwargs):
        request.update(url=url, **kwargs)
        return SimpleNamespace(
            content=b"fish wav bytes",
            raise_for_status=lambda: None,
        )

    monkeypatch.setattr("backend.app.voice.service.httpx.post", fake_post)
    provider = FishAudioTTS(
        api_key="server-only-key",
        model="s2.1-pro-free",
        reference_id="leon-voice-id",
    )

    assert provider.synthesize("Hello from LEON.") == b"fish wav bytes"
    assert request["url"] == "https://api.fish.audio/v1/tts"
    assert request["headers"] == {
        "Authorization": "Bearer server-only-key",
        "model": "s2.1-pro-free",
    }
    assert request["json"] == {
        "text": "Hello from LEON.",
        "format": "wav",
        "reference_id": "leon-voice-id",
    }


def test_voice_provider_is_selected_from_settings(monkeypatch):
    monkeypatch.setenv("VOICE_PROVIDER", "fish_audio")
    voice_provider = Settings(_env_file=None).voice_provider
    monkeypatch.setattr(settings, "voice_provider", voice_provider)

    assert LeonVoiceService(FakeAgent()).voice_provider == "fish_audio"


def test_fish_audio_failure_falls_back_to_piper(monkeypatch):
    monkeypatch.setattr(settings, "voice_provider", "fish_audio")
    agent = FakeAgent()
    piper = FakePiperVoice()
    service = LeonVoiceService(agent)
    monkeypatch.setattr(service, "_load_stt_model", lambda: FakeWhisperModel())
    monkeypatch.setattr(service, "_load_tts_voice", lambda: piper)

    class FailingFishAudio:
        def synthesize(self, text):
            raise VoiceServiceError("Fish Audio speech synthesis failed.")

    monkeypatch.setattr(service, "_load_fish_audio_tts", lambda: FailingFishAudio())
    result = asyncio.run(service.process(b"mock recording", ".webm"))

    assert agent.messages == ["What is the weather?"]
    assert piper.messages == ["Hello from LEON."]
    assert base64.b64decode(result["audio_base64"]).startswith(b"RIFF")
    assert result["audio_error"] is None


def test_both_tts_providers_failing_preserves_transcript_and_reply(monkeypatch):
    monkeypatch.setattr(settings, "voice_provider", "fish_audio")
    service = LeonVoiceService(FakeAgent())
    monkeypatch.setattr(service, "_load_stt_model", lambda: FakeWhisperModel())

    class FailingFishAudio:
        def synthesize(self, text):
            raise VoiceServiceError("Fish Audio speech synthesis failed.")

    def fail_piper():
        raise VoiceServiceError("The local Piper voice is missing.")

    monkeypatch.setattr(service, "_load_fish_audio_tts", lambda: FailingFishAudio())
    monkeypatch.setattr(service, "_load_tts_voice", fail_piper)
    result = asyncio.run(service.process(b"mock recording", ".webm"))

    assert result["transcript"] == "What is the weather?"
    assert result["assistant"] == "Hello from LEON."
    assert result["audio_base64"] == ""
    assert "Fish Audio speech synthesis failed." in result["audio_error"]
    assert "local Piper voice is missing" in result["audio_error"]
    assert "server-only-key" not in str(result)


def test_fish_audio_provider_does_not_send_request_without_api_key(monkeypatch):
    def unexpected_request(*args, **kwargs):
        raise AssertionError("Fish Audio request should not be made without a key")

    monkeypatch.setattr("backend.app.voice.service.httpx.post", unexpected_request)
    provider = FishAudioTTS(api_key="", model="s2.1-pro-free")

    with pytest.raises(VoiceServiceError, match="FISH_AUDIO_API_KEY"):
        provider.synthesize("Hello")


def test_voice_turn_rejects_empty_and_oversized_recordings():
    service = LeonVoiceService(FakeAgent())

    with pytest.raises(VoiceServiceError, match="recording was empty"):
        asyncio.run(service.process(b"", ".webm"))

    with pytest.raises(VoiceServiceError, match="too large"):
        asyncio.run(service.process(b"x" * (25 * 1024 * 1024 + 1), ".webm"))


def test_voice_api_accepts_audio_upload(monkeypatch):
    from fastapi.testclient import TestClient

    from backend.app.api import voice
    from backend.app.main import app

    async def process(recording, suffix):
        assert recording == b"mock recording"
        assert suffix == ".webm"
        return {
            "transcript": "Hello",
            "assistant": "Hi there.",
            "audio_base64": "",
            "audio_content_type": "audio/wav",
        }

    monkeypatch.setattr(voice.voice_service, "process", process)
    response = TestClient(app).post(
        "/api/voice/turn",
        files={"audio": ("recording.webm", b"mock recording", "audio/webm")},
    )

    assert response.status_code == 200
    assert response.json()["transcript"] == "Hello"
    assert response.json()["assistant"] == "Hi there."