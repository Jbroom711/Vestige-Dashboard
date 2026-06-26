"use client";

import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import { formatDateWithWeekday, formatMoney } from "@/lib/format";
import type { CapitalChange, CapitalChangeType } from "@/lib/types";

function todayISO(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function isMonday(iso: string): boolean {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).getDay() === 1;
}

export default function CapitalChangeForm() {
  const [type, setType] = useState<CapitalChangeType>("withdrawal");
  const [date, setDate] = useState<string>(todayISO());
  const [amount, setAmount] = useState<string>("");
  const [note, setNote] = useState<string>("");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [changes, setChanges] = useState<CapitalChange[] | null>(null);
  const [listError, setListError] = useState<string | null>(null);

  async function loadChanges() {
    try {
      const rows = await api.get<CapitalChange[]>("/capital");
      const sorted = [...rows].sort((a, b) => b.date.localeCompare(a.date));
      setChanges(sorted);
      setListError(null);
    } catch (e) {
      setListError(e instanceof ApiError ? e.message : "Failed to load capital changes");
    }
  }

  useEffect(() => {
    loadChanges();
  }, []);

  const additionOnNonMonday = type === "addition" && !isMonday(date);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    const numericAmount = Number(amount);
    if (!Number.isFinite(numericAmount) || numericAmount <= 0) {
      setError("Amount must be a positive number");
      return;
    }
    if (additionOnNonMonday) {
      setError("Capital additions must fall on a Monday");
      return;
    }

    setSubmitting(true);
    try {
      const created = await api.post<CapitalChange>("/capital", {
        date,
        amount: numericAmount.toFixed(2),
        type,
        note: note.trim() ? note.trim() : null,
      });
      setSuccess(
        `Recorded ${created.type} of ${formatMoney(created.amount)} on ${formatDateWithWeekday(created.date)}.`,
      );
      setAmount("");
      setNote("");
      await loadChanges();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to record capital change");
    }
    setSubmitting(false);
  }

  async function handleDelete(change: CapitalChange) {
    const confirmed = window.confirm(
      `Delete ${change.type} of ${formatMoney(change.amount)} on ${formatDateWithWeekday(change.date)}?`,
    );
    if (!confirmed) return;
    try {
      await api.delete(`/capital/${change.id}`);
      await loadChanges();
    } catch (e) {
      setListError(e instanceof ApiError ? e.message : "Failed to delete row");
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
            label="Withdrawal"
            active={type === "withdrawal"}
            onClick={() => setType("withdrawal")}
          />
          <TypeButton
            label="Addition"
            active={type === "addition"}
            onClick={() => setType("addition")}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block space-y-1">
            <span className="text-sm font-medium">Date</span>
            <input
              type="date"
              required
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-zinc-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-950"
            />
            {additionOnNonMonday && (
              <span className="text-xs text-amber-600 dark:text-amber-400">
                Additions must be a Monday (broker clears wires on Mondays).
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
              placeholder="20000.00"
              className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm tabular-nums shadow-sm focus:border-zinc-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-950"
            />
          </label>
        </div>

        <label className="block space-y-1">
          <span className="text-sm font-medium">Note (optional)</span>
          <input
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="e.g. quarterly distribution"
            className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-zinc-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-950"
          />
        </label>

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
          disabled={submitting || additionOnNonMonday}
          className="w-full rounded-md bg-zinc-900 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          {submitting ? "Saving…" : `Record ${type}`}
        </button>
      </form>

      <section className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <h3 className="mb-3 text-sm font-semibold">Recorded capital changes</h3>
        {listError && (
          <p className="mb-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
            {listError}
          </p>
        )}
        {changes === null ? (
          <p className="text-sm text-zinc-500">Loading…</p>
        ) : changes.length === 0 ? (
          <p className="text-sm text-zinc-500">None yet.</p>
        ) : (
          <ul className="divide-y divide-zinc-200 dark:divide-zinc-800">
            {changes.map((c) => (
              <li key={c.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                <div className="min-w-0 flex-1">
                  <div className="font-medium tabular-nums">
                    {formatDateWithWeekday(c.date)}
                  </div>
                  <div className="text-zinc-500">
                    {c.type === "addition" ? "Addition" : "Withdrawal"}
                    {c.note ? ` — ${c.note}` : ""}
                  </div>
                </div>
                <div
                  className={`shrink-0 text-right font-semibold tabular-nums ${
                    c.type === "addition"
                      ? "text-emerald-700 dark:text-emerald-400"
                      : "text-red-700 dark:text-red-400"
                  }`}
                >
                  {c.type === "addition" ? "+" : "−"}
                  {formatMoney(c.amount)}
                </div>
                <button
                  type="button"
                  onClick={() => handleDelete(c)}
                  className="shrink-0 rounded-md px-2 py-1 text-xs text-zinc-500 hover:bg-zinc-100 hover:text-red-700 dark:hover:bg-zinc-800 dark:hover:text-red-400"
                  aria-label="Delete"
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
