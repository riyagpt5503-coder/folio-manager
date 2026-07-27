import logging

import numpy as np
import pandas as pd

from app import gates
from app.config import settings
from app.data import market_data_cache
from app.models import RiskProfile
from app.optimizer import solve_portfolio

logger = logging.getLogger(__name__)

_DEFAULT_RISK_PROFILE = RiskProfile.moderate


class _LastSolve:
    def __init__(self) -> None:
        self.risk_profile: RiskProfile | None = None
        self.weights: dict[str, float] = {}
        self.binding_constraints: list[dict] = []

    def record(self, risk_profile: RiskProfile, weights: dict[str, float], binding_constraints: list[dict]) -> None:
        self.risk_profile = risk_profile
        self.weights = dict(weights)
        self.binding_constraints = binding_constraints


last_solve = _LastSolve()


def ensure_last_solve() -> _LastSolve:
    """Guarantees there's a solve to report on. If /api/portfolio hasn't been
    called yet this process, compute a default one so /api/risk is never empty."""
    if last_solve.risk_profile is None:
        prices, mu_by_profile, cov = market_data_cache.get()
        surviving, _ = gates.apply_gates(
            market_data_cache.nav_start_dates, market_data_cache.premium, as_of=prices.index[-1]
        )
        mu = mu_by_profile[_DEFAULT_RISK_PROFILE.value]
        weights, _, binding_constraints = solve_portfolio(
            _DEFAULT_RISK_PROFILE, mu.loc[surviving], cov.loc[surviving, surviving]
        )
        last_solve.record(_DEFAULT_RISK_PROFILE, weights, binding_constraints)
        logger.info("No prior solve found; computed a default '%s' solve for /api/risk", _DEFAULT_RISK_PROFILE.value)
    return last_solve


def correlation_matrix(cov: pd.DataFrame) -> pd.DataFrame:
    std = np.sqrt(np.diag(cov))
    corr = cov.values / np.outer(std, std)
    return pd.DataFrame(corr, index=cov.index, columns=cov.columns)


def risk_contributions(weights: dict[str, float], cov: pd.DataFrame) -> dict[str, float]:
    """Percent contribution to portfolio risk per asset: w_i * (Sigma w)_i / (w^T Sigma w)."""
    tickers = [t for t in weights if t in cov.index]
    if not tickers:
        return {}
    w = pd.Series({t: weights[t] for t in tickers})
    sigma_w = cov.loc[tickers, tickers].dot(w)
    portfolio_variance = float(w.dot(sigma_w))
    if portfolio_variance <= 0:
        return {t: 0.0 for t in tickers}
    contributions = (w * sigma_w) / portfolio_variance
    return {t: float(contributions[t]) for t in tickers}


def portfolio_max_drawdown(weights: dict[str, float], nav_prices: pd.DataFrame) -> float:
    """Historical max drawdown of a constant-weight (continuously rebalanced)
    portfolio over the same sample nav_prices/cov were estimated from."""
    tickers = [t for t in weights if t in nav_prices.columns]
    if not tickers:
        return 0.0
    daily_returns = nav_prices[tickers].pct_change().dropna()
    w = pd.Series({t: weights[t] for t in tickers})
    # Cash (if any) contributes 0 return every day, so it dampens the whole
    # series by the same (1 - cash_weight) factor used in /api/portfolio.
    portfolio_returns = daily_returns[tickers].dot(w) * (1 - settings.cash_weight)
    portfolio_index = (1 + portfolio_returns).cumprod()
    running_max = portfolio_index.cummax()
    drawdown = portfolio_index / running_max - 1
    return float(drawdown.min())
