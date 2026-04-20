# Vestige Dashboard — Backend

FastAPI service. Talks to Supabase (Postgres + Auth). Verifies Supabase JWTs
on every protected request and runs with RLS applied via a per-request
user-scoped client.

## First-time setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # then fill in Supabase values
```

Before the backend can reach the DB you need a Supabase project and the
initial migration applied — see [../supabase/README.md](../supabase/README.md).

## Run

```bash
uvicorn app.main:app --reload --port 8007
```

- Health check: http://localhost:8007/health
- Interactive docs: http://localhost:8007/docs

## Test

```bash
pytest                               # unit tests (calc, holidays)
pytest -k fee                        # run a subset
pytest -vv --tb=short                # verbose output
```

The pure-logic tests (in `tests/test_calc.py` and `tests/test_holidays.py`)
don't need Supabase running — no network, no DB.

## Layout

```
app/
├── main.py            # FastAPI app factory, CORS, router wiring
├── config.py          # env-backed Settings
├── auth.py            # JWT verification + role/approval gates
├── db.py              # Supabase client factory (anon, service, per-user)
├── calc.py            # Pure calc engine (compounding, fees, forecast)
├── holidays.py        # NYSE trading calendar
├── schemas.py         # Pydantic request/response models
└── routers/
    ├── profiles.py    # /profiles (self + admin approval)
    ├── returns.py     # /returns  (shared daily series; admin writes)
    ├── capital.py     # /capital  (per-user contributions/withdrawals)
    ├── fees.py        # /fees     (per-user monthly fees + override)
    └── dashboard.py   # /dashboard (summary KPIs, history)
```

## Status

Scaffold only — all router endpoints currently return 501 (Not Implemented).
Core math (`calc.py`, `holidays.py`) is implemented and tested.

Next steps (not yet done):
- Wire router handlers to Supabase (profiles/me + returns list first)
- Monthly fee rollover job (scheduled via Supabase cron or Railway cron)
- Validation of the Monday rule for capital additions
