import pandas as pd

from app.config import settings
from app.universe import ASSET_BY_TICKER


def implied_returns(cov: pd.DataFrame, w_policy: pd.Series, delta: float = 2.5) -> pd.Series:
    return delta * (cov @ w_policy)


def policy_weights(tickers: list[str]) -> pd.Series:
    """Map settings.policy_weights (per asset_class) to per-ticker weights,
    split equally among tickers sharing a class, renormalized over `tickers`."""
    tickers_by_class: dict[str, list[str]] = {}
    for ticker in tickers:
        asset_class = ASSET_BY_TICKER[ticker]["asset_class"]
        tickers_by_class.setdefault(asset_class, []).append(ticker)

    weights: dict[str, float] = {}
    for asset_class, class_tickers in tickers_by_class.items():
        per_ticker = settings.policy_weights.get(asset_class, 0.0) / len(class_tickers)
        for ticker in class_tickers:
            weights[ticker] = per_ticker

    w = pd.Series(weights, index=tickers)
    total = w.sum()
    return w / total if total else w
