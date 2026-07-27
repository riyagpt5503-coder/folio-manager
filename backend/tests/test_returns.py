import pytest

from app.config import settings
from app.models import RiskProfile
from app.optimizer import solve_portfolio
from app.returns import policy_weights_for_profile

ALL_PROFILES = [RiskProfile.conservative, RiskProfile.moderate, RiskProfile.aggressive]


@pytest.mark.parametrize("risk_profile", ALL_PROFILES)
def test_policy_portfolio_return_exceeds_risk_free_rate(mu_cov, risk_profile):
    # mu_cov's mu_by_profile is computed via settings.return_model, which
    # defaults to "implied" - i.e. exactly the implied_returns() path under
    # test here, using each profile's own policy weights.
    mu_by_profile, cov = mu_cov
    mu = mu_by_profile[risk_profile.value]
    w_policy = policy_weights_for_profile(risk_profile, list(cov.columns))
    portfolio_return = float(w_policy @ mu)
    assert portfolio_return > settings.risk_free_rate


@pytest.mark.parametrize("risk_profile", ALL_PROFILES)
def test_sharpe_positive_for_all_profiles(mu_cov, risk_profile):
    mu_by_profile, cov = mu_cov
    mu = mu_by_profile[risk_profile.value]
    _, performance = solve_portfolio(risk_profile, mu, cov)
    sharpe = performance[2]
    assert sharpe > 0
