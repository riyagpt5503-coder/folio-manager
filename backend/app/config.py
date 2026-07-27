from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    risk_free_rate: float = 0.065  # approx. short-term Indian G-Sec / T-bill yield
    cache_ttl_minutes: int = 60
    lookback_years: int = 5
    cash_weight: float = 0.0
    cash_return: float = 0.065
    return_model: Literal["implied", "historical"] = "implied"

    # Per-profile constraint sets: tighter bounds + heavier L2 (diversification)
    # pressure for conservative, looser bounds + lighter L2 for aggressive.
    # Each profile has a "default" per-ticker (min, max) bound plus overrides
    # for specific tickers (e.g. conservative lets GILT5YBEES.NS go well above
    # its default cap, since a 30%+ bonds policy can't fit under a flat 15%
    # per-ticker ceiling).
    weight_bounds_by_profile: dict[str, dict[str, tuple[float, float]]] = {
        "conservative": {
            "default": (0.0, 0.15),
            "GILT5YBEES.NS": (0.0, 0.50),
        },
        "moderate": {
            "default": (0.0, 0.25),
            "GILT5YBEES.NS": (0.0, 0.35),
        },
        "aggressive": {
            "default": (0.0, 0.35),
            "GILT5YBEES.NS": (0.0, 0.10),
        },
    }
    sector_lower_by_profile: dict[str, dict[str, float]] = {
        "conservative": {"Indian Government Bonds": 0.30},
        "moderate": {"Indian Large-Cap Equity": 0.15},
        "aggressive": {"Gold": 0.05, "Indian Government Bonds": 0.02},
    }
    sector_upper_by_profile: dict[str, dict[str, float]] = {
        "conservative": {"Gold": 0.10, "Silver": 0.05, "International Equity (US Tech)": 0.10},
        "moderate": {"Gold": 0.15, "Silver": 0.05, "International Equity (US Tech)": 0.15},
        "aggressive": {
            "Silver": 0.05,
            "International Equity (US Tech)": 0.20,
            "Indian IT Sector": 0.20,
            "Indian Financials": 0.20,
            "Indian Mid-Cap Equity": 0.25,
        },
    }
    l2_gamma_by_profile: dict[str, float] = {
        "conservative": 0.5,
        "moderate": 0.3,
        "aggressive": 0.03,
    }
    # Absolute annualized-vol target passed to efficient_risk() per profile.
    target_volatility_by_profile: dict[str, float] = {
        "conservative": 0.07,
        "moderate": 0.11,
        "aggressive": 0.16,
    }
    # Any nonzero weight below this is dropped and the universe re-solved
    # (see optimizer.solve_portfolio) rather than left as a dust position.
    min_position_size: float = 0.02

    # Per-profile strategic policy allocation by asset_class, used as w_policy
    # for implied (reverse-optimized) equilibrium returns. Each sums to 1.0.
    policy_weights_by_profile: dict[str, dict[str, float]] = {
        "conservative": {
            "Indian Large-Cap Equity": 0.25,
            "Indian Mid-Cap Equity": 0.05,
            "Indian Financials": 0.08,
            "Indian IT Sector": 0.05,
            "International Equity (US Tech)": 0.05,
            "Indian Government Bonds": 0.35,
            "Gold": 0.12,
            "Silver": 0.05,
        },
        "moderate": {
            "Indian Large-Cap Equity": 0.30,
            "Indian Mid-Cap Equity": 0.10,
            "Indian Financials": 0.10,
            "Indian IT Sector": 0.10,
            "International Equity (US Tech)": 0.10,
            "Indian Government Bonds": 0.15,
            "Gold": 0.10,
            "Silver": 0.05,
        },
        "aggressive": {
            "Indian Large-Cap Equity": 0.25,
            "Indian Mid-Cap Equity": 0.20,
            "Indian Financials": 0.15,
            "Indian IT Sector": 0.15,
            "International Equity (US Tech)": 0.15,
            "Indian Government Bonds": 0.02,
            "Gold": 0.05,
            "Silver": 0.03,
        },
    }
    cors_origins: list[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"


settings = Settings()
