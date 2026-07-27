import logging
from datetime import date

import pandas as pd

from app import db, gates
from app.config import settings
from app.data import market_data_cache
from app.models import RiskProfile
from app.optimizer import solve_portfolio
from app.universe import ASSET_BY_TICKER

logger = logging.getLogger(__name__)

# Standard "5/25 rule" style relative-drift band used by institutional rebalancing.
DRIFT_BREACH_THRESHOLD = 0.25

# Simplified 12-month equity-style threshold for the short/long-term flag.
# This is informational only, not authoritative tax classification - actual
# LTCG/STCG rules differ by asset type (equity/debt/gold) and have changed
# across recent Finance Acts. No tax amounts are computed anywhere here.
LONG_TERM_HOLDING_DAYS = 365


def _latest_nav_by_ticker() -> tuple[dict[str, float], pd.Timestamp]:
    raw = market_data_cache.nav_prices_raw
    latest: dict[str, float] = {}
    for ticker in raw.columns:
        series = raw[ticker].dropna()
        if not series.empty:
            latest[ticker] = float(series.iloc[-1])
    return latest, raw.index[-1]


def _target_weights(risk_profile: RiskProfile, prices: pd.DataFrame, mu: pd.Series, cov: pd.DataFrame) -> dict[str, float]:
    surviving, _ = gates.apply_gates(
        market_data_cache.nav_start_dates, market_data_cache.premium, as_of=prices.index[-1]
    )
    mu = mu.loc[surviving]
    cov = cov.loc[surviving, surviving]
    weights, _ = solve_portfolio(risk_profile, mu, cov)

    asset_weight = 1 - settings.cash_weight
    return {ticker: w * asset_weight for ticker, w in weights.items()}


def _select_lots_fifo(positions: list, ticker: str, qty_needed: float, as_of: date) -> list[dict]:
    """Oldest-lot-first selection for a sell order. Reports holding period and
    a simplified ST/LT flag per lot - no tax amounts are computed."""
    lots = sorted((row for row in positions if row["symbol"] == ticker), key=lambda row: row["buy_date"])
    selected: list[dict] = []
    remaining = qty_needed
    for row in lots:
        if remaining <= 1e-9:
            break
        take = min(row["qty"], remaining)
        buy_date = date.fromisoformat(row["buy_date"])
        holding_days = (as_of - buy_date).days
        selected.append(
            {
                "lot_id": row["lot_id"],
                "qty": round(take, 6),
                "buy_date": buy_date,
                "holding_period_days": holding_days,
                "term": "long_term" if holding_days > LONG_TERM_HOLDING_DAYS else "short_term",
            }
        )
        remaining -= take
    return selected


