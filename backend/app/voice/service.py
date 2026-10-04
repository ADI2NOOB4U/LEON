import base64
import io
import logging
import os
import tempfile
import threading
import time
import wave
from pathlib import Path
from typing import Any

from fastapi.concurrency import run_in_threadpool
import httpx

from backend.app.config.settings import settings


MAX_AUDIO_BYTES = 25 * 1024 * 1024
FISH_AUDIO_TTS_URL = "https://api.fish.audio/v1/tts"
logger = logging.getLogger(__name__)


class VoiceServiceError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int = 503,
        code: str = "voice_service_error",
        diagnostic: str | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.diagnostic = diagnostic


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
        except httpx.HTTPStatusError as exc:
            # Keep provider diagnostics: the caller can now distinguish an
            # invalid key, unavailable model, quota issue, or rejected voice.
            # Bound the response text because provider errors can be verbose.
            detail = " ".join(exc.response.text.split())[:300]
            message = f"Fish Audio returned HTTP {exc.response.status_code}."
            if detail:
                message = f"{message} {detail}"
            raise VoiceServiceError(message) from exc
        except httpx.RequestError as exc:
            raise VoiceServiceError(
                f"Fish Audio could not be reached ({type(exc).__name__})."
            ) from exc
        except Exception as exc:
            raise VoiceServiceError(
                f"Fish Audio speech synthesis failed ({type(exc).__name__})."
            ) from exc


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

    async def synthesize_text(self, text: str) -> bytes:
        text = text.strip()
        if not text:
            raise VoiceServiceError(
                "There is no text to read aloud.",
                422,
                "empty_speech_text",
            )
        if len(text) > 10000:
            raise VoiceServiceError(
                "The text to read aloud is too long.",
                422,
                "speech_text_too_long",
            )

        speech, _, _, _ = await run_in_threadpool(self._synthesize, text)
        if not speech:
            raise VoiceServiceError(
                "LEON's voice provider returned empty audio.",
                code="empty_speech_audio",
            )
        return speech

    async def process(self, audio: bytes, suffix: str) -> dict[str, str | None]:
        total_started = time.perf_counter()
        if not audio:
            raise VoiceServiceError(
                "The recording was empty. Try recording again.",
                422,
                "empty_audio",
            )
        if len(audio) > MAX_AUDIO_BYTES:
            raise VoiceServiceError(
                "The recording is too large (25 MB maximum).",
                413,
                "audio_too_large",
            )

        stt_model_reused = self._stt_model is not None
        stt_started = time.perf_counter()
        transcript = await run_in_threadpool(self._transcribe, audio, suffix)
        stt_ms = (time.perf_counter() - stt_started) * 1000

        llm_started = time.perf_counter()
        try:
            # Voice transcripts enter the same Intelligence Core as typed
            # commands. Deterministic actions use the normal command executor;
            # ordinary conversation keeps the low-latency agent path.
            from backend.app.intelligence import intelligence_core
            decision = intelligence_core.route(transcript)
            if decision.route in {"system.datetime", "media.spotify", "screen.local", "desktop.applications", "system.stats", "memory.local"}:
                from backend.app.api.command import CommandRequest, command
                command_result = await command(
                    CommandRequest(
                        message=transcript,
                        confirmed=decision.route == "media.spotify",
                    )
                )
                assistant = str(command_result.get("message", "LEON completed the request."))
            else:
                fast_chat = getattr(self.agent, "chat_fast", None)
                assistant = await (fast_chat(transcript) if fast_chat else self.agent.chat(transcript))
        except Exception as exc:
            raise VoiceServiceError(
                "LEON could not process the transcript.",
                502,
                "agent_failed",
            ) from exc
        llm_ms = (time.perf_counter() - llm_started) * 1000

        tts_provider_reused = (
            self._fish_audio_tts is not None
            if self.voice_provider == "fish_audio"
            else self._tts_voice is not None
        )
        tts_started = time.perf_counter()
        tts_provider_used: str | None = None
        tts_model_used: str | None = None
        tts_fallback_reason: str | None = None
        try:
            speech, tts_provider_used, tts_model_used, tts_fallback_reason = (
                await run_in_threadpool(self._synthesize, assistant)
            )
            audio_error = None
        except VoiceServiceError as exc:
            speech = b""
            audio_error = str(exc)
        tts_ms = (time.perf_counter() - tts_started) * 1000
        total_ms = (time.perf_counter() - total_started) * 1000
        logger.info(
            "Voice pipeline completed (stt_ms=%.1f, llm_ms=%.1f, tts_ms=%.1f, "
            "total_ms=%.1f, stt_model_reused=%s, tts_provider_reused=%s, "
            "tts_provider=%s, tts_model=%s, fallback=%s, audio_bytes=%d, "
            "tts_error=%s).",
            stt_ms,
            llm_ms,
            tts_ms,
            total_ms,
            stt_model_reused,
            tts_provider_reused,
            tts_provider_used or self.voice_provider,
            tts_model_used,
            bool(tts_fallback_reason),
            len(speech),
            bool(audio_error),
        )
        return {
            "transcript": transcript,
            "assistant": assistant,
            "audio_base64": base64.b64encode(speech).decode("ascii"),
            "audio_content_type": "audio/wav",
            "audio_error": audio_error,
            "tts_provider": tts_provider_used,
            "tts_model": tts_model_used,
            "tts_fallback_reason": tts_fallback_reason,
            "audio_bytes": len(speech),
        }

    def _load_stt_model(self) -> Any:
        if self._stt_model is None:
            with self._stt_lock:
                if self._stt_model is None:
                    if not self.stt_model_path.exists():
                        raise VoiceServiceError(
                            "The local faster-whisper model is missing. Download a "
                            "faster-whisper model to "
                            f"{self.stt_model_path} or set VOICE_STT_MODEL_PATH.",
                            code="stt_model_unavailable",
                        )
                    try:
                        from faster_whisper import WhisperModel

                        self._stt_model = WhisperModel(
                            str(self.stt_model_path),
                            device="cpu",
                            compute_type="int8",
                            cpu_threads=max(1, int(os.getenv("VOICE_STT_CPU_THREADS", str(os.cpu_count() or 1)))),
                            num_workers=1,
                            local_files_only=True,
                        )
                    except ImportError as exc:
                        raise VoiceServiceError(
                            "Speech recognition is unavailable. Install backend "
                            "requirements to enable faster-whisper.",
                            code="stt_unavailable",
                        ) from exc
                    except Exception as exc:
                        raise VoiceServiceError(
                            "The local faster-whisper model could not be loaded. "
                            "Check VOICE_STT_MODEL_PATH and the model files.",
                            code="stt_model_unavailable",
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

    @staticmethod
    def _decode_audio(audio_path: str) -> Any:
        try:
            import numpy as np
            # Browser recordings are commonly PCM WAV.  Avoid a PyAV
            # container/resampler round-trip when the input is already the
            # model's native 16 kHz mono format.
            with wave.open(audio_path, "rb") as wav_file:
                if (
                    wav_file.getnchannels() == 1
                    and wav_file.getsampwidth() == 2
                    and wav_file.getframerate() == 16000
                ):
                    samples = np.frombuffer(wav_file.readframes(wav_file.getnframes()), dtype=np.int16)
                    if samples.size:
                        return samples.astype(np.float32) / 32768.0
        except (wave.Error, EOFError):
            pass

        try:
            import av
            import numpy as np
        except ImportError as exc:
            raise VoiceServiceError(
                "Audio decoding is unavailable. Install PyAV from backend requirements.",
                503,
                "decoder_unavailable",
            ) from exc

        try:
            resampler = av.AudioResampler(
                format="s16",
                layout="mono",
                rate=16000,
            )
            raw_audio = io.BytesIO()
            with av.open(audio_path, mode="r") as container:
                if not container.streams.audio:
                    raise ValueError("The uploaded media has no audio stream.")
                for frame in container.decode(audio=0):
                    for output_frame in resampler.resample(frame):
                        raw_audio.write(output_frame.to_ndarray().tobytes())
                for output_frame in resampler.resample(None):
                    raw_audio.write(output_frame.to_ndarray().tobytes())

            if not raw_audio.tell():
                raise ValueError("The uploaded media contains no decodable audio frames.")

            return (
                np.frombuffer(raw_audio.getbuffer(), dtype=np.int16).astype(np.float32)
                / 32768.0
            )
        except Exception as exc:
            diagnostic = " ".join(str(exc).split())[:300] or type(exc).__name__
            raise VoiceServiceError(
                "The audio could not be decoded. Check the recording and try again.",
                422,
                "audio_decode_failed",
                diagnostic,
            ) from exc

    def _transcribe(self, audio: bytes, suffix: str) -> str:
        audio_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as audio_file:
                audio_file.write(audio)
                audio_path = audio_file.name

            audio_samples = self._decode_audio(audio_path)
            model = self._load_stt_model()
            transcript = ""
            for vad_filter in (True, False):
                segments, _ = model.transcribe(
                    audio_samples,
                    vad_filter=vad_filter,
                )
                transcript = " ".join(
                    segment.text.strip() for segment in segments
                ).strip()
                if transcript:
                    if not vad_filter:
                        logger.info(
                            "Speech transcription recovered without VAD "
                            "(extension=%s, bytes=%d).",
                            suffix,
                            len(audio),
                        )
                    break
            if not transcript:
                raise VoiceServiceError(
                    "No speech was detected. Try speaking closer to the microphone.",
                    422,
                    "no_speech_detected",
                )
            return transcript
        except VoiceServiceError:
            raise
        except Exception as exc:
            logger.exception(
                "Speech recognition failed after audio decoding (extension=%s, bytes=%d).",
                suffix,
                len(audio),
            )
            raise VoiceServiceError(
                "Speech recognition failed while processing the decoded audio. Try again.",
                503,
                "transcription_failed",
                " ".join(str(exc).split())[:300] or type(exc).__name__,
            ) from exc
        finally:
            if audio_path:
                Path(audio_path).unlink(missing_ok=True)

    def _synthesize(self, text: str) -> tuple[bytes, str, str, str | None]:
        if self.voice_provider == "fish_audio":
            try:
                speech = self._load_fish_audio_tts().synthesize(text)
                logger.info("Fish Audio TTS synthesis succeeded.")
                return speech, "fish_audio", settings.fish_audio_model, None
            except Exception as fish_error:
                fallback_reason = (
                    f"Fish Audio failed ({type(fish_error).__name__}); using Piper."
                )
                logger.warning(
                    "Fish Audio TTS failed; attempting Piper fallback (%s).",
                    type(fish_error).__name__,
                )
                try:
                    speech = self._synthesize_piper(text)
                    logger.info("Piper TTS fallback succeeded.")
                    return (
                        speech,
                        "piper",
                        self.tts_model_path.stem,
                        fallback_reason,
                    )
                except VoiceServiceError as piper_error:
                    raise VoiceServiceError(
                        f"{fish_error} Piper fallback also failed: {piper_error}"
                    ) from piper_error
        return self._synthesize_piper(text), "piper", self.tts_model_path.stem, None

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
