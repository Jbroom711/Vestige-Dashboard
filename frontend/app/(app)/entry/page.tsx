import CapitalChangeForm from "@/components/CapitalChangeForm";
import PlannedCapitalForm from "@/components/PlannedCapitalForm";

export default function EntryPage() {
  return (
    <div className="space-y-8">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Entry</h1>
        <p className="text-sm text-zinc-500">
          Record capital additions and withdrawals — already-happened and
          future-planned. Daily P&amp;L is pulled automatically by the cron;
          monthly fees auto-rollover each night.
        </p>
      </header>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
          Actual capital change
        </h2>
        <CapitalChangeForm />
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
          Planned future change
        </h2>
        <p className="text-xs text-zinc-500">
          Anything added here also appears on the Annual Projection tile and is
          factored into the year-end forecast.
        </p>
        <PlannedCapitalForm />
      </section>
    </div>
  );
}
