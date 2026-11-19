# Docker runbook — ai-inventory-management

Build, run, and end-to-end test the dockerized stack on this host
(Windows, 8 GB RAM, i7-3615QM). Written 2026-11-14 for task t_bdb15fb3.
Day-to-day operations (backups, restore, upgrades, troubleshooting) live in
[OPERATIONS.md](OPERATIONS.md); this file is the build-run-verify sequence and
does not repeat them.

## 0. Prerequisites — the engine must be running

`docker version` must show a **Client** *and* a **Server** section. On this
host the Docker client was installed but WSL had no distribution, so Docker
Desktop could not start ("Docker Desktop is unable to start"). Owner-side fix:

```powershell
wsl --install -d Ubuntu      # elevated shell, then reboot if asked
# start Docker Desktop, wait for the engine
docker version               # must show a Server section
```

`docker compose config` (YAML validation) works without the daemon; every
build/run command below needs it. Validated 2026-11-14 with a dummy
SECRET_KEY: `docker compose config` exits 0.

## 1. Environment

`.env` is gitignored and never committed. `.env.template` is the single
source of truth (`cp .env.template .env`, then set SECRET_KEY with
`python -c "import secrets; print(secrets.token_hex(32))"` — min 32 chars or
the app refuses to start). Verify with `docker compose config` (exit 0):
as of 2026-11-15 the template is dotenv-safe — it used to carry prose lines
that made `docker compose config` reject the copied `.env`. DATABASE_*
default to postgres/postgres/inventory, which matches compose;
NVIDIA_API_KEY is optional (forecast falls back to regression without it).
Only SECRET_KEY is required.

## 2. Build and run

```bash
docker compose build          # one project at a time on this 8 GB host
docker compose up -d
docker compose ps             # db and app must both be healthy
```

- App: http://127.0.0.1:8000 (loopback only).
- Database: postgres:16, **no published port** by design — publishing through
  the Docker userland proxy timed out under test-suite load. Host tools reach
  it through the network instead (§3).
- Health: app HEALTHCHECK probes /api/ready (liveness /api/health +
  readiness /api/ready with a real DB query); `docker compose ps` shows
  `State: healthy` once PostgreSQL answers.
- Monitoring (opt-in): `docker compose --profile monitoring up -d`
  (Prometheus + Grafana on 127.0.0.1:3000).

## 3. End-to-end test

**Scope ruling (owner, 2026-11-14): do NOT re-run the full e2e suite against
this stack.** The qa audit (card t_2249fa83, done) is the testing evidence:
158/158 pytest, lint/format/mypy/bandit/pip-audit clean, frontend tsc + 27
vitest + vite build clean, CI green — all executed against a real PostgreSQL
16.10 instance. The in-scope check on this card is: build + up + both
services healthy, plus the quick HTTP smoke below.

Required smoke (runs on the host, stdlib only):

```bash
# 0. stack from §2 must be up and healthy
# 1. first admin — the stack starts with no users; POST /api/auth/setup is
#    first-user-wins, no token
curl -sS -X POST http://127.0.0.1:8000/api/auth/setup \
  -H 'Content-Type: application/json' \
  -d '{"username": "e2e-admin", "password": "e2e-pass-1234"}'

# 2. HTTP checks against the running stack
python scripts/check_spa.py      # SPA mount + /api/health + /api/products at the root
SEED_USER=e2e-admin SEED_PASS=e2e-pass-1234 python scripts/check_api.py
# check_api logs in as the first admin and prints dashboard stats + one page
# of products (zeros are expected on a fresh database; a 200 from both
# authenticated endpoints proves the API talks to the stack's PostgreSQL)
```

Evidence to capture: the two script outputs, `docker compose ps` (healthy),
and `docker compose logs app | tail -50` (no tracebacks).

Optional full-stack path (only when a deliberate re-run is wanted; the db
publishes no port, so data seeding and pytest run inside the network):

```bash
./scripts/run_in_net.sh python scripts/seed_demo_data.py   # builds Dockerfile.dev on first use
./scripts/run_in_net.sh python -m pytest -q                # ~158 tests; CI parity
```

## 4. Notes from the audit (do not re-litigate)

- Two defects are already open from the audit card (unvalidated LLM forecast
  values reaching the API contract; unbounded login-attempt map for ghost
  usernames). They do not block build/run/e2e; they are fixable separately.
- `SECRET_KEY` mismatch between .env and a running container invalidates
  tokens on restart — generate once and reuse.
- The dev image (`Dockerfile.dev`, uvicorn --reload) is for iteration only;
  the e2e evidence above uses the production image.
- Verified on this host 2026-11-15 (task t_bdb15fb3): `docker compose build`
  exit 0, `docker compose up -d` → db + app healthy, `check_spa.py` green
  (SPA + health 200, products 401 unauthenticated), first admin created via
  /api/auth/setup, `check_api.py` login + dashboard + products all 200 from
  the stack's PostgreSQL. Evidence preserved in the task evidence dir.

## 5. Teardown / reset

```bash
docker compose down          # stop, keep data
docker compose down -v       # nuclear: drop pgdata (first init re-runs schema.sql)
```

## 6. Files

- `Dockerfile` — 2 stages: node:22-alpine builds the SPA (pnpm 11,
  tsc -b && vite build), python:3.13-slim serves it via uvicorn (non-root).
- `Dockerfile.dev` — dev image with hot reload and dev dependencies.
- `compose.yml` — db + app + opt-in monitoring profile, pinned project name.
- `scripts/run_in_net.sh` — runs any host command on the compose network
  (builds Dockerfile.dev on first use).