# AGENTS.md

Guidance for AI coding agents (Claude Code, Codex, Cursor, etc.) working in this repository.

## Project

Nextsci Agents is an open-source platform for building, running, and inspecting AI agents. Builders define agents on the web (a model, instructions, tools, and knowledge), the backend runs them, and every run can be followed step by step. It is a monorepo with two independent apps. Each app has its own dependencies and lockfile, and there is no root package manager.

## Repository layout

- `backend/` — Django 6 API on PostgreSQL (`config/` is the project package). Python venv in `backend/.venv`, deps pinned in `requirements.txt`. Settings come from environment variables, loaded from the repo-root `.env` for local runs.
  - `config/settings/` — `base.py` shared, `dev.py` (default, DEBUG on), `prod.py` (DEBUG off, requires `DJANGO_SECRET_KEY`, HTTPS-only). Select with `DJANGO_SETTINGS_MODULE`.
  - `config/checks.py` — Django system checks over every model in `apps/`: table, column, index, and constraint names are snake_case, so `manage.py check` fails on a name such as `agents_chatsession`. `config/apps.py` loads them. The rule: "Names in the database" in `.agents/backend.md`.
  - `apps/<app>/` — one Django app per domain in a fixed layout (`models.py`, `services.py`, `selectors.py`, `api/`, `tests/`). Create apps with `scripts/new-backend-app.sh <name>`. Layout, import rules, and the planned domain map: `.agents/backend.md`.
  - `.importlinter` — import contracts that `lint-imports` checks; `requirements-dev.txt` adds dev tools on top of `requirements.txt`.
  - `apps/accounts/` — email-login custom `User` (`AUTH_USER_MODEL = "accounts.User"`) and JWT auth.
  - `apps/integrations/` — third-party accounts a user connects through OAuth, starting with Google Calendar. `catalog.py` lists the integrations (URLs and the list endpoint come from it), `google.py` calls Google's OAuth endpoints with the standard library, and `fields.py` encrypts stored tokens with the Fernet key in `INTEGRATIONS_ENCRYPTION_KEY`. Google Calendar needs `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET`; `.env.example` says how to get them.
  - API is versioned under `/api/v1/`. Auth: `POST auth/token/` (email, password → access, refresh), `POST auth/token/refresh/`, `GET auth/me/`. Integrations: `GET integrations/`, `POST integrations/<id>/connect/` (→ `authorization_url`), `GET integrations/<id>/callback/` (Google redirects the browser here, so it takes no JWT, then redirects to `/integrations?connected=<id>` or `?error=<code>`), `DELETE integrations/<id>/`. DRF requires a JWT bearer token by default.
  - `apps/agents/` — chat sessions saved in Postgres (`agents_chat_session`, one row per conversation, and `agents_chat_message`, one row per message). Every endpoint is scoped to the signed-in user: `GET agents/sessions/` (newest activity first, each with a `title` read from its first user message), `POST agents/sessions/`, `GET agents/sessions/<id>/` (with `messages`), `DELETE agents/sessions/<id>/`, and `POST agents/sessions/<id>/messages/` (`{content}` → `{messages: [user, assistant]}`), which sends the saved history to OpenRouter (`openrouter.py`, with `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` from `.env`) and saves both messages only when the model answers (503 while the key is unset, 502 when OpenRouter fails). The `/agents` screen (`dashboard/src/features/agents/`) is a chat on these endpoints.
