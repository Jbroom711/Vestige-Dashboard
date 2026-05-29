"use client";

import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  useXAxisScale,
  useYAxisScale,
} from "recharts";

import { formatMoney, formatShortDate } from "@/lib/format";
import { useIsMobile } from "@/lib/useIsMobile";
import type { BalancePoint, CapitalChangePoint } from "@/lib/types";

function formatMoneyK(v: number): string {
  if (v === 0) return "$0";
  const abs = Math.abs(v);
  const sign = v < 0 ? "-" : "";
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(1)}M`;
  return `${sign}$${Math.round(abs / 1000)}k`;
}

interface Props {
  series: BalancePoint[];
  capitalChanges: CapitalChangePoint[];
  currentYear: number;
}

type View = "year" | "lifetime";

const MONTH_ABBR = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

export default function BalanceLineChart({ series, capitalChanges, currentYear }: Props) {
  const [view, setView] = useState<View>("year");
  const isMobile = useIsMobile();

  if (series.length === 0) {
    return (
      <div className="flex h-72 items-center justify-center rounded-xl border border-dashed border-zinc-300 bg-white text-sm text-zinc-500 dark:border-zinc-700 dark:bg-zinc-900">
        Balance series will appear once you have daily activity.
      </div>
    );
  }

  const { data, ticks, useQuarterly, ccAnnotations } = useMemo(() => {
    const yearStr = String(currentYear);
    // Filter series and capital changes by view.
    const filteredSeries =
      view === "year" ? series.filter((p) => p.date.startsWith(yearStr)) : series;
    const filteredCC =
      view === "year" ? capitalChanges.filter((c) => c.date.startsWith(yearStr)) : capitalChanges;

    const data = filteredSeries.map((p) => ({
      date: p.date,
      closing: Number(p.closingBalance),
      deployed: Number(p.deployedCapital),
    }));

    // Decide tick interval. Quarterly only when Lifetime view spans 2+ years.
    let useQuarterly = false;
    if (view === "lifetime" && data.length > 0) {
      const firstYear = Number(data[0].date.slice(0, 4));
      const lastYear = Number(data[data.length - 1].date.slice(0, 4));
      useQuarterly = lastYear - firstYear >= 2;
    }

    // Build category ticks. For monthly: first data point of each YYYY-MM.
    // For quarterly: first data point of each Jan/Apr/Jul/Oct.
    const ticks: string[] = [];
    const seen = new Set<string>();
    for (const p of data) {
      const key = useQuarterly
        ? `${p.date.slice(0, 4)}-Q${Math.ceil(Number(p.date.slice(5, 7)) / 3)}`
        : p.date.slice(0, 7);
      if (useQuarterly) {
        const m = Number(p.date.slice(5, 7));
        if (![1, 4, 7, 10].includes(m)) continue;
      }
      if (!seen.has(key)) {
        seen.add(key);
        ticks.push(p.date);
      }
    }

    // Resolve each capital change to (date, balance-at-that-date) PLUS the
    // previous trading day's balance so we can point the arrow at the middle
    // of the vertical "jump" the deposit/withdrawal creates on the line.
    // Then assign each annotation a horizontal offset based on its position
    // within its type-group:
    //   Deposits  → all rendered above the line, fanning LEFT
    //               (first/oldest gets the largest -offset)
    //   Withdrawals → all rendered below the line, fanning RIGHT
    //               (first/oldest gets the smallest +offset)
    const baseAnnotations = filteredCC
      .map((cc) => {
        const idx = data.findIndex((d) => d.date === cc.date);
        if (idx < 0) {
          const nextPoint = data.find((d) => d.date >= cc.date);
          if (!nextPoint) return null;
          return {
            ...cc,
            balance: nextPoint.closing,
            prevDate: undefined as string | undefined,
            prevBalance: undefined as number | undefined,
          };
        }
        const post = data[idx];
        const prev = idx > 0 ? data[idx - 1] : null;
        return {
          ...cc,
          balance: post.closing,
          prevDate: prev?.date,
          prevBalance: prev?.closing,
        };
      })
      .filter((x): x is NonNullable<typeof x> => x !== null);

    const depositCount = baseAnnotations.filter((a) => a.type === "addition").length;
    let depositIndex = 0;
    let withdrawalIndex = 0;
    const ccAnnotations = baseAnnotations.map((ann) => {
      if (ann.type === "addition") {
        const offset = -(depositCount - depositIndex) * 50;
        depositIndex += 1;
        return { ...ann, horizontalOffset: offset, above: true };
      }
      const offset = (withdrawalIndex + 1) * 50;
      withdrawalIndex += 1;
      return { ...ann, horizontalOffset: offset, above: false };
    });

    return { data, ticks, useQuarterly, ccAnnotations };
  }, [series, capitalChanges, view, currentYear]);

  const tickFormatter = (d: string) => {
    if (useQuarterly) {
      const y = d.slice(0, 4);
      const q = Math.ceil(Number(d.slice(5, 7)) / 3);
      return `Q${q} ${y}`;
    }
    return MONTH_ABBR[Number(d.slice(5, 7)) - 1] ?? "";
  };

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
          Overview
        </h3>
        <ViewToggle value={view} onChange={setView} />
      </div>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 30, right: 12, bottom: 30, left: 12 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="date"
              ticks={ticks}
              tickFormatter={tickFormatter}
              tick={{ fontSize: 11 }}
              interval={0}
            />
            <YAxis
              tickFormatter={(v: number) => (isMobile ? formatMoneyK(v) : formatMoney(v))}
              tick={{ fontSize: 11 }}
              width={isMobile ? 50 : 80}
            />
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
              name="Balance"
              dot={false}
              strokeWidth={2}
            />
            <CapitalChangesLayer annotations={ccAnnotations} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function ViewToggle({ value, onChange }: { value: View; onChange: (v: View) => void }) {
  const cls = (active: boolean) =>
    active
      ? "font-bold text-zinc-900 dark:text-zinc-100"
      : "font-normal text-[#666666] hover:text-zinc-900 dark:hover:text-zinc-100";
  return (
    <div className="flex items-center gap-4 text-sm">
      <button type="button" onClick={() => onChange("year")} className={cls(value === "year")}>
        Current Year
      </button>
      <button type="button" onClick={() => onChange("lifetime")} className={cls(value === "lifetime")}>
        Lifetime
      </button>
    </div>
  );
}

/**
 * Customized layer rendered outside the chart's plot-area clip path so the
 * labels are always visible, not clipped or hover-dependent.
 *
 * Uses the chart's xAxisMap / yAxisMap scales to convert each capital change
 * to pixel coordinates, then draws a dot, a short stem-and-arrow pointing at
 * the line, and a two-line label.
 */
function CapitalChangesLayer({
  annotations,
}: {
  annotations: {
    date: string;
    amount: string;
    type: "addition" | "withdrawal";
    balance: number;
    prevDate: string | undefined;
    prevBalance: number | undefined;
    horizontalOffset: number;
    above: boolean;
  }[];
}) {
  const xScale = useXAxisScale();
  const yScale = useYAxisScale();
  if (!xScale || !yScale) return null;
  const xs = xScale as (v: unknown) => number;
  const ys = yScale as (v: unknown) => number;

  return (
    <g>
      {annotations.map((ann, i) => {
        const cxPost = xs(ann.date);
        const cyPost = ys(ann.balance);
        if (typeof cxPost !== "number" || Number.isNaN(cxPost) || typeof cyPost !== "number" || Number.isNaN(cyPost)) {
          return null;
        }
        let tx = cxPost;
        let ty = cyPost;
        if (ann.prevDate !== undefined && ann.prevBalance !== undefined) {
          const cxPre = xs(ann.prevDate);
          const cyPre = ys(ann.prevBalance);
          if (typeof cxPre === "number" && !Number.isNaN(cxPre) && typeof cyPre === "number" && !Number.isNaN(cyPre)) {
            tx = (cxPre + cxPost) / 2;
            ty = (cyPre + cyPost) / 2;
          }
        }
        return (
          <CapitalChangeAnnotation
            key={`${ann.date}-${ann.type}-${i}`}
            tx={tx}
            ty={ty}
            amount={Number(ann.amount)}
            type={ann.type}
            date={ann.date}
            above={ann.above}
            horizontalOffset={ann.horizontalOffset}
          />
        );
      })}
    </g>
  );
}

function CapitalChangeAnnotation({
  tx,
  ty,
  amount,
  type,
  date,
  above,
  horizontalOffset,
}: {
  tx: number; // arrow target x — midpoint of the line jump
  ty: number; // arrow target y — midpoint of the line jump
  amount: number;
  type: "addition" | "withdrawal";
  date: string;
  above: boolean;
  horizontalOffset: number; // signed px; negative = left, positive = right
}) {
  // Vertical offset depends on above/below; horizontal offset is supplied so
  // callers can fan multiple callouts away from each other.
  const verticalOffset = above ? -28 : 28;
  const textCx = tx + horizontalOffset;
  const textCy = ty + verticalOffset;

  // Stem: a leader line from just outside the text block toward the target.
  // Approximate the text block as a rectangle (half-width × half-height),
  // find where the ray from the center exits that rectangle, then add a
  // 10-px gap so the stem visibly stops short of the text.
  const dx = tx - textCx;
  const dy = ty - textCy;
  const distance = Math.hypot(dx, dy);
  const cosA = dx / distance;
  const sinA = dy / distance;
  const halfW = 36; // approximate text half-width for "$XX,XXX (+)" at fontSize 11 bold
  const halfH = 13; // approximate text half-height for the 2 lines
  const gap = 3;
  const edgeDist = Math.min(
    Math.abs(cosA) > 1e-6 ? halfW / Math.abs(cosA) : Number.POSITIVE_INFINITY,
    Math.abs(sinA) > 1e-6 ? halfH / Math.abs(sinA) : Number.POSITIVE_INFINITY,
  );
  const stemPad = edgeDist + gap;
  const stemStartX = textCx + cosA * stemPad;
  const stemStartY = textCy + sinA * stemPad;

  // Filled triangle arrowhead at the target, oriented along the stem.
  const angle = Math.atan2(dy, dx);
  const arrowLen = 7;
  const arrowHalfWidth = 4;
  const baseX = tx - arrowLen * Math.cos(angle);
  const baseY = ty - arrowLen * Math.sin(angle);
  const perpX = arrowHalfWidth * Math.sin(angle);
  const perpY = -arrowHalfWidth * Math.cos(angle);
  const head = `M ${tx} ${ty} L ${baseX + perpX} ${baseY + perpY} L ${baseX - perpX} ${baseY - perpY} Z`;

  // Two-line label centered at (textCx, textCy). The "(+)" / "(-)" sign
  // gets its own color (deposit = dark green, withdrawal = red).
  const [y, m, d] = date.split("-").map(Number);
  const shortDate = `${m}/${d}/${String(y).slice(-2)}`;
  const sign = type === "addition" ? "(+)" : "(-)";
  const signColor = type === "addition" ? "#015c40" : "#dc2626";
  const firstY = textCy - 1;
  const secondY = textCy + 12;
  const stroke = "#111";

  return (
    <g>
      <line
        x1={stemStartX}
        y1={stemStartY}
        x2={baseX}
        y2={baseY}
        stroke={stroke}
        strokeWidth={1.5}
        strokeLinecap="round"
      />
      <path d={head} fill={stroke} stroke={stroke} strokeWidth={1.5} strokeLinejoin="round" />
      <text
        fontSize={11}
        fontWeight={700}
        textAnchor="middle"
        fill={stroke}
        style={{ fontVariantNumeric: "tabular-nums" }}
      >
        <tspan x={textCx} y={firstY}>
          {formatMoney(amount)}{" "}
          <tspan fill={signColor}>{sign}</tspan>
        </tspan>
        <tspan x={textCx} y={secondY} fontWeight={400}>{shortDate}</tspan>
      </text>
    </g>
  );
}
