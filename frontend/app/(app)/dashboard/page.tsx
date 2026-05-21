import BalanceLineChart from "@/components/dashboard/BalanceLineChart";
import DailyBarTile from "@/components/dashboard/DailyBarTile";
import DailyBarsChart from "@/components/dashboard/DailyBarsChart";
import MonthlyBarTile from "@/components/dashboard/MonthlyBarTile";
import Section from "@/components/dashboard/Section";
import YearlyBarTile from "@/components/dashboard/YearlyBarTile";
import { ApiError, apiServer } from "@/lib/api.server";
import { formatMoney } from "@/lib/format";
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
      <header className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <div className="text-right">
          <p className="text-xs uppercase tracking-wide text-zinc-500">Current balance</p>
          <p className="text-xl font-semibold tabular-nums">
            {formatMoney(snapshot.currentBalance)}
          </p>
          <p className="text-xs text-zinc-500">
            deployed {formatMoney(snapshot.deployedCapital)}
          </p>
        </div>
      </header>

      {/* Top row: 3 parallel tiles — Daily / Monthly / Yearly */}
      <div className="grid gap-4 lg:grid-cols-3">
        <DailyBarTile
          data={snapshot.yesterday}
          avgGross={snapshot.allTimeAvgGrossPl}
          avgNet={snapshot.allTimeAvgNetPl}
        />
        <MonthlyBarTile data={snapshot.month} />
        <YearlyBarTile data={snapshot.year} />
      </div>

      {/* Charts kept below the tile row */}
      <Section title="Daily breakdown" subtitle="Current month">
        <DailyBarsChart
          bars={snapshot.monthlyBars}
          avgGrossPl={snapshot.monthlyAvgGrossPl}
          avgNetPl={snapshot.monthlyAvgNetPl}
        />
      </Section>

      <Section title="Balance over time" subtitle="All-time">
        <BalanceLineChart series={snapshot.balanceSeries} />
      </Section>
    </div>
  );
}
