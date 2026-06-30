import { formatDateWithWeekday, formatMoney, formatSignedPercent } from "@/lib/format";
import type { DailyTile } from "@/lib/types";

const BAR_HEIGHT_PX = 280;

/**
 * Daily tile. Single full-height main bar matching Monthly/Yearly:
 *   - Positive day: 40/60 emerald split (Gross/Net) with today's % gain
 *     printed inside each segment, top-aligned.
 *   - Negative day: single red bar with today's loss % printed inside.
 *   - Zero / no-trade day: single grey bar with "0.00%" / "No change".
 *
 * Right column shows today's Gross $ and Net $ aligned to the bar's 40/60
 * split, mirroring Monthly/Yearly's right column.
 */
export default function DailyBarTile({ data }: { data: DailyTile }) {
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
    <div className="flex flex-col rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <header className="mb-4">
        <h2 className="text-3xl font-bold text-zinc-800 dark:text-zinc-100">
          {formatDateWithWeekday(data.tradingDate)}
        </h2>
      </header>

      <div className="mt-auto flex items-end justify-start gap-[11px] sm:justify-center">
        {/* Main bar — full-height, matching Monthly/Yearly. ml-4 on mobile
            mirrors Monthly's offset so all three top-row bars start at the
            same screen X on phones. */}
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
                  <span className="text-[28px] font-bold tabular-nums text-[#666666]">
                    {formatSignedPercent(data.grossPct, 2)}
                  </span>
                </div>
                <div className="flex flex-[3] flex-col items-center justify-start bg-emerald-700 pt-2 dark:bg-emerald-600">
                  <span className="text-[11px] font-medium uppercase tracking-wide text-white/80">
                    Net
                  </span>
                  <span className="text-[28px] font-bold tabular-nums text-white">
                    {formatSignedPercent(data.netPct, 2)}
                  </span>
                </div>
              </>
            ) : negative ? (
              <div className="flex flex-1 flex-col items-center justify-start bg-red-600 pt-2 dark:bg-red-700">
                <span className="text-[11px] font-medium uppercase tracking-wide text-white/80">
                  Loss
                </span>
                <span className="text-[28px] font-bold tabular-nums text-white">
                  {formatSignedPercent(data.grossPct, 2)}
                </span>
              </div>
            ) : (
              <div className="flex flex-1 flex-col items-center justify-start bg-zinc-200 pt-2 dark:bg-zinc-700">
                <span className="text-[11px] font-medium uppercase tracking-wide text-zinc-500">
                  No change
                </span>
                <span className="text-[28px] font-bold tabular-nums text-zinc-700 dark:text-zinc-200">
                  0.00%
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Right column: today's $ amounts aligned to bar segments. */}
        <div className="flex flex-col" style={{ height: BAR_HEIGHT_PX }}>
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
      ? "text-[#666666]"
      : tone === "loss"
        ? "text-red-700 dark:text-red-400"
        : "text-[#015c40]";
  return (
    <div className="flex flex-col items-start justify-start pt-2" style={{ flex }}>
      {/* Invisible spacer mirrors the "Gross"/"Net" label inside the bar so
          the $ amount's baseline aligns with the % amount's baseline. */}
      <span className="invisible text-[11px] font-medium uppercase tracking-wide">
        .
      </span>
      <span className={`text-[28px] font-bold tabular-nums ${color}`}>
        {formatMoney(amount)}
      </span>
    </div>
  );
}
