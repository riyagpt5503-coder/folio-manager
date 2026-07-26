"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Allocation } from "@/types/portfolio";
import { rupeeFormatter } from "@/lib/format";

const SEQUENTIAL_LIGHT = ["#184f95", "#1c5cab", "#256abf", "#2a78d6", "#3987e5", "#5598e7", "#6da7ec", "#86b6ef", "#9ec5f4"];
const SEQUENTIAL_DARK = ["#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab"];

function usePrefersDark() {
  const [isDark, setIsDark] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    setIsDark(mq.matches);
    const handler = (e: MediaQueryListEvent) => setIsDark(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);
  return isDark;
}

interface AllocationChartProps {
  allocations: Allocation[];
}

interface TooltipPayloadItem {
  payload: Allocation;
}

function ChartTooltip({ active, payload }: { active?: boolean; payload?: TooltipPayloadItem[] }) {
  if (!active || !payload || payload.length === 0) return null;
  const item = payload[0].payload;
  return (
    <div className="rounded-lg border border-[var(--border-hairline)] bg-surface-1 px-3 py-2 shadow-sm text-sm">
      <div className="font-medium text-text-primary">
        {item.ticker} · {item.name}
      </div>
      <div className="text-text-secondary">{item.asset_class}</div>
      <div className="mt-1 text-text-primary [font-variant-numeric:tabular-nums]">
        {(item.weight * 100).toFixed(1)}% · {rupeeFormatter.format(item.amount)}
      </div>
    </div>
  );
}

export function AllocationChart({ allocations }: AllocationChartProps) {
  const isDark = usePrefersDark();
  const ramp = isDark ? SEQUENTIAL_DARK : SEQUENTIAL_LIGHT;
  const chartHeight = Math.max(allocations.length * 40, 120);

  return (
    <div className="rounded-xl border border-[var(--border-hairline)] bg-surface-1 p-4">
      <h3 className="text-sm font-medium text-text-secondary mb-2">Allocation by holding</h3>
      <ResponsiveContainer width="100%" height={chartHeight}>
        <BarChart
          data={allocations}
          layout="vertical"
          margin={{ top: 4, right: 48, bottom: 4, left: 8 }}
          barCategoryGap={10}
        >
          <XAxis type="number" hide domain={[0, "dataMax"]} />
          <YAxis
            type="category"
            dataKey="ticker"
            axisLine={false}
            tickLine={false}
            width={92}
            tickFormatter={(value: string) => value.replace(/\.NS$/, "")}
            tick={{ fill: "var(--text-primary)", fontSize: 13, fontWeight: 500 }}
          />
          <Tooltip content={<ChartTooltip />} cursor={{ fill: "var(--gridline)", opacity: 0.4 }} />
          <Bar dataKey="weight" radius={[0, 4, 4, 0]} maxBarSize={22} isAnimationActive={false}>
            {allocations.map((entry, index) => (
              <Cell key={entry.ticker} fill={ramp[index % ramp.length]} />
            ))}
            <LabelList
              dataKey="weight"
              position="right"
              formatter={(value: number) => `${(value * 100).toFixed(1)}%`}
              style={{ fill: "var(--text-secondary)", fontSize: 12 }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
