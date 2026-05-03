import {
  formatDate,
  formatMoney,
  formatSignedMoney,
  formatSignedPercent,
} from "@/lib/format";
import type { DailyTile, MoneyStr } from "@/lib/types";

const TRADING_DAYS_PER_YEAR = 252;
const BAR_HEIGHT_PX = 280;       // visual height of the stacked bar
const HEADROOM_PX = 90;          // extra space above the bar so the avg line can float when today < avg
const CONTAINER_HEIGHT_PX = BAR_HEIGHT_PX + HEADROOM_PX;

/** (1 + dailyRate)^252 − 1, matches the user's G-sheet "Annualized (Full year)" column. */
function annualize(dailyRate: number): number {
  return Math.pow(1 + dailyRate, TRADING_DAYS_PER_YEAR) - 1;
}

/**
 * Daily section: a stacked single bar for the most recent trading day.
 *  - Full bar height = today's gross profit.
 *  - Bottom segment (60%) = net (dark green, white text).
 *  - Top segment (40%) = fee portion (light green, black text shows total gross).
 *  - Right of each segment: daily % and annualized % at the same height as the $ amount.
 *  - Horizontal dashed reference line = the all-time daily-average gross. The line
 *    sits at avg/today × bar_height from the bar's bottom: if today > avg the line
 *    falls inside the bar; if today < avg the line floats above the bar.
 */
export default function YesterdayTile({
  data,
  avgGross,
}: {
  data: DailyTile;
  avgGross: MoneyStr;
}) {
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

      <div className="flex items-end justify-center gap-5">
        {/* --- Bar container with headroom for the avg line --- */}
        <div className="relative" style={{ height: CONTAINER_HEIGHT_PX, width: 160 }}>
          {/* The bar (anchored at the bottom of the container) */}
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

          {/* Avg reference line + label */}
          <AvgLine grossToday={gross} avgGross={Number(avgGross)} />
        </div>

        {/* --- Right-side labels: daily % + annualized %, aligned to bar segments --- */}
        <div
          className="flex w-44 flex-col"
          style={{ height: BAR_HEIGHT_PX }}
        >
          {positive ? (
            <>
              <RatePair flex={2} pct={Number(data.grossPct)} />
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

function AvgLine({
  grossToday,
  avgGross,
}: {
  grossToday: number;
  avgGross: number;
}) {
  // Skip the line on losing or flat days, or if avg isn't available yet.
  if (grossToday <= 0 || avgGross <= 0) return null;

  // Position from bar bottom: avg / today × bar_height. If today < avg the
  // line floats above the bar (capped at the top of the headroom zone).
  const ratio = avgGross / grossToday;
  const linePxFromBottom = Math.min(CONTAINER_HEIGHT_PX - 6, ratio * BAR_HEIGHT_PX);
  const isAboveBar = linePxFromBottom > BAR_HEIGHT_PX;

  return (
    <>
      {/* The dashed line itself spans the bar width */}
      <div
        className="pointer-events-none absolute left-0 w-full border-t-2 border-dashed border-zinc-500 dark:border-zinc-400"
        style={{ bottom: linePxFromBottom }}
      />
      {/* Floating "avg $X" label at the right end of the line */}
      <div
        className="pointer-events-none absolute right-0 whitespace-nowrap rounded bg-white px-1 text-[11px] font-medium text-zinc-600 shadow-sm dark:bg-zinc-900 dark:text-zinc-300"
        style={{
          bottom: linePxFromBottom + 2,
          // If the line is above the bar, anchor the label slightly off-axis
          // so it stays readable; otherwise snap it neatly atop the line.
          transform: isAboveBar ? "translateY(0)" : "translateY(0)",
        }}
      >
        avg {formatMoney(avgGross)}
      </div>
    </>
  );
}

/** Right-side label block: daily % + annualized %, vertically centered in its segment. */
function RatePair({ flex, pct }: { flex: number; pct: number }) {
  const annual = annualize(pct);
  const tone =
    pct > 0
      ? "text-emerald-700 dark:text-emerald-400"
      : pct < 0
        ? "text-red-700 dark:text-red-400"
        : "text-zinc-600 dark:text-zinc-300";
  return (
    <div className="flex flex-col items-start justify-center" style={{ flex }}>
      <span className={`text-base font-semibold tabular-nums ${tone}`}>
        {formatSignedPercent(pct, 3)}
      </span>
      <span className="text-xs tabular-nums text-zinc-500">
        ({formatSignedPercent(annual, 1)} annual)
      </span>
    </div>
  );
}
