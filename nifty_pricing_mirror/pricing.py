"""Pairs spot/futures LTPs and derives the per-stock basis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

from .groww_client import GrowwClient
from .instruments import InstrumentPair


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


class PricingEngine:
    """Wraps a `GrowwClient` to refresh basis snapshots for a fixed universe."""

    def __init__(self, client: GrowwClient, pairs: list[InstrumentPair]):
        self._client = client
        self._pairs = pairs
        self._spot_keys = [p.spot.exchange_trading_symbol for p in pairs]
        self._future_keys = [p.future.exchange_trading_symbol for p in pairs]

    @property
    def pairs(self) -> list[InstrumentPair]:
        return self._pairs

    def snapshot(self, *, as_of: datetime | None = None) -> IndexSnapshot:
        as_of = as_of or datetime.now()

        spot_ltps = self._client.batched_ltp(
            self._client.SEGMENT_CASH, self._spot_keys
        )
        future_ltps = self._client.batched_ltp(
            self._client.SEGMENT_FNO, self._future_keys
        )

        rows: list[PriceRow] = []
        for pair in self._pairs:
            spot = spot_ltps.get(pair.spot.exchange_trading_symbol)
            future = future_ltps.get(pair.future.exchange_trading_symbol)
            dte = max((pair.future.expiry - as_of.date()).days, 0)
            rows.append(self._build_row(pair, spot, future, dte))

        # Aggregation lands in the next commit — for now ship a snapshot whose
        # counts/averages are zero so the rest of the system can wire up.
        return IndexSnapshot(
            timestamp=as_of,
            rows=tuple(rows),
            avg_basis_pct=None,
            avg_annualised_pct=None,
            premium_count=0,
            discount_count=0,
            flat_count=0,
            missing_count=0,
        )

    @staticmethod
    def _build_row(
        pair: InstrumentPair, spot: float | None, future: float | None, dte: int
    ) -> PriceRow:
        if spot is None or future is None or spot <= 0:
            return PriceRow(
                symbol=pair.spot.symbol,
                spot=spot,
                future=future,
                futures_symbol=pair.future.trading_symbol,
                expiry=pair.future.expiry,
                days_to_expiry=dte,
                basis=None,
                basis_pct=None,
                annualised_pct=None,
                stance=Stance.UNKNOWN,
            )

        basis = future - spot
        basis_pct = (future / spot - 1.0) * 100.0
        # Annualise using simple proportion; dte=0 (expiry day) collapses to dte=1
        # so we never divide by zero and the number remains interpretable.
        annualised = basis_pct * (365.0 / max(dte, 1))

        if abs(basis_pct) < 0.01:
            stance = Stance.FLAT
        elif basis_pct > 0:
            stance = Stance.PREMIUM
        else:
            stance = Stance.DISCOUNT

        return PriceRow(
            symbol=pair.spot.symbol,
            spot=spot,
            future=future,
            futures_symbol=pair.future.trading_symbol,
            expiry=pair.future.expiry,
            days_to_expiry=dte,
            basis=basis,
            basis_pct=basis_pct,
            annualised_pct=annualised,
            stance=stance,
        )
