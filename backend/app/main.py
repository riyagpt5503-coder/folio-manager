import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import db, gates, risk
from app.config import settings
from app.data import market_data_cache
from app.errors import DataFetchError, OptimizationError
from app.models import (
    Allocation,
    BindingConstraint,
    ExcludedTicker,
    MetricsResponse,
    PortfolioMeta,
    PortfolioRequest,
    PortfolioResponse,
    PortfolioStats,
    Position,
    PositionCreate,
    RebalanceResponse,
    RiskContribution,
    RiskProfile,
    RiskResponse,
    TickerMetrics,
)
from app.optimizer import solve_portfolio
from app.rebalance import compute_rebalance
from app.universe import ASSET_BY_TICKER

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    try:
        market_data_cache.get()
        logger.info("Startup warm-up fetch succeeded")
    except DataFetchError as exc:
        logger.warning("Startup warm-up fetch failed, will retry on first request: %s", exc)
    yield


app = FastAPI(title="Portfolio Manager API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DataFetchError)
async def data_fetch_error_handler(request: Request, exc: DataFetchError):
    return JSONResponse(status_code=502, content={"error": "data_fetch_failed", "message": str(exc)})


@app.exception_handler(OptimizationError)
async def optimization_error_handler(request: Request, exc: OptimizationError):
    return JSONResponse(status_code=500, content={"error": "optimization_failed", "message": str(exc)})


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "cache_warm": market_data_cache.is_warm,
        "cache_age_seconds": (
            round(market_data_cache.cache_age_seconds, 1) if market_data_cache.is_warm else None
        ),
    }


@app.get("/api/metrics", response_model=MetricsResponse)
async def get_metrics():
    prices, _, _ = market_data_cache.get()
    return MetricsResponse(
        as_of=prices.index[-1].strftime("%Y-%m-%d"),
        cache_age_seconds=round(market_data_cache.cache_age_seconds, 1),
        metrics={ticker: TickerMetrics(**m) for ticker, m in market_data_cache.metrics.items()},
    )


@app.post("/api/positions", response_model=Position, status_code=201)
async def create_position(position: PositionCreate):
    row = db.create_position(position.symbol, position.qty, position.buy_date.isoformat(), position.buy_price)
    return Position(**dict(row))


@app.get("/api/positions", response_model=list[Position])
async def list_positions():
    return [Position(**dict(row)) for row in db.list_positions()]


@app.delete("/api/positions/{lot_id}", status_code=204)
async def delete_position(lot_id: int):
    if not db.delete_position(lot_id):
        raise HTTPException(status_code=404, detail=f"Position {lot_id} not found")


@app.get("/api/risk", response_model=RiskResponse)
async def get_risk():
    prices, _, cov = market_data_cache.get()
    solve = risk.ensure_last_solve()

    corr = risk.correlation_matrix(cov).round(6)
    contributions = risk.risk_contributions(solve.weights, cov)
    max_dd = risk.portfolio_max_drawdown(solve.weights, prices)

    return RiskResponse(
        as_of=prices.index[-1].strftime("%Y-%m-%d"),
        risk_profile=solve.risk_profile,
        correlation_matrix=corr.to_dict(),
        risk_contributions=[
            RiskContribution(ticker=t, weight=round(solve.weights[t], 6), percent_contribution=round(pct, 6))
            for t, pct in sorted(contributions.items(), key=lambda kv: -kv[1])
        ],
        portfolio_max_drawdown=round(max_dd, 6),
        binding_constraints=[BindingConstraint(**b) for b in solve.binding_constraints],
    )


@app.get("/api/rebalance", response_model=RebalanceResponse)
async def get_rebalance(risk_profile: RiskProfile):
    return RebalanceResponse(**compute_rebalance(risk_profile))


@app.post("/api/portfolio", response_model=PortfolioResponse)
async def compute_portfolio(req: PortfolioRequest):
    prices, mu_by_profile, cov = market_data_cache.get()
    mu = mu_by_profile[req.risk_profile.value]

    surviving_tickers, excluded = gates.apply_gates(
        market_data_cache.nav_start_dates,
        market_data_cache.premium,
        as_of=prices.index[-1],
    )
    mu = mu.loc[surviving_tickers]
    cov = cov.loc[surviving_tickers, surviving_tickers]

    weights, (expected_return, volatility, sharpe), binding_constraints = solve_portfolio(req.risk_profile, mu, cov)
    risk.last_solve.record(req.risk_profile, weights, binding_constraints)

    target_volatility = settings.target_volatility_by_profile[req.risk_profile.value]
    achieved_volatility = volatility

    cash_weight = settings.cash_weight
    asset_weight = 1 - cash_weight
    weights = {ticker: weight * asset_weight for ticker, weight in weights.items()}
    expected_return = expected_return * asset_weight + cash_weight * settings.cash_return
    volatility = volatility * asset_weight
    sharpe = (expected_return - settings.risk_free_rate) / volatility if volatility else 0.0

    allocations = []
    for ticker, weight in sorted(weights.items(), key=lambda kv: kv[1], reverse=True):
        if weight <= 0:
            continue
        asset = ASSET_BY_TICKER[ticker]
        allocations.append(
            Allocation(
                ticker=ticker,
                name=asset["name"],
                asset_class=asset["asset_class"],
                weight=round(weight, 6),
                amount=round(weight * req.amount, 2),
            )
        )

    if cash_weight > 0:
        allocations.append(
            Allocation(
                ticker="CASH",
                name="Cash",
                asset_class="Cash / Money Market",
                weight=round(cash_weight, 6),
                amount=round(cash_weight * req.amount, 2),
            )
        )

    data_as_of = prices.index[-1]
    data_as_of_str = data_as_of.strftime("%Y-%m-%d") if hasattr(data_as_of, "strftime") else str(data_as_of)
    data_from = prices.index[0]
    data_from_str = data_from.strftime("%Y-%m-%d") if hasattr(data_from, "strftime") else str(data_from)
    effective_years = (data_as_of - data_from).days / 365.25

    return PortfolioResponse(
        risk_profile=req.risk_profile,
        amount=req.amount,
        allocations=allocations,
        portfolio_stats=PortfolioStats(
            expected_annual_return=round(expected_return, 6),
            annual_volatility=round(volatility, 6),
            sharpe_ratio=round(sharpe, 6),
        ),
        meta=PortfolioMeta(
            data_as_of=data_as_of_str,
            data_from=data_from_str,
            lookback_years=settings.lookback_years,
            effective_years=round(effective_years, 2),
            risk_free_rate=settings.risk_free_rate,
            cache_age_seconds=round(market_data_cache.cache_age_seconds, 1),
            failed_tickers=market_data_cache.failed_tickers,
            excluded=[ExcludedTicker(**e) for e in excluded],
            target_volatility=round(target_volatility, 6),
            achieved_volatility=round(achieved_volatility, 6),
        ),
    )
