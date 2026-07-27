import logging

import pandas as pd
from pypfopt import EfficientFrontier, objective_functions

from app.config import settings
from app.errors import OptimizationError
from app.models import RiskProfile
from app.universe import ASSET_BY_TICKER

logger = logging.getLogger(__name__)

WeightsAndPerformance = tuple[dict[str, float], tuple[float, float, float]]


def _feasible_sector_lower(mu: pd.Series) -> dict[str, float]:
    """Drop sector_lower entries for asset classes with no surviving tickers
    in mu's index - otherwise the lower bound is infeasible (there's nothing
    left to allocate to satisfy it)."""
    surviving_classes = {ASSET_BY_TICKER[t]["asset_class"] for t in mu.index if t in ASSET_BY_TICKER}
    feasible: dict[str, float] = {}
    for asset_class, lower in settings.sector_lower.items():
        if asset_class in surviving_classes:
            feasible[asset_class] = lower
        else:
            logger.warning(
                "Dropping sector_lower constraint for asset_class '%s' (%.4f): no surviving tickers after gates",
                asset_class,
                lower,
            )
    return feasible


def _new_frontier(mu: pd.Series, cov: pd.DataFrame, max_weight: float, gamma: float) -> EfficientFrontier:
    ef = EfficientFrontier(mu, cov, weight_bounds=(0, max_weight))
    ef.add_objective(objective_functions.L2_reg, gamma=gamma)
    ef.add_sector_constraints(
        sector_mapper={t: a["asset_class"] for t, a in ASSET_BY_TICKER.items()},
        sector_lower=_feasible_sector_lower(mu),
        sector_upper=settings.sector_upper,
    )
    return ef


def solve_portfolio(risk_profile: RiskProfile, mu: pd.Series, cov: pd.DataFrame) -> WeightsAndPerformance:
    max_weight = settings.max_weight_by_profile[risk_profile.value]
    gamma = settings.l2_gamma_by_profile[risk_profile.value]
    target_volatility = settings.target_volatility_by_profile[risk_profile.value]

    try:
        try:
            ef = _new_frontier(mu, cov, max_weight, gamma)
            ef.efficient_risk(target_volatility=target_volatility)
        except Exception as exc:  # noqa: BLE001 - target infeasible (below the achievable minimum); fall back
            logger.warning(
                "efficient_risk(target_volatility=%.4f) infeasible for '%s': %s; falling back to min_volatility()",
                target_volatility,
                risk_profile.value,
                exc,
            )
            ef = _new_frontier(mu, cov, max_weight, gamma)
            ef.min_volatility()

        weights = ef.clean_weights()
        performance = ef.portfolio_performance(risk_free_rate=settings.risk_free_rate)
        achieved_volatility = performance[1]

        if abs(achieved_volatility - target_volatility) > 1e-4:
            logger.info(
                "Risk profile '%s': target_volatility=%.4f achieved_volatility=%.4f",
                risk_profile.value,
                target_volatility,
                achieved_volatility,
            )

        return weights, performance
    except Exception as exc:  # noqa: BLE001 - wrap into our own error type
        raise OptimizationError(f"Optimization failed for risk profile '{risk_profile.value}': {exc}") from exc
