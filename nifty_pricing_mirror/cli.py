"""Entry point: orchestrate auth → instrument resolution → snapshot."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

from .config import Settings
from .display import render_snapshot
from .groww_client import AuthenticationError, GrowwClient
from .instruments import InstrumentsRepo, resolve_universe
from .nifty50 import load_symbols
from .pricing import PricingEngine

log = logging.getLogger("nifty_mirror")


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="nifty-mirror",
        description=(
            "Spot vs nearest-futures basis surface for the Nifty 50, "
            "powered by the Groww trading API."
        ),
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
        help="Enable INFO-level logs.",
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
    snapshot = engine.snapshot()
    console.print(render_snapshot(snapshot))
    return 0


if __name__ == "__main__":
    sys.exit(main())
