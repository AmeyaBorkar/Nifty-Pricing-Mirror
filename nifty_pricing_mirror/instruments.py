"""Loads Groww's instrument master and resolves each stock to its near futures contract."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import requests

from .config import INSTRUMENTS_CACHE_PATH, INSTRUMENTS_URL

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class FuturesContract:
    underlying: str
    trading_symbol: str       # e.g. "RELIANCE25MAYFUT"
    expiry: date
    lot_size: int
    tick_size: float
    exchange: str             # "NSE"

    @property
    def exchange_trading_symbol(self) -> str:
        return f"{self.exchange}_{self.trading_symbol}"


@dataclass(frozen=True)
class SpotInstrument:
    symbol: str               # e.g. "RELIANCE"
    trading_symbol: str
    exchange: str

    @property
    def exchange_trading_symbol(self) -> str:
        return f"{self.exchange}_{self.trading_symbol}"


@dataclass(frozen=True)
class InstrumentPair:
    spot: SpotInstrument
    future: FuturesContract


class InstrumentsRepo:
    """Loads + queries the Groww instruments CSV with on-disk caching."""

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

    # --------------------------------------------------------------- queries
    def resolve_pair(
        self,
        symbol: str,
        as_of: date | None = None,
    ) -> InstrumentPair | None:
        """Return matched spot+future for `symbol`, or None if either side is missing."""

        df = self.load()
        as_of = as_of or date.today()

        spot = self._resolve_spot(df, symbol)
        if spot is None:
            log.warning("No NSE cash instrument found for %s", symbol)
            return None

        future = self._resolve_near_future(df, symbol, as_of)
        if future is None:
            log.warning("No active NSE futures contract found for %s", symbol)
            return None

        return InstrumentPair(spot=spot, future=future)

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

    @staticmethod
    def _resolve_near_future(
        df: pd.DataFrame, symbol: str, as_of: date
    ) -> FuturesContract | None:
        mask = (
            (df["underlying_symbol"] == symbol)
            & (df["instrument_type"] == "FUT")
            & (df["exchange"] == "NSE")
            & (df["segment"] == "FNO")
            & (df["expiry_date"].notna())
            & (df["expiry_date"] >= as_of)
        )
        rows = df.loc[mask].sort_values("expiry_date")
        if rows.empty:
            return None

        row = rows.iloc[0]
        return FuturesContract(
            underlying=symbol,
            trading_symbol=str(row["trading_symbol"]),
            expiry=row["expiry_date"],
            lot_size=int(row["lot_size"]) if pd.notna(row.get("lot_size")) else 0,
            tick_size=float(row["tick_size"]) if pd.notna(row.get("tick_size")) else 0.05,
            exchange="NSE",
        )


def resolve_universe(
    repo: InstrumentsRepo, symbols: list[str], as_of: date | None = None
) -> tuple[list[InstrumentPair], list[str]]:
    """Return (resolved pairs, list of symbols that could not be matched)."""

    resolved: list[InstrumentPair] = []
    skipped: list[str] = []
    for symbol in symbols:
        pair = repo.resolve_pair(symbol, as_of=as_of)
        if pair is None:
            skipped.append(symbol)
        else:
            resolved.append(pair)
    return resolved, skipped
