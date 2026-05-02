"""Domain types for the spot vs futures basis surface."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum


class Stance(str, Enum):
    PREMIUM = "PREMIUM"
    DISCOUNT = "DISCOUNT"
    FLAT = "FLAT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class PriceRow:
    symbol: str
    spot: float | None
    future: float | None
    futures_symbol: str
    expiry: date
    days_to_expiry: int
    basis: float | None           # future - spot
    basis_pct: float | None       # (future / spot - 1) * 100
    annualised_pct: float | None  # basis_pct * (365 / dte)
    stance: Stance


@dataclass(frozen=True)
class IndexSnapshot:
    timestamp: datetime
    rows: tuple[PriceRow, ...]
    avg_basis_pct: float | None
    avg_annualised_pct: float | None
    premium_count: int
    discount_count: int
    flat_count: int
    missing_count: int

    @property
    def total(self) -> int:
        return len(self.rows)
