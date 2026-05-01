"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatMoney } from "@/lib/format";
import type { DailyBarPoint } from "@/lib/types";

interface Props {
  bars: DailyBarPoint[];
  avgGrossPl: string;
  avgNetPl: string;
}

interface Row {
  day: string;
  winNet: number | null;
  winFee: number | null;
  loss: number | null;
  gross: number;
  net: number;
}

export default function DailyBarsChart({ bars, avgGrossPl, avgNetPl }: Props) {
  if (bars.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-dashed border-zinc-300 bg-white text-sm text-zinc-500 dark:border-zinc-700 dark:bg-zinc-900">
        No daily activity in the current month yet.
      </div>
    );
  }

  // For winning days the bar splits into a "net" segment + "fee" segment
  // stacked on top, so the full bar height = gross. For losing days we draw
  // a single negative-going red bar.
  const data: Row[] = bars.map((b) => {
    const gross = Number(b.grossPl);
    const net = Number(b.netPl);
    const fee = Number(b.feePortion);
    const day = b.date.slice(8, 10); // "DD"
    if (gross >= 0) {
      return { day, winNet: net, winFee: fee, loss: null, gross, net };
    }
    return { day, winNet: null, winFee: null, loss: gross, gross, net };
  });

  const avgGross = Number(avgGrossPl);
  const avgNet = Number(avgNetPl);

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <h3 className="mb-2 text-sm font-medium text-zinc-700 dark:text-zinc-300">
        Daily P&amp;L · current month
      </h3>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 12, bottom: 8, left: 12 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis dataKey="day" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: number) => formatMoney(v)} width={80} />
            <Tooltip
              formatter={(value, key) => {
                const k = String(key);
                const label =
                  k === "winNet"
                    ? "Net (kept)"
                    : k === "winFee"
                      ? "Fee portion"
                      : "Loss";
                return [formatMoney(Number(value)), label];
              }}
              labelFormatter={(d) => `Day ${d}`}
              contentStyle={{ fontSize: 12 }}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <ReferenceLine y={0} stroke="#9ca3af" />
            <ReferenceLine
              y={avgGross}
              stroke="#059669"
              strokeDasharray="4 4"
              label={{
                value: `avg gross ${formatMoney(avgGross)}`,
                position: "right",
                fill: "#059669",
                fontSize: 10,
              }}
            />
            <ReferenceLine
              y={avgNet}
              stroke="#65a30d"
              strokeDasharray="4 4"
              label={{
                value: `avg net ${formatMoney(avgNet)}`,
                position: "right",
                fill: "#65a30d",
                fontSize: 10,
              }}
            />
            <Bar dataKey="winNet" stackId="day" fill="#10b981" name="Net (kept)" />
            <Bar dataKey="winFee" stackId="day" fill="#86efac" name="Fee portion" />
            <Bar dataKey="loss" stackId="loss" fill="#ef4444" name="Loss" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
