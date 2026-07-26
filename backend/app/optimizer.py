import logging

import pandas as pd
from pypfopt import EfficientFrontier, objective_functions

from app.config import settings
from app.errors import OptimizationError
from app.models import RiskProfile

logger = logging.getLogger(__name__)

WeightsAndPerformance = tuple[dict[str, float], tuple[float, float, float]]


def _new_frontier(mu: pd.Series, cov: pd.DataFrame) -> EfficientFrontier:
    ef = EfficientFrontier(mu, cov, weight_bounds=(0, settings.max_weight))
    ef.add_objective(objective_functions.L2_reg, gamma=0.1)
    return ef


def _solve_min_volatility(mu: pd.Series, cov: pd.DataFrame) -> WeightsAndPerformance:
    ef = _new_frontier(mu, cov)
    ef.min_volatility()
    weights = ef.clean_weights()
    performance = ef.portfolio_performance(risk_free_rate=settings.risk_free_rate)
    return weights, performance


def _solve_max_sharpe(mu: pd.Series, cov: pd.DataFrame) -> WeightsAndPerformance:
    ef = _new_frontier(mu, cov)
    ef.max_sharpe(risk_free_rate=settings.risk_free_rate)
    weights = ef.clean_weights()
    performance = ef.portfolio_performance(risk_free_rate=settings.risk_free_rate)
    return weights, performance


def _solve_moderate(
    mu: pd.Series,
    cov: pd.DataFrame,
    min_vol_perf: tuple[float, float, float],
    max_sharpe_perf: tuple[float, float, float],
    min_vol_weights: dict[str, float],
    max_sharpe_weights: dict[str, float],
) -> WeightsAndPerformance:
    v_min = min_vol_perf[1]
    v_max = max_sharpe_perf[1]
    v_target = v_min + 0.5 * (v_max - v_min)
    v_target = max(v_target, v_min * 1.05)

    try:
        ef = _new_frontier(mu, cov)
        ef.efficient_risk(target_volatility=v_target)
        weights = ef.clean_weights()
        performance = ef.portfolio_performance(risk_free_rate=settings.risk_free_rate)
        return weights, performance
    except Exception as exc:  # noqa: BLE001 - fall back below
        logger.warning("efficient_risk(target_volatility=%.4f) failed: %s; trying efficient_return fallback", v_target, exc)

    r_min = min_vol_perf[0]
    r_max = max_sharpe_perf[0]
    r_target = r_min + 0.5 * (r_max - r_min)
    try:
        ef = _new_frontier(mu, cov)
        ef.efficient_return(target_return=r_target)
        weights = ef.clean_weights()
        performance = ef.portfolio_performance(risk_free_rate=settings.risk_free_rate)
        return weights, performance
    except Exception as exc:  # noqa: BLE001 - final fallback below
        logger.warning("efficient_return(target_return=%.4f) failed: %s; blending weight vectors", r_target, exc)

    tickers = mu.index
    blended = {t: 0.5 * min_vol_weights.get(t, 0.0) + 0.5 * max_sharpe_weights.get(t, 0.0) for t in tickers}
    blended_return = sum(blended[t] * mu[t] for t in tickers)
    blended_variance = sum(
        blended[t1] * blended[t2] * cov.loc[t1, t2] for t1 in tickers for t2 in tickers
    )
    blended_vol = blended_variance**0.5
    blended_sharpe = (blended_return - settings.risk_free_rate) / blended_vol if blended_vol else 0.0
    return blended, (blended_return, blended_vol, blended_sharpe)


def solve_portfolio(risk_profile: RiskProfile, mu: pd.Series, cov: pd.DataFrame) -> WeightsAndPerformance:
    try:
        min_vol_weights, min_vol_perf = _solve_min_volatility(mu, cov)
        if risk_profile == RiskProfile.conservative:
            return min_vol_weights, min_vol_perf

        max_sharpe_weights, max_sharpe_perf = _solve_max_sharpe(mu, cov)
        if risk_profile == RiskProfile.aggressive:
            return max_sharpe_weights, max_sharpe_perf

        return _solve_moderate(
            mu, cov, min_vol_perf, max_sharpe_perf, min_vol_weights, max_sharpe_weights
        )
    except Exception as exc:  # noqa: BLE001 - wrap into our own error type
        raise OptimizationError(f"Optimization failed for risk profile '{risk_profile.value}': {exc}") from exc