def compute_drift_and_orders(
    current_weight_by_ticker: dict[str, float],
    target_by_ticker: dict[str, float],
    value_by_ticker: dict[str, float],
    total_value: float,
    latest_nav: dict[str, float],
    positions: list,
    as_of: date,
) -> tuple[list[dict], list[dict]]:
    """Pure drift/order computation: aggregates current vs target weights per
    asset_class, flags sleeves breaching DRIFT_BREACH_THRESHOLD, and proposes
    buy/sell orders only for tickers in a breaching sleeve. Returns
    (drift_records, proposed_orders)."""
    all_tickers = sorted(set(current_weight_by_ticker) | set(target_by_ticker))

    asset_classes = sorted({ASSET_BY_TICKER[t]["asset_class"] for t in all_tickers if t in ASSET_BY_TICKER})
    drift_out = []
    breaching_classes: set[str] = set()
    for ac in asset_classes:
        class_tickers = [t for t in all_tickers if ASSET_BY_TICKER.get(t, {}).get("asset_class") == ac]
        current_c = sum(current_weight_by_ticker.get(t, 0.0) for t in class_tickers)
        target_c = sum(target_by_ticker.get(t, 0.0) for t in class_tickers)
        abs_drift = current_c - target_c

        if target_c > 0:
            rel_drift = abs_drift / target_c
            breaching = abs(rel_drift) > DRIFT_BREACH_THRESHOLD
        elif current_c > 0:
            rel_drift = None  # held, but optimizer targets zero - always a breach
            breaching = True
        else:
            rel_drift = 0.0
            breaching = False

        if breaching:
            breaching_classes.add(ac)

        drift_out.append(
            {
                "asset_class": ac,
                "current_weight": round(current_c, 6),
                "target_weight": round(target_c, 6),
                "absolute_drift": round(abs_drift, 6),
                "relative_drift": round(rel_drift, 6) if rel_drift is not None else None,
                "breaching": breaching,
            }
        )

    orders = []
    if total_value > 0:
        for t in all_tickers:
            ac = ASSET_BY_TICKER.get(t, {}).get("asset_class")
            if ac not in breaching_classes:
                continue
            delta = target_by_ticker.get(t, 0.0) - current_weight_by_ticker.get(t, 0.0)
            if abs(delta) < 1e-6:
                continue

            nav = latest_nav.get(t)
            if nav is None:
                continue  # can't size an order for a ticker with no NAV

            if delta < 0:
                sell_value = min(-delta * total_value, value_by_ticker.get(t, 0.0))
                qty = sell_value / nav
                orders.append(
                    {
                        "ticker": t,
                        "asset_class": ac,
                        "side": "sell",
                        "qty": round(qty, 6),
                        "estimated_value": round(sell_value, 2),
                        "lots": _select_lots_fifo(positions, t, qty, as_of),
                    }
                )
            else:
                buy_value = delta * total_value
                qty = buy_value / nav
                orders.append(
                    {
                        "ticker": t,
                        "asset_class": ac,
                        "side": "buy",
                        "qty": round(qty, 6),
                        "estimated_value": round(buy_value, 2),
                        "lots": [],
                    }
                )

    return drift_out, orders


def compute_rebalance(risk_profile: RiskProfile) -> dict:
    prices, mu, cov = market_data_cache.get()  # ensures the cache (incl. nav_prices_raw) is warm

    positions = db.list_positions()
    latest_nav, as_of_ts = _latest_nav_by_ticker()
    as_of = as_of_ts.date()

    qty_by_ticker: dict[str, float] = {}
    for row in positions:
        symbol = row["symbol"]
        if symbol not in latest_nav:
            logger.warning("Skipping lot %s: no NAV available for %s", row["lot_id"], symbol)
            continue
        qty_by_ticker[symbol] = qty_by_ticker.get(symbol, 0.0) + row["qty"]

    value_by_ticker = {t: qty * latest_nav[t] for t, qty in qty_by_ticker.items()}
    total_value = sum(value_by_ticker.values())

    target_by_ticker = _target_weights(risk_profile, prices, mu, cov)

    all_tickers = sorted(set(value_by_ticker) | set(target_by_ticker))
    current_weight_by_ticker = {
        t: (value_by_ticker.get(t, 0.0) / total_value if total_value else 0.0) for t in all_tickers
    }

    current_weights_out = [
        {
            "ticker": t,
            "asset_class": ASSET_BY_TICKER.get(t, {}).get("asset_class", "Unknown"),
            "qty": round(qty_by_ticker[t], 6),
            "latest_nav": latest_nav[t],
            "value": round(value_by_ticker[t], 2),
            "weight": round(current_weight_by_ticker[t], 6),
        }
        for t in value_by_ticker
    ]

    target_weights_out = [
        {
            "ticker": t,
            "asset_class": ASSET_BY_TICKER.get(t, {}).get("asset_class", "Unknown"),
            "weight": round(w, 6),
        }
        for t, w in target_by_ticker.items()
    ]

    drift_out, orders = compute_drift_and_orders(
        current_weight_by_ticker, target_by_ticker, value_by_ticker, total_value, latest_nav, positions, as_of
    )

    return {
        "risk_profile": risk_profile,
        "as_of": as_of.isoformat(),
        "total_portfolio_value": round(total_value, 2),
        "drift_threshold": DRIFT_BREACH_THRESHOLD,
        "current_weights": current_weights_out,
        "target_weights": target_weights_out,
        "drift": drift_out,
        "proposed_orders": orders,
    }
