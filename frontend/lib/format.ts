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

export function formatSignedMoney(value: string | number, currency = "USD"): string {
  const n = typeof value === "string" ? Number(value) : value;
  const sign = n > 0 ? "+" : "";
  return sign + formatMoney(n, currency);
}

export function formatSignedPercent(value: string | number, digits = 2): string {
  const n = typeof value === "string" ? Number(value) : value;
  const sign = n > 0 ? "+" : "";
  return sign + formatPercent(n, digits);
}

/** Percentage points (one percentage minus another), e.g. "+0.42pp". */
export function formatPercentagePoints(value: string | number, digits = 2): string {
  const n = typeof value === "string" ? Number(value) : value;
  const pp = n * 100;
  const sign = pp > 0 ? "+" : "";
  return `${sign}${pp.toFixed(digits)}pp`;
}

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

export function monthName(month: number): string {
  return MONTH_NAMES[month - 1] ?? String(month);
}
