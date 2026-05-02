import { formatDate, formatSignedMoney } from "@/lib/format";
import type { DailyTile } from "@/lib/types";

/**
 * Daily section: a single vertical stacked bar for the most recent trading
 * day. The full bar height is the gross profit. For winning days the bar
 * splits into two segments — the bottom 60% is the net (dark green, white
 * text showing the net $), the top 40% is the fee portion (lighter green,
 * black text labeled with the *total gross* so the entire bar's value is
 * visible at a glance). Losing days collapse to a single red bar.
 */
export default function YesterdayTile({ data }: { data: DailyTile }) {
  if (!data.tradingDate) {
    return (
      <div className="rounded-xl border border-dashed border-zinc-300 bg-white px-4 py-6 text-center text-sm text-zinc-500 dark:border-zinc-700 dark:bg-zinc-900">
        No daily returns entered yet.
      </div>
    );
  }

  const gross = Number(data.grossPl);
  const net = Number(data.netPl);
  const positive = gross > 0;
  const negative = gross < 0;

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <p className="mb-4 text-sm text-zinc-500">
        {data.label}
        <span className="mx-2 text-zinc-300 dark:text-zinc-600">·</span>
        <span className="text-zinc-700 dark:text-zinc-300">{formatDate(data.tradingDate)}</span>
      </p>

      <div className="flex items-center justify-center">
        <div className="flex h-72 w-40 flex-col overflow-hidden rounded-lg shadow-inner">
          {positive ? (
            <>
              {/* Top 40% — fee portion, lighter green, black text shows total gross */}
              <div className="flex flex-[2] flex-col items-center justify-center bg-emerald-300 dark:bg-emerald-400">
                <span className="text-[11px] font-medium uppercase tracking-wide text-black/60">
                  Gross
                </span>
                <span className="text-2xl font-semibold tabular-nums text-black">
                  {formatSignedMoney(gross)}
                </span>
              </div>
              {/* Bottom 60% — net, dark green, white text */}
              <div className="flex flex-[3] flex-col items-center justify-center bg-emerald-700 dark:bg-emerald-600">
                <span className="text-[11px] font-medium uppercase tracking-wide text-white/80">
                  Net
                </span>
                <span className="text-2xl font-semibold tabular-nums text-white">
                  {formatSignedMoney(net)}
                </span>
              </div>
            </>
          ) : negative ? (
            <div className="flex flex-1 flex-col items-center justify-center bg-red-600 dark:bg-red-700">
              <span className="text-[11px] font-medium uppercase tracking-wide text-white/80">
                Loss
              </span>
              <span className="text-2xl font-semibold tabular-nums text-white">
                {formatSignedMoney(gross)}
              </span>
            </div>
          ) : (
            <div className="flex flex-1 flex-col items-center justify-center bg-zinc-200 dark:bg-zinc-700">
              <span className="text-[11px] font-medium uppercase tracking-wide text-zinc-500">
                No change
              </span>
              <span className="text-2xl font-semibold tabular-nums text-zinc-700 dark:text-zinc-200">
                $0
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
