import CapitalChangeForm from "@/components/CapitalChangeForm";

export default function EntryPage() {
  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Entry</h1>
        <p className="text-sm text-zinc-500">
          Record capital additions and withdrawals. Daily P&amp;L is pulled
          automatically by the cron; monthly fees auto-rollover each night.
        </p>
      </header>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
          Capital change
        </h2>
        <CapitalChangeForm />
      </section>
    </div>
  );
}
