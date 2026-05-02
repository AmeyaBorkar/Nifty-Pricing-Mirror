"""Stock universe definitions and loaders.

Defaults to the Nifty 200; the Nifty 50 subset is also bundled. Both lists
mirror the canonical NSE archives (`ind_nifty50list.csv`,
`ind_nifty200list.csv`). NSE rebalances each index periodically — pass a
custom symbols file via the CLI if you need a different snapshot.
"""

from __future__ import annotations

from pathlib import Path

NIFTY_50_SYMBOLS: tuple[str, ...] = (
    "ADANIENT",
    "ADANIPORTS",
    "APOLLOHOSP",
    "ASIANPAINT",
    "AXISBANK",
    "BAJAJ-AUTO",
    "BAJFINANCE",
    "BAJAJFINSV",
    "BEL",
    "BHARTIARTL",
    "CIPLA",
    "COALINDIA",
    "DRREDDY",
    "EICHERMOT",
    "ETERNAL",
    "GRASIM",
    "HCLTECH",
    "HDFCBANK",
    "HDFCLIFE",
    "HINDALCO",
    "HINDUNILVR",
    "ICICIBANK",
    "ITC",
    "INFY",
    "INDIGO",
    "JSWSTEEL",
    "JIOFIN",
    "KOTAKBANK",
    "LT",
    "M&M",
    "MARUTI",
    "MAXHEALTH",
    "NTPC",
    "NESTLEIND",
    "ONGC",
    "POWERGRID",
    "RELIANCE",
    "SBILIFE",
    "SHRIRAMFIN",
    "SBIN",
    "SUNPHARMA",
    "TCS",
    "TATACONSUM",
    "TMPV",
    "TATASTEEL",
    "TECHM",
    "TITAN",
    "TRENT",
    "ULTRACEMCO",
    "WIPRO",
)

NIFTY_200_SYMBOLS: tuple[str, ...] = (
    "360ONE", "ABB", "APLAPOLLO", "AUBANK", "ADANIENSOL",
    "ADANIENT", "ADANIGREEN", "ADANIPORTS", "ADANIPOWER", "ATGL",
    "ABCAPITAL", "ALKEM", "AMBUJACEM", "APOLLOHOSP", "ASHOKLEY",
    "ASIANPAINT", "ASTRAL", "AUROPHARMA", "DMART", "AXISBANK",
    "BSE", "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BAJAJHLDNG",
    "BANKBARODA", "BANKINDIA", "BDL", "BEL", "BHARATFORG",
    "BHEL", "BPCL", "BHARTIARTL", "GROWW", "BIOCON",
    "BLUESTARCO", "BOSCHLTD", "BRITANNIA", "CGPOWER", "CANBK",
    "CHOLAFIN", "CIPLA", "COALINDIA", "COCHINSHIP", "COFORGE",
    "COLPAL", "CONCOR", "COROMANDEL", "CUMMINSIND", "DLF",
    "DABUR", "DIVISLAB", "DIXON", "DRREDDY", "EICHERMOT",
    "ETERNAL", "EXIDEIND", "NYKAA", "FEDERALBNK", "FORTIS",
    "GAIL", "GVT&D", "GMRAIRPORT", "GLENMARK", "GODFRYPHLP",
    "GODREJCP", "GODREJPROP", "GRASIM", "HCLTECH", "HDFCAMC",
    "HDFCBANK", "HDFCLIFE", "HAVELLS", "HEROMOTOCO", "HINDALCO",
    "HAL", "HINDPETRO", "HINDUNILVR", "HINDZINC", "POWERINDIA",
    "HUDCO", "HYUNDAI", "ICICIBANK", "ICICIGI", "ICICIAMC",
    "IDFCFIRSTB", "ITC", "INDIANB", "INDHOTEL", "IOC",
    "IRCTC", "IRFC", "IREDA", "INDUSTOWER", "INDUSINDBK",
    "NAUKRI", "INFY", "INDIGO", "JSWENERGY", "JSWSTEEL",
    "JINDALSTEL", "JIOFIN", "JUBLFOOD", "KEI", "KPITTECH",
    "KALYANKJIL", "KOTAKBANK", "LTF", "LGEINDIA", "LICHSGFIN",
    "LTM", "LT", "LAURUSLABS", "LENSKART", "LODHA",
    "LUPIN", "MRF", "M&MFIN", "M&M", "MANKIND",
    "MARICO", "MARUTI", "MFSL", "MAXHEALTH", "MAZDOCK",
    "MOTILALOFS", "MPHASIS", "MCX", "MUTHOOTFIN", "NHPC",
    "NMDC", "NTPC", "NATIONALUM", "NESTLEIND", "OBEROIRLTY",
    "ONGC", "OIL", "PAYTM", "OFSS", "POLICYBZR",
    "PIIND", "PAGEIND", "PATANJALI", "PERSISTENT", "PHOENIXLTD",
    "PIDILITIND", "POLYCAB", "PFC", "POWERGRID", "PREMIERENE",
    "PRESTIGE", "PNB", "RECLTD", "RADICO", "RVNL",
    "RELIANCE", "SBICARD", "SBILIFE", "SRF", "MOTHERSON",
    "SHREECEM", "SHRIRAMFIN", "ENRIN", "SIEMENS", "SOLARINDS",
    "SBIN", "SAIL", "SUNPHARMA", "SUPREMEIND", "SUZLON",
    "SWIGGY", "TVSMOTOR", "TATACAP", "TATACOMM", "TCS",
    "TATACONSUM", "TATAELXSI", "TATAINVEST", "TMCV", "TMPV",
    "TATAPOWER", "TATASTEEL", "TECHM", "TITAN", "TORNTPHARM",
    "TRENT", "TIINDIA", "UPL", "ULTRACEMCO", "UNIONBANK",
    "UNITDSPR", "VBL", "VEDL", "VMM", "IDEA",
    "VOLTAS", "WAAREEENER", "WIPRO", "YESBANK", "ZYDUSLIFE",
)

INDICES: dict[str, tuple[str, ...]] = {
    "nifty50": NIFTY_50_SYMBOLS,
    "nifty200": NIFTY_200_SYMBOLS,
}

DEFAULT_INDEX = "nifty200"


def load_symbols(
    path: Path | None = None,
    *,
    index: str | None = None,
) -> tuple[str, ...]:
    """Return the symbols to track.

    `path` (a text file) takes precedence over `index`. If both are None we
    fall back to the default index.
    """

    if path is not None:
        raw = path.read_text(encoding="utf-8").splitlines()
        cleaned = []
        for line in raw:
            sym = line.split("#", 1)[0].strip()
            if sym:
                cleaned.append(sym.upper())
        if not cleaned:
            raise ValueError(f"No symbols found in {path}")
        return tuple(cleaned)

    name = (index or DEFAULT_INDEX).lower()
    try:
        return INDICES[name]
    except KeyError as exc:
        valid = ", ".join(sorted(INDICES))
        raise ValueError(f"Unknown index '{index}'. Choose one of: {valid}") from exc
