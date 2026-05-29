-- Single-row table where the daily scraper stores the latest auth cookie
-- for vhg.app, plus when it was last refreshed. Lets WordPress's "sliding
-- session" pattern keep the cookie alive indefinitely: each successful
-- scrape captures the refreshed Set-Cookie response and updates this row,
-- so the user only has to paste a fresh cookie once at bootstrap (and
-- again after any extended outage).
--
-- The table is keyed by `name` so other scrapers (or other broker accounts)
-- can share the same schema later without a migration.

create table if not exists scraper_cookies (
  name text primary key,
  cookie text not null,
  refreshed_at timestamptz not null default now()
);

alter table scraper_cookies enable row level security;

-- Service role only; nothing user-facing reads or writes this.
create policy "scraper_cookies service-only"
  on scraper_cookies for all
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');
