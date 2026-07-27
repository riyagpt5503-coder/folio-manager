import numpy as np
import pandas as pd

from app.config import settings

ROLLING_YEARS = 3
TRADING_DAYS_PER_YEAR = 252


def _rolling_window_returns(nav: pd.Series, years: int = ROLLING_YEARS) -> pd.Series:
    """Total return over each date-anchored [t, t + years] window, for every
    start date t that has a window fully contained in the series. Uses
    calendar-date offsets (not a fixed row count) so gaps/holidays in the NAV
    calendar don't skew the window length."""
    last_date = nav.index[-1]
    starts: list[pd.Timestamp] = []
    values: list[float] = []

    for t in nav.index:
        target = t + pd.DateOffset(years=years)
        if target > last_date:
            break
        end_price = nav.asof(target)
        if pd.isna(end_price):
            continue
        starts.append(t)
        values.append(end_price / nav.loc[t] - 1)

    return pd.Series(values, index=starts)


def _annualized_vol(daily_returns: pd.Series) -> float:
    return float(daily_returns.std(ddof=0) * np.sqrt(TRADING_DAYS_PER_YEAR))


def _max_drawdown(nav: pd.Series) -> float:
    running_max = nav.cummax()
    drawdown = nav / running_max - 1
    return float(drawdown.min())


def _cagr(nav: pd.Series) -> float:
    days = (nav.index[-1] - nav.index[0]).days
    if days <= 0:
        return 0.0
    return float((nav.iloc[-1] / nav.iloc[0]) ** (365.25 / days) - 1)


def _sortino_ratio(nav: pd.Series, daily_returns: pd.Series) -> float:
    downside = daily_returns[daily_returns < 0]
    if downside.empty:
        return 0.0
    downside_deviation = downside.std(ddof=0) * np.sqrt(TRADING_DAYS_PER_YEAR)
    if not downside_deviation:
        return 0.0
    return float((_cagr(nav) - settings.risk_free_rate) / downside_deviation)


def compute_ticker_metrics(nav: pd.Series) -> dict:
    nav = nav.dropna()
    daily_returns = nav.pct_change().dropna()
    window_returns = _rolling_window_returns(nav)

    return {
        "rolling_3y_return_median": float(window_returns.median()) if not window_returns.empty else None,
        "rolling_3y_return_p10": float(window_returns.quantile(0.10)) if not window_returns.empty else None,
        "rolling_3y_window_count": int(len(window_returns)),
        "annualized_vol": _annualized_vol(daily_returns),
        "max_drawdown": _max_drawdown(nav),
        "sortino_ratio": _sortino_ratio(nav, daily_returns),
    }


def compute_metrics(nav_prices: pd.DataFrame) -> dict[str, dict]:
    """nav_prices: per-ticker NAV columns, NOT intersected across tickers -
    each column should retain its own full history so short-lived tickers
    don't truncate the sample available to longer-lived ones."""
    return {ticker: compute_ticker_metrics(nav_prices[ticker]) for ticker in nav_prices.columns}
