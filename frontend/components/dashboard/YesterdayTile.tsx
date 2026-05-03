import { formatDate, formatSignedMoney, formatSignedPercent } from "@/lib/format";
import type { DailyTile } from "@/lib/types";

const TRADING_DAYS_PER_YEAR = 252;

/** (1 + dailyRate)^252 − 1, matching the user's sheet "Annualized (Full year)" column. */
function annualize(dailyRate: number): number {
  return Math.pow(1 + dailyRate, TRADING_DAYS_PER_YEAR) - 1;
}

/**
 * One block of right-side labels that sits next to a bar segment. The flex
 * weight matches the segment's height so the dollar value inside the bar
 * lines up with the daily % on the right.
 */
function RatePair({ flex, pct }: { flex: number; pct: number }) {
  const annual = annualize(pct);
  const tone =
    pct > 0
      ? "text-emerald-700 dark:text-emerald-400"
      : pct < 0
        ? "text-red-700 dark:text-red-400"
        : "text-zinc-600 dark:text-zinc-300";
  return (
    <div
      className="flex flex-col items-start justify-center"
      style={{ flex }}
    >
      <span className={`text-base font-semibold tabular-nums ${tone}`}>
        {formatSignedPercent(pct, 3)}
      </span>
      <span className="text-xs tabular-nums text-zinc-500">
        ({formatSignedPercent(annual, 1)} annual)
      </span>
    </div>
  );
}

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

      <div className="flex items-stretch justify-center gap-5">
        {/* The stacked bar */}
        <div className="flex h-72 w-40 flex-col overflow-hidden rounded-lg shadow-inner">
          {positive ? (
            <>
              <div className="flex flex-[2] flex-col items-center justify-center bg-emerald-300 dark:bg-emerald-400">
                <span className="text-[11px] font-medium uppercase tracking-wide text-black/60">
                  Gross
                </span>
                <span className="text-2xl font-semibold tabular-nums text-black">
                  {formatSignedMoney(gross)}
                </span>
              </div>
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

        {/* Right-side labels: daily % and annualized %, matching segment heights */}
        <div className="flex h-72 w-44 flex-col">
          {positive ? (
            <>
              {/* Aligned with top (gross) segment */}
              <RatePair flex={2} pct={Number(data.grossPct)} />
              {/* Aligned with bottom (net) segment */}
              <RatePair flex={3} pct={Number(data.netPct)} />
            </>
          ) : negative ? (
            <RatePair flex={1} pct={Number(data.grossPct)} />
          ) : (
            <div className="flex flex-1 items-center justify-start text-xs text-zinc-400">—</div>
          )}
        </div>
      </div>
    </div>
  );
}
