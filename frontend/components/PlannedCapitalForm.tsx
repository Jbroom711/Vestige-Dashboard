"use client";

import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import { formatDateWithWeekday, formatMoney } from "@/lib/format";
import type { CapitalChangeType, PlannedCapitalChange } from "@/lib/types";

// NYSE Monday holidays in the current operating year. Same set the Annual
// Projection tile uses for its plan-deposit Monday-rolling logic; keep them
// in sync if either is updated.
const MONDAY_HOLIDAYS = new Set<string>([
  "2026-01-19", // MLK Day
  "2026-02-16", // Presidents Day
  "2026-05-25", // Memorial Day
  "2026-09-07", // Labor Day
]);

function todayISO(): string {
  const now = new Date();
  return isoFromDate(now);
}
function isoFromDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}
function tomorrowISO(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return isoFromDate(d);
}
function yearEndISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-12-31`;
}

/** Returns next Monday on/after `isoDate` that isn't a Monday NYSE holiday,
 *  or null if no such Monday remains in the same calendar year. */
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

export default function PlannedCapitalForm() {
  const [type, setType] = useState<CapitalChangeType>("addition");
  const [date, setDate] = useState<string>("");
  const [amount, setAmount] = useState<string>("");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [plans, setPlans] = useState<PlannedCapitalChange[] | null>(null);
  const [listError, setListError] = useState<string | null>(null);

  async function loadPlans() {
    try {
      const rows = await api.get<PlannedCapitalChange[]>("/planned-capital");
      const sorted = [...rows].sort((a, b) => a.date.localeCompare(b.date));
      setPlans(sorted);
      setListError(null);
    } catch (e) {
      setListError(e instanceof ApiError ? e.message : "Failed to load planned changes");
    }
  }

  useEffect(() => {
    loadPlans();
  }, []);

  // For additions we silently roll forward to the next valid deposit Monday.
  const effectiveDate =
    date && type === "addition" ? nextDepositMonday(date) : date || null;
  const rolledForward =
    type === "addition" && date && effectiveDate && effectiveDate !== date;
  const noMondayRemaining = type === "addition" && date && !effectiveDate;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    const numericAmount = Number(amount);
    if (!Number.isFinite(numericAmount) || numericAmount <= 0) {
      setError("Amount must be a positive number");
      return;
    }
    if (!date) {
      setError("Pick a date");
      return;
    }
    if (date <= todayISO()) {
      setError("Planned date must be in the future");
      return;
    }
    if (date > yearEndISO()) {
      setError("Planned date must be within the current calendar year");
      return;
    }
    if (type === "addition" && !effectiveDate) {
      setError("No deposit Mondays remain this year");
      return;
    }

    setSubmitting(true);
    try {
      const created = await api.post<PlannedCapitalChange>("/planned-capital", {
        date: effectiveDate,
        amount: numericAmount.toFixed(2),
        type,
      });
      setSuccess(
        `Planned ${created.type} of ${formatMoney(created.amount)} on ${formatDateWithWeekday(created.date)}.`,
      );
      setDate("");
      setAmount("");
      await loadPlans();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to save planned change");
    }
    setSubmitting(false);
  }

  async function handleDelete(plan: PlannedCapitalChange) {
    const confirmed = window.confirm(
      `Remove planned ${plan.type} of ${formatMoney(plan.amount)} on ${formatDateWithWeekday(plan.date)}?`,
    );
    if (!confirmed) return;
    try {
      await api.delete(`/planned-capital/${plan.id}`);
      await loadPlans();
    } catch (e) {
      setListError(e instanceof ApiError ? e.message : "Failed to remove plan");
    }
  }

  return (
    <div className="space-y-6">
      <form
        onSubmit={handleSubmit}
        className="space-y-4 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900"
      >
        <div className="flex gap-2">
          <TypeButton
            label="Addition"
            active={type === "addition"}
            onClick={() => setType("addition")}
          />
          <TypeButton
            label="Withdrawal"
            active={type === "withdrawal"}
            onClick={() => setType("withdrawal")}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block space-y-1">
            <span className="text-sm font-medium">Date</span>
            <input
              type="date"
              required
              min={tomorrowISO()}
              max={yearEndISO()}
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-zinc-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-950"
            />
            {rolledForward && (
              <span className="block text-xs italic text-zinc-500">
                Deposit clears on {formatDateWithWeekday(effectiveDate!)}.
              </span>
            )}
            {noMondayRemaining && (
              <span className="block text-xs text-amber-600 dark:text-amber-400">
                No deposit Mondays remain in this calendar year.
              </span>
            )}
          </label>

          <label className="block space-y-1">
            <span className="text-sm font-medium">Amount (USD)</span>
            <input
              type="number"
              required
              min="0.01"
              step="0.01"
              inputMode="decimal"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="50000.00"
              className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm tabular-nums shadow-sm focus:border-zinc-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-950"
            />
          </label>
        </div>

        {error && (
          <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
            {error}
          </p>
        )}
        {success && (
          <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
            {success}
          </p>
        )}

        <button
          type="submit"
          disabled={submitting || Boolean(noMondayRemaining)}
          className="w-full rounded-md bg-zinc-900 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          {submitting ? "Saving…" : `Plan ${type}`}
        </button>
      </form>

      <section className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <h3 className="mb-3 text-sm font-semibold">Planned future changes</h3>
        {listError && (
          <p className="mb-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
            {listError}
          </p>
        )}
        {plans === null ? (
          <p className="text-sm text-zinc-500">Loading…</p>
        ) : plans.length === 0 ? (
          <p className="text-sm text-zinc-500">
            None planned. Add one above to factor it into the Annual Projection.
          </p>
        ) : (
          <ul className="divide-y divide-zinc-200 dark:divide-zinc-800">
            {plans.map((p) => (
              <li key={p.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                <div className="min-w-0 flex-1">
                  <div className="font-medium tabular-nums">
                    {formatDateWithWeekday(p.date)}
                  </div>
                  <div className="text-zinc-500">
                    {p.type === "addition" ? "Addition" : "Withdrawal"}
                    {p.note ? ` — ${p.note}` : ""}
                  </div>
                </div>
                <div
                  className={`shrink-0 text-right font-semibold tabular-nums ${
                    p.type === "addition"
                      ? "text-emerald-700 dark:text-emerald-400"
                      : "text-red-700 dark:text-red-400"
                  }`}
                >
                  {p.type === "addition" ? "+" : "−"}
                  {formatMoney(p.amount)}
                </div>
                <button
                  type="button"
                  onClick={() => handleDelete(p)}
                  className="shrink-0 rounded-md px-2 py-1 text-xs text-zinc-500 hover:bg-zinc-100 hover:text-red-700 dark:hover:bg-zinc-800 dark:hover:text-red-400"
                  aria-label="Remove"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function TypeButton({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex-1 rounded-md border px-3 py-2 text-sm font-medium transition-colors ${
        active
          ? "border-zinc-900 bg-zinc-900 text-white dark:border-zinc-100 dark:bg-zinc-100 dark:text-zinc-900"
          : "border-zinc-300 bg-white text-zinc-700 hover:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-300"
      }`}
    >
      {label}
    </button>
  );
}
