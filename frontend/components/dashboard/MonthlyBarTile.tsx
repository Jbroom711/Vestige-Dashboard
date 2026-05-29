import { formatMoney, formatSignedPercent, monthName } from "@/lib/format";
import type { MonthTile } from "@/lib/types";

const BAR_HEIGHT_PX = 280;

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

      <div className="mt-auto flex items-end justify-center gap-[11px]">
        {/* --- The projection bar (no header, just the bar) --- */}
        <div className="relative shrink-0" style={{ height: BAR_HEIGHT_PX, width: 120 }}>
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
