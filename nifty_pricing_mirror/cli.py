"""Entry point: orchestrate auth → instrument resolution → live basis loop."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

from .config import Settings
from .display import LiveSurface, render_snapshot
from .groww_client import AuthenticationError, GrowwClient
from .instruments import InstrumentsRepo, resolve_universe
from .nifty50 import load_symbols
from .pricing import PricingEngine

log = logging.getLogger("nifty_mirror")


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="nifty-mirror",
        description=(
            "Live spot vs nearest-futures basis surface for the Nifty 50, "
            "powered by the Groww trading API."
        ),
    )
    p.add_argument(
        "--interval",
        type=float,
        default=None,
        help="Seconds between refreshes (default: NIFTY_REFRESH_SECONDS env or 3.0).",
    )
    p.add_argument(
        "--once",
        action="store_true",
        help="Print a single snapshot and exit (no live loop).",
    )
    p.add_argument(
        "--symbols-file",
        type=Path,
        default=None,
        help=(
            "Optional path to a text file of underlying symbols (one per line, "
            "'#' for comments). Defaults to the bundled Nifty 50 list."
        ),
    )
    p.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable INFO-level logs (off by default to keep the live UI clean).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_argparser().parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(message)s",
        handlers=[RichHandler(show_path=False, show_time=False, markup=True)],
    )

    console = Console()
    settings = Settings.from_env()
    interval = args.interval if args.interval is not None else settings.refresh_seconds

    symbols = load_symbols(args.symbols_file)
    console.print(
        f"[bold]Universe:[/bold] {len(symbols)} symbols "
        f"({'custom' if args.symbols_file else 'default Nifty 50'})"
    )

    try:
        client = GrowwClient(settings)
    except AuthenticationError as exc:
        console.print(f"[bold red]Auth error:[/bold red] {exc}")
        return 2

    repo = InstrumentsRepo(cache_hours=settings.instruments_cache_hours)
    with console.status("[bold cyan]Loading Groww instrument master…", spinner="dots"):
        repo.load()

    pairs, skipped = resolve_universe(repo, list(symbols))
    if skipped:
        console.print(
            f"[yellow]Skipped {len(skipped)} symbol(s) without a matched "
            f"NSE futures contract:[/yellow] {', '.join(skipped)}"
        )
    if not pairs:
        console.print("[bold red]No tradable pairs resolved — aborting.[/bold red]")
        return 3

    engine = PricingEngine(client, pairs)

    if args.once:
        snapshot = engine.snapshot()
        console.print(render_snapshot(snapshot))
        return 0

    return _run_live(engine, interval, console)


def _run_live(engine: PricingEngine, interval: float, console: Console) -> int:
    try:
        with LiveSurface(console=console) as surface:
            surface.show_message("Fetching first snapshot…")
            while True:
                try:
                    snapshot = engine.snapshot()
                    surface.update(snapshot)
                except Exception as exc:  # transient API errors should not kill the loop
                    log.warning("Snapshot refresh failed: %s", exc)
                    surface.show_message(
                        f"Refresh failed: {exc}\nRetrying in {interval:.1f}s…",
                        style="red",
                    )
                time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped.[/dim]")
        return 0


if __name__ == "__main__":
    sys.exit(main())
