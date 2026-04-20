/**
 * Display formatters for money, percentages, and dates.
 *
 * API payloads deliver money/percentages as decimal strings to preserve
 * precision — we parse them here only for rendering, never for math.
 */

export function formatMoney(value: string | number, currency = "USD"): string {
  const n = typeof value === "string" ? Number(value) : value;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(n);
}

export function formatPercent(value: string | number, digits = 2): string {
  const n = typeof value === "string" ? Number(value) : value;
  return new Intl.NumberFormat("en-US", {
    style: "percent",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(n);
}

export function formatDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  // Avoid Date() so we don't introduce TZ drift for date-only values
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(new Date(y, m - 1, d));
}

export function formatShortDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
  }).format(new Date(y, m - 1, d));
}
