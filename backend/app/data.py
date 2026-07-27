import logging
import time

import pandas as pd
import requests
from pypfopt import expected_returns, risk_models

from app import metrics as metrics_module
from app.config import settings
from app.errors import DataFetchError
from app.models import RiskProfile
from app.nav import fetch_nav_series, load_instruments
from app.returns import implied_returns, policy_weights_for_profile
from app.universe import TICKERS

logger = logging.getLogger(__name__)

_RETRY_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 2
_MIN_SURVIVING_TICKERS = 4
_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

_session = requests.Session()
_session.headers.update({"User-Agent": _USER_AGENT})


class MarketDataCache:
    def __init__(self) -> None:
        self._nav_prices: pd.DataFrame | None = None
        self._nav_prices_raw: pd.DataFrame | None = None
        self._yahoo_prices: pd.DataFrame | None = None
        self._premium: pd.DataFrame | None = None
        self._nav_start_dates: dict[str, pd.Timestamp] = {}
        self._mu_by_profile: dict[str, pd.Series] = {}
        self._cov: pd.DataFrame | None = None
        self._metrics: dict[str, dict] = {}
        self._fetched_at: float | None = None
        self._failed_tickers: list[str] = []

    @property
    def is_warm(self) -> bool:
        return self._nav_prices is not None

    @property
    def cache_age_seconds(self) -> float:
        if self._fetched_at is None:
            return float("inf")
        return time.time() - self._fetched_at

    @property
    def failed_tickers(self) -> list[str]:
        return self._failed_tickers

    @property
    def yahoo_prices(self) -> pd.DataFrame:
        return self._yahoo_prices

    @property
    def premium(self) -> pd.DataFrame:
        return self._premium

    @property
    def nav_start_dates(self) -> dict[str, pd.Timestamp]:
        return self._nav_start_dates

    @property
    def nav_prices_raw(self) -> pd.DataFrame:
        return self._nav_prices_raw

    @property
    def metrics(self) -> dict[str, dict]:
        return self._metrics

    def get(self) -> tuple[pd.DataFrame, dict[str, pd.Series], pd.DataFrame]:
        """Returns (nav_prices, mu_by_profile, cov) - NAV is the primary series
        driving both. mu_by_profile has one entry per RiskProfile since each
        profile's implied returns derive from its own policy weights."""
        ttl_seconds = settings.cache_ttl_minutes * 60
        if self._nav_prices is None or self.cache_age_seconds > ttl_seconds:
            self._refresh()
        return self._nav_prices, self._mu_by_profile, self._cov

    def _refresh(self) -> None:
        nav_prices, nav_prices_raw, yahoo_prices, nav_start_dates, failed_tickers = _fetch_prices_with_retry()
        self._nav_prices = nav_prices
        self._nav_prices_raw = nav_prices_raw
        self._yahoo_prices = yahoo_prices
        self._premium = (yahoo_prices - nav_prices) / nav_prices
        self._nav_start_dates = nav_start_dates
        self._failed_tickers = failed_tickers
        self._cov = risk_models.CovarianceShrinkage(nav_prices).ledoit_wolf()

        if settings.return_model == "historical":
            historical_mu = expected_returns.mean_historical_return(nav_prices)
            self._mu_by_profile = {profile.value: historical_mu for profile in RiskProfile}
        else:
            self._mu_by_profile = {
                profile.value: implied_returns(
                    self._cov, policy_weights_for_profile(profile, list(nav_prices.columns))
                )
                for profile in RiskProfile
            }

        self._metrics = metrics_module.compute_metrics(nav_prices_raw)
        self._fetched_at = time.time()
        logger.info(
            "Market data cache refreshed (NAV primary, return_model=%s): %d rows, %d tickers",
            settings.return_model,
            len(nav_prices),
            len(nav_prices.columns),
        )


