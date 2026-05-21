import { formatSignedMoney, formatSignedPercent } from "@/lib/format";
import type { YearTile } from "@/lib/types";

const BAR_HEIGHT_PX = 280;
const HEADER_PX = 36; // space above the bar/column for "YTD / Full (E)" labels

/**
 * Yearly tile. Bar = projected full-year gross. Right side is a single
 * narrow column with YTD ($) and Full Est. ($) stacked vertically, colored
 * to match the header labels ("YTD" black/bold, "Full (E)" grey/bold).
 */
export default function YearlyBarTile({ data }: { data: YearTile }) {
  const projGross = Number(data.projectedGrossPl);
  const projNet = Number(data.projectedNetPl);
  const projGrossPct = Number(data.projectedGrossPct);
  const projNetPct = Number(data.projectedNetPct);
  const positive = projGross > 0;

  return (
    <div className="flex flex-col rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <header className="mb-4 flex items-baseline justify-between gap-3">
        <h2 className="text-base font-semibold text-zinc-800 dark:text-zinc-100">
          {data.year}
        </h2>
        <p className="text-sm text-zinc-500">
          {data.totalTradingDays - data.remainingTradingDays} of {data.totalTradingDays} trading days
        </p>
      </header>

      <div className="mt-auto flex items-end justify-center gap-5">
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
                    {formatSignedPercent(projGrossPct, 1)}
                  </span>
                </div>
                <div className="flex flex-[3] flex-col items-center justify-center bg-emerald-700 dark:bg-emerald-600">
                  <span className="text-[11px] font-medium uppercase tracking-wide text-white/80">
                    Net
                  </span>
                  <span className="text-3xl font-bold tabular-nums text-white">
                    {formatSignedPercent(projNetPct, 1)}
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

        <DollarColumn
          ytdGross={Number(data.grossPl)}
          ytdNet={Number(data.netPl)}
          fullGross={projGross}
          fullNet={projNet}
        />
      </div>
    </div>
  );
}

function DollarColumn({
  ytdGross,
  ytdNet,
  fullGross,
  fullNet,
}: {
  ytdGross: number;
  ytdNet: number;
  fullGross: number;
  fullNet: number;
}) {
  return (
    <div className="flex w-24 flex-col" style={{ height: BAR_HEIGHT_PX + HEADER_PX }}>
      <div className="flex-none pb-1" style={{ height: HEADER_PX }}>
        <p className="text-xs font-bold leading-tight text-zinc-900 dark:text-zinc-100">YTD</p>
        <p className="text-xs font-bold leading-tight text-zinc-500">Full (E)</p>
      </div>
      <div className="flex flex-1 flex-col">
        <DollarPair flex={2} primary={ytdGross} secondary={fullGross} />
        <DollarPair flex={3} primary={ytdNet} secondary={fullNet} />
      </div>
    </div>
  );
}

function DollarPair({ flex, primary, secondary }: { flex: number; primary: number; secondary: number }) {
  return (
    <div
      className="flex flex-col items-start justify-center gap-0.5"
      style={{ flex }}
    >
      <span className="text-sm font-semibold tabular-nums text-zinc-900 dark:text-zinc-100">
        {formatSignedMoney(primary)}
      </span>
      <span className="text-sm font-semibold tabular-nums text-zinc-500">
        {formatSignedMoney(secondary)}
      </span>
    </div>
  );
}
