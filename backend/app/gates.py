import pandas as pd

MIN_NAV_HISTORY_YEARS = 3.0
MAX_ABS_MEAN_PREMIUM = 0.005
PREMIUM_WINDOW_DAYS = 30


def apply_gates(
    nav_start_dates: dict[str, pd.Timestamp],
    premium: pd.DataFrame,
    as_of: pd.Timestamp,
) -> tuple[list[str], list[dict[str, str]]]:
    """Filter tickers before optimization. Returns (surviving_tickers, excluded)."""
    surviving: list[str] = []
    excluded: list[dict[str, str]] = []

    for ticker in premium.columns:
        start_date = nav_start_dates.get(ticker)
        if start_date is None:
            excluded.append({"ticker": ticker, "reason": "no NAV history available"})
            continue

        history_years = (as_of - start_date).days / 365.25
        if history_years < MIN_NAV_HISTORY_YEARS:
            excluded.append(
                {
                    "ticker": ticker,
                    "reason": f"only {history_years:.1f}y of NAV history (< {MIN_NAV_HISTORY_YEARS:.0f}y required)",
                }
            )
            continue

        recent_premium = premium[ticker].dropna().tail(PREMIUM_WINDOW_DAYS)
        mean_premium = recent_premium.mean() if not recent_premium.empty else 0.0
        if abs(mean_premium) > MAX_ABS_MEAN_PREMIUM:
            excluded.append(
                {
                    "ticker": ticker,
                    "reason": (
                        f"30d mean premium {mean_premium:+.4f} exceeds +/-{MAX_ABS_MEAN_PREMIUM:.3f}"
                    ),
                }
            )
            continue

        surviving.append(ticker)

    return surviving, excluded
