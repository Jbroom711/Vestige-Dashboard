import AnnualBarsChart from "@/components/dashboard/AnnualBarsChart";
import AnnualProjectionTile from "@/components/dashboard/AnnualProjectionTile";
import BalanceLineChart from "@/components/dashboard/BalanceLineChart";
import DailyBarTile from "@/components/dashboard/DailyBarTile";
import DailyBarsChart from "@/components/dashboard/DailyBarsChart";
import MonthlyBarTile from "@/components/dashboard/MonthlyBarTile";
import ScraperStatusLine from "@/components/dashboard/ScraperStatusLine";
import YearlyBarTile from "@/components/dashboard/YearlyBarTile";
import { ApiError, apiServer } from "@/lib/api.server";
import { formatMoney, formatSignedPercent } from "@/lib/format";
import type { DashboardSnapshot } from "@/lib/types";

export default async function DashboardPage() {
  let snapshot: DashboardSnapshot;
  try {
    snapshot = await apiServer.get<DashboardSnapshot>("/dashboard/snapshot");
  } catch (e) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
        Failed to load dashboard:{" "}
        {e instanceof ApiError ? `${e.status} — ${e.message}` : "Unknown error"}
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <header className="-mb-2 flex flex-col gap-1 sm:mb-0 sm:flex-row sm:items-baseline sm:gap-3">
        <h1 className="hidden text-2xl font-semibold tracking-tight sm:block">Dashboard</h1>
        <div className="flex flex-col gap-0.5 sm:ml-auto sm:items-end sm:gap-0">
          {/* Top metric line — split LEFT/RIGHT on mobile, packed on the right on desktop */}
          <div className="flex w-full items-baseline justify-between gap-3 sm:w-auto sm:justify-end">
            <p className="text-sm tabular-nums sm:text-base">
              <span className="font-normal text-zinc-500">Balance </span>
              <span className="font-bold text-zinc-900 dark:text-zinc-100">
                {formatMoney(snapshot.currentBalance)}
              </span>
            </p>
            <p className="text-sm tabular-nums sm:text-base">
              <span className="font-normal text-zinc-500">Net YTD </span>
              <span className="font-bold text-zinc-900 dark:text-zinc-100">
                {formatMoney(snapshot.year.netPl)},{" "}
                {formatSignedPercent(snapshot.year.projectedNetPct, 1)}
              </span>
            </p>
          </div>
          <ScraperStatusLine />
        </div>
      </header>

      {/* Top row: 3 parallel tiles — Daily / Monthly / Yearly.
          Daily and Monthly are sized to their content (no trailing whitespace);
          Yearly takes the remaining width so the row fills the page column. */}
      <div className="grid gap-4 lg:grid-cols-[auto_auto_1fr]">
        <DailyBarTile
          data={snapshot.yesterday}
          avgGross={snapshot.allTimeAvgGrossPl}
          avgNet={snapshot.allTimeAvgNetPl}
        />
        <MonthlyBarTile data={snapshot.month} />
        <YearlyBarTile data={snapshot.year} />
      </div>

      {/* Current month — one bar per trading day */}
      <DailyBarsChart
        bars={snapshot.monthlyBars}
        avgGrossPl={snapshot.monthlyAvgGrossPl}
        avgNetPl={snapshot.monthlyAvgNetPl}
      />

      {/* Current year — one bar per month */}
      <AnnualBarsChart
        bars={snapshot.annualBars}
        avgGrossPl={snapshot.annualAvgGrossPl}
        avgNetPl={snapshot.annualAvgNetPl}
        year={Number(snapshot.asOf.slice(0, 4))}
      />

      <BalanceLineChart
        series={snapshot.balanceSeries}
        capitalChanges={snapshot.capitalChanges}
        currentYear={Number(snapshot.asOf.slice(0, 4))}
      />

      {/* Full-width Annual Projection tile */}
      <AnnualProjectionTile
        data={snapshot.annualProjection}
        plannedChanges={snapshot.plannedChanges}
      />
    </div>
  );
}
