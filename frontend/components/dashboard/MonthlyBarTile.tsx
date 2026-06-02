"use client";

import { useState } from "react";

import { api } from "@/lib/api";
import { formatMoney, formatSignedPercent, monthName } from "@/lib/format";
import type { DashboardSnapshot, MonthTile } from "@/lib/types";

const BAR_HEIGHT_PX = 280;

/**
 * Monthly tile. Bar = projected full-month gross. The right side is a single
 * narrow column with MTD ($) and Full Est. ($) stacked vertically.
 *
 * Includes a small ▾ next to the month name that opens a dropdown of all
 * previous months in the current year — clicking one re-fetches the
 * snapshot at that month's last day and swaps in its month tile. Current
 * month is the default; clicking it from the dropdown returns to it.
 */
export default function MonthlyBarTile({ data: initialData }: { data: MonthTile }) {
  const [data, setData] = useState<MonthTile>(initialData);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const today = new Date();
  const currentYear = today.getFullYear();
  const currentMonth = today.getMonth() + 1;
  const viewingMonth = data.month;
  const isViewingCurrent = viewingMonth === currentMonth && data.year === currentYear;

  // Past months of the current year, plus the current month at the top of
  // the list so the user can quickly return to "now."
  const monthOptions: number[] = [currentMonth];
  for (let m = 1; m < currentMonth; m += 1) monthOptions.push(m);

  async function selectMonth(m: number) {
    setOpen(false);
    if (m === viewingMonth && data.year === currentYear) return;
    setLoading(true);
    setError(null);
    try {
      // Last day of selected month (Date(year, m, 0) gives day 0 of m+1 = last of m).
      const lastDay = new Date(currentYear, m, 0).getDate();
      const asOf = `${currentYear}-${String(m).padStart(2, "0")}-${String(lastDay).padStart(2, "0")}`;
      const snapshot = await api.get<DashboardSnapshot>("/dashboard/snapshot", { as_of: asOf });
      setData(snapshot.month);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load month");
    }
    setLoading(false);
  }

  const projGross = Number(data.projectedGrossPl);
  const projNet = Number(data.projectedNetPl);
  const projGrossPct = Number(data.projectedGrossPct);
  const projNetPct = Number(data.projectedNetPct);
  const positive = projGross > 0;

  return (
    <div className="flex flex-col rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <header className="mb-4 flex items-baseline justify-between gap-3">
        <div className="relative flex items-baseline gap-1">
          <h2 className="text-3xl font-bold text-zinc-800 dark:text-zinc-100">
            {monthName(data.month)}
          </h2>
          {monthOptions.length > 1 && (
            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              aria-label="Pick a different month"
              className="ml-1 inline-flex h-5 w-5 items-center justify-center rounded text-xs text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
            >
              ▾
            </button>
          )}
          {open && (
            <div className="absolute left-0 top-full z-20 mt-1 min-w-[120px] rounded-md border border-zinc-200 bg-white py-1 text-sm shadow-md dark:border-zinc-700 dark:bg-zinc-900">
              {monthOptions.map((m) => {
                const isSelected = m === viewingMonth;
                const isCurrent = m === currentMonth;
                return (
                  <button
                    key={m}
                    type="button"
                    onClick={() => selectMonth(m)}
                    className={`block w-full px-3 py-1 text-left hover:bg-zinc-100 dark:hover:bg-zinc-800 ${
                      isSelected ? "font-semibold text-zinc-900 dark:text-zinc-100" : "text-zinc-700 dark:text-zinc-300"
                    }`}
                  >
                    {monthName(m)}
                    {isCurrent ? " (current)" : ""}
                  </button>
                );
              })}
            </div>
          )}
        </div>
        <p className="text-sm text-zinc-500">
          {loading
            ? "loading…"
            : error
              ? error
              : isViewingCurrent
                ? `${data.totalTradingDays - data.remainingTradingDays} of ${data.totalTradingDays} trading days`
                : `${data.totalTradingDays} trading days`}
        </p>
      </header>

      <div className="mt-auto flex items-end justify-start gap-[11px] sm:justify-center">
        {/* --- The projection bar (no header, just the bar) ---
            ml-4 on mobile pushes this bar right by 16px so it lines up
            horizontally with Daily's main bar (which sits 16px in from the
            tile-inner left due to the narrow avg side-bar + 4px gap) and
            with Yearly's centered main bar. On desktop the row is centered
            so no offset is needed. */}
        <div className="relative ml-4 shrink-0 sm:ml-0" style={{ height: BAR_HEIGHT_PX, width: 120 }}>
          <div
            className="absolute bottom-0 left-0 flex w-full flex-col overflow-hidden rounded-lg shadow-inner"
            style={{ height: BAR_HEIGHT_PX }}
          >
            {positive ? (
              <>
                <div className="flex flex-[2] flex-col items-center justify-start bg-emerald-300 pt-2 dark:bg-emerald-400">
                  <span className="text-[11px] font-medium uppercase tracking-wide text-[#666666]">
                    Gross
                  </span>
                  <span className="text-3xl font-bold tabular-nums text-[#666666]">
                    {formatSignedPercent(projGrossPct, 2)}
                  </span>
                </div>
                <div className="flex flex-[3] flex-col items-center justify-start bg-emerald-700 pt-2 dark:bg-emerald-600">
                  <span className="text-[11px] font-medium uppercase tracking-wide text-white/80">
                    Net
                  </span>
                  <span className="text-3xl font-bold tabular-nums text-white">
                    {formatSignedPercent(projNetPct, 2)}
                  </span>
                </div>
              </>
            ) : (
              <div className="flex flex-1 flex-col items-center justify-start bg-zinc-200 pt-2 dark:bg-zinc-700">
                <span className="text-[11px] font-medium uppercase tracking-wide text-zinc-500">
                  No projection
                </span>
                <span className="text-2xl font-semibold tabular-nums text-zinc-700 dark:text-zinc-200">
                  —
                </span>
              </div>
            )}
          </div>
        </div>

        {/* --- Right side: header labels above, then stacked values aligned to bar segments --- */}
        <DollarColumn
          mtdGross={Number(data.grossPl)}
          mtdNet={Number(data.netPl)}
          fullGross={projGross}
          fullNet={projNet}
        />
      </div>
    </div>
  );
}

