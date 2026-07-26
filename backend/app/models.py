from enum import Enum

from pydantic import BaseModel, Field


class RiskProfile(str, Enum):
    conservative = "conservative"
    moderate = "moderate"
    aggressive = "aggressive"


class PortfolioRequest(BaseModel):
    amount: float = Field(gt=0, le=1_000_000_000)
    risk_profile: RiskProfile


class Allocation(BaseModel):
    ticker: str
    name: str
    asset_class: str
    weight: float
    amount: float


class PortfolioStats(BaseModel):
    expected_annual_return: float
    annual_volatility: float
    sharpe_ratio: float


class PortfolioMeta(BaseModel):
    data_as_of: str
    lookback_years: int
    risk_free_rate: float
    cache_age_seconds: float
    disclaimer: str = (
        "Educational tool based on historical market data; not financial advice."
    )


class PortfolioResponse(BaseModel):
    risk_profile: RiskProfile
    amount: float
    allocations: list[Allocation]
    portfolio_stats: PortfolioStats
    meta: PortfolioMeta


class ErrorResponse(BaseModel):
    error: str
    message: str
