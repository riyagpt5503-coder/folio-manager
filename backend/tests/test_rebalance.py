from datetime import date

from app.rebalance import compute_drift_and_orders


def test_drift_calc_no_orders_when_current_equals_target():
    weights = {
        "NIFTYBEES.NS": 0.20,
        "GOLDBEES.NS": 0.15,
        "SILVERBEES.NS": 0.05,
    }
    total_value = 100_000.0
    value_by_ticker = {t: w * total_value for t, w in weights.items()}
    latest_nav = {t: 100.0 for t in weights}

    drift, orders = compute_drift_and_orders(
        current_weight_by_ticker=weights,
        target_by_ticker=weights,
        value_by_ticker=value_by_ticker,
        total_value=total_value,
        latest_nav=latest_nav,
        positions=[],
        as_of=date(2026, 1, 1),
    )

    assert orders == []
    assert len(drift) == 3
    for record in drift:
        assert record["breaching"] is False
        assert record["absolute_drift"] == 0.0
        assert record["relative_drift"] == 0.0
