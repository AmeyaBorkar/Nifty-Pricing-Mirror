"""Offline end-to-end smoke test.

Exercises everything except the actual Groww auth + LTP call:
  1. Downloads the public instrument master CSV.
  2. Resolves the Nifty 50 universe to (spot, near-future) pairs.
  3. Runs `PricingEngine.snapshot` against a fake client that returns
     deterministic synthetic LTPs so we can validate rendering.
"""

from __future__ import annotations

import io
from datetime import date

from rich.console import Console

from nifty_pricing_mirror.display import render_snapshot
from nifty_pricing_mirror.instruments import InstrumentsRepo, resolve_universe
from nifty_pricing_mirror.nifty50 import NIFTY_50_SYMBOLS
from nifty_pricing_mirror.pricing import PricingEngine


class FakeClient:
    """Pretends to be GrowwClient — returns synthetic prices."""

    SEGMENT_CASH = "CASH"
    SEGMENT_FNO = "FNO"
    EXCHANGE_NSE = "NSE"

    def batched_ltp(self, segment, exchange_trading_symbols):
        # Spot=100*hash%500+250, Future=spot*(1 + small basis %).
        prices = {}
        for i, key in enumerate(exchange_trading_symbols):
            base = 250 + (abs(hash(key)) % 5000) / 10.0
            if segment == self.SEGMENT_FNO:
                # Alternate premium / discount / flat to exercise all stances.
                tweak = {0: 1.0035, 1: 0.998, 2: 1.0001, 3: 1.0, 4: 0.9925}[i % 5]
                prices[key] = round(base * tweak, 2)
            else:
                prices[key] = round(base, 2)
        return prices


def main() -> int:
    console = Console(record=True, width=180)

    repo = InstrumentsRepo()
    df = repo.load()
    console.print(f"[bold]Instruments loaded:[/bold] {len(df):,} rows")

    pairs, skipped = resolve_universe(repo, list(NIFTY_50_SYMBOLS), as_of=date.today())
    console.print(f"[bold]Resolved pairs:[/bold] {len(pairs)} / {len(NIFTY_50_SYMBOLS)}")
    if skipped:
        console.print(f"[yellow]Skipped:[/yellow] {', '.join(skipped)}")

    if not pairs:
        console.print("[red]No pairs resolved — aborting.[/red]")
        return 1

    # Show 5 sample pairs to prove the futures match looks sane.
    for pair in pairs[:5]:
        console.print(
            f"  {pair.spot.symbol:12s} -> spot {pair.spot.exchange_trading_symbol:24s}"
            f" | future {pair.future.exchange_trading_symbol:32s}"
            f" expiry {pair.future.expiry} lot {pair.future.lot_size}"
        )

    engine = PricingEngine(FakeClient(), pairs)
    snapshot = engine.snapshot()
    console.print(render_snapshot(snapshot))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
