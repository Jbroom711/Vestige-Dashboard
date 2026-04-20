-- ============================================================================
-- Vestige Dashboard — Initial Schema
-- ============================================================================
-- Tables: profiles, daily_returns, capital_changes, monthly_fees
-- Enums:  user_role, user_status, capital_change_type, return_entry_mode
-- Helpers: is_admin(uid), set_updated_at(), handle_new_user(),
--          prevent_self_role_change()
-- RLS on every user-facing table
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Enums
-- ----------------------------------------------------------------------------
create type user_role as enum ('admin', 'viewer');
create type user_status as enum ('pending', 'approved', 'rejected');
create type capital_change_type as enum ('addition', 'withdrawal');
create type return_entry_mode as enum ('percent', 'balance');

-- ----------------------------------------------------------------------------
-- Shared helper: set_updated_at trigger fn
-- ----------------------------------------------------------------------------
create or replace function set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

-- ============================================================================
-- profiles — extends auth.users
-- ============================================================================
create table profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    email text not null unique,
    role user_role not null default 'viewer',
    status user_status not null default 'pending',
    starting_balance numeric(14,2) not null default 0,
    join_date date not null default current_date,
    commission_rate numeric(5,4) not null default 0.40,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (commission_rate >= 0 and commission_rate <= 1),
    check (starting_balance >= 0)
);

create trigger profiles_set_updated_at
    before update on profiles
    for each row execute function set_updated_at();

-- Auto-create a profiles row whenever a new auth user is created
create or replace function handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into public.profiles (id, email)
    values (new.id, new.email);
    return new;
end;
$$;

create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function handle_new_user();

-- Prevent non-admins from changing their own role or status
create or replace function prevent_self_role_change()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    if auth.uid() = new.id then
        if new.role is distinct from old.role
           or new.status is distinct from old.status then
            if not exists (
                select 1 from profiles
                where id = auth.uid() and role = 'admin' and status = 'approved'
            ) then
                raise exception 'Only admins can change role or status';
            end if;
        end if;
    end if;
    return new;
end;
$$;

create trigger profiles_role_guard
    before update on profiles
    for each row execute function prevent_self_role_change();

-- ----------------------------------------------------------------------------
-- is_admin helper — used by RLS policies below
-- ----------------------------------------------------------------------------
create or replace function is_admin(uid uuid)
returns boolean
language sql
security definer
stable
set search_path = public
as $$
    select exists (
        select 1 from profiles
        where id = uid and role = 'admin' and status = 'approved'
    );
$$;

-- ============================================================================
-- daily_returns — shared reference series (admin-only write)
-- ============================================================================
create table daily_returns (
    date date primary key,
    gross_pl_pct numeric(10,6) not null,
    entry_mode return_entry_mode not null default 'percent',
    raw_balance numeric(14,2),
    entered_by uuid not null references profiles(id),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (entry_mode = 'percent' or raw_balance is not null)
);

create index idx_daily_returns_date on daily_returns(date desc);

create trigger daily_returns_set_updated_at
    before update on daily_returns
    for each row execute function set_updated_at();

-- ============================================================================
-- capital_changes — per-user
-- ============================================================================
create table capital_changes (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references profiles(id) on delete cascade,
    date date not null,
    amount numeric(14,2) not null,
    type capital_change_type not null,
    note text,
    created_at timestamptz not null default now(),
    check (amount > 0)
);

create index idx_capital_changes_user_date
    on capital_changes(user_id, date desc);

-- Monday-only rule for additions is enforced at the API layer (backend knows
-- the NYSE holiday calendar). The DB just stores valid rows.

-- ============================================================================
-- monthly_fees — per-user, auto-calc + optional manual override
-- ============================================================================
create table monthly_fees (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references profiles(id) on delete cascade,
    year int not null,
    month int not null check (month between 1 and 12),
    auto_amount numeric(14,2) not null,
    auto_deducted_on date not null,
    manual_amount numeric(14,2),
    manual_deducted_on date,
    carryforward_used numeric(14,2) not null default 0,
    carryforward_remaining numeric(14,2) not null default 0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (user_id, year, month),
    check (auto_amount >= 0),
    check (manual_amount is null or manual_amount >= 0),
    check (carryforward_used >= 0),
    check (carryforward_remaining >= 0)
);

create index idx_monthly_fees_user on monthly_fees(user_id, year desc, month desc);

create trigger monthly_fees_set_updated_at
    before update on monthly_fees
    for each row execute function set_updated_at();

-- ============================================================================
-- Row Level Security
-- ============================================================================
alter table profiles enable row level security;
alter table daily_returns enable row level security;
alter table capital_changes enable row level security;
alter table monthly_fees enable row level security;

-- ---- profiles -------------------------------------------------------------
create policy profiles_select_own_or_admin on profiles
    for select
    using (auth.uid() = id or is_admin(auth.uid()));

create policy profiles_update_own on profiles
    for update
    using (auth.uid() = id)
    with check (auth.uid() = id);

create policy profiles_admin_update on profiles
    for update
    using (is_admin(auth.uid()))
    with check (is_admin(auth.uid()));

-- Inserts happen via the handle_new_user() trigger (security definer).
-- No INSERT policy is intentionally given to end users.

-- ---- daily_returns --------------------------------------------------------
create policy daily_returns_select_authenticated on daily_returns
    for select
    using (auth.role() = 'authenticated');

create policy daily_returns_admin_all on daily_returns
    for all
    using (is_admin(auth.uid()))
    with check (is_admin(auth.uid()));

-- ---- capital_changes ------------------------------------------------------
create policy capital_changes_own_all on capital_changes
    for all
    using (user_id = auth.uid())
    with check (user_id = auth.uid());

create policy capital_changes_admin_read on capital_changes
    for select
    using (is_admin(auth.uid()));

-- ---- monthly_fees ---------------------------------------------------------
create policy monthly_fees_select_own_or_admin on monthly_fees
    for select
    using (user_id = auth.uid() or is_admin(auth.uid()));

create policy monthly_fees_update_own on monthly_fees
    for update
    using (user_id = auth.uid())
    with check (user_id = auth.uid());

-- Inserts/deletes of monthly_fees happen via the backend service role
-- (scheduled month-rollover job). No user-facing INSERT/DELETE policy.
