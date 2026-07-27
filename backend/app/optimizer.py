import logging

import pandas as pd
from pypfopt import EfficientFrontier, objective_functions

from app.config import settings
from app.errors import OptimizationError
from app.models import RiskProfile
from app.universe import ASSET_BY_TICKER

logger = logging.getLogger(__name__)

_WEIGHT_TOLERANCE = 1e-4
_MIN_POSITION_MAX_RETRIES = 2

# (weights, (return, vol, sharpe), binding_constraints)
SolveResult = tuple[dict[str, float], tuple[float, float, float], list[dict]]


def _feasible_sector_lower(mu: pd.Series, sector_lower: dict[str, float]) -> dict[str, float]:
    """Drop sector_lower entries for asset classes with no surviving tickers
    in mu's index - otherwise the lower bound is infeasible (there's nothing
    left to allocate to satisfy it)."""
    surviving_classes = {ASSET_BY_TICKER[t]["asset_class"] for t in mu.index if t in ASSET_BY_TICKER}
    feasible: dict[str, float] = {}
    for asset_class, lower in sector_lower.items():
        if asset_class in surviving_classes:
            feasible[asset_class] = lower
        else:
            logger.warning(
                "Dropping sector_lower constraint for asset_class '%s' (%.4f): no surviving tickers after gates",
                asset_class,
                lower,
            )
    return feasible


def _new_frontier(
    mu: pd.Series,
    cov: pd.DataFrame,
    weight_bounds: list[tuple[float, float]],
    gamma: float,
    sector_lower: dict[str, float],
    sector_upper: dict[str, float],
) -> EfficientFrontier:
    ef = EfficientFrontier(mu, cov, weight_bounds=weight_bounds)
    ef.add_objective(objective_functions.L2_reg, gamma=gamma)
    ef.add_sector_constraints(
        sector_mapper={t: a["asset_class"] for t, a in ASSET_BY_TICKER.items()},
        sector_lower=_feasible_sector_lower(mu, sector_lower),
        sector_upper=sector_upper,
    )
    return ef


def _detect_binding_constraints(
    weights: dict[str, float],
    bounds_config: dict[str, tuple[float, float]],
    sector_lower: dict[str, float],
    sector_upper: dict[str, float],
) -> list[dict]:
    """Compares the solved weights against the configured bounds directly
    (tolerance-based boundary check) rather than reading solver dual
    variables, which pypfopt/cvxpy don't reliably expose across solvers."""
    default_bounds = bounds_config["default"]
    binding: list[dict] = []

    for ticker, weight in weights.items():
        lower, upper = bounds_config.get(ticker, default_bounds)
        if weight <= lower + _WEIGHT_TOLERANCE:
            binding.append({"constraint": "weight_lower_bound", "scope": ticker, "bound": lower, "value": round(weight, 6)})
        elif weight >= upper - _WEIGHT_TOLERANCE:
            binding.append({"constraint": "max_weight", "scope": ticker, "bound": upper, "value": round(weight, 6)})

    sector_totals: dict[str, float] = {}
    for ticker, weight in weights.items():
        sector = ASSET_BY_TICKER.get(ticker, {}).get("asset_class")
        if sector:
            sector_totals[sector] = sector_totals.get(sector, 0.0) + weight

    for sector, lower in sector_lower.items():
        total = sector_totals.get(sector, 0.0)
        if total <= lower + _WEIGHT_TOLERANCE:
            binding.append({"constraint": "sector_lower", "scope": sector, "bound": lower, "value": round(total, 6)})

    for sector, upper in sector_upper.items():
        total = sector_totals.get(sector, 0.0)
        if total >= upper - _WEIGHT_TOLERANCE:
            binding.append({"constraint": "sector_upper", "scope": sector, "bound": upper, "value": round(total, 6)})

    return binding


def _solve_once(
    mu: pd.Series,
    cov: pd.DataFrame,
    bounds_config: dict[str, tuple[float, float]],
    gamma: float,
    sector_lower: dict[str, float],
    sector_upper: dict[str, float],
    target_volatility: float,
) -> tuple[dict[str, float], tuple[float, float, float]]:
    default_bounds = bounds_config["default"]
    weight_bounds = [bounds_config.get(ticker, default_bounds) for ticker in mu.index]
    ef = _new_frontier(mu, cov, weight_bounds, gamma, sector_lower, sector_upper)
    ef.efficient_risk(target_volatility=target_volatility)
    weights = ef.clean_weights()
    performance = ef.portfolio_performance(risk_free_rate=settings.risk_free_rate)
    return weights, performance


def solve_portfolio(risk_profile: RiskProfile, mu: pd.Series, cov: pd.DataFrame) -> SolveResult:
    bounds_config = settings.weight_bounds_by_profile[risk_profile.value]
    gamma = settings.l2_gamma_by_profile[risk_profile.value]
    target_volatility = settings.target_volatility_by_profile[risk_profile.value]
    sector_lower = settings.sector_lower_by_profile[risk_profile.value]
    sector_upper = settings.sector_upper_by_profile[risk_profile.value]

    try:
        # No fallback here on purpose: a silent fallback to min_volatility()
        # previously masked a real misconfiguration (conservative's bond-heavy
        # policy didn't fit under its old flat max_weight), so an infeasible
        # target now surfaces as a genuine OptimizationError instead.
        for attempt in range(_MIN_POSITION_MAX_RETRIES + 1):
            weights, performance = _solve_once(mu, cov, bounds_config, gamma, sector_lower, sector_upper, target_volatility)

            undersized = [t for t, w in weights.items() if 0 < w < settings.min_position_size]
            if not undersized or attempt == _MIN_POSITION_MAX_RETRIES:
                break

            # Drop and re-solve on the reduced universe rather than
            # zero-and-renormalize, which would silently violate the sector
            # and per-ticker bounds the remaining weights were solved under.
            logger.info(
                "Risk profile '%s': dropping undersized position(s) %s (< %.4f) and re-solving (attempt %d/%d)",
                risk_profile.value,
                undersized,
                settings.min_position_size,
                attempt + 1,
                _MIN_POSITION_MAX_RETRIES,
            )
            remaining = [t for t in mu.index if t not in undersized]
            mu = mu.loc[remaining]
            cov = cov.loc[remaining, remaining]

        achieved_volatility = performance[1]

        if abs(achieved_volatility - target_volatility) > 1e-4:
            logger.info(
                "Risk profile '%s': target_volatility=%.4f achieved_volatility=%.4f",
                risk_profile.value,
                target_volatility,
                achieved_volatility,
            )

        binding_constraints = _detect_binding_constraints(weights, bounds_config, sector_lower, sector_upper)
        if binding_constraints:
            logger.info(
                "Risk profile '%s': binding constraints: %s",
                risk_profile.value,
                "; ".join(
                    f"{b['constraint']}[{b['scope']}]={b['value']:.4f} (bound {b['bound']:.4f})"
                    for b in binding_constraints
                ),
            )

        return weights, performance, binding_constraints
    except Exception as exc:  # noqa: BLE001 - wrap into our own error type
        raise OptimizationError(f"Optimization failed for risk profile '{risk_profile.value}': {exc}") from exc
