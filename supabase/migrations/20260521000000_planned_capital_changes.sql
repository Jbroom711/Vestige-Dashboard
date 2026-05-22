-- ============================================================================
-- planned_capital_changes — user's intended future deposits / withdrawals
-- ============================================================================
-- Distinct from `capital_changes` (which records actual past events).
-- Used by the Annual Projection tile to model "what would my year-end look
-- like if I planned X deposit/withdrawal on date Y?" Constraints (Monday-only
-- additions, future date, within current year) are enforced at the API layer
-- so the DB just stores valid rows.

create table planned_capital_changes (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references profiles(id) on delete cascade,
    date date not null,
    amount numeric(14,2) not null,
    type capital_change_type not null,        -- reuses existing enum (addition | withdrawal)
    note text,
    created_at timestamptz not null default now(),
    check (amount > 0)
);

create index idx_planned_capital_changes_user_date
    on planned_capital_changes(user_id, date);

-- RLS: users CRUD their own plans
alter table planned_capital_changes enable row level security;

create policy planned_capital_changes_own_all on planned_capital_changes
    for all
    using (user_id = auth.uid())
    with check (user_id = auth.uid());
