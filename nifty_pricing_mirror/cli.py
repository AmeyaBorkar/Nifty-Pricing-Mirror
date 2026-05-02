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
from .csv_export import append_history, write_snapshot
from .display import LiveSurface, render_snapshot
from .groww_client import AuthenticationError, GrowwClient
from .instruments import InstrumentsRepo, resolve_universe
from .pricing import IndexSnapshot, PricingEngine
from .server import DashboardServer
from .universe import DEFAULT_INDEX, INDICES, load_symbols

log = logging.getLogger("nifty_mirror")


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="nifty-mirror",
        description=(
            "Live spot vs nearest-futures basis surface for an NSE index, "
            "powered by the Groww trading API."
        ),
    )
    p.add_argument(
        "--index",
        choices=sorted(INDICES.keys()),
        default=DEFAULT_INDEX,
        help=f"Bundled index to track (default: {DEFAULT_INDEX}). "
             "Ignored when --symbols-file is given.",
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
            "'#' for comments). Overrides --index when set."
        ),
    )
    p.add_argument(
        "--csv-out",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Atomically rewrite this CSV with the latest snapshot after each "
            "refresh. Safe to point Excel / Power Query at this path."
        ),
    )
    p.add_argument(
        "--csv-history",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Append every refresh to this CSV (timestamped, one row per "
            "stock per refresh). Ideal for time-series Pivot charts."
        ),
    )
    p.add_argument(
        "--serve",
        nargs="?",
        const=8080,
        type=int,
        default=None,
        metavar="PORT",
        help=(
            "Start the HTTP dashboard alongside the live loop. Default port "
            "is 8080 (e.g. `--serve` or `--serve 9000`). Disables the in-"
            "terminal table to keep stdout clean for status messages."
        ),
    )
    p.add_argument(
        "--host",
        default="127.0.0.1",
        help="Dashboard bind address. Use 0.0.0.0 to expose on the LAN.",
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

    symbols = load_symbols(args.symbols_file, index=args.index)
    label = "custom" if args.symbols_file else args.index
    console.print(f"[bold]Universe:[/bold] {len(symbols)} symbols ({label})")

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

    if args.csv_out:
        console.print(f"[dim]Snapshot CSV -> {args.csv_out}[/dim]")
    if args.csv_history:
        console.print(f"[dim]History CSV  -> {args.csv_history}[/dim]")

    server: DashboardServer | None = None
    if args.serve is not None:
        server = DashboardServer(host=args.host, port=args.serve)
        try:
            server.start()
        except OSError as exc:
            console.print(
                f"[bold red]Could not bind dashboard to {args.host}:{args.serve}: {exc}[/bold red]"
            )
            return 4
        console.print(
            f"[bold cyan]Dashboard:[/bold cyan] {server.url}  "
            f"[dim](Ctrl+C to stop)[/dim]"
        )

    try:
        if args.once:
            snapshot = engine.snapshot()
            console.print(render_snapshot(snapshot))
            _export_snapshot(snapshot, args.csv_out, args.csv_history)
            if server is not None:
                server.update(snapshot)
            return 0

        return _run_live(
            engine, interval, console, args.csv_out, args.csv_history, server
        )
    finally:
        if server is not None:
            server.stop()


def _run_live(
    engine: PricingEngine,
    interval: float,
    console: Console,
    csv_out: Path | None,
    csv_history: Path | None,
    server: DashboardServer | None,
) -> int:
    # When serving the dashboard, skip the in-terminal Live table — the
    # browser is the primary surface and keeping stdout clean lets the user
    # follow refresh status / errors line by line.
    if server is not None:
        return _run_headless_loop(engine, interval, console, csv_out, csv_history, server)

    try:
        with LiveSurface(console=console) as surface:
            surface.show_message("Fetching first snapshot…")
            while True:
                try:
                    snapshot = engine.snapshot()
                    surface.update(snapshot)
                    _export_snapshot(snapshot, csv_out, csv_history)
                except Exception as exc:  # transient API errors should not kill the loop
                    log.warning("Snapshot refresh failed: %s", exc)
                    surface.show_message(
                        f"Refresh failed: {exc}\nRetrying in {interval:.1f}s...",
                        style="red",
                    )
                time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped.[/dim]")
        return 0


def _run_headless_loop(
    engine: PricingEngine,
    interval: float,
    console: Console,
    csv_out: Path | None,
    csv_history: Path | None,
    server: DashboardServer,
) -> int:
    console.print(f"[dim]Refreshing every {interval:.1f}s. Ctrl+C to stop.[/dim]")
    refresh_count = 0
    try:
        while True:
            try:
                snapshot = engine.snapshot()
                server.update(snapshot)
                _export_snapshot(snapshot, csv_out, csv_history)
                refresh_count += 1
                if refresh_count % 20 == 1:
                    console.print(
                        f"[dim]{snapshot.timestamp:%H:%M:%S}[/dim] "
                        f"refresh #{refresh_count} "
                        f"premium={snapshot.premium_count} "
                        f"discount={snapshot.discount_count} "
                        f"missing={snapshot.missing_count}"
                    )
            except Exception as exc:
                log.warning("Snapshot refresh failed: %s", exc)
                console.print(f"[red]refresh failed:[/red] {exc}")
            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped.[/dim]")
        return 0


def _export_snapshot(
    snapshot: IndexSnapshot,
    csv_out: Path | None,
    csv_history: Path | None,
) -> None:
    """Best-effort CSV writes; log and continue on failure so the loop survives."""

    if csv_out is not None:
        try:
            write_snapshot(snapshot, csv_out)
        except OSError as exc:
            log.warning("CSV snapshot write to %s failed: %s", csv_out, exc)
    if csv_history is not None:
        try:
            append_history(snapshot, csv_history)
        except OSError as exc:
            log.warning("CSV history append to %s failed: %s", csv_history, exc)


if __name__ == "__main__":
    sys.exit(main())
