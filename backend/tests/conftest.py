import numpy as np
import pandas as pd
import pytest

from app.universe import TICKERS

# (annual_return, annual_vol, market_beta) per ticker, chosen so that the
# sector-capped assets (Gold, Silver, International Equity) are the most
# attractive on a risk-adjusted basis and actually pressure their caps.
_RETURN_VOL_BETA = {
    "NIFTYBEES.NS": (0.12, 0.15, 0.80),
    "JUNIORBEES.NS": (0.16, 0.20, 0.70),
    "BANKBEES.NS": (0.13, 0.18, 0.75),
    "ITBEES.NS": (0.14, 0.19, 0.70),
    "MON100.NS": (0.22, 0.22, 0.40),
    "GILT5YBEES.NS": (0.07, 0.05, 0.10),
    "GOLDBEES.NS": (0.20, 0.12, 0.10),
    "SILVERBEES.NS": (0.25, 0.28, 0.20),
}


@pytest.fixture
def fixed_prices() -> pd.DataFrame:
    """A deterministic, seeded price DataFrame standing in for a live Yahoo fetch."""
    dates = pd.bdate_range("2020-01-01", periods=756)  # ~3 trading years
    rng = np.random.default_rng(42)
    market_factor = rng.normal(0, 1, len(dates))

    columns = {}
    for ticker in TICKERS:
        ann_return, ann_vol, beta = _RETURN_VOL_BETA[ticker]
        idio = rng.normal(0, 1, len(dates))
        systematic = beta * market_factor + np.sqrt(max(1 - beta**2, 0)) * idio
        daily_returns = ann_return / 252 + (ann_vol / np.sqrt(252)) * systematic
        columns[ticker] = 100 * np.cumprod(1 + daily_returns)

    return pd.DataFrame(columns, index=dates)


@pytest.fixture
def mu_cov(monkeypatch, fixed_prices):
    """mu_by_profile/cov computed by the real data-layer pipeline, with the
    network fetch mocked out. mu_by_profile has one Series per RiskProfile."""
    from app.data import MarketDataCache

    nav_start_dates = {ticker: fixed_prices.index[0] for ticker in fixed_prices.columns}
    monkeypatch.setattr(
        "app.data._fetch_and_clean_prices",
        lambda: (fixed_prices, fixed_prices.copy(), fixed_prices.copy(), nav_start_dates, []),
    )
    cache = MarketDataCache()
    _, mu_by_profile, cov = cache.get()
    return mu_by_profile, cov
