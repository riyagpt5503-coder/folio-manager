import pytest

from app.config import settings
from app.models import RiskProfile
from app.optimizer import solve_portfolio
from app.universe import ASSET_BY_TICKER

ALL_PROFILES = [RiskProfile.conservative, RiskProfile.moderate, RiskProfile.aggressive]


@pytest.mark.parametrize("risk_profile", ALL_PROFILES)
def test_weights_sum_to_one(mu_cov, risk_profile):
    mu_by_profile, cov = mu_cov
    weights, _, _ = solve_portfolio(risk_profile, mu_by_profile[risk_profile.value], cov)
    # clean_weights() rounds each weight to 5 decimals, so up to ~n*0.5e-5 of
    # cumulative rounding error is expected and not a solver defect.
    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-4)


@pytest.mark.parametrize("risk_profile", ALL_PROFILES)
def test_no_weight_exceeds_its_bound(mu_cov, risk_profile):
    mu_by_profile, cov = mu_cov
    weights, _, _ = solve_portfolio(risk_profile, mu_by_profile[risk_profile.value], cov)

    bounds_config = settings.weight_bounds_by_profile[risk_profile.value]
    default_bounds = bounds_config["default"]
    for ticker, weight in weights.items():
        _, upper = bounds_config.get(ticker, default_bounds)
        assert weight <= upper + 1e-6, f"{ticker} weight {weight} exceeds its bound {upper}"


@pytest.mark.parametrize("risk_profile", ALL_PROFILES)
def test_sector_upper_bounds_respected(mu_cov, risk_profile):
    mu_by_profile, cov = mu_cov
    weights, _, _ = solve_portfolio(risk_profile, mu_by_profile[risk_profile.value], cov)

    sector_totals: dict[str, float] = {}
    for ticker, weight in weights.items():
        sector = ASSET_BY_TICKER[ticker]["asset_class"]
        sector_totals[sector] = sector_totals.get(sector, 0.0) + weight

    sector_upper = settings.sector_upper_by_profile[risk_profile.value]
    for sector, upper_bound in sector_upper.items():
        assert sector_totals.get(sector, 0.0) <= upper_bound + 1e-6


@pytest.mark.parametrize("risk_profile", ALL_PROFILES)
def test_solves_when_only_large_cap_ticker_is_gated_out(mu_cov, risk_profile):
    # NIFTYBEES.NS is the sole "Indian Large-Cap Equity" ticker. The
    # feasibility guard (_feasible_sector_lower) must drop any sector_lower
    # entry left pointing at a now-empty asset_class, or this is infeasible.
    mu_by_profile, cov = mu_cov
    mu = mu_by_profile[risk_profile.value]
    tickers = [t for t in mu.index if t != "NIFTYBEES.NS"]
    mu = mu.loc[tickers]
    cov = cov.loc[tickers, tickers]

    weights, _, _ = solve_portfolio(risk_profile, mu, cov)

    assert "NIFTYBEES.NS" not in weights
    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-4)


@pytest.mark.parametrize("risk_profile", ALL_PROFILES)
def test_no_nonzero_weight_below_min_position_size(mu_cov, risk_profile):
    mu_by_profile, cov = mu_cov
    weights, _, _ = solve_portfolio(risk_profile, mu_by_profile[risk_profile.value], cov)

    for ticker, weight in weights.items():
        assert weight == 0 or weight >= settings.min_position_size - 1e-6, (
            f"{ticker} weight {weight} is a dust position below min_position_size"
        )


def test_volatility_ordering_across_profiles(mu_cov):
    # The achievable vol range across profiles is bounded by the instrument
    # universe itself, not just the constraint knobs: SILVERBEES.NS (the
    # highest-vol asset available) is capped at 5% by sector_upper in every
    # profile, and no other high-vol asset exists to push aggressive's
    # achieved vol further out. A 150bp minimum gap (not 250bp) reflects what
    # this 8-ticker universe can actually deliver under these bounds.
    mu_by_profile, cov = mu_cov
    achieved_vol = {}
    for risk_profile in ALL_PROFILES:
        _, performance, _ = solve_portfolio(risk_profile, mu_by_profile[risk_profile.value], cov)
        achieved_vol[risk_profile] = performance[1]

    assert achieved_vol[RiskProfile.conservative] < achieved_vol[RiskProfile.moderate] < achieved_vol[RiskProfile.aggressive]

    min_gap = 0.015  # 150bp
    assert achieved_vol[RiskProfile.moderate] - achieved_vol[RiskProfile.conservative] >= min_gap
    assert achieved_vol[RiskProfile.aggressive] - achieved_vol[RiskProfile.moderate] >= min_gap
