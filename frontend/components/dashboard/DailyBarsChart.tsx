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

import { formatMoney, formatSignedPercent, monthName } from "@/lib/format";
import { useIsMobile } from "@/lib/useIsMobile";
import type { DailyBarPoint } from "@/lib/types";

interface Props {
  bars: DailyBarPoint[];
  avgGrossPl: string;
  avgNetPl: string;
}

interface Row {
  day: string;
  dayNum: number;
  winNet: number | null;
  winFee: number | null;
  loss: number | null;
  gross: number;
  net: number;
  grossPct: number;
  netPct: number;
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
  // a single negative-going red bar. Future trading days arrive with all
  // zeros from the backend — we render those as null so the x-axis tick
  // is drawn but no bar appears.
  const data: Row[] = bars.map((b) => {
    const gross = Number(b.grossPl);
    const net = Number(b.netPl);
    const fee = Number(b.feePortion);
    const grossPct = Number(b.grossPct);
    const netPct = Number(b.netPct);
    const day = b.date.slice(8, 10); // "DD"
    const dayNum = Number(day);
    const base = { day, dayNum, gross, net, grossPct, netPct };
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

  const [y, m] = bars[0].date.split("-").map(Number);
  const monthFullName = monthName(m);
  const title = `${monthFullName} ${y} Daily Performance`;
  const isMobile = useIsMobile();
  // Reserve less right margin on mobile (just enough to fit "$X,XXX"), no
  // "Avg" suffix on each line; render a single "Avg" column header instead.
  const rightMargin = isMobile ? 50 : 140;
  const leftMargin = isMobile ? 0 : 12;

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-2 shadow-sm dark:border-zinc-800 dark:bg-zinc-900 sm:p-2">
      <div className="relative mb-2 flex items-baseline justify-between">
        <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
          {title}
        </h3>
        {isMobile && (
          <span
            className="text-xs font-medium text-zinc-500"
            style={{ marginRight: 2 }}
          >
            Avg
          </span>
        )}
      </div>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: rightMargin, bottom: 8, left: leftMargin }} barCategoryGap="18%">
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="day"
              tick={{ fontSize: 11 }}
              interval={0}
              tickFormatter={isMobile ? (d: string) => String(Number(d)) : undefined}
            />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: number) => formatMoney(v)} width={80} />
            <Tooltip content={<OrderedTooltip titlePrefix={`${monthFullName} `} useDayNum />} />
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
            {/* Legend & stacking order: Net first (bottom), Gross on top of it, Loss last. */}
            <Bar dataKey="winNet" stackId="day" fill="#047857" name="Net" />
            <Bar dataKey="winFee" stackId="day" fill="#6ee7b7" name="Gross" />
            <Bar dataKey="loss" stackId="day" fill="#dc2626" name="Loss" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/**
 * Custom tooltip: orders rows Net → Gross → Loss, applies per-row styling
 * (Net bold + dark green; Gross grey; Loss red), and prints the % gain after
 * each $ value (e.g. "Net: $1,506 (+0.32%)").
 */
type TooltipPayload = {
  name?: string | number;
  value?: number | string;
  payload?: Row;
};
function OrderedTooltip({
  active,
  payload,
  label,
  titlePrefix = "",
  useDayNum = false,
}: {
  active?: boolean;
  payload?: TooltipPayload[];
  label?: string | number;
  titlePrefix?: string;
  useDayNum?: boolean;
}) {
  if (!active || !payload?.length) return null;
  const order = ["Net", "Gross", "Loss"];
  const rows = [...payload]
    .filter((p) => p?.name !== undefined && p?.value !== undefined && p?.value !== null)
    .sort((a, b) => order.indexOf(String(a.name)) - order.indexOf(String(b.name)));
  const rowData = payload[0]?.payload;
  // Title: "May 15" — month name prefix + day number with no leading zero.
  const titleSuffix = useDayNum && rowData ? rowData.dayNum : label;
  return (
    <div className="inline-block rounded border border-zinc-200 bg-white px-3 py-2 text-xs shadow dark:border-zinc-700 dark:bg-zinc-900">
      <div className="mb-1 font-semibold text-zinc-900 dark:text-zinc-100">
        {titlePrefix}{titleSuffix}
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
        // Gross row should show the FULL gross (net + fee portion), not just
        // the stacked-bar's fee segment. Loss days carry the negative gross
        // on the rowData.gross field.
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

/**
 * Custom legend forced into the order Net → Gross → Loss regardless of how
 * Recharts orders Bar dataKeys internally.
 */
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

/**
 * Label rendered at the right end of an average ReferenceLine. The dollar
 * value sits vertically centered on the dotted line, with "Average" printed
 * just below it. Recharts hands us a viewBox describing the line's drawable
 * region — { x, y, width, height } — and we anchor the text at the right
 * end of the chart plot area.
 */
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
