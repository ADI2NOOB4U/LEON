from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "LEON"
    app_version: str = "0.1.0"

    model_provider: str = "mock"

    ollama_base_url: str = "http://127.0.0.1:11434/v1"
    ollama_model: str = "qwen3:8b"

    colibri_base_url: str = "http://127.0.0.1:8080/v1"
    colibri_model: str = ""

    request_timeout: float = 120.0

    workspace_dir: Path = BASE_DIR / "workspace"
    data_dir: Path = BASE_DIR / "data"

    # Email credentials are populated only from environment-backed settings.
    email_provider: str = ""
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_refresh_token: str = ""
    gmail_sender: str = ""
    email_task_result_to: str = ""
    notification_provider: str = "desktop"

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / "backend" / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
