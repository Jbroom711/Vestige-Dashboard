import { formatSignedMoney, formatSignedPercent, monthName } from "@/lib/format";
import type { MonthTile } from "@/lib/types";

const BAR_HEIGHT_PX = 280;

/**
 * Monthly tile. The bar represents the full-month *projection* (gross =
 * MTD + remaining-trading-days × avg-daily-gain compounded; net = gross × 0.6
 * since the broker takes 40% at month-end). To the right of the bar, two
 * columns: MTD (already realized) and Full Est. (projected full-month total),
 * each with gross + net dollar amounts vertically aligned to the bar's
 * top/bottom segments.
 */
export default function MonthlyBarTile({ data }: { data: MonthTile }) {
  const projGross = Number(data.projectedGrossPl);
  const projNet = Number(data.projectedNetPl);
  const projGrossPct = Number(data.projectedGrossPct);
  const projNetPct = Number(data.projectedNetPct);
  const positive = projGross > 0;

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <header className="mb-4">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Monthly</h2>
        <p className="mt-0.5 text-sm text-zinc-600 dark:text-zinc-400">
          {monthName(data.month)} {data.year}
          <span className="mx-2 text-zinc-300 dark:text-zinc-600">·</span>
          <span className="text-zinc-500">
            {data.remainingTradingDays} day{data.remainingTradingDays === 1 ? "" : "s"} remaining
          </span>
        </p>
      </header>

      <div className="flex items-end justify-center gap-5">
        {/* --- The projection bar --- */}
        <div className="relative" style={{ height: BAR_HEIGHT_PX, width: 160 }}>
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

        {/* --- Right side: MTD and Full Est. columns --- */}
        <DollarColumn
          label="MTD"
          grossDollar={Number(data.grossPl)}
          netDollar={Number(data.netPl)}
        />
        <DollarColumn
          label="Full Est."
          grossDollar={projGross}
          netDollar={projNet}
        />
      </div>
    </div>
  );
}

function DollarColumn({
  label,
  grossDollar,
  netDollar,
}: {
  label: string;
  grossDollar: number;
  netDollar: number;
}) {
  return (
    <div className="flex w-24 flex-col" style={{ height: BAR_HEIGHT_PX }}>
      <p className="pb-1 text-[10px] font-semibold uppercase tracking-wide text-zinc-500">
        {label}
      </p>
      <DollarLine flex={2} amount={grossDollar} />
      <DollarLine flex={3} amount={netDollar} />
    </div>
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
      <span className={`text-base font-semibold tabular-nums ${tone}`}>
        {formatSignedMoney(amount)}
      </span>
    </div>
  );
}
