"""Loads Groww's instrument master CSV with on-disk caching."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import pandas as pd
import requests

from .config import INSTRUMENTS_CACHE_PATH, INSTRUMENTS_URL

log = logging.getLogger(__name__)


class InstrumentsRepo:
    """Downloads + caches the Groww instruments CSV; lazy-loads into pandas."""

    def __init__(self, cache_hours: float = 12.0, cache_path: Path = INSTRUMENTS_CACHE_PATH):
        self._cache_hours = cache_hours
        self._cache_path = cache_path
        self._df: pd.DataFrame | None = None

    def load(self) -> pd.DataFrame:
        if self._df is not None:
            return self._df

        if self._is_cache_fresh():
            log.info("Loading instruments from cache: %s", self._cache_path)
            df = pd.read_csv(self._cache_path, low_memory=False)
        else:
            log.info("Downloading instruments from %s", INSTRUMENTS_URL)
            df = self._download_and_cache()

        # Normalise dtypes once so the rest of the code can rely on them.
        if "expiry_date" in df.columns:
            df["expiry_date"] = pd.to_datetime(df["expiry_date"], errors="coerce").dt.date
        for col in ("trading_symbol", "underlying_symbol", "exchange",
                    "instrument_type", "segment"):
            if col in df.columns:
                df[col] = df[col].astype("string").str.strip()

        self._df = df
        return df

    def _is_cache_fresh(self) -> bool:
        if not self._cache_path.exists():
            return False
        age_hours = (time.time() - self._cache_path.stat().st_mtime) / 3600.0
        return age_hours < self._cache_hours

    def _download_and_cache(self) -> pd.DataFrame:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        resp = requests.get(INSTRUMENTS_URL, timeout=30)
        resp.raise_for_status()
        self._cache_path.write_bytes(resp.content)
        return pd.read_csv(self._cache_path, low_memory=False)
