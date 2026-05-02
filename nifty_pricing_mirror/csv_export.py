"""Atomic CSV exporters for the basis surface.

Two modes:

* ``write_snapshot(path)`` — replaces ``path`` with the current snapshot in a
  single atomic ``rename`` so a consumer (Excel via Power Query, pandas,
  dashboards, etc.) can poll without ever seeing a half-written file.

* ``append_history(path)`` — appends one row per stock per refresh, useful
  for time-series Pivot charts.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from .pricing import IndexSnapshot, PriceRow

SNAPSHOT_HEADERS: tuple[str, ...] = (
    "rank",
    "symbol",
    "spot",
    "future",
    "futures_symbol",
    "expiry",
    "days_to_expiry",
    "basis",
    "basis_pct",
    "annualised_pct",
    "stance",
    "timestamp",
)


def write_snapshot(snapshot: IndexSnapshot, path: Path) -> None:
    """Atomically replace ``path`` with one row per stock from this snapshot.

    Uses ``Path.replace`` which is an atomic syscall on both Windows and
    POSIX, so any reader (Excel, Power Query, pandas) either gets the
    previous snapshot or the new one — never a partial file.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(SNAPSHOT_HEADERS)
        for idx, row in enumerate(snapshot.rows, start=1):
            writer.writerow(_format_row(idx, row, snapshot.timestamp))
    tmp.replace(path)


def append_history(snapshot: IndexSnapshot, path: Path) -> None:
    """Append every row of this snapshot to a growing history CSV."""

    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        if write_header:
            writer.writerow(SNAPSHOT_HEADERS)
        for idx, row in enumerate(snapshot.rows, start=1):
            writer.writerow(_format_row(idx, row, snapshot.timestamp))


def _format_row(idx: int, row: PriceRow, ts: datetime) -> list:
    return [
        idx,
        row.symbol,
        _num(row.spot),
        _num(row.future),
        row.futures_symbol,
        row.expiry.isoformat() if row.expiry else "",
        row.days_to_expiry,
        _num(row.basis),
        _num(row.basis_pct),
        _num(row.annualised_pct),
        row.stance.value,
        ts.isoformat(timespec="seconds"),
    ]


def _num(value: float | None) -> str:
    """Empty cell when the LTP is missing — Excel reads that as a blank."""
    if value is None:
        return ""
    return f"{value:.6g}"
