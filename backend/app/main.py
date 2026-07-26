import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.data import market_data_cache
from app.errors import DataFetchError, OptimizationError
from app.models import (
    Allocation,
    PortfolioMeta,
    PortfolioRequest,
    PortfolioResponse,
    PortfolioStats,
)
from app.optimizer import solve_portfolio
from app.universe import ASSET_BY_TICKER

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
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


@app.post("/api/portfolio", response_model=PortfolioResponse)
async def compute_portfolio(req: PortfolioRequest):
    prices, mu, cov = market_data_cache.get()
    weights, (expected_return, volatility, sharpe) = solve_portfolio(req.risk_profile, mu, cov)

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
        ),
    )
