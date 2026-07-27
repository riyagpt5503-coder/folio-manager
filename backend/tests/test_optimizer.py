import pytest

from app.config import settings
from app.models import RiskProfile
from app.optimizer import solve_portfolio
from app.universe import ASSET_BY_TICKER

ALL_PROFILES = [RiskProfile.conservative, RiskProfile.moderate, RiskProfile.aggressive]


@pytest.mark.parametrize("risk_profile", ALL_PROFILES)
def test_weights_sum_to_one(mu_cov, risk_profile):
    mu_by_profile, cov = mu_cov
    weights, _ = solve_portfolio(risk_profile, mu_by_profile[risk_profile.value], cov)
    # clean_weights() rounds each weight to 5 decimals, so up to ~n*0.5e-5 of
    # cumulative rounding error is expected and not a solver defect.
    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-4)


@pytest.mark.parametrize("risk_profile", ALL_PROFILES)
def test_no_weight_exceeds_max_weight(mu_cov, risk_profile):
    mu_by_profile, cov = mu_cov
    weights, _ = solve_portfolio(risk_profile, mu_by_profile[risk_profile.value], cov)
    max_weight = settings.max_weight_by_profile[risk_profile.value]
    for ticker, weight in weights.items():
        assert weight <= max_weight + 1e-6, f"{ticker} weight {weight} exceeds max_weight"


@pytest.mark.parametrize("risk_profile", ALL_PROFILES)
def test_sector_upper_bounds_respected(mu_cov, risk_profile):
    mu_by_profile, cov = mu_cov
    weights, _ = solve_portfolio(risk_profile, mu_by_profile[risk_profile.value], cov)

    sector_totals: dict[str, float] = {}
    for ticker, weight in weights.items():
        sector = ASSET_BY_TICKER[ticker]["asset_class"]
        sector_totals[sector] = sector_totals.get(sector, 0.0) + weight

    for sector, upper_bound in settings.sector_upper.items():
        assert sector_totals.get(sector, 0.0) <= upper_bound + 1e-6


@pytest.mark.parametrize("risk_profile", ALL_PROFILES)
def test_solves_when_only_large_cap_ticker_is_gated_out(mu_cov, risk_profile):
    # NIFTYBEES.NS is the sole "Indian Large-Cap Equity" ticker. Before the
    # feasibility guard, sector_lower for that class would still require 20%
    # (now 15%) of a sector with zero available tickers - infeasible.
    mu_by_profile, cov = mu_cov
    mu = mu_by_profile[risk_profile.value]
    tickers = [t for t in mu.index if t != "NIFTYBEES.NS"]
    mu = mu.loc[tickers]
    cov = cov.loc[tickers, tickers]

    weights, _ = solve_portfolio(risk_profile, mu, cov)

    assert "NIFTYBEES.NS" not in weights
    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-4)
