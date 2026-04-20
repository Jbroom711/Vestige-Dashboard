export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-zinc-500">
          Your daily balance, gain history, and year-end projection. Read-only.
        </p>
      </header>

      <section className="grid gap-4 sm:grid-cols-3">
        <KpiCard label="Current balance" value="—" />
        <KpiCard label="MTD gross P&L" value="—" />
        <KpiCard label="Projected year-end" value="—" />
      </section>

      <section className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <h2 className="mb-2 text-sm font-medium text-zinc-500">Balance over time</h2>
        <div className="flex h-64 items-center justify-center text-sm text-zinc-400">
          Chart renders here once data is wired up.
        </div>
      </section>

      <p className="text-xs text-zinc-400">
        Not yet connected to the backend — endpoints stubbed at 501.
      </p>
    </div>
  );
}

function KpiCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <p className="text-xs uppercase tracking-wide text-zinc-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
    </div>
  );
}
