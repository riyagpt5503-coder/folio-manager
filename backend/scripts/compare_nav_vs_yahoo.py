"""Print Yahoo adjclose vs AMFI NAV side by side for one ticker.

Usage:
    python scripts/compare_nav_vs_yahoo.py NIFTYBEES.NS
    python scripts/compare_nav_vs_yahoo.py GOLDBEES.NS --rows 60
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from app.data import _fetch_ticker_series
from app.nav import fetch_nav_series, load_instruments


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ticker", help="NSE symbol as it appears in config/instruments.csv, e.g. GOLDBEES.NS")
    parser.add_argument("--rows", type=int, default=30, help="Number of most recent aligned rows to print (default: 30)")
    args = parser.parse_args()

    instruments = load_instruments()
    matches = instruments.loc[instruments["nse_symbol"] == args.ticker]
    if matches.empty:
        raise SystemExit(f"{args.ticker!r} not found in config/instruments.csv")
    amfi_code = matches.iloc[0]["amfi_code"]

    print(f"Fetching Yahoo price history for {args.ticker}...")
    yahoo_series = _fetch_ticker_series(args.ticker)

    print(f"Fetching AMFI NAV history for amfi_code={amfi_code}...")
    nav_series = fetch_nav_series(amfi_code)

    combined = pd.concat({"yahoo_price": yahoo_series, "amfi_nav": nav_series}, axis=1, join="inner")
    combined["ratio"] = combined["amfi_nav"] / combined["yahoo_price"]

    pd.set_option("display.max_rows", None)
    print()
    print(f"{args.ticker} (amfi_code={amfi_code}): {len(combined)} overlapping dates")
    print(combined.tail(args.rows))


if __name__ == "__main__":
    main()
