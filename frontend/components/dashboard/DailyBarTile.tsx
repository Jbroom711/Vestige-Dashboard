import { formatDate, formatSignedMoney, formatSignedPercent } from "@/lib/format";
import type { DailyTile, MoneyStr } from "@/lib/types";

const BAR_HEIGHT_PX = 280;
const HEADROOM_PX = 90;
const CONTAINER_HEIGHT_PX = BAR_HEIGHT_PX + HEADROOM_PX;
const TOP_SEGMENT_FRACTION = 2 / 5;     // 40% (fee/gross-label zone)
const BOTTOM_SEGMENT_FRACTION = 3 / 5;  // 60% (net zone)
const TOP_SEGMENT_PX = BAR_HEIGHT_PX * TOP_SEGMENT_FRACTION;
const BOTTOM_SEGMENT_PX = BAR_HEIGHT_PX * BOTTOM_SEGMENT_FRACTION;

/**
 * Daily tile. Stacked bar with the percentage inside each segment and dollar
 * amounts to the right. Two thick-dashed reference lines:
 *   - gross-zone (top 40% of bar): gray, anchored at avg_gross_$ / today_gross_$
 *   - net-zone (bottom 60% of bar): white, anchored at avg_net_$ / today_net_$
 * Lines float above the bar when today is below the corresponding average.
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
  const positive = gross > 0;
  const negative = gross < 0;

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <header className="mb-4">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Daily</h2>
        <p className="mt-0.5 text-sm text-zinc-600 dark:text-zinc-400">
          {data.label}
          <span className="mx-2 text-zinc-300 dark:text-zinc-600">·</span>
          <span className="text-zinc-700 dark:text-zinc-300">{formatDate(data.tradingDate)}</span>
        </p>
      </header>

      <div className="flex items-end justify-center gap-5">
        {/* --- Bar container with headroom for avg lines --- */}
        <div className="relative" style={{ height: CONTAINER_HEIGHT_PX, width: 160 }}>
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
                    {formatSignedPercent(data.grossPct, 3)}
                  </span>
                </div>
                <div className="flex flex-[3] flex-col items-center justify-center bg-emerald-700 dark:bg-emerald-600">
                  <span className="text-[11px] font-medium uppercase tracking-wide text-white/80">
                    Net
                  </span>
                  <span className="text-3xl font-bold tabular-nums text-white">
                    {formatSignedPercent(data.netPct, 3)}
                  </span>
                </div>
              </>
            ) : negative ? (
              <div className="flex flex-1 flex-col items-center justify-center bg-red-600 dark:bg-red-700">
                <span className="text-[11px] font-medium uppercase tracking-wide text-white/80">
                  Loss
                </span>
                <span className="text-3xl font-bold tabular-nums text-white">
                  {formatSignedPercent(data.grossPct, 3)}
                </span>
              </div>
            ) : (
              <div className="flex flex-1 flex-col items-center justify-center bg-zinc-200 dark:bg-zinc-700">
                <span className="text-[11px] font-medium uppercase tracking-wide text-zinc-500">
                  No change
                </span>
                <span className="text-3xl font-bold tabular-nums text-zinc-700 dark:text-zinc-200">
                  0.00%
                </span>
              </div>
            )}
          </div>

          {/* Gross reference line — gray, in the fee/top zone */}
          <AvgLineWithLabel
            todayDollar={gross}
            avgDollar={Number(avgGross)}
            sectionHeightPx={BAR_HEIGHT_PX}
            baseOffsetPx={0}
            colorClass="border-zinc-500 dark:border-zinc-300"
            labelText={`avg gross ${formatMoneyShort(Number(avgGross))}`}
            labelTone="text-zinc-600 dark:text-zinc-300"
          />
          {/* Net reference line — white, in the bottom net zone */}
          <AvgLineWithLabel
            todayDollar={net}
            avgDollar={Number(avgNet)}
            sectionHeightPx={BOTTOM_SEGMENT_PX}
            baseOffsetPx={0}
            colorClass="border-white"
            labelText={`avg net ${formatMoneyShort(Number(avgNet))}`}
            labelTone="text-zinc-600 dark:text-zinc-300"
          />
        </div>

        {/* --- Right column: $ amounts at matching segment heights --- */}
        <div className="flex w-40 flex-col" style={{ height: BAR_HEIGHT_PX }}>
          {positive ? (
            <>
              <DollarLine flex={2} amount={gross} />
              <DollarLine flex={3} amount={net} />
            </>
          ) : negative ? (
            <DollarLine flex={1} amount={gross} />
          ) : (
            <div className="flex flex-1 items-center justify-start text-xs text-zinc-400">$0</div>
          )}
        </div>
      </div>
    </div>
  );
}

function AvgLineWithLabel({
  todayDollar,
  avgDollar,
  sectionHeightPx,
  baseOffsetPx,
  colorClass,
  labelText,
  labelTone,
}: {
  todayDollar: number;
  avgDollar: number;
  sectionHeightPx: number;
  baseOffsetPx: number;
  colorClass: string;
  labelText: string;
  labelTone: string;
}) {
  if (todayDollar <= 0 || avgDollar <= 0) return null;
  const ratio = avgDollar / todayDollar;
  const linePx = baseOffsetPx + Math.min(CONTAINER_HEIGHT_PX - 6, ratio * sectionHeightPx);

  return (
    <>
      <div
        className={`pointer-events-none absolute left-0 w-full border-t-4 border-dashed ${colorClass}`}
        style={{ bottom: linePx }}
      />
      <div
        className={`pointer-events-none absolute left-full ml-2 -translate-y-1/2 whitespace-nowrap text-[11px] font-medium ${labelTone}`}
        style={{ bottom: linePx }}
      >
        {labelText}
      </div>
    </>
  );
}

function DollarLine({ flex, amount }: { flex: number; amount: number }) {
  const tone =
    amount > 0
      ? "text-emerald-700 dark:text-emerald-400"
      : amount < 0
        ? "text-red-700 dark:text-red-400"
        : "text-zinc-600 dark:text-zinc-300";
  return (
    <div className="flex flex-col items-start justify-center" style={{ flex }}>
      <span className={`text-xl font-semibold tabular-nums ${tone}`}>
        {formatSignedMoney(amount)}
      </span>
    </div>
  );
}

function formatMoneyShort(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}
