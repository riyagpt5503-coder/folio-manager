import logging
import time

import pandas as pd
import requests
from pypfopt import expected_returns, risk_models

from app.config import settings
from app.errors import DataFetchError
from app.universe import TICKERS

logger = logging.getLogger(__name__)

_RETRY_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 2
_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

_session = requests.Session()
_session.headers.update({"User-Agent": _USER_AGENT})


class MarketDataCache:
    def __init__(self) -> None:
        self._prices: pd.DataFrame | None = None
        self._mu: pd.Series | None = None
        self._cov: pd.DataFrame | None = None
        self._fetched_at: float | None = None

    @property
    def is_warm(self) -> bool:
        return self._prices is not None

    @property
    def cache_age_seconds(self) -> float:
        if self._fetched_at is None:
            return float("inf")
        return time.time() - self._fetched_at

    def get(self) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
        ttl_seconds = settings.cache_ttl_minutes * 60
        if self._prices is None or self.cache_age_seconds > ttl_seconds:
            self._refresh()
        return self._prices, self._mu, self._cov

    def _refresh(self) -> None:
        prices = _fetch_prices_with_retry()
        self._prices = prices
        self._mu = expected_returns.mean_historical_return(prices)
        self._cov = risk_models.CovarianceShrinkage(prices).ledoit_wolf()
        self._fetched_at = time.time()
        logger.info("Market data cache refreshed: %d rows, %d tickers", len(prices), len(prices.columns))


def _fetch_prices_with_retry() -> pd.DataFrame:
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


def _fetch_and_clean_prices() -> pd.DataFrame:
    series_list: list[pd.Series] = []
    failed: list[str] = []

    for ticker in TICKERS:
        try:
            series_list.append(_fetch_ticker_series(ticker))
        except Exception as exc:  # noqa: BLE001 - collect and report all failures together
            logger.warning("Failed to fetch %s: %s", ticker, exc)
            failed.append(ticker)

    if failed:
        raise DataFetchError(f"No data returned for ticker(s): {', '.join(failed)}")

    prices = pd.concat(series_list, axis=1)
    prices = prices[TICKERS]
    prices = prices.ffill(limit=5)
    prices = prices.dropna(how="any")

    if prices.empty:
        raise DataFetchError("Price matrix is empty after cleaning; no overlapping date range across tickers")

    still_missing = [t for t in TICKERS if prices[t].isna().any()]
    if still_missing:
        raise DataFetchError(f"Unresolvable gaps in data for ticker(s): {', '.join(still_missing)}")

    return prices


market_data_cache = MarketDataCache()
