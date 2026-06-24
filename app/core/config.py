import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BACKEND_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./rapidrelief.db")
    firebase_service_account_path: str = os.getenv(
        "FIREBASE_SERVICE_ACCOUNT_PATH",
        "app/firebase/firebase_service_account.json",
    )
    realtime_stream_interval_seconds: float = float(
        os.getenv("REALTIME_STREAM_INTERVAL_SECONDS", "5")
    )


settings = Settings()


def backend_path(path: str) -> Path:
    value = Path(path)
    if value.is_absolute():
        return value
    return BACKEND_ROOT / value
