export default function EntryPage() {
  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Entry</h1>
        <p className="text-sm text-zinc-500">
          Log recent daily P&amp;L, capital contributions/withdrawals, or adjust the monthly fee.
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2">
        <EntryCard
          title="Daily P&L"
          description="Enter today's gain as a percentage or a new total balance."
        />
        <EntryCard
          title="Capital change"
          description="Additions (Mondays only) or withdrawals (any trading day)."
        />
        <EntryCard
          title="Monthly fee"
          description="Adjust the automatically calculated fee for any month."
        />
      </div>

      <p className="text-xs text-zinc-400">
        Forms will appear here once backend endpoints are implemented.
      </p>
    </div>
  );
}

function EntryCard({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <h2 className="text-sm font-semibold">{title}</h2>
      <p className="mt-1 text-sm text-zinc-500">{description}</p>
    </div>
  );
}
