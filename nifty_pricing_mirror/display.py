"""Rich-based rendering of the spot/futures basis table."""

from __future__ import annotations

from rich.table import Table
from rich.text import Text

from .pricing import IndexSnapshot, PriceRow, Stance


def render_snapshot(snapshot: IndexSnapshot) -> Table:
    return _build_table(snapshot)


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
