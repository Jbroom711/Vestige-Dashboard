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

import { formatMoney, formatSignedPercent } from "@/lib/format";
import { useIsMobile } from "@/lib/useIsMobile";
import type { AnnualBarPoint } from "@/lib/types";

function formatMoneyK(v: number): string {
  if (v === 0) return "$0";
  const abs = Math.abs(v);
  const sign = v < 0 ? "-" : "";
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(1)}M`;
  return `${sign}$${Math.round(abs / 1000)}k`;
}

interface Props {
  bars: AnnualBarPoint[];
  avgGrossPl: string;
  avgNetPl: string;
  year: number;
}

interface Row {
  month: string;
  monthFull: string;
  winNet: number | null;
  winFee: number | null;
  loss: number | null;
  gross: number;
  net: number;
  grossPct: number;
  netPct: number;
}

const MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MONTH_INITIAL = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];
const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

export default function AnnualBarsChart({ bars, avgGrossPl, avgNetPl, year }: Props) {
  if (bars.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-dashed border-zinc-300 bg-white text-sm text-zinc-500 dark:border-zinc-700 dark:bg-zinc-900">
        No annual data yet.
      </div>
    );
  }

  const data: Row[] = bars.map((b) => {
    const gross = Number(b.grossPl);
    const net = Number(b.netPl);
    const fee = Number(b.feePortion);
    const grossPct = Number(b.grossPct);
    const netPct = Number(b.netPct);
    const label = MONTH_ABBR[b.month - 1] ?? String(b.month);
    const monthFull = MONTH_NAMES[b.month - 1] ?? String(b.month);
    const base = { month: label, monthFull, gross, net, grossPct, netPct };
    if (gross === 0 && net === 0 && fee === 0) {
      return { ...base, winNet: null, winFee: null, loss: null };
    }
    if (gross >= 0) {
      return { ...base, winNet: net, winFee: fee, loss: null };
    }
    return { ...base, winNet: null, winFee: null, loss: gross };
  });

  const avgGross = Number(avgGrossPl);
  const avgNet = Number(avgNetPl);
  const title = `Annual ${year} Performance`;
  const isMobile = useIsMobile();
  const rightMargin = isMobile ? 70 : 140;
  const leftMargin = isMobile ? 0 : 12;
  const yAxisWidth = isMobile ? 50 : 80;
  const tickFormatter = isMobile
    ? (m: string) => {
        const idx = MONTH_ABBR.indexOf(m);
        return idx >= 0 ? MONTH_INITIAL[idx] : m;
      }
    : undefined;

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-2 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <div className="relative mb-2 flex items-baseline justify-between">
        <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
          {title}
        </h3>
        {isMobile && (
          <span className="text-xs font-medium text-zinc-500" style={{ marginRight: 2 }}>
            Avg
          </span>
        )}
      </div>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: rightMargin, bottom: 8, left: leftMargin }} barCategoryGap="14%">
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis dataKey="month" tick={{ fontSize: 11 }} interval={0} tickFormatter={tickFormatter} />
            <YAxis
              tick={{ fontSize: 11 }}
              tickFormatter={(v: number) => (isMobile ? formatMoneyK(v) : formatMoney(v))}
              width={yAxisWidth}
            />
            <Tooltip content={<OrderedTooltip year={year} />} />
            <Legend wrapperStyle={{ fontSize: 12 }} content={() => <OrderedLegend />} />
            <ReferenceLine y={0} stroke="#9ca3af" />
            <ReferenceLine
              y={avgGross}
              stroke="#999999"
              strokeDasharray="4 4"
              label={<AvgLabel value={avgGross} color="#999999" hideSuffix={isMobile} />}
            />
            <ReferenceLine
              y={avgNet}
              stroke="#015c40"
              strokeDasharray="4 4"
              label={<AvgLabel value={avgNet} color="#015c40" hideSuffix={isMobile} />}
            />
            <Bar dataKey="winNet" stackId="month" fill="#047857" name="Net" />
            <Bar dataKey="winFee" stackId="month" fill="#6ee7b7" name="Gross" />
            <Bar dataKey="loss" stackId="month" fill="#dc2626" name="Loss" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

type TooltipPayload = {
  name?: string | number;
  value?: number | string;
  payload?: Row;
};
function OrderedTooltip({
  active,
  payload,
  year,
}: {
  active?: boolean;
  payload?: TooltipPayload[];
  label?: string | number;
  year: number;
}) {
  if (!active || !payload?.length) return null;
  const order = ["Net", "Gross", "Loss"];
  const rows = [...payload]
    .filter((p) => p?.name !== undefined && p?.value !== undefined && p?.value !== null)
    .sort((a, b) => order.indexOf(String(a.name)) - order.indexOf(String(b.name)));
  const rowData = payload[0]?.payload;
  // Title: full month name + year, e.g. "May 2026".
  const title = rowData ? `${rowData.monthFull} ${year}` : String(year);
  return (
    <div className="inline-block rounded border border-zinc-200 bg-white px-3 py-2 text-xs shadow dark:border-zinc-700 dark:bg-zinc-900">
      <div className="mb-1 font-semibold text-zinc-900 dark:text-zinc-100">
        {title}
      </div>
      {rows.map((item, i) => {
        const name = String(item.name);
        const color =
          name === "Net"
            ? "#015c40"
            : name === "Gross"
              ? "#666666"
              : name === "Loss"
                ? "#dc2626"
                : "#111";
        const fontWeight = name === "Net" ? 700 : 400;
        const displayValue =
          rowData && name === "Net"
            ? rowData.net
            : rowData && (name === "Gross" || name === "Loss")
              ? rowData.gross
              : Number(item.value);
        const pct = rowData
          ? name === "Net"
            ? rowData.netPct
            : rowData.grossPct
          : undefined;
        return (
          <div key={i} style={{ color, fontWeight }} className="whitespace-nowrap tabular-nums">
            {name}: {formatMoney(displayValue)}
            {pct !== undefined ? ` (${formatSignedPercent(pct, 2)})` : ""}
          </div>
        );
      })}
    </div>
  );
}

function OrderedLegend() {
  const items = [
    { name: "Net", swatch: "#047857", text: "#047857" },
    { name: "Gross", swatch: "#6ee7b7", text: "#666666" },
    { name: "Loss", swatch: "#ff9999", text: "#dc2626" },
  ];
  return (
    <div className="flex items-center justify-center gap-5 pt-1 text-xs">
      {items.map((it) => (
        <div key={it.name} className="flex items-center gap-1.5">
          <span
            className="inline-block h-3 w-3 rounded-sm"
            style={{ backgroundColor: it.swatch }}
          />
          <span style={{ color: it.text }}>{it.name}</span>
        </div>
      ))}
    </div>
  );
}

function AvgLabel({
  value,
  color,
  viewBox,
  hideSuffix = false,
}: {
  value: number;
  color: string;
  viewBox?: { x?: number; y?: number; width?: number; height?: number };
  hideSuffix?: boolean;
}) {
  if (!viewBox) return null;
  const x = (viewBox.x ?? 0) + (viewBox.width ?? 0) + 8;
  const y = viewBox.y ?? 0;
  return (
    <g>
      <text x={x} y={y} dy={5} fill={color} style={{ fontVariantNumeric: "tabular-nums" }}>
        <tspan fontSize={hideSuffix ? 14 : 19} fontWeight={700}>{formatMoney(value)}</tspan>
        {!hideSuffix && (
          <tspan fontSize={15} fontWeight={400} dx={4}>Avg</tspan>
        )}
      </text>
    </g>
  );
}
