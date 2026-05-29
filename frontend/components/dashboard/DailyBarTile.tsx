import { formatDateWithWeekday, formatMoney, formatSignedPercent } from "@/lib/format";
import type { DailyTile, MoneyStr } from "@/lib/types";

const BAR_HEIGHT_PX = 280;
const MAIN_BAR_WIDTH_PX = 120;          // matches Monthly/Yearly main bar
const NARROW_BAR_WIDTH_PX = 12;         // ~10% of main bar
const BAR_GAP_PX = 4;

/**
 * Daily tile. Two side-by-side bottom-aligned bars:
 *   - Narrow bar on the left = historical *average* daily gross. Same 40/60
 *     emerald split as the main bar, no text — just shading.
 *   - Wide main bar on the right = today's actual gross. Same 40/60 split,
 *     with the % gain printed inside each segment (top-aligned).
 *
 * Both bars share the same px-per-dollar so they're directly comparable. If
 * today > avg the main bar is taller; if today < avg the narrow bar is.
 *
 * Loss days: main bar turns red, single segment, still bottom-anchored.
 *
 * Right column mirrors Monthly/Yearly: header row ("Today" / "Avg") above
 * a two-row stack of $ values aligned to the bar's 40/60 split.
 */
export default function DailyBarTile({
  data,
  avgGross,
  avgNet,
}: {
  data: DailyTile;
  avgGross: MoneyStr;
  avgNet: MoneyStr;
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
  const avgGrossN = Number(avgGross);
  const avgNetN = Number(avgNet);
  const positive = gross > 0;
  const negative = gross < 0;

  // Shared px-per-dollar scale so the two bars are directly comparable.
  const scaleMax = Math.max(Math.abs(gross), Math.abs(avgGrossN), 1);
  const pxPerDollar = BAR_HEIGHT_PX / scaleMax;
  const mainBarHeight = Math.max(2, Math.abs(gross) * pxPerDollar);
  const narrowBarHeight = avgGrossN > 0 ? Math.max(2, avgGrossN * pxPerDollar) : 0;

  return (
    <div className="flex flex-col rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <header className="mb-4">
        <h2 className="text-3xl font-bold text-zinc-800 dark:text-zinc-100">
          {formatDateWithWeekday(data.tradingDate)}
        </h2>
      </header>

      <div className="mt-auto flex items-end justify-start gap-[11px] sm:justify-center">
        {/* --- Bars: narrow avg + main, both bottom-anchored --- */}
        <div
          className="flex shrink-0 items-end"
          style={{
            height: BAR_HEIGHT_PX,
            width: NARROW_BAR_WIDTH_PX + BAR_GAP_PX + MAIN_BAR_WIDTH_PX,
            gap: BAR_GAP_PX,
          }}
        >
          {/* Narrow avg bar */}
          <div style={{ width: NARROW_BAR_WIDTH_PX, height: narrowBarHeight }}>
            {narrowBarHeight > 0 && (
              <div
                className="flex h-full w-full flex-col overflow-hidden rounded-sm shadow-inner"
                title={`Avg gross ${formatMoney(avgGrossN)} · Avg net ${formatMoney(avgNetN)}`}
              >
                <div className="flex-[2] bg-emerald-300 dark:bg-emerald-400" />
                <div className="flex-[3] bg-emerald-700 dark:bg-emerald-600" />
              </div>
            )}
          </div>

          {/* Main bar */}
          <div
            className="flex flex-col overflow-hidden rounded-lg shadow-inner"
            style={{ width: MAIN_BAR_WIDTH_PX, height: mainBarHeight }}
          >
            {positive ? (
              <>
                <div className="flex flex-[2] flex-col items-center justify-start bg-emerald-300 pt-2 dark:bg-emerald-400">
                  <span className="text-[11px] font-medium uppercase tracking-wide text-[#666666]">
                    Gross
                  </span>
                  <span className="text-3xl font-bold tabular-nums text-[#666666]">
                    {formatSignedPercent(data.grossPct, 2)}
                  </span>
                </div>
                <div className="flex flex-[3] flex-col items-center justify-start bg-emerald-700 pt-2 dark:bg-emerald-600">
                  <span className="text-[11px] font-medium uppercase tracking-wide text-white/80">
                    Net
                  </span>
                  <span className="text-3xl font-bold tabular-nums text-white">
                    {formatSignedPercent(data.netPct, 2)}
                  </span>
                </div>
              </>
            ) : negative ? (
              <div className="flex flex-1 flex-col items-center justify-start bg-red-600 pt-2 dark:bg-red-700">
                <span className="text-[11px] font-medium uppercase tracking-wide text-white/80">
                  Loss
                </span>
                <span className="text-3xl font-bold tabular-nums text-white">
                  {formatSignedPercent(data.grossPct, 2)}
                </span>
              </div>
            ) : (
              <div className="flex flex-1 flex-col items-center justify-start bg-zinc-200 pt-2 dark:bg-zinc-700">
                <span className="text-[11px] font-medium uppercase tracking-wide text-zinc-500">
                  No change
                </span>
                <span className="text-3xl font-bold tabular-nums text-zinc-700 dark:text-zinc-200">
                  0.00%
                </span>
              </div>
            )}
          </div>
        </div>

        {/* --- Right column: Today $ only, one row per bar segment.
              No fixed width — column sizes to its widest text so there's
              no trailing whitespace inside it. --- */}
        <div
          className="flex flex-col"
          style={{ height: mainBarHeight }}
        >
          {positive ? (
            <>
              <DollarRow flex={2} amount={gross} tone="gross" />
              <DollarRow flex={3} amount={net} tone="net" />
            </>
          ) : negative ? (
            <DollarRow flex={1} amount={gross} tone="loss" />
          ) : (
            <DollarRow flex={1} amount={0} tone="net" />
          )}
        </div>
      </div>
    </div>
  );
}

function DollarRow({
  flex,
  amount,
  tone,
}: {
  flex: number;
  amount: number;
  tone: "gross" | "net" | "loss";
}) {
  const color =
    tone === "gross"
      ? "text-[#999999]"
      : tone === "loss"
        ? "text-red-700 dark:text-red-400"
        : "text-[#015c40]";
  return (
    <div className="flex flex-col items-start justify-start pt-2" style={{ flex }}>
      {/* Invisible spacer mirrors the "Gross"/"Net" label inside the bar so the
          $ amount's baseline aligns with the % amount's baseline. */}
      <span className="invisible text-[11px] font-medium uppercase tracking-wide">
        .
      </span>
      <span className={`text-3xl font-bold tabular-nums ${color}`}>
        {formatMoney(amount)}
      </span>
    </div>
  );
}
