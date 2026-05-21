/**
 * Shared TypeScript types for API payloads.
 *
 * These mirror backend Pydantic schemas in `backend/app/schemas.py`, but
 * converted to camelCase and with strings instead of Python's Decimal
 * (backend serializes Decimal as JSON strings for precision).
 */

export type UserRole = "admin" | "viewer";
export type UserStatus = "pending" | "approved" | "rejected";
export type ReturnEntryMode = "percent" | "balance";
export type CapitalChangeType = "addition" | "withdrawal";

/** Money values arrive as strings from the API to preserve Decimal precision. */
export type MoneyStr = string;
/** Percentage as decimal fraction (e.g. "0.0123" for 1.23%). */
export type PctStr = string;

export interface Profile {
  id: string;
  email: string;
  role: UserRole;
  status: UserStatus;
  startingBalance: MoneyStr;
  joinDate: string;      // ISO date
  commissionRate: PctStr;
  createdAt: string;
  updatedAt: string;
}

export interface DailyReturn {
  date: string;
  grossPlPct: PctStr;
  entryMode: ReturnEntryMode;
  rawBalance: MoneyStr | null;
  enteredBy: string;
}

export interface CapitalChange {
  id: string;
  userId: string;
  date: string;
  amount: MoneyStr;
  type: CapitalChangeType;
  note: string | null;
}

export interface MonthlyFee {
  id: string;
  userId: string;
  year: number;
  month: number;
  autoAmount: MoneyStr;
  autoDeductedOn: string;
  manualAmount: MoneyStr | null;
  manualDeductedOn: string | null;
  carryforwardUsed: MoneyStr;
  carryforwardRemaining: MoneyStr;
}

export interface DayState {
  date: string;
  priorBalance: MoneyStr;
  grossPl: MoneyStr;
  capitalNet: MoneyStr;
  feeDeducted: MoneyStr;
  closingBalance: MoneyStr;
}

export interface DashboardSummary {
  asOf: string;
  currentBalance: MoneyStr;
  deployedCapital: MoneyStr;
  mtdGrossPl: MoneyStr;
  mtdAccruedFee: MoneyStr;
  netBalance: MoneyStr;
  ytdGain: MoneyStr;
  avgDailyGainRate: PctStr;
  projectedYearEndBalance: MoneyStr;
}

// ---------- /dashboard/snapshot composite payload ------------------------
export interface DailyTile {
  label: "Today" | "Yesterday" | "Last day";
  tradingDate: string | null;
  grossPl: MoneyStr;
  grossPct: PctStr;
  netPl: MoneyStr;
  netPct: PctStr;
  avgGrossPctToDate: PctStr | null;
  avgNetPctToDate: PctStr | null;
}

export interface MonthTile {
  year: number;
  month: number;
  // Realized (MTD)
  grossPl: MoneyStr;
  grossPct: PctStr;
  netPl: MoneyStr;
  netPct: PctStr;
  // Projection
  avgDailyGainRate: PctStr;
  remainingTradingDays: number;
  projectedGrossPl: MoneyStr;
  projectedNetPl: MoneyStr;
  projectedGrossPct: PctStr;
  projectedNetPct: PctStr;
}

export interface YearTile {
  year: number;
  // Realized (YTD)
  grossPl: MoneyStr;
  grossPct: PctStr;
  netPl: MoneyStr;
  netPct: PctStr;
  // Projection
  avgDailyGainRate: PctStr;
  remainingTradingDays: number;
  projectedGrossPl: MoneyStr;
  projectedNetPl: MoneyStr;
  projectedGrossPct: PctStr;
  projectedNetPct: PctStr;
  projectedYearEndBalance: MoneyStr;
}

export interface DailyBarPoint {
  date: string;
  grossPl: MoneyStr;
  feePortion: MoneyStr;
  netPl: MoneyStr;
}

export interface BalancePoint {
  date: string;
  closingBalance: MoneyStr;
  deployedCapital: MoneyStr;
}

export interface DashboardSnapshot {
  asOf: string;
  currentBalance: MoneyStr;
  deployedCapital: MoneyStr;
  yesterday: DailyTile;
  month: MonthTile;
  year: YearTile;
  monthlyBars: DailyBarPoint[];
  monthlyAvgGrossPl: MoneyStr;
  monthlyAvgNetPl: MoneyStr;
  allTimeAvgGrossPl: MoneyStr;
  allTimeAvgNetPl: MoneyStr;
  balanceSeries: BalancePoint[];
}
