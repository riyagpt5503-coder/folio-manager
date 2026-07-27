import pytest

from app.config import settings
from app.models import RiskProfile
from app.optimizer import solve_portfolio
from app.universe import ASSET_BY_TICKER

ALL_PROFILES = [RiskProfile.conservative, RiskProfile.moderate, RiskProfile.aggressive]


@pytest.mark.parametrize("risk_profile", ALL_PROFILES)
def test_weights_sum_to_one(mu_cov, risk_profile):
    mu, cov = mu_cov
    weights, _ = solve_portfolio(risk_profile, mu, cov)
    # clean_weights() rounds each weight to 5 decimals, so up to ~n*0.5e-5 of
    # cumulative rounding error is expected and not a solver defect.
    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-4)


@pytest.mark.parametrize("risk_profile", ALL_PROFILES)
def test_no_weight_exceeds_max_weight(mu_cov, risk_profile):
    mu, cov = mu_cov
    weights, _ = solve_portfolio(risk_profile, mu, cov)
    for ticker, weight in weights.items():
        assert weight <= settings.max_weight + 1e-6, f"{ticker} weight {weight} exceeds max_weight"


@pytest.mark.parametrize("risk_profile", ALL_PROFILES)
def test_sector_upper_bounds_respected(mu_cov, risk_profile):
    mu, cov = mu_cov
    weights, _ = solve_portfolio(risk_profile, mu, cov)

    sector_totals: dict[str, float] = {}
    for ticker, weight in weights.items():
        sector = ASSET_BY_TICKER[ticker]["asset_class"]
        sector_totals[sector] = sector_totals.get(sector, 0.0) + weight

    for sector, upper_bound in settings.sector_upper.items():
        assert sector_totals.get(sector, 0.0) <= upper_bound + 1e-6