function DollarColumn({
  mtdGross,
  mtdNet,
  fullGross,
  fullNet,
}: {
  mtdGross: number;
  mtdNet: number;
  fullGross: number;
  fullNet: number;
}) {
  return (
    <div className="flex flex-col" style={{ height: BAR_HEIGHT_PX }}>
      <DollarPair flex={2} mtd={mtdGross} full={fullGross} tone="gross" />
      <DollarPair flex={3} mtd={mtdNet} full={fullNet} tone="net" />
    </div>
  );
}

function DollarPair({
  flex,
  mtd,
  full,
  tone,
}: {
  flex: number;
  mtd: number;
  full: number;
  tone: "gross" | "net";
}) {
  const color =
    tone === "gross"
      ? "text-[#999999]"
      : "text-[#015c40]";
  return (
    <div
      className="flex flex-col items-start justify-start pt-2"
      style={{ flex }}
    >
      {/* Invisible spacer mirrors the "Gross"/"Net" label inside the bar so the
          E value's baseline aligns with the % amount's baseline. */}
      <span className="invisible text-[11px] font-medium uppercase tracking-wide">
        .
      </span>
      <span className={`whitespace-nowrap text-3xl font-bold tabular-nums ${color}`}>
        {formatMoney(full)} <span className="text-xl font-bold">E</span>
      </span>
      <span className={`mt-1 text-base font-normal tabular-nums ${color}`}>
        {formatMoney(mtd)} <span className="text-sm font-normal">MTD</span>
      </span>
    </div>
  );
}
