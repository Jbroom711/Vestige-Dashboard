"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { api, ApiError } from "@/lib/api";
import { formatMoney, formatSignedMoney, formatSignedPercent } from "@/lib/format";
import type { AnnualProjectionTileData, PlannedCapitalChange } from "@/lib/types";

interface Props {
  data: AnnualProjectionTileData;
  plannedChanges: PlannedCapitalChange[];
}

/**
 * Full-width tile below the 3-tile row. Left side: starting/current balance,
 * planning forms for deposits/withdrawals. Right side: projected full-year
 * gross/net that auto-incorporates any planned changes.
 */
export default function AnnualProjectionTile({ data, plannedChanges }: Props) {
  const deposits = plannedChanges.filter((p) => p.type === "addition");
  const withdrawals = plannedChanges.filter((p) => p.type === "withdrawal");

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <header className="mb-4 flex items-baseline justify-between gap-3">
        <h2 className="text-base font-semibold uppercase tracking-wide text-zinc-500">
          Annual Projection
        </h2>
      </header>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Left column: balances + plan forms */}
        <div className="space-y-5">
          <div className="space-y-2">
            <BalanceRow label="Starting Balance" amount={data.startingBalance} />
            <BalanceRow label="Current Balance" amount={data.currentBalance} />
          </div>

          <PlanSection
            label="Plan a Deposit"
            type="addition"
            existing={deposits}
            mondayOnly={true}
          />
          <PlanSection
            label="Plan a Withdrawal"
            type="withdrawal"
            existing={withdrawals}
            mondayOnly={false}
          />
        </div>

        {/* Right column: projection */}
        <div className="space-y-3 rounded-lg bg-zinc-50 p-5 dark:bg-zinc-950">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
            Projected Full Year
          </h3>
          <ProjectionRow
            label="Gross Gain"
            pct={data.projectedGrossPct}
            amount={data.projectedGrossPl}
          />
          <ProjectionRow
            label="Net Gain"
            pct={data.projectedNetPct}
            amount={data.projectedNetPl}
          />
          <div className="pt-3 border-t border-zinc-200 dark:border-zinc-800">
            <p className="text-xs text-zinc-500">Projected year-end balance</p>
            <p className="text-2xl font-bold tabular-nums text-zinc-800 dark:text-zinc-100">
              {formatMoney(data.projectedYearEndBalance)}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function BalanceRow({ label, amount }: { label: string; amount: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="text-sm text-zinc-600 dark:text-zinc-400">{label}:</span>
      <span className="text-base font-semibold tabular-nums text-zinc-800 dark:text-zinc-100">
        {formatMoney(amount)}
      </span>
    </div>
  );
}

function ProjectionRow({
  label,
  pct,
  amount,
}: {
  label: string;
  pct: string;
  amount: string;
}) {
  const amountNum = Number(amount);
  const tone =
    amountNum > 0
      ? "text-emerald-700 dark:text-emerald-400"
      : amountNum < 0
        ? "text-red-700 dark:text-red-400"
        : "text-zinc-700 dark:text-zinc-300";
  return (
    <div>
      <p className="text-xs text-zinc-500">{label}</p>
      <p className={`text-2xl font-bold tabular-nums ${tone}`}>
        {formatSignedPercent(pct, 1)}
        <span className="ml-3 text-base font-semibold">{formatSignedMoney(amountNum)}</span>
      </p>
    </div>
  );
}

function PlanSection({
  label,
  type,
  existing,
  mondayOnly,
}: {
  label: string;
  type: "addition" | "withdrawal";
  existing: PlannedCapitalChange[];
  mondayOnly: boolean;
}) {
  const [open, setOpen] = useState(existing.length > 0);
  const hasAny = existing.length > 0;

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="text-sm font-medium text-emerald-700 hover:text-emerald-900 dark:text-emerald-400 dark:hover:text-emerald-200"
      >
        {open ? `▾ ${label}` : `▸ ${label}`}
        {hasAny && !open && (
          <span className="ml-2 text-xs text-zinc-500">
            ({existing.length} planned)
          </span>
        )}
      </button>

      {open && (
        <div className="space-y-2 pl-4">
          {existing.map((p) => (
            <PlanRow key={p.id} plan={p} />
          ))}
          <AddPlanForm type={type} mondayOnly={mondayOnly} />
        </div>
      )}
    </div>
  );
}

