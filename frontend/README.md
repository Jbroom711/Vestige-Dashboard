# Vestige Dashboard — Frontend

Next.js 16 (App Router) + React 19 + TypeScript + Tailwind 4. PWA-installable.
Handles Supabase auth entirely on the client + proxy (via `@supabase/ssr`),
then talks to the FastAPI backend on port 8007 for everything else.

## First-time setup

```bash
cd frontend
npm install
cp .env.local.example .env.local     # fill with Supabase + API URL
```

You need a Supabase project (see [`../supabase/README.md`](../supabase/README.md))
and the backend running on :8007 (see [`../backend/README.md`](../backend/README.md)).

## Run

```bash
npm run dev       # dev server on http://localhost:3007
npm run build     # production build
npm start         # run production build (also on 3007)
npm run lint      # ESLint
npm run typecheck # tsc --noEmit
```

## Route map

```
app/
├── layout.tsx                 # root shell + PWA service worker registration
├── page.tsx                   # redirect -> /dashboard
├── globals.css                # Tailwind 4 entry: @import "tailwindcss"
├── manifest.ts                # PWA manifest
├── (auth)/
│   ├── layout.tsx             # centered card layout
│   ├── login/page.tsx
│   └── signup/page.tsx
├── auth/callback/route.ts     # Supabase OAuth / email verification callback
├── pending/page.tsx           # shown to users awaiting admin approval
└── (app)/
    ├── layout.tsx             # header + View/Entry nav + sign-out
    ├── dashboard/page.tsx     # KPIs + charts (View mode)
    └── entry/page.tsx         # forms for P&L / capital / fee (Entry mode)

proxy.ts                        # Next 16 middleware replacement — auth gate
lib/
├── supabase/browser.ts
├── supabase/server.ts
├── api.ts                      # snake<->camel, bearer auth, fetch wrapper
├── types.ts                    # shared API types
└── format.ts                   # money / percent / date formatters
components/
├── AppNav.tsx                  # View/Entry tabs
├── SignOutButton.tsx
└── ServiceWorkerRegistrar.tsx
```

## Notes for future agents

- This repo is pinned to Next.js 16, which has breaking changes from 14/15.
  See [`AGENTS.md`](AGENTS.md). Always consult `node_modules/next/dist/docs/`
  before touching Next-specific APIs.
- Auth gate lives in `proxy.ts` at the project root (NOT `middleware.ts`).
- `params`, `searchParams`, and `cookies()` are all async — always await.
- Tailwind 4 uses `@import "tailwindcss"`, not the old `@tailwind` directives.
- UI uses plain Tailwind with semantic zinc colors. Any component library
  (shadcn/ui, headlessui, etc.) should be discussed first — it's a UI
  decision per the root `CLAUDE.md` guardrails.

## Status

Scaffold only. UI renders but no data is wired up — dashboard and entry
pages show placeholder cards. Next steps (not yet done):
- Fetch `/dashboard/summary` from Server Components via `lib/api.ts`
- Entry forms (daily P&L, capital change, fee override)
- Recharts line chart for balance history
- PWA icons (`public/icons/icon-192.png`, `public/icons/icon-512.png`)
