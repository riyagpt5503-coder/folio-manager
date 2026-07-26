"use client";

import { useState } from "react";
import { PortfolioForm } from "@/components/PortfolioForm";
import { PortfolioStats } from "@/components/PortfolioStats";
import { AllocationChart } from "@/components/AllocationChart";
import { AllocationTable } from "@/components/AllocationTable";
import { LoadingState } from "@/components/LoadingState";
import { ErrorState } from "@/components/ErrorState";
import { Disclaimer } from "@/components/Disclaimer";
import { fetchPortfolio, PortfolioApiError } from "@/lib/api";
import type { PortfolioResponse, RiskProfile } from "@/types/portfolio";

type Status = "idle" | "loading" | "success" | "error";

export default function Home() {
  const [status, setStatus] = useState<Status>("idle");
  const [result, setResult] = useState<PortfolioResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string>("");

  async function handleSubmit(amount: number, riskProfile: RiskProfile) {
    setStatus("loading");
    try {
      const data = await fetchPortfolio({ amount, risk_profile: riskProfile });
      setResult(data);
      setStatus("success");
    } catch (err) {
      const message =
        err instanceof PortfolioApiError ? err.message : "Something went wrong. Please try again.";
      setErrorMessage(message);
      setStatus("error");
    }
  }

  return (
    <main className="flex-1 flex flex-col items-center px-4 py-12 sm:py-16">
      <div className="w-full max-w-2xl flex flex-col gap-8">
        <div className="flex flex-col gap-2">
          <h1 className="text-2xl sm:text-3xl font-semibold text-text-primary">
            Portfolio builder
          </h1>
          <p className="text-text-secondary">
            Enter an amount and a risk profile to get an optimized allocation across a diversified
            ETF universe, based on Modern Portfolio Theory.
          </p>
        </div>

        <PortfolioForm onSubmit={handleSubmit} isLoading={status === "loading"} />

        {status === "loading" && <LoadingState />}
        {status === "error" && <ErrorState message={errorMessage} />}

        {status === "success" && result && (
          <div className="flex flex-col gap-4">
            <PortfolioStats stats={result.portfolio_stats} />
            <AllocationChart allocations={result.allocations} />
            <AllocationTable allocations={result.allocations} />
            <Disclaimer
              text={result.meta.disclaimer}
              dataAsOf={result.meta.data_as_of}
              lookbackYears={result.meta.lookback_years}
            />
          </div>
        )}
      </div>
    </main>
  );
}
