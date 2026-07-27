from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    risk_free_rate: float = 0.065  # approx. short-term Indian G-Sec / T-bill yield
    cache_ttl_minutes: int = 60
    lookback_years: int = 5
    max_weight: float = 0.20
    cash_weight: float = 0.0
    cash_return: float = 0.065
    sector_lower: dict[str, float] = {"Indian Large-Cap Equity": 0.20}
    sector_upper: dict[str, float] = {
        "Gold": 0.15,
        "Silver": 0.05,
        "International Equity (US Tech)": 0.15,
    }
    return_model: Literal["implied", "historical"] = "implied"
    # Strategic policy allocation by asset_class, used as w_policy for implied
    # (reverse-optimized) equilibrium returns. Must sum to 1.0.
    policy_weights: dict[str, float] = {
        "Indian Large-Cap Equity": 0.30,
        "Indian Mid-Cap Equity": 0.10,
        "Indian Financials": 0.10,
        "Indian IT Sector": 0.10,
        "International Equity (US Tech)": 0.10,
        "Indian Government Bonds": 0.15,
        "Gold": 0.10,
        "Silver": 0.05,
    }
    cors_origins: list[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"


settings = Settings()
