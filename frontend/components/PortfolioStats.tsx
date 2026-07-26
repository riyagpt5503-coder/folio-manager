import type { PortfolioStats as PortfolioStatsType } from "@/types/portfolio";

interface PortfolioStatsProps {
  stats: PortfolioStatsType;
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function PortfolioStats({ stats }: PortfolioStatsProps) {
  const tiles = [
    { label: "Expected annual return", value: formatPercent(stats.expected_annual_return) },
    { label: "Annual volatility", value: formatPercent(stats.annual_volatility) },
    { label: "Sharpe ratio", value: stats.sharpe_ratio.toFixed(2) },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
      {tiles.map((tile) => (
        <div
          key={tile.label}
          className="rounded-xl border border-[var(--border-hairline)] bg-surface-1 p-4"
        >
          <div className="text-sm text-text-secondary">{tile.label}</div>
          <div className="text-2xl font-semibold text-text-primary mt-1">{tile.value}</div>
        </div>
      ))}
    </div>
  );
}
