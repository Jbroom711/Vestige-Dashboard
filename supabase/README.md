# Supabase setup

## First-time setup

1. Create a new Supabase project at https://supabase.com/dashboard
2. In the SQL Editor, open and run `migrations/20260419000000_initial_schema.sql`
3. Enable Email auth in **Authentication → Providers** (disable "Confirm email" if you want to skip the verification step during dev)
4. **Bootstrap the first admin** — after you sign up through the app once, run this in the SQL Editor (replace with your email):

   ```sql
   update profiles
   set role = 'admin', status = 'approved'
   where email = 'you@example.com';
   ```

   From then on, that admin account can approve pending viewer accounts by flipping `profiles.status` to `approved` (either via the app UI once built, or directly in the SQL Editor).

## Environment values to copy

From **Project Settings → API**:
- `SUPABASE_URL` → `NEXT_PUBLIC_SUPABASE_URL` (frontend) and `SUPABASE_URL` (backend)
- `anon` key → `NEXT_PUBLIC_SUPABASE_ANON_KEY` (frontend)
- `service_role` key → `SUPABASE_SERVICE_KEY` (backend only — never expose this client-side)
- `JWT Secret` (under **Project Settings → API → JWT Settings**) → `SUPABASE_JWT_SECRET` (backend)

## Running subsequent migrations

New migration files go in `migrations/` with a timestamped name like
`YYYYMMDDHHMMSS_description.sql`. Apply them in order via the SQL Editor or the
Supabase CLI (`supabase db push` after `supabase link`).
