import os
from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[3]
_PIPER_MODEL_PATH = (
    BASE_DIR / "data" / "models" / "piper" / "en_US-lessac-medium.onnx"
)
_ROOT_PIPER_MODEL_PATH = BASE_DIR / "en_US-lessac-medium.onnx"
if (
    not _PIPER_MODEL_PATH.is_file()
    and _ROOT_PIPER_MODEL_PATH.is_file()
    and _ROOT_PIPER_MODEL_PATH.with_suffix(".onnx.json").is_file()
):
    _PIPER_MODEL_PATH = _ROOT_PIPER_MODEL_PATH


class Settings(BaseSettings):
    app_name: str = "LEON"
    app_version: str = "0.1.0"
    app_env: str = "development"
    cors_allowed_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173"
    )
    cors_development_origins: str = (
        "http://localhost:5174,http://127.0.0.1:5174"
    )

    model_provider: str = "mock"

    cloud_ai_enabled: bool = False
    cloud_ai_provider: str = "gemini"
    cloud_ai_model: str = "gemini-3.8-flash"
    cloud_ai_embedding_model: str = "text-embedding-004"
    cloud_ai_search_grounding: bool = True
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_api_key: SecretStr = SecretStr("")

    ollama_base_url: str = "http://127.0.0.1:11434/v1"
    ollama_model: str = "qwen3:8b"
    # Empty keeps the legacy OLLAMA_MODEL setting as the general-model fallback.
    ollama_general_model: str = ""
    ollama_coding_model: str = "qwen2.5-coder:7b"
    ollama_embedding_model: str = "qwen3-embedding:0.6b"
    vision_enabled: bool = True
    vision_model: str = "qwen3-vl:8b"
    vision_max_image_mb: float = 10.0
    vision_max_width: int = 4096
    vision_max_height: int = 4096
    vision_timeout_seconds: float = 120.0
    media_enabled: bool = True
    media_default_provider: str = "auto"
    media_confirm_external: bool = True
    spotify_client_id: str = ""
    spotify_client_secret: SecretStr = SecretStr("")
    spotify_redirect_uri: str = "http://127.0.0.1:8000/api/media/spotify/callback"
    frontend_base_url: str = "http://127.0.0.1:5174"
    spotify_token_path: Path = BASE_DIR / "data" / "spotify_tokens.json"

    @field_validator("frontend_base_url", mode="before")
    @classmethod
    def default_frontend_base_url(cls, value: str | None, info) -> str:
        raw_value = str(value).strip() if value is not None else ""
        if raw_value:
            return raw_value.rstrip("/")

        app_env = info.data.get("app_env") if info.data else None
        if app_env is None:
            app_env = os.getenv("APP_ENV", "development")
        app_env = str(app_env).strip().lower()
        return "http://127.0.0.1:5174" if app_env in {"dev", "development", "local"} else "http://127.0.0.1:5173"

    @field_validator("spotify_token_path", mode="before")
    @classmethod
    def anchor_spotify_token_path(cls, value: Path | str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else BASE_DIR / path

    colibri_base_url: str = "http://127.0.0.1:8080/v1"
    colibri_model: str = ""

    request_timeout: float = 120.0
    research_max_search_iterations: int = 3
    research_max_pages: int = 20
    web_request_timeout: float = 30.0

    workspace_dir: Path = BASE_DIR / "workspace"
    data_dir: Path = BASE_DIR / "data"
    voice_stt_model_path: Path = BASE_DIR / "data" / "models" / "faster-whisper-small"
    voice_tts_model_path: Path = _PIPER_MODEL_PATH
    voice_provider: str = "piper"
    fish_audio_api_key: SecretStr = SecretStr("")
    fish_audio_model: str = "s2.1-pro-free"
    fish_audio_reference_id: str = ""

    # Email credentials are populated only from environment-backed settings.
    email_provider: str = ""
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_refresh_token: str = ""
    gmail_sender: str = ""
    email_task_result_to: str = ""
    notification_provider: str = "desktop"

    @property
    def cors_origins(self) -> list[str]:
        origins = [
            origin.strip()
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        ]
        if self.app_env.strip().lower() in {"dev", "development", "local"}:
            origins.extend(
                origin.strip()
                for origin in self.cors_development_origins.split(",")
                if origin.strip()
            )
        return list(dict.fromkeys(origins))

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / "backend" / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
