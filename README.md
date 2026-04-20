# Vestige Dashboard

A personal investment tracking dashboard for a commission-based trading platform. Tracks daily P&L, platform fees, capital contributions/withdrawals, and forecasts year-end returns.

## Stack

- **Frontend:** Next.js (App Router, TypeScript) — port `3007`
- **Backend:** FastAPI (Python 3.11+) — port `8007`
- **Database & Auth:** Supabase (Postgres + Auth)

## Business rules

- **Commission:** Platform takes 40% of net monthly gains
- **Fee accrual:** Accrues daily throughout the month based on MTD gross P&L
- **Fee deduction:** Lump-sum deducted from reported balance on first trading day of following month
- **Loss carryforward:** Monthly losses offset future gains indefinitely (no expiration)
- **Trading days:** NYSE calendar (weekdays excluding market holidays)
- **Capital additions:** Mondays only (and Monday must be a trading day)
- **Capital withdrawals:** Any trading day
- **Principal denominator:** Deployed capital = starting balance + net capital contributions

## Getting started

### Prerequisites

- Node.js 20+ and pnpm (or npm)
- Python 3.11+
- A Supabase project (free tier is fine)

### Setup

```bash
# 1. Backend
cd backend
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env         # fill in Supabase values
uvicorn app.main:app --reload --port 8007

# 2. Frontend (new terminal)
cd frontend
pnpm install
cp .env.local.example .env.local   # fill in Supabase values
pnpm dev
```

Frontend: http://localhost:3007
Backend docs: http://localhost:8007/docs

### Environment variables

**`backend/.env`**
```
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
SUPABASE_JWT_SECRET=...
FRONTEND_ORIGIN=http://localhost:3007
```

**`frontend/.env.local`**
```
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
NEXT_PUBLIC_API_URL=http://localhost:8007
```

## Project structure

```
Vestige_Dashboard/
├── backend/              # FastAPI app
│   └── app/
│       ├── main.py
│       ├── calc.py       # Fee + forecast engine (tested)
│       ├── holidays.py   # NYSE calendar
│       ├── models.py     # Pydantic + SQLAlchemy
│       └── routers/
├── frontend/             # Next.js app
│   ├── app/
│   ├── components/
│   └── lib/
├── CLAUDE.md             # Context for Claude Code
└── README.md
```

## Common commands

| Task | Command |
|---|---|
| Run backend | `cd backend && uvicorn app.main:app --reload --port 8007` |
| Run frontend | `cd frontend && pnpm dev` |
| Run tests | `cd backend && pytest` |
| Lint frontend | `cd frontend && pnpm lint` |
| Type-check frontend | `cd frontend && pnpm tsc --noEmit` |

## License

Private / personal use.