def _fetch_prices_with_retry() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, pd.Timestamp], list[str]]:
    last_error: Exception | None = None
    for attempt in range(1, _RETRY_ATTEMPTS + 1):
        try:
            return _fetch_and_clean_prices()
        except Exception as exc:  # noqa: BLE001 - broad by design, we wrap/raise our own type
            last_error = exc
            logger.warning("Market data fetch attempt %d/%d failed: %s", attempt, _RETRY_ATTEMPTS, exc)
            if attempt < _RETRY_ATTEMPTS:
                time.sleep(_RETRY_BACKOFF_SECONDS * attempt)
    raise DataFetchError(f"Failed to fetch market data after {_RETRY_ATTEMPTS} attempts: {last_error}")


def _fetch_ticker_series(ticker: str) -> pd.Series:
    resp = _session.get(
        _CHART_URL.format(ticker=ticker),
        params={"range": f"{settings.lookback_years}y", "interval": "1d"},
        timeout=15,
    )
    resp.raise_for_status()
    payload = resp.json()

    chart = payload.get("chart", {})
    if chart.get("error"):
        raise DataFetchError(f"Yahoo Finance error for {ticker}: {chart['error']}")

    results = chart.get("result") or []
    if not results:
        raise DataFetchError(f"No chart result returned for {ticker}")

    result = results[0]
    timestamps = result.get("timestamp")
    quote = result.get("indicators", {}).get("adjclose") or result.get("indicators", {}).get("quote")
    if not timestamps or not quote:
        raise DataFetchError(f"No price series in response for {ticker}")

    closes = quote[0].get("adjclose") or quote[0].get("close")
    if not closes:
        raise DataFetchError(f"No adjclose/close data in response for {ticker}")

    index = pd.to_datetime(timestamps, unit="s").normalize()
    series = pd.Series(closes, index=index, name=ticker)
    return series[~series.index.duplicated(keep="last")]


def _fetch_and_clean_prices() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, pd.Timestamp], list[str]]:
    instruments = load_instruments()
    amfi_code_by_ticker = dict(zip(instruments["nse_symbol"], instruments["amfi_code"]))

    nav_series_list: list[pd.Series] = []
    yahoo_series_list: list[pd.Series] = []
    nav_start_dates: dict[str, pd.Timestamp] = {}
    failed: list[str] = []

    for ticker in TICKERS:
        try:
            nav_series = fetch_nav_series(amfi_code_by_ticker[ticker])
            nav_series.name = ticker
            yahoo_series = _fetch_ticker_series(ticker)
        except Exception as exc:  # noqa: BLE001 - collect and report all failures together
            logger.warning("Failed to fetch %s: %s", ticker, exc)
            failed.append(ticker)
            continue

        nav_start_dates[ticker] = nav_series.index[0]
        nav_series_list.append(nav_series)
        yahoo_series_list.append(yahoo_series)

    if failed:
        logger.warning("Dropping failed ticker(s), proceeding with the rest: %s", ", ".join(failed))

    surviving_tickers = [t for t in TICKERS if t not in failed]
    if len(surviving_tickers) < _MIN_SURVIVING_TICKERS:
        raise DataFetchError(
            f"Only {len(surviving_tickers)} ticker(s) survived after dropping failed ticker(s) "
            f"{', '.join(failed)}; need at least {_MIN_SURVIVING_TICKERS}"
        )

    nav_prices_raw = pd.concat(nav_series_list, axis=1)[surviving_tickers]
    nav_prices_raw = nav_prices_raw.ffill(limit=5)

    nav_prices = nav_prices_raw.dropna(how="any")

    if nav_prices.empty:
        raise DataFetchError("NAV price matrix is empty after cleaning; no overlapping date range across tickers")

    still_missing = [t for t in surviving_tickers if nav_prices[t].isna().any()]
    if still_missing:
        raise DataFetchError(f"Unresolvable gaps in NAV data for ticker(s): {', '.join(still_missing)}")

    yahoo_prices = pd.concat(yahoo_series_list, axis=1)[surviving_tickers]
    yahoo_prices = yahoo_prices.reindex(nav_prices.index).ffill(limit=5)

    logger.info(
        "Cleaned NAV price matrix: index[0]=%s index[-1]=%s len=%d nav_start_dates=%s",
        nav_prices.index[0],
        nav_prices.index[-1],
        len(nav_prices),
        nav_start_dates,
    )

    return nav_prices, nav_prices_raw, yahoo_prices, nav_start_dates, failed


market_data_cache = MarketDataCache()