function PlanRow({ plan }: { plan: PlannedCapitalChange }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function remove() {
    setBusy(true);
    try {
      await api.delete(`/planned-capital/${plan.id}`);
      router.refresh();
    } catch {
      setBusy(false);
    }
  }

  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900">
      <span className="font-medium tabular-nums text-zinc-700 dark:text-zinc-200">
        {plan.date}
      </span>
      <span className="font-semibold tabular-nums text-zinc-800 dark:text-zinc-100">
        {formatMoney(plan.amount)}
      </span>
      <button
        type="button"
        onClick={remove}
        disabled={busy}
        className="text-xs text-zinc-500 hover:text-red-600 disabled:opacity-50"
      >
        {busy ? "…" : "Remove"}
      </button>
    </div>
  );
}

// NYSE Monday holidays that 2026 actually has. If a user picks a date whose
// "next Monday" lands on one of these, the deposit rolls to the Monday after.
const MONDAY_HOLIDAYS = new Set<string>([
  "2026-01-19", // MLK Day
  "2026-02-16", // Presidents Day
  "2026-05-25", // Memorial Day
  "2026-09-07", // Labor Day
]);

function isoFromDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** Returns next Monday on/after `isoDate` that isn't a Monday NYSE holiday,
 * or null if no such Monday exists in the same calendar year. */
function nextDepositMonday(isoDate: string): string | null {
  const [y, m, d] = isoDate.split("-").map(Number);
  const date = new Date(y, m - 1, d);
  const offsetToMonday = (1 - date.getDay() + 7) % 7;
  date.setDate(date.getDate() + offsetToMonday);
  while (MONDAY_HOLIDAYS.has(isoFromDate(date))) {
    date.setDate(date.getDate() + 7);
  }
  if (date.getFullYear() > y) return null;
  return isoFromDate(date);
}

function formatPrettyDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    month: "numeric",
    day: "numeric",
    year: "numeric",
  }).format(new Date(y, m - 1, d));
}

function AddPlanForm({
  type,
  mondayOnly,
}: {
  type: "addition" | "withdrawal";
  mondayOnly: boolean;
}) {
  const router = useRouter();
  const [date, setDate] = useState("");
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const today = new Date();
  const yearEnd = new Date(today.getFullYear(), 11, 31);
  const minDate = new Date(today.getTime() + 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
  const maxDate = yearEnd.toISOString().slice(0, 10);

  // For deposits, auto-roll to the next Monday. The note tells the user.
  const effectiveDate = date
    ? mondayOnly
      ? nextDepositMonday(date)
      : date
    : "";

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!date || !amount) {
      setError("Date and amount required");
      return;
    }
    if (mondayOnly && !effectiveDate) {
      setError("No deposit Mondays remain this year");
      return;
    }
    setBusy(true);
    try {
      await api.post("/planned-capital", {
        date: effectiveDate,
        amount,
        type,
      });
      setDate("");
      setAmount("");
      router.refresh();
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Failed to save";
      setError(msg);
    } finally {
      setBusy(false);
    }
  }

  // Show the "begins trading on..." note only when the auto-rolled Monday
  // differs from the date the user actually picked.
  const showRollNote =
    mondayOnly && date && effectiveDate && effectiveDate !== date;

  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
      <div className="flex flex-col space-y-0.5">
        <label className="space-y-0.5">
          <span className="block text-[10px] uppercase tracking-wide text-zinc-500">Date</span>
          <input
            type="date"
            min={minDate}
            max={maxDate}
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="rounded-md border border-zinc-300 bg-white px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          />
        </label>
        {showRollNote ? (
          <p className="text-[11px] italic text-zinc-500">
            Begins trading on {formatPrettyDate(effectiveDate!)}
          </p>
        ) : null}
      </div>
      <label className="space-y-0.5">
        <span className="block text-[10px] uppercase tracking-wide text-zinc-500">Amount $</span>
        <input
          type="number"
          min="0.01"
          step="0.01"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          className="w-28 rounded-md border border-zinc-300 bg-white px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-950"
        />
      </label>
      <button
        type="submit"
        disabled={busy}
        className="rounded-md bg-emerald-700 px-3 py-1 text-sm font-medium text-white hover:bg-emerald-800 disabled:opacity-50"
      >
        {busy ? "Saving…" : "Add"}
      </button>
      {error && (
        <p className="basis-full text-xs text-red-600">{error}</p>
      )}
    </form>
  );
}
