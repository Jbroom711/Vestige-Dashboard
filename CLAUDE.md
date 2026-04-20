# CLAUDE.md

Instructions for Claude Code working on the Vestige Dashboard project. Read this file before making changes.

## Project overview

Vestige Dashboard is a **multi-user** investment tracking app modeled on a copy-trading pattern:

- **One or more admin users** publish the daily gross gain/loss percentage from their real brokerage account.
- **Viewer users** sign up (invite-only, admin approval required) and have their own personal balances. Their balance compounds at the same daily **rate** as the admin's published return, starting from their own principal on their `join_date`.
- Every user — admin or viewer — tracks their own capital contributions/withdrawals and pays the same 40% commission on monthly gains (with loss carryforward).

The app is a PWA (installable on phones) hosted on Vercel (frontend) + Railway (backend).

## Tech stack

- **Backend:** FastAPI (Python 3.11+), SQLAlchemy, Supabase Python client, pytest
- **Frontend:** Next.js 14+ (App Router), TypeScript, Tailwind CSS, Recharts, Supabase JS client, PWA (manifest + service worker)
- **Database:** Supabase (Postgres) with Row Level Security
- **Auth:** Supabase Auth (email/password, invite-only)
- **Deploy:** Frontend → Vercel, Backend → Railway

## Ports (NEVER change without explicit approval)

- Frontend (local dev): **3007**
- Backend (local dev): **8007**

Hardcoded in config and docs. Ask before changing.

## Roles & access

Two roles in `profiles.role`:

| Role | Can write `daily_returns` | Can manage own capital/fees | Can approve new users |
|---|---|---|---|
| `admin` | Yes | Yes | Yes |
| `viewer` | No (read only) | Yes (their own rows) | No |

`profiles.status` is `pending` → `approved` → (optionally `rejected`). Pending users are blocked at the router level until an admin flips their status. Multiple admins are supported.

### Bootstrap
The very first admin has to be promoted manually in the Supabase SQL editor after initial signup:
```sql
update profiles set role = 'admin', status = 'approved' where email = 'you@example.com';
```

## Business rules (CRITICAL — get these right)

### Commission
- Rate: **40%** of net monthly gains per user (stored in `profiles.commission_rate`, configurable)

### Daily return % — the shared reference series
- Admin enters one row per trading day into `daily_returns`.
- Two entry modes:
  - **Percent mode** — admin enters the gross P&L % directly.
  - **Balance mode** — admin enters the new total account balance; the system derives the % as `(new_balance − prior_balance − today_capital_changes) / prior_balance`.
- `prior_balance` = admin's closing balance from the previous trading day.
- The same `gross_pl_pct` is applied to every viewer's prior balance, so everyone compounds at the same rate.

### Per-user balance evolution (daily)
```
today_gain_$  = prior_balance * daily_returns[date].gross_pl_pct
today_close   = prior_balance + today_gain_$ + net_capital_changes_today - fee_deducted_today
```

### Monthly fee — per-user, auto-computed with manual override
For each user and each month M, in chronological order:
```
month_gain_$ = sum of (prior_balance * daily_pct) over trading days in M, user-specific
if month_gain_$ >= 0:
    offset = min(carryforward, month_gain_$)
    taxable = month_gain_$ - offset
    auto_amount = taxable * commission_rate
    carryforward -= offset
else:
    auto_amount = 0
    carryforward += abs(month_gain_$)
```
- `carryforward` starts at $0 per user, persists indefinitely across months.
- Fee is deducted on the **first trading day of month M+1** (via `auto_deducted_on`).
- User can override via `manual_amount` and/or `manual_deducted_on`. Manual values always supersede auto values when present.
- Effective values: `coalesce(manual_amount, auto_amount)`, `coalesce(manual_deducted_on, auto_deducted_on)`.

### Trading days
- NYSE calendar (see `backend/app/holidays.py`)
- Weekdays excluding NYSE holidays.
- `daily_returns` rows only on trading days.

