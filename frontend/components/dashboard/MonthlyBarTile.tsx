import { formatSignedMoney, formatSignedPercent, monthName } from "@/lib/format";
import type { MonthTile } from "@/lib/types";

const BAR_HEIGHT_PX = 280;
const HEADER_PX = 36; // space above the bar/column for "MTD / Full (E)" labels

/**
 * Monthly tile. Bar = projected full-month gross. The right side is a single
 * narrow column with MTD ($) and Full Est. ($) stacked vertically, colored
 * to match the header labels ("MTD" black/bold, "Full (E)" grey/bold).
 */
export default function MonthlyBarTile({ data }: { data: MonthTile }) {
  const projGross = Number(data.projectedGrossPl);
  const projNet = Number(data.projectedNetPl);
  const projGrossPct = Number(data.projectedGrossPct);
  const projNetPct = Number(data.projectedNetPct);
  const positive = projGross > 0;

  return (
    <div className="flex flex-col rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <header className="mb-4 flex items-baseline justify-between gap-3">
        <h2 className="text-3xl font-bold text-zinc-800 dark:text-zinc-100">
          {monthName(data.month)}
        </h2>
        <p className="text-sm text-zinc-500">
          {data.totalTradingDays - data.remainingTradingDays} of {data.totalTradingDays} trading days
        </p>
      </header>

      <div className="mt-auto flex items-end justify-center gap-5">
        {/* --- The projection bar (no header, just the bar) --- */}
        <div className="relative" style={{ height: BAR_HEIGHT_PX, width: 140 }}>
          <div
            className="absolute bottom-0 left-0 flex w-full flex-col overflow-hidden rounded-lg shadow-inner"
            style={{ height: BAR_HEIGHT_PX }}
          >
            {positive ? (
              <>
                <div className="flex flex-[2] flex-col items-center justify-center bg-emerald-300 dark:bg-emerald-400">
                  <span className="text-[11px] font-medium uppercase tracking-wide text-black/60">
                    Gross
                  </span>
                  <span className="text-3xl font-bold tabular-nums text-black">
                    {formatSignedPercent(projGrossPct, 2)}
                  </span>
                </div>
                <div className="flex flex-[3] flex-col items-center justify-center bg-emerald-700 dark:bg-emerald-600">
                  <span className="text-[11px] font-medium uppercase tracking-wide text-white/80">
                    Net
                  </span>
                  <span className="text-3xl font-bold tabular-nums text-white">
                    {formatSignedPercent(projNetPct, 2)}
                  </span>
                </div>
              </>
            ) : (
              <div className="flex flex-1 flex-col items-center justify-center bg-zinc-200 dark:bg-zinc-700">
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
    <div className="flex w-36 flex-col" style={{ height: BAR_HEIGHT_PX + HEADER_PX }}>
      {/* Header labels: stacked, MTD black/bold + Full (E) grey/bold */}
      <div className="flex-none pb-1" style={{ height: HEADER_PX }}>
        <p className="text-xs font-bold leading-tight text-zinc-900 dark:text-zinc-100">MTD</p>
        <p className="text-xs font-bold leading-tight text-zinc-500">Full (E)</p>
      </div>
      {/* Values, with the bar's 2/3 vertical split */}
      <div className="flex flex-1 flex-col">
        <DollarPair flex={2} mtd={mtdGross} full={fullGross} />
        <DollarPair flex={3} mtd={mtdNet} full={fullNet} />
      </div>
    </div>
  );
}

function DollarPair({ flex, mtd, full }: { flex: number; mtd: number; full: number }) {
  const mtdTone =
    mtd > 0
      ? "text-emerald-700 dark:text-emerald-400"
      : mtd < 0
        ? "text-red-700 dark:text-red-400"
        : "text-zinc-700 dark:text-zinc-300";
  return (
    <div
      className="flex flex-col items-start justify-center gap-0.5"
      style={{ flex }}
    >
      <span className={`text-sm font-semibold tabular-nums ${mtdTone}`}>
        {formatSignedMoney(mtd)}
      </span>
      <span className="text-xl font-semibold tabular-nums text-zinc-500">
        {formatSignedMoney(full)} <span className="text-xl font-medium">E</span>
      </span>
    </div>
  );
}
