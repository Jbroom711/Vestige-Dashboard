import { formatMoney, formatSignedMoney, formatSignedPercent } from "@/lib/format";
import type { YearTile as YearTileData } from "@/lib/types";

export default function YearTile({ data }: { data: YearTileData }) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      <Stat label="YTD Gross" dollar={data.grossPl} percent={data.grossPct} />
      <Stat label="YTD Net" dollar={data.netPl} percent={data.netPct} />
      <Projection
        balance={data.projectedYearEndBalance}
        avgRate={data.avgDailyGainRate}
      />
    </div>
  );
}

function Stat({
  label,
  dollar,
  percent,
}: {
  label: string;
  dollar: string;
  percent: string;
}) {
  const dn = Number(dollar);
  const tone =
    dn > 0
      ? "text-emerald-600 dark:text-emerald-400"
      : dn < 0
        ? "text-red-600 dark:text-red-400"
        : "text-zinc-700 dark:text-zinc-300";

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <p className="text-xs uppercase tracking-wide text-zinc-500">{label}</p>
      <p className={`mt-1 text-2xl font-semibold tabular-nums ${tone}`}>
        {formatSignedMoney(dn)}
      </p>
      <p className={`text-sm tabular-nums ${tone}`}>{formatSignedPercent(percent)}</p>
    </div>
  );
}

function Projection({
  balance,
  avgRate,
}: {
  balance: string;
  avgRate: string;
}) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <p className="text-xs uppercase tracking-wide text-zinc-500">Projected year-end</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-zinc-700 dark:text-zinc-300">
        {formatMoney(balance)}
      </p>
      <p className="text-sm tabular-nums text-zinc-500">
        avg daily {formatSignedPercent(avgRate)}
      </p>
    </div>
  );
}
