"""Loads Groww's instrument master and resolves cash-segment spot rows."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import requests

from .config import INSTRUMENTS_CACHE_PATH, INSTRUMENTS_URL

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SpotInstrument:
    symbol: str               # e.g. "RELIANCE"
    trading_symbol: str
    exchange: str

    @property
    def exchange_trading_symbol(self) -> str:
        return f"{self.exchange}_{self.trading_symbol}"


class InstrumentsRepo:
    """Downloads + caches the Groww instruments CSV; lazy-loads into pandas."""

    def __init__(self, cache_hours: float = 12.0, cache_path: Path = INSTRUMENTS_CACHE_PATH):
        self._cache_hours = cache_hours
        self._cache_path = cache_path
        self._df: pd.DataFrame | None = None

    # --------------------------------------------------------------- loading
    def load(self) -> pd.DataFrame:
        if self._df is not None:
            return self._df

        if self._is_cache_fresh():
            log.info("Loading instruments from cache: %s", self._cache_path)
            df = pd.read_csv(self._cache_path, low_memory=False)
        else:
            log.info("Downloading instruments from %s", INSTRUMENTS_URL)
            df = self._download_and_cache()

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

    # --------------------------------------------------------------- queries
    def resolve_spot(self, symbol: str) -> SpotInstrument | None:
        df = self.load()
        return self._resolve_spot(df, symbol)

    @staticmethod
    def _resolve_spot(df: pd.DataFrame, symbol: str) -> SpotInstrument | None:
        mask = (
            (df["underlying_symbol"].fillna(df["trading_symbol"]) == symbol)
            & (df["instrument_type"] == "EQ")
            & (df["exchange"] == "NSE")
            & (df["segment"] == "CASH")
        )
        rows = df.loc[mask]
        if rows.empty:
            # Some stocks list the symbol only in trading_symbol (no underlying).
            mask = (
                (df["trading_symbol"] == symbol)
                & (df["instrument_type"] == "EQ")
                & (df["exchange"] == "NSE")
                & (df["segment"] == "CASH")
            )
            rows = df.loc[mask]
        if rows.empty:
            return None

        row = rows.iloc[0]
        return SpotInstrument(
            symbol=symbol,
            trading_symbol=str(row["trading_symbol"]),
            exchange="NSE",
        )
