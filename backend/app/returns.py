import pandas as pd

from app.config import settings
from app.models import RiskProfile
from app.universe import ASSET_BY_TICKER


def implied_returns(cov: pd.DataFrame, w_policy: pd.Series, delta: float = 2.5) -> pd.Series:
    # delta * (cov @ w_policy) is the equilibrium EXCESS return; add the
    # risk-free rate back to get total return, matching PyPortfolioOpt's
    # market_implied_prior_returns.
    return delta * (cov @ w_policy) + settings.risk_free_rate


def policy_weights_for_profile(risk_profile: RiskProfile, tickers: list[str]) -> pd.Series:
    """Map settings.policy_weights_by_profile[risk_profile] (per asset_class)
    to per-ticker weights, split equally among tickers sharing a class,
    renormalized over `tickers`."""
    class_weights = settings.policy_weights_by_profile[risk_profile.value]

    tickers_by_class: dict[str, list[str]] = {}
    for ticker in tickers:
        asset_class = ASSET_BY_TICKER[ticker]["asset_class"]
        tickers_by_class.setdefault(asset_class, []).append(ticker)

    weights: dict[str, float] = {}
    for asset_class, class_tickers in tickers_by_class.items():
        per_ticker = class_weights.get(asset_class, 0.0) / len(class_tickers)
        for ticker in class_tickers:
            weights[ticker] = per_ticker

    w = pd.Series(weights, index=tickers)
    total = w.sum()
    return w / total if total else w
