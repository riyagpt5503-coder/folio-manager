import type { Allocation } from "@/types/portfolio";
import { rupeeFormatterPrecise } from "@/lib/format";

interface AllocationTableProps {
  allocations: Allocation[];
}

export function AllocationTable({ allocations }: AllocationTableProps) {
  return (
    <div className="rounded-xl border border-[var(--border-hairline)] bg-surface-1 overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border-hairline)] text-left text-text-secondary">
            <th className="px-4 py-3 font-medium">Ticker</th>
            <th className="px-4 py-3 font-medium">Name</th>
            <th className="px-4 py-3 font-medium">Asset class</th>
            <th className="px-4 py-3 font-medium text-right">Weight</th>
            <th className="px-4 py-3 font-medium text-right">Amount</th>
          </tr>
        </thead>
        <tbody>
          {allocations.map((a) => (
            <tr key={a.ticker} className="border-b border-[var(--border-hairline)] last:border-0">
              <td className="px-4 py-3 font-medium text-text-primary">{a.ticker}</td>
              <td className="px-4 py-3 text-text-secondary">{a.name}</td>
              <td className="px-4 py-3 text-text-secondary">{a.asset_class}</td>
              <td className="px-4 py-3 text-right text-text-primary [font-variant-numeric:tabular-nums]">
                {(a.weight * 100).toFixed(1)}%
              </td>
              <td className="px-4 py-3 text-right text-text-primary [font-variant-numeric:tabular-nums]">
                {rupeeFormatterPrecise.format(a.amount)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