### Capital changes (applies to all users, admin and viewer)
- **Additions:** Monday only, AND that Monday must be a trading day. Enforced at the API layer.
- **Withdrawals:** any trading day.
- Never weekends or holidays.

### Deployed capital (informational, not the return denominator)
- `deployed_capital = starting_balance + sum(capital additions) − sum(capital withdrawals)`
- Shown in the UI as "net invested to date."
- **Not** used for daily return % — that uses prior balance (time-weighted).

### Forecast (year-end net)
- Simple projection: `avg_daily_gain_rate * remaining_trading_days_to_Dec_31`, applied to the most recent balance and compounded.
- Count trading days from the day after last entry to Dec 31 of the current year.

## Data model

Core tables (full SQL in `supabase/migrations/`):

- `profiles` — extends `auth.users`; `role`, `status`, `starting_balance`, `join_date`, `commission_rate`
- `daily_returns` — shared; `date` (PK), `gross_pl_pct`, `entry_mode`, `raw_balance`, `entered_by`
- `capital_changes` — per-user; `date`, `amount`, `type` (`addition` | `withdrawal`), `note`
- `monthly_fees` — per-user; `year`, `month`, `auto_amount`, `auto_deducted_on`, `manual_amount`, `manual_deducted_on`, `carryforward_used`, `carryforward_remaining`

RLS summary:
- `daily_returns`: all authenticated read; admin-only write
- `capital_changes`, `monthly_fees`: users CRUD their own rows; admins read all
- `profiles`: users read/update own (role/status locked by trigger); admins read/update any

## File conventions

### Backend
- One router per resource: `routers/returns.py`, `routers/capital.py`, `routers/fees.py`, `routers/profiles.py`, `routers/dashboard.py`
- Pure functions in `calc.py` — no DB, no FastAPI. Takes data, returns data. Every function has a pytest test.
- Pydantic schemas in `schemas.py`, separate from any ORM models.
- Supabase JWT verified on every request; admin-only endpoints check `profiles.role`.

### Frontend
- Components in `components/`, PascalCase filenames.
- Shared utilities in `lib/format.ts`, `lib/api.ts`, `lib/types.ts`, `lib/supabase.ts`.
- TypeScript strict mode — no `any` without a justification comment.
- Server components by default; `'use client'` only for forms, charts, hooks.
- API calls via the `lib/api.ts` wrapper — never raw `fetch` in components.
- Dashboard has two top-level modes: **View** (read-only charts + history) and **Entry** (forms for P&L / balance / capital / fee).

### Naming
- DB columns: `snake_case`
- Python: `snake_case` functions/vars, `PascalCase` classes
- TypeScript: `camelCase` vars/functions, `PascalCase` types/components
- snake_case ↔ camelCase conversion happens at the API boundary (in `lib/api.ts`)

## Testing

- Backend: `pytest` must pass before any commit that touches `calc.py`.
- Required coverage: daily compounding math, fee calc with/without carryforward, month boundary, Monday rule, forecast, viewer-vs-admin isolation.
- Frontend: no test framework yet; rely on TypeScript + manual QA.

## Guardrails — ask before doing

1. **Changing ports** (3007 / 8007) — always ask
2. **Changing the fee or compounding math** — confirm the rule change first, show the math
3. **Installing new dependencies** — list them first with a reason
4. **Deleting DB data or migrations** — never without explicit "yes, delete"
5. **Modifying `.env` files or committing secrets** — never commit `.env`, always `.env.example`
6. **Force-pushing or rewriting git history** — never
7. **Changing RLS policies or role-check logic** — flag every time; this is the security boundary

## Git conventions

- Branches: `feature/short-description`, `fix/short-description`
- Commits: imperative mood, present tense ("Add Monday rule validation", not "Added...")
- Keep commits small and focused; one concern per commit
- Push to `main` only after tests pass

## When in doubt

Stop and ask. This is financial software handling real money for multiple people — correctness beats speed. If a user request contradicts a business rule above, flag it and confirm before changing.
