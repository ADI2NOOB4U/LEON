import asyncio
import base64
import io
import threading
import wave
from types import SimpleNamespace

import av
import numpy as np
import pytest
from av import AudioFrame

from backend.app.config.settings import Settings, settings
from backend.app.voice.service import FishAudioTTS, LeonVoiceService, VoiceServiceError


class FakeAgent:
    def __init__(self):
        self.messages = []

    async def chat(self, message):
        self.messages.append(message)
        return "Hello from LEON."


class FakeWhisperModel:
    def __init__(self, transcript="What is the weather?"):
        self.options = []
        self.thread_id = None
        self.audio_samples = None
        self.transcript = transcript

    def transcribe(self, audio_samples, **options):
        self.thread_id = threading.get_ident()
        self.options.append(options)
        self.audio_samples = audio_samples
        assert isinstance(audio_samples, np.ndarray)
        assert audio_samples.dtype == np.float32
        assert audio_samples.size

        class Segment:
            text = self.transcript

        return iter([Segment()]), object()


def wav_recording():
    audio = io.BytesIO()
    with wave.open(audio, "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(16000)
        recording.writeframes(b"\x01\x00" * 1600)
    return audio.getvalue()


def webm_opus_recording():
    audio = io.BytesIO()
    with av.open(audio, mode="w", format="webm") as container:
        stream = container.add_stream("libopus", rate=48000)
        frame = AudioFrame.from_ndarray(
            np.zeros((1, 48000), dtype=np.int16),
            format="s16",
            layout="mono",
        )
        frame.sample_rate = 48000
        for packet in stream.encode(frame):
            container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return audio.getvalue()


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


@pytest.fixture(autouse=True)
def use_mock_piper_provider(monkeypatch):
    """Keep voice service tests independent from backend/.env provider settings."""
    monkeypatch.setattr(settings, "voice_provider", "piper")


def test_voice_turn_transcribes_calls_agent_and_returns_speech(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr("backend.app.voice.service.tempfile.tempdir", str(tmp_path))
    event_loop_thread = threading.get_ident()
    agent = FakeAgent()
    whisper = FakeWhisperModel()
    piper = FakePiperVoice()
    service = LeonVoiceService(agent)
    monkeypatch.setattr(service, "_load_stt_model", lambda: whisper)
    monkeypatch.setattr(service, "_load_tts_voice", lambda: piper)

    result = asyncio.run(service.process(wav_recording(), ".wav"))

    assert result["transcript"] == "What is the weather?"
    assert result["assistant"] == "Hello from LEON."
    assert agent.messages == ["What is the weather?"]
    assert piper.messages == ["Hello from LEON."]
    assert whisper.options == [{"vad_filter": True}]
    assert whisper.audio_samples.size == 1600
    assert whisper.thread_id != event_loop_thread
    assert piper.thread_id != event_loop_thread
    speech = base64.b64decode(result["audio_base64"])
    with wave.open(io.BytesIO(speech), "rb") as wav_file:
        assert wav_file.getframerate() == 16000
    assert result["audio_content_type"] == "audio/wav"
    assert list(tmp_path.iterdir()) == []


def test_voice_media_command_is_explicitly_confirmed(monkeypatch):
    from backend.app.intelligence import intelligence_core

    agent = FakeAgent()
    service = LeonVoiceService(agent)
    piper = FakePiperVoice()
    monkeypatch.setattr(
        service,
        "_load_stt_model",
        lambda: FakeWhisperModel("Play Here Comes the Sun on YouTube Music."),
    )
    monkeypatch.setattr(service, "_load_tts_voice", lambda: piper)
    monkeypatch.setattr(
        intelligence_core,
        "route",
        lambda _transcript: SimpleNamespace(route="media.spotify"),
    )
    calls = {}

    async def execute_command(request):
        calls["confirmed"] = request.confirmed
        return {"message": "Opened YouTube Music search."}

    monkeypatch.setattr("backend.app.api.command.command", execute_command)

    result = asyncio.run(service.process(wav_recording(), ".wav"))

    assert calls["confirmed"] is True
    assert result["assistant"] == "Opened YouTube Music search."


def test_transcription_retries_without_vad_for_quiet_speech(tmp_path, monkeypatch):
    class VADFallbackWhisper:
        def __init__(self):
            self.options = []

        def transcribe(self, audio_samples, **options):
            self.options.append(options)

            class Segment:
                text = "" if options["vad_filter"] else "Hello, Leon."

            return iter([Segment()]), object()

    whisper = VADFallbackWhisper()
    service = LeonVoiceService(
        FakeAgent(),
        stt_model_path=tmp_path / "unused-model",
    )
    monkeypatch.setattr(service, "_load_stt_model", lambda: whisper)

    transcript = service._transcribe(wav_recording(), ".wav")

    assert transcript == "Hello, Leon."
    assert whisper.options == [{"vad_filter": True}, {"vad_filter": False}]


def test_transcription_still_rejects_audio_with_no_recognized_speech(
    tmp_path,
    monkeypatch,
):
    class SilentWhisper:
        def transcribe(self, audio_samples, **options):
            return iter([]), object()

    service = LeonVoiceService(
        FakeAgent(),
        stt_model_path=tmp_path / "unused-model",
    )
    monkeypatch.setattr(service, "_load_stt_model", lambda: SilentWhisper())

    with pytest.raises(VoiceServiceError, match="No speech was detected"):
        service._transcribe(wav_recording(), ".wav")


def test_voice_tts_receives_only_user_facing_agent_text(monkeypatch):
    from backend.app.core.agent import LeonAgent

    class ThinkingRouter:
        async def chat(self, messages, role="general", **kwargs):
            return "<think>hidden reasoning</think>Spoken answer."

    agent = LeonAgent()
    agent.router = ThinkingRouter()
    piper = FakePiperVoice()
    service = LeonVoiceService(agent)
    monkeypatch.setattr(
        service,
        "_load_stt_model",
        lambda: FakeWhisperModel("What did you say?"),
    )
    monkeypatch.setattr(service, "_load_tts_voice", lambda: piper)

    result = asyncio.run(service.process(wav_recording(), ".wav"))

    assert result["assistant"] == "Spoken answer."
    assert piper.messages == ["Spoken answer."]


def test_webm_opus_voice_turn_decodes_and_runs_full_pipeline(monkeypatch):
    agent = FakeAgent()
    whisper = FakeWhisperModel()
    piper = FakePiperVoice()
    service = LeonVoiceService(agent)
    monkeypatch.setattr(service, "_load_stt_model", lambda: whisper)
    monkeypatch.setattr(service, "_load_tts_voice", lambda: piper)

    result = asyncio.run(service.process(webm_opus_recording(), ".webm"))

    assert result["transcript"] == "What is the weather?"
    assert result["assistant"] == "Hello from LEON."
    assert whisper.audio_samples.size == 16000
    assert agent.messages == ["What is the weather?"]
    assert piper.messages == ["Hello from LEON."]
    assert base64.b64decode(result["audio_base64"]).startswith(b"RIFF")


def test_voice_turn_reports_missing_local_stt_model(tmp_path):
    service = LeonVoiceService(
        FakeAgent(),
        stt_model_path=tmp_path / "missing-model",
        tts_model_path=tmp_path / "missing-voice.onnx",
    )

    with pytest.raises(VoiceServiceError, match="local faster-whisper model is missing"):
        asyncio.run(service.process(wav_recording(), ".wav"))


def test_voice_turn_keeps_text_when_piper_is_unavailable(monkeypatch):
    agent = FakeAgent()
    service = LeonVoiceService(agent)
    monkeypatch.setattr(service, "_load_stt_model", lambda: FakeWhisperModel())

    def missing_voice():
        raise VoiceServiceError("The local Piper voice is missing.")

    monkeypatch.setattr(service, "_load_tts_voice", missing_voice)
    result = asyncio.run(service.process(wav_recording(), ".wav"))

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
            assert text == "Hello from LEON."
            raise VoiceServiceError("Fish Audio speech synthesis failed.")

    monkeypatch.setattr(service, "_load_fish_audio_tts", lambda: FailingFishAudio())
    result = asyncio.run(service.process(wav_recording(), ".wav"))

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
            assert text == "Hello from LEON."
            raise VoiceServiceError("Fish Audio speech synthesis failed.")

    def fail_piper():
        raise VoiceServiceError("The local Piper voice is missing.")

    monkeypatch.setattr(service, "_load_fish_audio_tts", lambda: FailingFishAudio())
    monkeypatch.setattr(service, "_load_tts_voice", fail_piper)
    result = asyncio.run(service.process(wav_recording(), ".wav"))

    assert result["transcript"] == "What is the weather?"
    assert result["assistant"] == "Hello from LEON."
    assert result["audio_base64"] == ""
    assert "Fish Audio speech synthesis failed." in result["audio_error"]
    assert "local Piper voice is missing" in result["audio_error"]
    assert "server-only-key" not in str(result)


def test_fish_audio_provider_does_not_send_request_without_api_key(monkeypatch):
    def unexpected_request(*args, **kwargs):
        assert args or kwargs
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


def test_invalid_audio_returns_decode_error_and_cleans_temporary_file(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr("backend.app.voice.service.tempfile.tempdir", str(tmp_path))
    service = LeonVoiceService(FakeAgent())

    with pytest.raises(VoiceServiceError) as error:
        service._transcribe(b"not an audio file", ".webm")

    assert error.value.status_code == 422
    assert error.value.code == "audio_decode_failed"
    assert error.value.diagnostic
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "invalid_audio",
    [
        b"not an audio file",
        b"RIFF\x00\x00\x00\x00WAVE",
    ],
)
def test_invalid_and_truncated_audio_are_rejected(invalid_audio):
    with pytest.raises(VoiceServiceError) as error:
        service = LeonVoiceService(FakeAgent())
        service._transcribe(invalid_audio, ".webm")

    assert error.value.status_code == 422
    assert error.value.code == "audio_decode_failed"


def test_stt_failure_is_reported_separately_from_decode_failure():
    service = LeonVoiceService(FakeAgent())

    class FailingWhisperModel:
        def transcribe(self, _audio_samples, **_options):
            assert _audio_samples.size
            assert _options == {"vad_filter": True}
            raise RuntimeError("inference failed")

    service._load_stt_model = lambda: FailingWhisperModel()
    with pytest.raises(VoiceServiceError) as error:
        service._transcribe(wav_recording(), ".wav")

    assert error.value.status_code == 503
    assert error.value.code == "transcription_failed"
    assert "Speech recognition failed" in str(error.value)


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


def test_voice_speech_api_returns_backend_generated_audio(monkeypatch):
    from fastapi.testclient import TestClient

    from backend.app.api import voice
    from backend.app.main import app

    calls = []

    def synthesize(text):
        calls.append(text)
        return b"RIFF-generated-audio", "piper", "test-voice", None

    monkeypatch.setattr(voice.voice_service, "_synthesize", synthesize)
    response = TestClient(app).post(
        "/api/voice/speech",
        json={"text": "  Read this reply aloud.  "},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content == b"RIFF-generated-audio"
    assert calls == ["Read this reply aloud."]


def test_voice_speech_api_surfaces_tts_errors(monkeypatch):
    from fastapi.testclient import TestClient

    from backend.app.api import voice
    from backend.app.main import app

    def fail_synthesis(_text):
        raise VoiceServiceError(
            "The configured voice provider is unavailable.",
            503,
            "tts_unavailable",
        )

    monkeypatch.setattr(voice.voice_service, "_synthesize", fail_synthesis)
    response = TestClient(app).post(
        "/api/voice/speech",
        json={"text": "Read this reply aloud."},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "tts_unavailable",
        "message": "The configured voice provider is unavailable.",
    }


def test_voice_speech_api_rejects_blank_text():
    from fastapi.testclient import TestClient

    from backend.app.main import app

    response = TestClient(app).post("/api/voice/speech", json={"text": "   "})

    assert response.status_code == 422


def test_webm_opus_multipart_upload_completes_voice_turn(monkeypatch):
    from fastapi.testclient import TestClient

    from backend.app.api import voice
    from backend.app.main import app

    agent = FakeAgent()
    whisper = FakeWhisperModel()
    piper = FakePiperVoice()
    monkeypatch.setattr(voice.voice_service, "agent", agent)
    monkeypatch.setattr(voice.voice_service, "_load_stt_model", lambda: whisper)
    monkeypatch.setattr(voice.voice_service, "_load_tts_voice", lambda: piper)

    response = TestClient(app).post(
        "/api/voice/turn",
        files={
            "audio": (
                "recording.webm",
                webm_opus_recording(),
                "audio/webm;codecs=opus",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["transcript"] == "What is the weather?"
    assert response.json()["assistant"] == "Hello from LEON."
    assert base64.b64decode(response.json()["audio_base64"]).startswith(b"RIFF")
    assert whisper.audio_samples.size == 16000


def test_voice_api_rejects_wrong_multipart_field():
    from fastapi.testclient import TestClient

    from backend.app.main import app

    response = TestClient(app).post(
        "/api/voice/turn",
        files={"recording": ("recording.webm", b"data", "audio/webm")},
    )

    assert response.status_code == 422


def test_voice_api_rejects_unsupported_mime():
    from fastapi.testclient import TestClient

    from backend.app.main import app

    response = TestClient(app).post(
        "/api/voice/turn",
        files={"audio": ("recording.bin", b"data", "application/octet-stream")},
    )

    assert response.status_code == 415
    assert response.json()["detail"]["code"] == "unsupported_audio_type"


def test_voice_api_rejects_oversized_upload(monkeypatch):
    from fastapi.testclient import TestClient

    from backend.app.api import voice
    from backend.app.main import app

    monkeypatch.setattr(voice, "MAX_AUDIO_BYTES", 3)
    response = TestClient(app).post(
        "/api/voice/turn",
        files={"audio": ("recording.webm", b"four", "audio/webm")},
    )

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "audio_too_large"


def test_voice_api_rejects_empty_audio_with_structured_error():
    from fastapi.testclient import TestClient

    from backend.app.main import app

    response = TestClient(app).post(
        "/api/voice/turn",
        files={"audio": ("recording.webm", b"", "audio/webm")},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "empty_audio"
