"""Nifty 50 constituent universe.

The default list mirrors the canonical NSE archive
(`ind_nifty50list.csv`). NSE rebalances the index periodically — pass a
custom symbols file via the CLI if you need a different snapshot.
"""

from __future__ import annotations

from pathlib import Path

NIFTY_50_SYMBOLS: tuple[str, ...] = (
    "ADANIENT",
    "ADANIPORTS",
    "APOLLOHOSP",
    "ASIANPAINT",
    "AXISBANK",
    "BAJAJ-AUTO",
    "BAJFINANCE",
    "BAJAJFINSV",
    "BEL",
    "BHARTIARTL",
    "CIPLA",
    "COALINDIA",
    "DRREDDY",
    "EICHERMOT",
    "ETERNAL",
    "GRASIM",
    "HCLTECH",
    "HDFCBANK",
    "HDFCLIFE",
    "HINDALCO",
    "HINDUNILVR",
    "ICICIBANK",
    "ITC",
    "INFY",
    "INDIGO",
    "JSWSTEEL",
    "JIOFIN",
    "KOTAKBANK",
    "LT",
    "M&M",
    "MARUTI",
    "MAXHEALTH",
    "NTPC",
    "NESTLEIND",
    "ONGC",
    "POWERGRID",
    "RELIANCE",
    "SBILIFE",
    "SHRIRAMFIN",
    "SBIN",
    "SUNPHARMA",
    "TCS",
    "TATACONSUM",
    "TMPV",
    "TATASTEEL",
    "TECHM",
    "TITAN",
    "TRENT",
    "ULTRACEMCO",
    "WIPRO",
)


def load_symbols(path: Path | None = None) -> tuple[str, ...]:
    if path is None:
        return NIFTY_50_SYMBOLS
    raw = path.read_text(encoding="utf-8").splitlines()
    cleaned = []
    for line in raw:
        sym = line.split("#", 1)[0].strip()
        if sym:
            cleaned.append(sym.upper())
    if not cleaned:
        raise ValueError(f"No symbols found in {path}")
    return tuple(cleaned)
