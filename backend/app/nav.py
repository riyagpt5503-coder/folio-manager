import logging
from pathlib import Path

import pandas as pd
import requests

from app.errors import DataFetchError

logger = logging.getLogger(__name__)

_NAV_URL = "https://api.mfapi.in/mf/{amfi_code}"
_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_INSTRUMENTS_CSV = _REPO_ROOT / "config" / "instruments.csv"

_session = requests.Session()
_session.headers.update({"User-Agent": _USER_AGENT})

# AMFI publishes raw per-unit NAV, not adjusted for unit splits/consolidations
# (unlike Yahoo's adjclose). Several of these ETFs did large splits - e.g.
# NIFTYBEES/BANKBEES 1:10 and GOLDBEES 1:100 on 2019-12-23 - which show up as
# a fabricated ~90%+ single-day move. A real diversified ETF/index NAV cannot
# genuinely move this much in one day, so treat any jump past this threshold
# as a split and rescale the pre-split history to match.
_SPLIT_JUMP_THRESHOLD = 0.5


def _adjust_for_splits(series: pd.Series) -> pd.Series:
    adjusted = series.copy()
    pct_change = adjusted.pct_change()
    split_dates = pct_change[pct_change.abs() > _SPLIT_JUMP_THRESHOLD].index

    for split_date in split_dates:
        loc = adjusted.index.get_loc(split_date)
        if loc == 0:
            continue
        ratio = adjusted.iloc[loc] / adjusted.iloc[loc - 1]
        adjusted.iloc[:loc] *= ratio

    return adjusted


def load_instruments(path: Path = _INSTRUMENTS_CSV) -> pd.DataFrame:
    return pd.read_csv(path)


def fetch_nav_series(amfi_code: int | str) -> pd.Series:
    resp = _session.get(_NAV_URL.format(amfi_code=amfi_code), timeout=15)
    resp.raise_for_status()
    payload = resp.json()

    records = payload.get("data") or []
    if not records:
        raise DataFetchError(f"No NAV data returned for AMFI code {amfi_code}")

    dates = pd.to_datetime([r["date"] for r in records], format="%d-%m-%Y")
    navs = [float(r["nav"]) for r in records]
    series = pd.Series(navs, index=dates).sort_index()
    series = series[~series.index.duplicated(keep="last")]
    return _adjust_for_splits(series)


def fetch_nav_matrix(instruments: pd.DataFrame | None = None) -> pd.DataFrame:
    """NAV history for every instrument, indexed by date with columns = nse_symbol."""
    if instruments is None:
        instruments = load_instruments()

    series_list = []
    for _, row in instruments.iterrows():
        series = fetch_nav_series(row["amfi_code"])
        series.name = row["nse_symbol"]
        series_list.append(series)

    return pd.concat(series_list, axis=1)
