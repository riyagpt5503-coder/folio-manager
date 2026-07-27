from datetime import date
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


class ExcludedTicker(BaseModel):
    ticker: str
    reason: str


class PortfolioMeta(BaseModel):
    data_as_of: str
    data_from: str
    lookback_years: int
    effective_years: float
    risk_free_rate: float
    cache_age_seconds: float
    failed_tickers: list[str]
    excluded: list[ExcludedTicker]
    disclaimer: str = (
        "Educational tool based on historical market data; not financial advice."
    )


class PortfolioResponse(BaseModel):
    risk_profile: RiskProfile
    amount: float
    allocations: list[Allocation]
    portfolio_stats: PortfolioStats
    meta: PortfolioMeta


class TickerMetrics(BaseModel):
    rolling_3y_return_median: float | None
    rolling_3y_return_p10: float | None
    rolling_3y_window_count: int
    annualized_vol: float
    max_drawdown: float
    sortino_ratio: float


class MetricsResponse(BaseModel):
    as_of: str
    cache_age_seconds: float
    metrics: dict[str, TickerMetrics]


class PositionCreate(BaseModel):
    symbol: str
    qty: float = Field(gt=0)
    buy_date: date
    buy_price: float = Field(gt=0)


class Position(BaseModel):
    lot_id: int
    symbol: str
    qty: float
    buy_date: date
    buy_price: float


class CurrentWeight(BaseModel):
    ticker: str
    asset_class: str
    qty: float
    latest_nav: float
    value: float
    weight: float


class TargetWeight(BaseModel):
    ticker: str
    asset_class: str
    weight: float


class AssetClassDrift(BaseModel):
    asset_class: str
    current_weight: float
    target_weight: float
    absolute_drift: float
    relative_drift: float | None
    breaching: bool


class SoldLot(BaseModel):
    lot_id: int
    qty: float
    buy_date: date
    holding_period_days: int
    term: str


class ProposedOrder(BaseModel):
    ticker: str
    asset_class: str
    side: str
    qty: float
    estimated_value: float
    lots: list[SoldLot] = []


class RebalanceResponse(BaseModel):
    risk_profile: RiskProfile
    as_of: str
    total_portfolio_value: float
    drift_threshold: float
    current_weights: list[CurrentWeight]
    target_weights: list[TargetWeight]
    drift: list[AssetClassDrift]
    proposed_orders: list[ProposedOrder]


class BindingConstraint(BaseModel):
    constraint: str
    scope: str
    bound: float
    value: float


class RiskContribution(BaseModel):
    ticker: str
    weight: float
    percent_contribution: float


class RiskResponse(BaseModel):
    as_of: str
    risk_profile: RiskProfile
    correlation_matrix: dict[str, dict[str, float]]
    risk_contributions: list[RiskContribution]
    portfolio_max_drawdown: float
    binding_constraints: list[BindingConstraint]


class ErrorResponse(BaseModel):
    error: str
    message: str
