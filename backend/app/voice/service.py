import base64
import io
import tempfile
import threading
import wave
from pathlib import Path
from typing import Any

from fastapi.concurrency import run_in_threadpool
import httpx

from backend.app.config.settings import settings


MAX_AUDIO_BYTES = 25 * 1024 * 1024
FISH_AUDIO_TTS_URL = "https://api.fish.audio/v1/tts"


class VoiceServiceError(Exception):
    def __init__(self, message: str, status_code: int = 503):
        super().__init__(message)
        self.status_code = status_code


class FishAudioTTS:
    def __init__(self, api_key: str, model: str, reference_id: str = ""):
        self.api_key = api_key
        self.model = model
        self.reference_id = reference_id

    def synthesize(self, text: str) -> bytes:
        if not self.api_key:
            raise VoiceServiceError(
                "Fish Audio is selected but FISH_AUDIO_API_KEY is not configured."
            )

        payload: dict[str, Any] = {"text": text, "format": "wav"}
        if self.reference_id:
            payload["reference_id"] = self.reference_id

        try:
            response = httpx.post(
                FISH_AUDIO_TTS_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "model": self.model,
                },
                json=payload,
                timeout=settings.request_timeout,
            )
            response.raise_for_status()
            if not response.content:
                raise ValueError("Fish Audio returned an empty audio response")
            return response.content
        except Exception as exc:
            raise VoiceServiceError("Fish Audio speech synthesis failed.") from exc


class LeonVoiceService:
    def __init__(
        self,
        agent: Any,
        stt_model_path: Path | None = None,
        tts_model_path: Path | None = None,
    ):
        self.agent = agent
        self.stt_model_path = stt_model_path or settings.voice_stt_model_path
        self.tts_model_path = tts_model_path or settings.voice_tts_model_path
        self._stt_model: Any = None
        self._tts_voice: Any = None
        self._fish_audio_tts: FishAudioTTS | None = None
        self._stt_lock = threading.Lock()
        self._tts_lock = threading.Lock()
        self._fish_audio_lock = threading.Lock()
        configured_provider = (settings.voice_provider or "piper").strip().lower()
        self.voice_provider = (
            "fish_audio" if configured_provider in {"fish", "fish_audio"} else "piper"
        )

    async def process(self, audio: bytes, suffix: str) -> dict[str, str | None]:
        if not audio:
            raise VoiceServiceError("The recording was empty. Try recording again.", 422)
        if len(audio) > MAX_AUDIO_BYTES:
            raise VoiceServiceError("The recording is too large (25 MB maximum).", 413)

        transcript = await run_in_threadpool(self._transcribe, audio, suffix)
        try:
            assistant = await self.agent.chat(transcript)
        except Exception as exc:
            raise VoiceServiceError("LEON could not process the transcript.", 502) from exc

        try:
            speech = await run_in_threadpool(self._synthesize, assistant)
            audio_error = None
        except VoiceServiceError as exc:
            speech = b""
            audio_error = str(exc)
        return {
            "transcript": transcript,
            "assistant": assistant,
            "audio_base64": base64.b64encode(speech).decode("ascii"),
            "audio_content_type": "audio/wav",
            "audio_error": audio_error,
        }

    def _load_stt_model(self) -> Any:
        if self._stt_model is None:
            with self._stt_lock:
                if self._stt_model is None:
                    if not self.stt_model_path.exists():
                        raise VoiceServiceError(
                            "The local faster-whisper model is missing. Download a "
                            "faster-whisper model to "
                            f"{self.stt_model_path} or set VOICE_STT_MODEL_PATH."
                        )
                    try:
                        from faster_whisper import WhisperModel

                        self._stt_model = WhisperModel(
                            str(self.stt_model_path),
                            device="cpu",
                            compute_type="int8",
                            local_files_only=True,
                        )
                    except ImportError as exc:
                        raise VoiceServiceError(
                            "Speech recognition is unavailable. Install backend "
                            "requirements to enable faster-whisper."
                        ) from exc
                    except Exception as exc:
                        raise VoiceServiceError(
                            "The local faster-whisper model could not be loaded. "
                            "Check VOICE_STT_MODEL_PATH and the model files."
                        ) from exc
        return self._stt_model

    def _load_tts_voice(self) -> Any:
        if self._tts_voice is None:
            with self._tts_lock:
                if self._tts_voice is None:
                    if not self.tts_model_path.is_file():
                        raise VoiceServiceError(
                            "The local Piper voice is missing. Place a Piper .onnx "
                            "voice at "
                            f"{self.tts_model_path} or set VOICE_TTS_MODEL_PATH."
                        )
                    if not self.tts_model_path.with_suffix(".onnx.json").is_file():
                        raise VoiceServiceError(
                            "The Piper voice configuration is missing beside "
                            f"{self.tts_model_path}."
                        )
                    try:
                        from piper import PiperVoice

                        self._tts_voice = PiperVoice.load(str(self.tts_model_path))
                    except ImportError as exc:
                        raise VoiceServiceError(
                            "Speech synthesis is unavailable. Install backend "
                            "requirements to enable Piper."
                        ) from exc
                    except Exception as exc:
                        raise VoiceServiceError(
                            "The local Piper voice could not be loaded. Check its "
                            ".onnx and .onnx.json files."
                        ) from exc
        return self._tts_voice

    def _load_fish_audio_tts(self) -> FishAudioTTS:
        if self._fish_audio_tts is None:
            with self._fish_audio_lock:
                if self._fish_audio_tts is None:
                    self._fish_audio_tts = FishAudioTTS(
                        api_key=settings.fish_audio_api_key.get_secret_value(),
                        model=settings.fish_audio_model,
                        reference_id=settings.fish_audio_reference_id,
                    )
        return self._fish_audio_tts

    def _transcribe(self, audio: bytes, suffix: str) -> str:
        model = self._load_stt_model()
        audio_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as audio_file:
                audio_file.write(audio)
                audio_path = audio_file.name

            segments, _ = model.transcribe(audio_path, vad_filter=True)
            transcript = " ".join(segment.text.strip() for segment in segments).strip()
            if not transcript:
                raise VoiceServiceError(
                    "No speech was detected. Try speaking closer to the microphone.",
                    422,
                )
            return transcript
        except VoiceServiceError:
            raise
        except Exception as exc:
            raise VoiceServiceError(
                "The recording could not be decoded. Try recording again. (WebM, "
                "WAV, OGG, MP4, and MP3 are supported.)",
                422,
            ) from exc
        finally:
            if audio_path:
                Path(audio_path).unlink(missing_ok=True)

    def _synthesize(self, text: str) -> bytes:
        if self.voice_provider == "fish_audio":
            try:
                return self._load_fish_audio_tts().synthesize(text)
            except Exception as fish_error:
                try:
                    return self._synthesize_piper(text)
                except VoiceServiceError as piper_error:
                    raise VoiceServiceError(
                        f"{fish_error} Piper fallback also failed: {piper_error}"
                    ) from piper_error
        return self._synthesize_piper(text)

    def _synthesize_piper(self, text: str) -> bytes:
        voice = self._load_tts_voice()
        audio = io.BytesIO()
        try:
            with wave.open(audio, "wb") as wav_file:
                voice.synthesize_wav(text, wav_file)
            return audio.getvalue()
        except Exception as exc:
            raise VoiceServiceError(
                "LEON replied, but Piper could not synthesize speech. Check the local "
                "voice model."
            ) from exc