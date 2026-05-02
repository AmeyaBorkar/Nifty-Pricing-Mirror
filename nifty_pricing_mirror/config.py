from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

INSTRUMENTS_URL = "https://growwapi-assets.groww.in/instruments/instrument.csv"
INSTRUMENTS_CACHE_PATH = ROOT / ".cache" / "instruments.csv"


@dataclass(frozen=True)
class Settings:
    access_token: str | None
    api_key: str | None
    api_secret: str | None
    totp_secret: str | None
    refresh_seconds: float
    instruments_cache_hours: float

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            access_token=_clean(os.getenv("GROWW_ACCESS_TOKEN")),
            api_key=_clean(os.getenv("GROWW_API_KEY")),
            api_secret=_clean(os.getenv("GROWW_API_SECRET")),
            totp_secret=_clean(os.getenv("GROWW_TOTP_SECRET")),
            refresh_seconds=float(os.getenv("NIFTY_REFRESH_SECONDS", "3")),
            instruments_cache_hours=float(os.getenv("NIFTY_INSTRUMENTS_CACHE_HOURS", "12")),
        )


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None
