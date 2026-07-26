"use client";

import { useState } from "react";
import type { RiskProfile } from "@/types/portfolio";

const RISK_PROFILES: { value: RiskProfile; label: string; description: string }[] = [
  { value: "conservative", label: "Conservative", description: "Lower risk, steadier returns" },
  { value: "moderate", label: "Moderate", description: "Balanced risk and return" },
  { value: "aggressive", label: "Aggressive", description: "Higher risk, higher growth potential" },
];

interface PortfolioFormProps {
  onSubmit: (amount: number, riskProfile: RiskProfile) => void;
  isLoading: boolean;
}

export function PortfolioForm({ onSubmit, isLoading }: PortfolioFormProps) {
  const [amountInput, setAmountInput] = useState("100000");
  const [riskProfile, setRiskProfile] = useState<RiskProfile>("moderate");
  const [validationError, setValidationError] = useState<string | null>(null);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const amount = Number(amountInput);
    if (!Number.isFinite(amount) || amount <= 0) {
      setValidationError("Enter an amount greater than ₹0.");
      return;
    }
    setValidationError(null);
    onSubmit(amount, riskProfile);
  }

  return (
    <form
      onSubmit={handleSubmit}
      noValidate
      className="rounded-xl border border-[var(--border-hairline)] bg-surface-1 p-6 flex flex-col gap-6"
    >
      <div className="flex flex-col gap-2">
        <label htmlFor="amount" className="text-sm font-medium text-text-secondary">
          Amount to invest
        </label>
        <div className="relative">
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-text-muted">
            ₹
          </span>
          <input
            id="amount"
            type="number"
            min="1"
            step="any"
            inputMode="decimal"
            value={amountInput}
            onChange={(e) => setAmountInput(e.target.value)}
            className="w-full rounded-lg border border-[var(--border-hairline)] bg-transparent py-2.5 pl-7 pr-3 text-lg text-text-primary [font-variant-numeric:tabular-nums] focus:outline-none focus:ring-2 focus:ring-[var(--series-blue)]"
            placeholder="1,00,000"
          />
        </div>
        {validationError && <p className="text-sm text-[#d03b3b]">{validationError}</p>}
      </div>

      <fieldset className="flex flex-col gap-2">
        <legend className="text-sm font-medium text-text-secondary mb-2">Risk profile</legend>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {RISK_PROFILES.map((profile) => {
            const isSelected = riskProfile === profile.value;
            return (
              <button
                key={profile.value}
                type="button"
                onClick={() => setRiskProfile(profile.value)}
                aria-pressed={isSelected}
                className={`rounded-lg border px-4 py-3 text-left transition-colors ${
                  isSelected
                    ? "border-[var(--series-blue)] bg-[var(--series-blue)]/10"
                    : "border-[var(--border-hairline)] hover:bg-[var(--gridline)]/40"
                }`}
              >
                <div className="font-medium text-text-primary">{profile.label}</div>
                <div className="text-xs text-text-muted mt-0.5">{profile.description}</div>
              </button>
            );
          })}
        </div>
      </fieldset>

      <button
        type="submit"
        disabled={isLoading}
        className="rounded-lg bg-[var(--series-blue)] text-white font-medium py-2.5 px-4 disabled:opacity-60 disabled:cursor-not-allowed hover:opacity-90 transition-opacity"
      >
        {isLoading ? "Computing…" : "Build my portfolio"}
      </button>
    </form>
  );
}