- `dashboard/` — Vite + React + TypeScript app that self-hosters deploy. Opens on sign-in, has no landing page. Calls the API on its own origin (`/api`); in development Vite proxies `/api` to Django (`API_PROXY_TARGET`, default `http://localhost:8000`). Every screen has a URL (`/sign-in`, `/agents`, `/agents/<id>` for a saved chat, `/runs`, `/tools`, `/knowledge`, `/integrations`). `src/app/` holds the TanStack Router route tree and its sign-in guards (`router.tsx`) and the signed-in shell (`shell/AppShell.tsx`, its sidebar sections listed in `shell/sections.ts`). How to add a screen: the Routing section of `.agents/react.md`. Each domain lives in `src/features/<name>/`: server calls in `api.ts`, its hooks and TanStack Query in `hooks/`, its components in `components/`. `features/auth/` is the first, `features/agents/` lists the saved chats beside the open chat, and `features/integrations/` lists the integrations and connects or disconnects each one. Shared code: the stored session and `authedFetch`, which sends the access token and refreshes it once on a 401, in `src/api/` (every feature calls the API as the signed-in user through it, and throws `SessionExpired` when the refresh fails too, which `src/main.tsx` turns into a trip to sign-in); shadcn/ui components on Tailwind CSS v4 in `src/components/ui/`, other shared components in `src/components/`, shared hooks in `src/hooks/` (the persisted theme choice is a zustand store in `src/hooks/useTheme.ts`), and query keys in `src/lib/queryKeys.ts`. npm. The Vite dev server answers every path with `index.html`. A production static host must do the same for any path that is not a file, or deep links and reloads return 404.
- `dashboard/src/design.css` — the design tokens (each color a `light-dark()` pair), base styles, and shared components. `DESIGNS.md` documents every value.
- `scripts/check-design.sh` — enforces the UI rules in `.agents/ui.md`; `scripts/check.sh` runs it
- `scripts/check-react.sh` — enforces the React code layout in `.agents/react.md`; `scripts/check.sh` runs it
- `dashboard/AGENTS.md`, `backend/AGENTS.md` — per-app pointers to the rules below, loaded by agents working inside each app
- `scripts/screenshot.mjs` — full-page screenshot of a running app at an exact width, including widths under 500px (`LOCAL_STORAGE` seeds a signed-in session for screens behind sign-in)
- `scripts/e2e/theme.mjs` — end-to-end test of the System, Light, and Dark theme switch against the running dashboard
- `scripts/e2e-dashboard.sh` — end-to-end dashboard test in Chrome against a throwaway database: sign-in, URL routing (deep links, the sign-in redirect, back, reload, not-found), the sidebar, the theme switch, the Agents chat (saved chats open at their own address and survive a reload, a failed send saves nothing, the phone sheet, delete with its confirmation), the Integrations screen and its connect callback, and sign-out with its confirmation dialog (`COLOR_SCHEME=light|dark` sets the screenshots' theme; `E2E_API_PORT`, `E2E_DASH_PORT`, `E2E_CDP_PORT` move its ports); drives `scripts/e2e/signin.mjs`. It seeds two chats with `scripts/e2e/seed-chats.py` and runs the backend with an empty `OPENROUTER_API_KEY`, so it never calls a model
- `scripts/make-oauth-client.sh [project-id]` — sets up the Google Calendar OAuth client: gcloud signs in, creates the project if missing, and enables the Calendar API, then the script opens the Console pages for the consent screen and the Web client (Google has no CLI or API for that client), and writes `GOOGLE_OAUTH_*` and a missing `INTEGRATIONS_ENCRYPTION_KEY` into `.env`. Safe to rerun
- `scripts/check-docs.sh` — fails when a doc in `.agents/` is not indexed or a relative markdown link breaks; `scripts/check.sh` runs it
- `compose.yaml` — runs Postgres, backend, and dashboard together
- `.env.example` — every config variable; copy to `.env` (gitignored)
- `.moon/workspace.yml`, `backend/moon.yml`, `dashboard/moon.yml` — moon task runner config
- `.prototools` — pins node for proto, which moon puts first on task PATH
- `scripts/check.sh` — installs, typechecks, tests, and builds both apps; run before declaring work done
- `README.md` — project overview
- `docs/admin.md` — how-to for creating the master admin (Django superuser), signing in to the dashboard, and adding accounts. Update it when account or sign-in behavior changes.
- `AGENTS.md` — this file; the single source of truth for agent instructions
- `CLAUDE.md` — imports this file for Claude Code
- `.agents/` — agent rules, workflow, and lessons; index in `.agents/README.md`

## Agent docs

Detailed guidance lives in `.agents/`. Start with [.agents/README.md](.agents/README.md): it holds the rules for every change, says which doc covers which area, and lists every enforced check. Read the relevant file before working in that area:

- [.agents/workflow.md](.agents/workflow.md) — set up, run the apps, branch and commit, and verify each kind of change. Read it before your first change.
- [.agents/worktrees.md](.agents/worktrees.md) — one git worktree per feature with `.agents/worktree.sh` (`new`, `ship`, `clean`), shipped to `origin/dev` after `scripts/check.sh` passes.
- [.agents/lessons.md](.agents/lessons.md) — mistakes this project already made, with the symptom, the cause, and the fix. Read the section for your area.
- [DESIGNS.md](DESIGNS.md) — design system: colors, type, components, the sign-in screen, and the dashboard shell. Read it before any UI work in `dashboard/`.
- [.agents/ui.md](.agents/ui.md) — rules that keep the dashboard on the design, and how to verify UI work. Read it before changing `dashboard/src/`.
- [.agents/backend.md](.agents/backend.md) — Django layout: one app per domain, `api` → `services`/`selectors` → `models`, the domain dependency order, the planned apps, and the agent runtime. Read it before changing `backend/`.
- [.agents/react.md](.agents/react.md) — React code layout for the dashboard: one folder per feature in `src/features/`, custom hooks and TanStack Query only in hook folders, server calls only in API modules, and no imports between features. Read it before writing React code in `dashboard/`.

## Commands

Verify everything: `./scripts/check.sh`

Run backend (:8000) and dashboard (:5174) together: `moon run :dev`. Each project's `install` task runs first: it creates `backend/.venv` and installs `requirements.txt`, and runs `npm ci` in `dashboard/` when `package-lock.json` changed. Needs a running PostgreSQL configured in `.env`.

Apply migrations: `moon run backend:migrate`. Create the master admin: `moon run backend:createsuperuser` (installs and migrates first, then prompts for email and password; add `-- --noinput` with `DJANGO_SUPERUSER_EMAIL` and `DJANGO_SUPERUSER_PASSWORD` set to skip the prompts).

Whole stack in Docker: `cp .env.example .env && docker compose up --build`. Ports: backend 8000, dashboard 5174, Postgres `POSTGRES_HOST_PORT` (default 5432).

Backend (`cd backend`):
- Setup: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`, then fill the `POSTGRES_*` values in the repo-root `.env` for a running Postgres
- Migrate: `.venv/bin/python manage.py migrate`
- Run: `.venv/bin/python manage.py runserver`
- Check: `.venv/bin/python manage.py check`
- Import rules: `.venv/bin/lint-imports` (needs `pip install -r requirements-dev.txt`)
- New app: `scripts/new-backend-app.sh <name>` (from the repository root)
- Test: `.venv/bin/python manage.py test` (creates a throwaway test DB, so the Postgres user needs CREATEDB)
- Add a dependency: `.venv/bin/pip install <pkg>`, then add `<pkg>==<version>` by hand to `requirements.txt` (runtime) or `requirements-dev.txt` (tools). Do not `pip freeze` into `requirements.txt`: the venv also holds the dev tools.

Dashboard (`cd dashboard`):
- Setup: `npm install`
- Run: `npm run dev` (http://localhost:5174; needs the backend on :8000)
- Lint: `npm run lint` (oxlint)
- Build + typecheck: `npm run build`

## Conventions

The rules for every change are in `.agents/README.md`. In short:

- Keep changes small and focused; don't add unrelated refactors.
- Add or update tests alongside behaviour changes.
- Don't commit secrets, credentials, model provider API keys, or large data files.
- Document new commands and structure in this file when you add them.
