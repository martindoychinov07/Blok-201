from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "dementia-edge-mvp"
    app_env: str = "dev"

    database_path: str = "./data/mvp.db"
    demo_mode: bool = True

    default_patient_id: str = "patient-001"
    default_device_id: str = "device-001"
    ingest_shared_key: str = "dev-ingest-key"

    geofence_exit_confirmations: int = 2
    geofence_cooldown_sec: int = 120

    fall_impact_g_threshold: float = 2.5
    fall_inactivity_sec: int = 20

    notify_telegram_enabled: bool = False
    notify_telegram_bot_token: str = ""
    notify_telegram_chat_id: str = ""

    demo_transcript_interval_sec: int = 8
    demo_gps_interval_sec: int = 5
    demo_accel_interval_sec: int = 1

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def ensure_paths(self) -> None:
        db_path = Path(self.database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_paths()
    return settings
