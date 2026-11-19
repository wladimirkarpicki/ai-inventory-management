# FREEZE: ai-inventory-management

**Status: FROZEN (2026-11-19).** Active development is complete and the board
is closed. The GitHub repository is **not archived**: archiving requires the
owner's explicit approval, requested through a GitHub issue (see
§7). Until that decision, this repository is the read-only record of the
project.

## 1. What this is

A single-stack inventory management application: FastAPI backend, React SPA
frontend, PostgreSQL database, optional LLM forecast refinement (NVIDIA API,
with a regression fallback when the key is absent), packaged with Docker
Compose. Delivery history lives on the `ai-inventory-management` kanban board
(closed); the retro-freeze audit and e2e validation are the close-out evidence.

## 2. Final repository state

- Freeze head: `457685bf811527ec6c58207e2ccb0635bb71a0a1` on `main`
  (SECURITY.md CodeQL correction, fixes #78), on top of `83e9839`
  (ADR-001 landing, fixes #80), on top of `c26aaae` (PR #70 squash merge).
- Working tree clean; `main` and `origin/main` identical; no open PRs;
  no open issues.
- Audit issues #78-#83 all closed with landed fixes (see §5).

## 3. Stack versions (final)

- **Backend** (python:3.13-slim image): fastapi >= 0.162.5,
  uvicorn >= 0.54.0, psycopg 3.3.8, PyJWT >= 2.15.1, Werkzeug >= 3.1.9,
  prometheus-fastapi-instrumentator >= 8.1.0, python-dotenv, python-multipart.
- **Frontend**: react ^19.3.1, vite ^8.3.8, tailwindcss ^4.3.5,
  typescript ^7.0.2, pnpm 11 (image build).
- **Database**: postgres:16 (no published port by design, see the runbook).
- **Quality gates at freeze**: ruff check/format, mypy, bandit, pip-audit all
  clean; backend pytest 174 passed on the final tree (158/158 at the audit
  baseline on c738066, plus security-header and LLM-parity tests landed after);
  frontend tsc + 27 vitest tests + production build clean.

## 4. CI state

Branch protection on `main` requires ten checks: `pytest`, `frontend`,
`docker`, `Bandit (SAST)`, `Ruff (Lint & Format)`, `Mypy (Type Check)`,
`pip-audit (SCA)`, `Analyze (python)`, `Analyze (actions)`,
`Analyze (javascript-typescript)`.

All ten were verified **success** on the freeze head `457685b` via the
check-runs API (2026-11-19). CodeQL runs via the repository default setup
(actions, javascript-typescript, python, default query suite); three Analyze
checks gate merges to `main`. At the audit: 0 code-scanning alerts, 0
Dependabot alerts.

## 5. Known issues and their disposition (all closed)

| # | Severity | Finding | Disposition |
|---|----------|---------|-------------|
| 78 | HIGH | SECURITY.md claimed "There is no CodeQL analysis" while the default setup is active and gating | Fixed in `457685b`; owner closed 2026-11-19 |
| 79 | MEDIUM | QA-approved security-header hardening never landed | Landed `f82d203` (CSP extras, COOP/CORP, Permissions-Policy) with regression tests |
| 80 | MEDIUM | ADR-001 decisions never landed; docs/adr/ missing | Landed `83e9839` (5 ADRs + index, status Proposed) |
| 81 | MEDIUM | Local clone 2 commits ahead of origin (docker runbook) | Pushed `3412b41` + `918865b` |
| 82 | LOW | SECURITY.md self-contradiction on headers | Resolved with the #79 landing |
| 83 | LOW | PR hygiene: PR #70 + 7 Dependabot PRs undecided | #71-#77 merged, #70 squash-merged after QA round-2 approval |

Residual notes (not defects):

- The freeze host could not boot the compose stack (Docker engine service
  stopped, non-elevated shell). The e2e validation substituted a full local
  stack (PostgreSQL 16.10 + uvicorn serving the built SPA on 127.0.0.1:8000)
  and the compose boot itself was verified healthy earlier (2026-11-15,
  recorded in the runbook §4).
- Remote branches `feat/ai-refinement-parity`, `docs-align-with-code`,
  `fix/env-consolidation` and two `dependabot/*` branches remain after their
  merges; deleting them is post-freeze hygiene, not required for correctness.
- This file is the only commit the freeze makes beyond the audit fixes.

## 6. How to reboot the stack

Full Docker path (details in [DOCKER-RUNBOOK.md](DOCKER-RUNBOOK.md), day-to-day
ops in [OPERATIONS.md](OPERATIONS.md)):

```bash
# Engine must be running: `docker version` must show a Server section.
cp .env.template .env
python -c "import secrets; print(secrets.token_hex(32))"   # set as SECRET_KEY, min 32 chars
docker compose config        # must exit 0
docker compose build
docker compose up -d
docker compose ps            # db and app must both be healthy
```

App: http://127.0.0.1:8000 (loopback only). Optional monitoring:
`docker compose --profile monitoring up -d` (Prometheus + Grafana on
127.0.0.1:3000). Smoke: `POST /api/auth/setup` for the first admin, then
`python scripts/check_spa.py` and `SEED_USER=... SEED_PASS=... python scripts/check_api.py`.
Teardown: `docker compose down` (keep data) or `docker compose down -v`
(nuclear).

No-Docker fallback (validated as the e2e substitute): PostgreSQL 16.10 +
uvicorn serving the API and the built SPA on 127.0.0.1:8000.

## 7. Archive status

Not archived. Approval requested from the owner via a GitHub issue on this
repository; the freeze board card carries the same summary. If approved, the
archive step is one API call (`PATCH /repos/{owner}/{repo} {"archived": true}`)
and this file's status line should be updated in the same motion.