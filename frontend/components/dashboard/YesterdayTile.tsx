import {
  formatDate,
  formatPercentagePoints,
  formatSignedMoney,
  formatSignedPercent,
} from "@/lib/format";
import type { DailyTile } from "@/lib/types";

export default function YesterdayTile({ data }: { data: DailyTile }) {
  if (!data.tradingDate) {
    return (
      <div className="rounded-xl border border-dashed border-zinc-300 bg-white px-4 py-6 text-center text-sm text-zinc-500 dark:border-zinc-700 dark:bg-zinc-900">
        No daily returns entered yet — the previous-day view will appear here once you log
        your first day.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <p className="text-sm text-zinc-500">
        {data.label}
        <span className="mx-2 text-zinc-300 dark:text-zinc-600">·</span>
        <span className="text-zinc-700 dark:text-zinc-300">{formatDate(data.tradingDate)}</span>
      </p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <PerfCard
          label="Gross gain"
          dollar={data.grossPl}
          percent={data.grossPct}
          avgPercent={data.avgGrossPctToDate}
        />
        <PerfCard
          label="Net gain"
          dollar={data.netPl}
          percent={data.netPct}
          avgPercent={data.avgNetPctToDate}
        />
      </div>
    </div>
  );
}

function PerfCard({
  label,
  dollar,
  percent,
  avgPercent,
}: {
  label: string;
  dollar: string;
  percent: string;
  avgPercent: string | null;
}) {
  const dn = Number(dollar);
  const positive = dn > 0;
  const negative = dn < 0;
  const tone = positive
    ? "text-emerald-600 dark:text-emerald-400"
    : negative
      ? "text-red-600 dark:text-red-400"
      : "text-zinc-700 dark:text-zinc-300";

  const diff = avgPercent !== null ? Number(percent) - Number(avgPercent) : null;
  const diffTone =
    diff === null
      ? ""
      : diff > 0
        ? "text-emerald-600 dark:text-emerald-400"
        : diff < 0
          ? "text-red-600 dark:text-red-400"
          : "text-zinc-500";

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <p className="text-xs uppercase tracking-wide text-zinc-500">{label}</p>
      <p className={`mt-1 text-2xl font-semibold tabular-nums ${tone}`}>
        {formatSignedMoney(dn)}
      </p>
      <p className={`text-sm tabular-nums ${tone}`}>{formatSignedPercent(percent)}</p>
      {diff !== null ? (
        <p className={`mt-2 text-xs tabular-nums ${diffTone}`}>
          {formatPercentagePoints(diff)} vs avg
        </p>
      ) : null}
    </div>
  );
}
