"""Rich-based live rendering of the spot/futures basis surface."""

from __future__ import annotations

from datetime import datetime

from rich.align import Align
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .pricing import IndexSnapshot, PriceRow, Stance


def render_snapshot(snapshot: IndexSnapshot) -> Group:
    return Group(_build_table(snapshot), _build_footer(snapshot))


def _build_table(snapshot: IndexSnapshot) -> Table:
    table = Table(
        title=f"Nifty 50 - Spot vs Futures   (refreshed {snapshot.timestamp:%H:%M:%S})",
        title_style="bold white on blue",
        header_style="bold cyan",
        show_lines=False,
        expand=True,
        padding=(0, 1),
    )

    table.add_column("#", justify="right", style="dim", width=3)
    table.add_column("Symbol", style="bold", min_width=12)
    table.add_column("Spot", justify="right")
    table.add_column("Futures", justify="right")
    table.add_column("Contract", style="dim")
    table.add_column("Expiry", style="dim", justify="center")
    table.add_column("DTE", justify="right", style="dim")
    table.add_column("Basis", justify="right")
    table.add_column("Basis %", justify="right")
    table.add_column("Annualised %", justify="right")
    table.add_column("Stance", justify="center")

    for idx, row in enumerate(snapshot.rows, start=1):
        table.add_row(*_format_row(idx, row))

    return table


def _format_row(idx: int, row: PriceRow) -> list[Text | str]:
    spot = _fmt_price(row.spot)
    future = _fmt_price(row.future)
    basis = _signed(row.basis, fmt="{:+.2f}")
    basis_pct = _signed(row.basis_pct, fmt="{:+.3f}%")
    ann = _signed(row.annualised_pct, fmt="{:+.2f}%")
    stance_cell = _stance_text(row.stance)

    expiry = row.expiry.strftime("%d-%b-%y") if row.expiry else "-"
    dte = str(row.days_to_expiry)

    return [
        str(idx),
        row.symbol,
        spot,
        future,
        row.futures_symbol,
        expiry,
        dte,
        basis,
        basis_pct,
        ann,
        stance_cell,
    ]


def _fmt_price(value: float | None) -> Text:
    if value is None:
        return Text("--", style="dim italic")
    return Text(f"{value:,.2f}")


def _signed(value: float | None, *, fmt: str) -> Text:
    if value is None:
        return Text("--", style="dim italic")
    style = "green" if value > 0 else "red" if value < 0 else "white"
    return Text(fmt.format(value), style=style)


def _stance_text(stance: Stance) -> Text:
    # ASCII-only markers so the table renders on legacy Windows code pages.
    if stance is Stance.PREMIUM:
        return Text("^ PREMIUM", style="bold green")
    if stance is Stance.DISCOUNT:
        return Text("v DISCOUNT", style="bold red")
    if stance is Stance.FLAT:
        return Text("~ FLAT", style="yellow")
    return Text(".. N/A", style="dim italic")


def _build_footer(snapshot: IndexSnapshot) -> Panel:
    avg_basis = _signed(snapshot.avg_basis_pct, fmt="{:+.3f}%")
    avg_ann = _signed(snapshot.avg_annualised_pct, fmt="{:+.2f}%")

    bias = _index_bias(snapshot)

    line1 = Text.assemble(
        ("Index basis bias  ", "bold"),
        bias,
        ("    avg basis ", "dim"),
        avg_basis,
        ("    avg annualized ", "dim"),
        avg_ann,
    )
    line2 = Text.assemble(
        (f"  premium {snapshot.premium_count}", "green"),
        ("   ", ""),
        (f"discount {snapshot.discount_count}", "red"),
        ("   ", ""),
        (f"flat {snapshot.flat_count}", "yellow"),
        ("   ", ""),
        (f"missing {snapshot.missing_count}", "dim"),
        ("   total ", "dim"),
        (str(snapshot.total), "bold"),
    )

    return Panel(
        Align.left(Group(line1, line2)),
        title="Index Snapshot",
        border_style="blue",
    )


def _index_bias(snapshot: IndexSnapshot) -> Text:
    p, d = snapshot.premium_count, snapshot.discount_count
    if p == 0 and d == 0:
        return Text("UNKNOWN", style="dim")
    if p > d * 1.5:
        return Text("CONTANGO (futures rich)", style="bold green")
    if d > p * 1.5:
        return Text("BACKWARDATION (futures cheap)", style="bold red")
    return Text("MIXED", style="bold yellow")


class LiveSurface:
    """Context manager around `rich.live.Live` for the basis table."""

    def __init__(self, console: Console | None = None):
        self._console = console or Console()
        self._live: Live | None = None

    def __enter__(self) -> "LiveSurface":
        self._live = Live(
            renderable=Text(""),
            console=self._console,
            refresh_per_second=4,
            screen=False,
        )
        self._live.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._live is not None:
            self._live.__exit__(exc_type, exc, tb)

    def update(self, snapshot: IndexSnapshot) -> None:
        assert self._live is not None
        self._live.update(render_snapshot(snapshot))

    def show_message(self, message: str, *, style: str = "yellow") -> None:
        assert self._live is not None
        self._live.update(Panel(Text(message, style=style), title="Status"))
