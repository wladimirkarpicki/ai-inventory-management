# Architecture Decision Records — ADR-001 (security hardening)

Status: **Proposed** — the owner/DM accepts, not the author.
Date: 2026-11-12.
Scope: the five open decisions in `SECURITY.md` that need an accepted
technical direction before any implementation lands. This directory is the
index; each decision is one numbered record.

| ADR | Decision | Closes (`SECURITY.md`) |
|-----|----------|------------------------|
| [0001](0001-persistent-login-lockout.md) | Persistent login lockout in a PostgreSQL table | "Login lockout is per-process and in-memory" (239–241) |
| [0002](0002-token-revocation.md) | Per-user `token_version` revocation, no blocklist | "Token invalidation is by existence, not revocation" (242–245) |
| [0003](0003-secret-key-rotation.md) | `kid` header + dual-key verification window | "Single symmetric key, no rotation" (246–248) |
| [0004](0004-metrics-exposure.md) | Fence `/metrics` off the published port | "`/metrics` … unauthenticated" (256–260) |
| [0005](0005-first-run-setup-token.md) | Opt-in `SETUP_TOKEN` for `/api/auth/setup` | "First-run setup is a race" (48–57) |

Every record cites the file and line it changes. Line numbers refer to the
tree this wave was written against (`main.py` 2,114 lines, `SECURITY.md` 287
lines, commit `c738066` on `main`).

## Rollout ordering

Schema lands before the code that reads it, because there is no migration
runner to order it for you (that tooling is gap 7 and is **not** decided
here). Each step is its own reviewable patch and is individually revertible.

1. **`migrations/006_login_attempts.sql` + `schema.sql` mirror.** DDL only,
   no application change. The test suite builds its database from
   `schema.sql` alone (`tests/conftest.py` 43–56), so the table must exist in
   `schema.sql`, not only in a migration file.
2. **Lockout read/write against that table** (replaces the three helpers at
   `main.py` 267–293). Cannot ship before step 1.
3. **`migrations/007_token_version.sql` + `schema.sql` mirror.** DDL only:
   `users.token_version INTEGER NOT NULL DEFAULT 0`.
4. **`token_version` enforcement** — claim in `create_token`
   (`main.py` 217–223), check in `get_current_user` (`main.py` 226–258), bump
   in `change_password` (`main.py` 385–409) and `reset_user_password`
   (`main.py` 526–544). Cannot ship before step 3.
5. **SECRET_KEY rotation** (`kid` + dual-key window). Deliberately after step
   4: steps 4 and 5 edit the same two functions, and landing the smaller diff
   first keeps each patch reviewable.
6. **`/metrics` fence.** Independent of steps 1–5; land it **before** the E3
   TLS proxy so the proxy never needs a `/metrics` rule.
7. **`SETUP_TOKEN` for first-run setup.** Independent; land it before the E3
   TLS proxy makes `/api/auth/setup` reachable from outside the host.

Steps 6 and 7 are independent of each other and of the database work. The
security-headers card (`object-src 'none'`, `upgrade-insecure-requests`, COOP,
CORP, `Permissions-Policy` at `main.py` 105–134) is independent of all seven
and is already scoped elsewhere.

## What this wave deliberately does not decide

- **Migration tooling** — no runner, no version table, no ordering check
  (`SECURITY.md` 269–272). Deferred to E2/E3. This wave only follows the
  existing convention: idempotent numbered SQL in `migrations/`, mirrored in
  `schema.sql`.
- **TLS termination** — no TLS in the app container (`SECURITY.md` 277–279).
  Deferred to E3. Steps 6 and 7 assume it is coming and are ordered for it.
- **CodeQL** — not configured (`SECURITY.md` 190–194). Moved into the
  baseline card by the scope decision, not this one.
- **CORS production origins** — only the two Vite dev origins today
  (`main.py` 93–102, `SECURITY.md` 253–255). Deferred to E4, because it needs
  an origin list from the owner.
- **The remaining security headers** (gap 1) — a separate card implements
  them; this wave only confirms that scope.
- **A per-token logout blocklist** — recorded in ADR-0002 as the follow-up if
  true multi-device logout is ever wanted. Not built here.
- **Password hashing parameters** — Werkzeug's default is accepted, not a gap
  (`SECURITY.md` 249–252).
- **README/SECURITY.md banner wording** — owner-gated by the scope decision;
  this wave does not touch banner text.

## Documentation hygiene for the implementing cards

Two claims go false the moment their ADR lands and must be updated in the
same patch, not later: `README.md` 176 ("attempt state is kept in process
memory, so it also resets when the server restarts") and `SECURITY.md`
239–241. `README.md` 177, `README.md` 151 and 153, `docs/OPERATIONS.md` 87 and
109–111, and `SECURITY.md` 242–248 and 256–260 carry the same exposure.

Separately, and not this wave's to fix: `SECURITY.md` 235–238 still says
"Security headers are documented but not implemented", which contradicts the
same file at 138–148. The security-headers card should correct that line.
