import pandas as pd

from app.gates import MAX_ABS_MEAN_PREMIUM, apply_gates


def test_gates_exclude_ticker_with_short_history():
    as_of = pd.Timestamp("2026-01-01")
    tickers = ["OLD_TICKER", "NEW_TICKER"]

    nav_start_dates = {
        "OLD_TICKER": as_of - pd.DateOffset(years=5),
        "NEW_TICKER": as_of - pd.DateOffset(years=1),  # < 3y history
    }

    # Negligible, well within the premium band, so only the history gate is exercised.
    dates = pd.bdate_range(end=as_of, periods=40)
    premium = pd.DataFrame(0.0, index=dates, columns=tickers)
    assert (premium.abs() <= MAX_ABS_MEAN_PREMIUM).all().all()

    surviving, excluded = apply_gates(nav_start_dates, premium, as_of=as_of)

    assert surviving == ["OLD_TICKER"]

    excluded_by_ticker = {e["ticker"]: e["reason"] for e in excluded}
    assert "NEW_TICKER" in excluded_by_ticker
    assert "history" in excluded_by_ticker["NEW_TICKER"].lower()
    assert "OLD_TICKER" not in excluded_by_ticker
