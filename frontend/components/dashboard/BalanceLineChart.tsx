"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatMoney, formatShortDate } from "@/lib/format";
import type { BalancePoint } from "@/lib/types";

interface Props {
  series: BalancePoint[];
}

export default function BalanceLineChart({ series }: Props) {
  if (series.length === 0) {
    return (
      <div className="flex h-72 items-center justify-center rounded-xl border border-dashed border-zinc-300 bg-white text-sm text-zinc-500 dark:border-zinc-700 dark:bg-zinc-900">
        Balance series will appear once you have daily activity.
      </div>
    );
  }

  const data = series.map((p) => ({
    date: p.date,
    closing: Number(p.closingBalance),
    deployed: Number(p.deployedCapital),
  }));

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <h3 className="mb-2 text-sm font-medium text-zinc-700 dark:text-zinc-300">
        Balance over time
      </h3>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 12, bottom: 8, left: 12 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="date"
              tickFormatter={(d: string) => formatShortDate(d)}
              tick={{ fontSize: 11 }}
            />
            <YAxis tickFormatter={(v: number) => formatMoney(v)} tick={{ fontSize: 11 }} width={80} />
            <Tooltip
              formatter={(value) => formatMoney(Number(value))}
              labelFormatter={(d) => (typeof d === "string" ? formatShortDate(d) : "")}
              contentStyle={{ fontSize: 12 }}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Line
              type="monotone"
              dataKey="closing"
              stroke="#10b981"
              name="Closing balance"
              dot={false}
              strokeWidth={2}
            />
            <Line
              type="monotone"
              dataKey="deployed"
              stroke="#6366f1"
              name="Deployed capital"
              dot={false}
              strokeWidth={2}
              strokeDasharray="4 4"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
