export type RiskProfile = "conservative" | "moderate" | "aggressive";

export interface PortfolioRequestBody {
  amount: number;
  risk_profile: RiskProfile;
}

export interface Allocation {
  ticker: string;
  name: string;
  asset_class: string;
  weight: number;
  amount: number;
}

export interface PortfolioStats {
  expected_annual_return: number;
  annual_volatility: number;
  sharpe_ratio: number;
}

export interface PortfolioMeta {
  data_as_of: string;
  lookback_years: number;
  risk_free_rate: number;
  cache_age_seconds: number;
  disclaimer: string;
}

export interface PortfolioResponse {
  risk_profile: RiskProfile;
  amount: number;
  allocations: Allocation[];
  portfolio_stats: PortfolioStats;
  meta: PortfolioMeta;
}

export interface ApiErrorBody {
  error: string;
  message: string;
}
