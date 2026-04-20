# CLAUDE.md

Instructions for Claude Code working on the Vestige Dashboard project. Read this file before making changes.

## Project overview

Vestige Dashboard is a personal investment tracking app for a trading platform that charges a 40% commission on net monthly gains. The app lets the user log daily gross P&L, capital changes, and see computed net balance, forecasts, and history. It's a single-user app authenticated via Supabase.

## Tech stack

- **Backend:** FastAPI (Python 3.11+), SQLAlchemy, Supabase Python client, pytest
- **Frontend:** Next.js 14+ (App Router), TypeScript, Tailwind CSS, Recharts, Supabase JS client
- **Database:** Supabase (Postgres) with Row Level Security
- **Auth:** Supabase Auth (email/password, single user)

## Ports (NEVER change without explicit approval)

- Frontend: **3007**
- Backend: **8007**

These are hardcoded in config files and documentation. If port conflicts arise, ask the user before changing.

## Business rules (CRITICAL — get these right)

The fee calculation is the heart of this app. Bugs here are expensive.

### Commission
- Rate: **40%** of net monthly gains (stored in settings, configurable)
- User keeps 60% of winning months

### Monthly fee calculation (with loss carryforward)
```
For each month M in chronological order:
    month_net = sum of daily gross P&L for month M (trading days only)

    if month_net >= 0:
        offset = min(carryforward, month_net)
        taxable = month_net - offset
        fee_for_month_M = taxable * commission_rate
        carryforward -= offset
    else:
        fee_for_month_M = 0
        carryforward += abs(month_net)
```

The `carryforward` starts at $0 and persists across months indefinitely.

### Fee deduction timing
- Fee for month M is deducted on the **first trading day of month M+1**
- Before deduction: the reported balance includes the unpaid fee (inflated)
- "Net balance" = reported balance − month-to-date accrued fee

### Trading days
- Use NYSE calendar (see `backend/app/holidays.py`)
- Weekdays excluding NYSE holidays
- Gross P&L can only be entered on trading days

### Capital changes
- **Additions (+):** Mondays only, AND Monday must be a trading day (not MLK Day, Memorial Day, etc.)
- **Withdrawals (−):** Any trading day
- **Never:** Weekends or holidays

### Principal / denominator for daily return %
- `deployed_capital = starting_balance + sum(all capital changes to date)`
- Do NOT use reported balance or net balance as denominator

### Daily net profit (for display)
- If `grossPL >= 0`: `dailyNet = grossPL * (1 - commission_rate)` — you keep 60%
- If `grossPL < 0`: `dailyNet = grossPL` — full loss (but it creates carryforward that offsets future fees)

### Forecast
- Simple average: `avg_daily_net * remaining_trading_days_to_Dec_31`
- Count trading days from day after last entry to Dec 31 of current year

## File conventions

### Backend
- One router per resource: `routers/entries.py`, `routers/settings.py`, `routers/dashboard.py`
- Pure functions in `calc.py` — no DB access, no FastAPI imports. Takes data, returns data. Testable.
- Pydantic schemas in `schemas.py`, separate from SQLAlchemy models
- Every calc function gets a test in `tests/test_calc.py`

### Frontend
- Components in `components/`, PascalCase filenames
- Shared utilities in `lib/format.ts`, `lib/api.ts`, `lib/types.ts`
- TypeScript strict mode — no `any` without justification comment
- Server components by default; `'use client'` only when needed (forms, charts, hooks)
- API calls go through `lib/api.ts` wrapper, never raw `fetch` in components

### Naming
- DB columns: `snake_case`
- Python: `snake_case` functions and vars, `PascalCase` classes
- TypeScript: `camelCase` for vars/functions, `PascalCase` for types/components
- API responses: convert snake_case → camelCase at the boundary (in `lib/api.ts`)

## Testing

- Backend: `pytest` must pass before any commit that touches `calc.py`
- Required test coverage: fee calc with/without carryforward, month boundary, Monday rule validation, forecast math
- Frontend: no test framework set up yet (optional); rely on TypeScript + manual QA for now

## Guardrails — ask before doing

1. **Changing ports** (3007 / 8007) — always ask
2. **Changing the fee calc logic** — confirm the rule change first, show me the math
3. **Installing new dependencies** — list them first with a reason
4. **Deleting DB data or migrations** — never without explicit "yes, delete"
5. **Modifying `.env` files or committing secrets** — never commit `.env`, always `.env.example`
6. **Force-pushing or rewriting git history** — never

## Git conventions

- Branches: `feature/short-description`, `fix/short-description`
- Commits: imperative mood, present tense ("Add Monday rule validation", not "Added...")
- Keep commits small and focused; one concern per commit
- Push to `main` only after tests pass

## When in doubt

Stop and ask. This is financial software for personal use, correctness beats speed. If a user request contradicts a business rule above, flag it and confirm before changing.
