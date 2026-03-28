from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "dementia-transcript-backend"
    app_env: str = "dev"

    transcript_database_path: str = "./data/transcript_analysis.db"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_timeout_sec: int = 25
    gemini_fallback_enabled: bool = True

    default_patient_id: str = "p_001"
    max_audio_upload_mb: int = 20
    transcription_model: str = "tiny"
    transcription_device: str = "cpu"
    transcription_compute_type: str = "int8"
    transcription_language: Optional[str] = None

    analysis_webhook_enabled: bool = False
    analysis_webhook_url: str = "http://localhost:5000/api/ai/transcript-analysis"
    analysis_webhook_timeout_sec: int = 5
    analysis_webhook_bearer_token: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def ensure_paths(self) -> None:
        Path(self.transcript_database_path).parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_paths()
    return settings
