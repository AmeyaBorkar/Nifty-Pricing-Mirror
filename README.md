# Nifty Pricing Mirror

Live spot vs nearest-futures basis surface for an NSE index, powered by the
[Groww trading API](https://groww.in/trade-api). Renders a Rich-based table
in the terminal, optionally serves a browser dashboard, and can stream
snapshots to CSV for Excel / Power Query.

## What it shows

For every stock in the universe (Nifty 200 by default, Nifty 50 also bundled),
each refresh fetches:

- **Spot LTP** from the NSE cash segment
- **Nearest-expiry futures LTP** from NSE FNO

…and derives:

- `basis = future - spot`
- `basis_pct = (future / spot - 1) * 100`
- `annualised_pct = basis_pct * (365 / days_to_expiry)`
- A **stance** per stock — `PREMIUM` / `DISCOUNT` / `FLAT` / `UNKNOWN`
- An **index bias** — `CONTANGO` / `BACKWARDATION` / `MIXED`

## Installation

```powershell
python -m pip install -r requirements.txt
```

Python 3.10+ is required (uses PEP 604 union syntax and `from __future__
import annotations`).

## Authentication

Copy `.env.example` to `.env` and fill **one** of the three credential paths:

| Path | Variables | Notes |
| --- | --- | --- |
| A | `GROWW_ACCESS_TOKEN` | Paste from the Groww dashboard. Short-lived. |
| B | `GROWW_API_KEY` + `GROWW_API_SECRET` | Rotated daily by Groww. |
| C | `GROWW_API_KEY` + `GROWW_TOTP_SECRET` | Long-lived. Recommended. |

Generate credentials at <https://groww.in/trade-api/api-keys>.

## Usage

```powershell
python -m nifty_pricing_mirror.cli
```

…or use the wrapper script:

```powershell
.\run.ps1                          # default live loop, Nifty 200
.\run.ps1 -Once                    # single snapshot, then exit
.\run.ps1 -InstallDeps             # install/refresh requirements first
```

### CLI flags

| Flag | Default | Purpose |
| --- | --- | --- |
| `--index {nifty50,nifty200}` | `nifty200` | Bundled universe to track. |
| `--symbols-file PATH` | — | Use a custom universe (one symbol per line, `#` comments). Overrides `--index`. |
| `--interval SECONDS` | `NIFTY_REFRESH_SECONDS` env or `3.0` | Seconds between refreshes. |
| `--once` | off | Print one snapshot and exit. |
| `--csv-out PATH` | — | Atomically rewrite this CSV with the latest snapshot every refresh. Safe to point Excel / Power Query at. |
| `--csv-history PATH` | — | Append every refresh to this CSV (timestamped, one row per stock per refresh). |
| `--serve [PORT]` | off (default port `8080`) | Start the HTTP dashboard alongside the loop. Disables the in-terminal table. |
| `--host` | `127.0.0.1` | Dashboard bind address. Use `0.0.0.0` to expose on the LAN. |
| `--verbose`, `-v` | off | INFO-level logs. |

### Examples

```powershell
# Live terminal table, Nifty 50, 5-second refresh
python -m nifty_pricing_mirror.cli --index nifty50 --interval 5

# Browser dashboard at http://127.0.0.1:9000
python -m nifty_pricing_mirror.cli --serve 9000

# Atomic snapshot for Excel + a growing time-series log
python -m nifty_pricing_mirror.cli `
    --csv-out .\out\latest.csv `
    --csv-history .\out\history.csv

# Custom universe
python -m nifty_pricing_mirror.cli --symbols-file .\my_basket.txt
```

## How it works

1. **Auth** — `groww_client.py` resolves credentials from env (token → key+secret → key+TOTP) and instantiates `GrowwAPI`.
2. **Instrument master** — `instruments.py` downloads Groww's instrument CSV (cached on disk for 12h by default), then resolves each symbol to a spot row and the nearest active futures contract.
3. **Pricing loop** — `pricing.py` issues two batched `get_ltp` calls per refresh (cash + FNO), pairs them by symbol, and computes basis / annualised yield. The Groww live-data limit (10 req/sec, 300 req/min) is respected via a `_MIN_GAP_SECONDS` throttle.
4. **Surfaces** — by default `display.py` renders a `rich.live.Live` table in the terminal. With `--serve`, `server.py` runs a threaded Flask app that serves a static dashboard (under `nifty_pricing_mirror/static/`) and exposes the latest snapshot as JSON at `/api/snapshot`.
5. **CSV side-channels** — `csv_export.py` writes the current snapshot via a tmp-file + `Path.replace` (atomic on Windows and POSIX), so an Excel / Power Query consumer never reads a half-written file.

## Project layout

```
nifty_pricing_mirror/
  cli.py            # argparse + main loop orchestration
  config.py         # dotenv-backed Settings
  groww_client.py   # auth + batched LTP fetch
  instruments.py    # instrument-master download, cache, resolution
  pricing.py        # basis / annualised math, stance + bias
  display.py        # Rich live table
  server.py         # Flask dashboard server
  csv_export.py     # atomic CSV snapshot + history append
  universe.py       # Nifty 50 / Nifty 200 symbol lists
  static/           # browser dashboard (HTML/CSS/JS)
__main__.py         # `python "Nifty Pricing Mirror"` entry point
run.ps1             # PowerShell wrapper
smoke_test.py       # quick sanity check
.env.example        # credential template
```

## Notes

- Index constituents are baked in. NSE rebalances periodically — pass
  `--symbols-file` if you need a different snapshot.
- A symbol with no active NSE futures contract (or no cash listing) is logged
  as skipped at startup; it won't appear in the table.
- The `.cache/instruments.csv` file is refreshed automatically once it
  exceeds `NIFTY_INSTRUMENTS_CACHE_HOURS` (default 12h). Delete it to force
  a fresh download.
