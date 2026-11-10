# Security Audit

> **Scope note.** This audit describes a **prototype**, not a hardened
> production system. The properties below are what the code actually does
> today, measured rather than assumed. They are a reasonable baseline for a
> local demo and are not a claim that the application is safe to expose to
> untrusted networks or real data.

This document audits the security behaviour of the FastAPI backend in `main.py`,
its database access, authentication, authorisation, the optional LLM call, and
what CI enforces. It reflects the code as reviewed on this branch. Every claim
below is tied to what is in the source; anything that could not be verified, or
that contradicts the [README](README.md), is stated explicitly rather than
assumed. The feature list itself lives in the README and is not repeated here.

## Authentication

- Identity travels as a **bearer token**. The scheme is `HTTPBearer`
  (`auto_error=False`), consumed in `get_current_user`. A request with no
  `Authorization` header gets `401 "Not authenticated."`; a token that fails to
  decode gets `401 "Invalid or expired token."` (any `jwt.PyJWTError`, which
  covers a bad signature, a malformed token, and an expired one).
- Tokens are **HS256 JWTs** signed with `SECRET_KEY` (`create_token`). The
  payload carries `sub` (the user id as a string), `username`, and
  `exp = now + 12 hours` (`TOKEN_TTL_HOURS = 12`). PyJWT validates `exp` on
  decode, so a token is rejected 12 hours after it was issued. There is no
  refresh token and no server-side session store.
- **Token invalidation for deleted accounts.** `get_current_user` re-reads the
  account from the database on every request
  (`SELECT id, username, role FROM users WHERE id = %s`). If the row is gone it
  raises `401 "Account no longer exists."`. So when an admin deletes an account,
  its outstanding tokens stop working on the very next request.
- **Malformed subject claims are rejected, not crashed.** `sub` is
  attacker-controlled once a token is signed, so a token carrying
  `sub = "not-a-number"` used to raise an unhandled `ValueError` and surface as
  **HTTP 500**. The conversion is now wrapped and returns
  `401 "Invalid or expired token."`, matching every other invalid credential.
  Two regression tests forge a malformed and a missing subject and assert 401.
- **State transitions are single conditional statements.** `receive_order` and
  `cancel_order` previously read an order's status and then updated stock and
  the status in separate statements. Two concurrent receives of the same order
  both passed the same check and both added the quantity, double-counting
  stock. Both endpoints now transition with
  `UPDATE ... WHERE id = %s AND status = 'ordered' RETURNING`, and stock is
  only touched when that UPDATE returns a row; the loser gets `409 Conflict`
  and rolls back. The whole receive path (stock, movement, status) is still one
  transaction.
- **First-run setup is a race, not a guessing problem.** `POST /api/auth/setup`
  creates the initial admin while no user exists, and it will do so for
  *anyone* who reaches it with any password of 8+ characters. Rate limiting was
  considered and rejected here: it cannot work, because the login limiter only
  trips when a failed attempt is registered and setup registers none, and it
  would not close the real risk anyway. The endpoint accepts any password, so
  an attacker does not brute-force anything, they simply POST their own and win
  a race with the legitimate operator. The control is operational: run setup
  promptly on an instance reachable by anyone else, and add a setup token if a
  shared deployment ever needs one.
- **Login rate limiting.** Failed sign-ins are counted per username in an
  in-process map. `LOGIN_MAX_ATTEMPTS = 5` failures for one username lock that
  username for `LOGIN_LOCKOUT_SECONDS = 15 * 60` (15 minutes); a locked login
  returns `429 "Too many failed attempts. Try again in 15 minutes."`. A
  successful sign-in clears the counter for that username. The counter is a fixed
  15-minute window anchored at the first failure (`first_ts`): while the window
  has not elapsed the failed attempts accumulate, and once it has, the entry is
  discarded and the count starts over. The state lives in process memory, so it
  also resets when the process restarts.

## Authorisation

- There are exactly two roles, `user` and `admin`, and both values are validated
  on create and update (`data.role not in ("user", "admin")` is rejected).
- **Server-side role check.** `require_admin` is a dependency that raises
  `403 "Admin only."` when `user["role"] != "admin"`. It guards every account
  management endpoint: `GET/POST /api/users`, `PATCH /api/users/{id}`,
  `DELETE /api/users/{id}`, and `POST /api/users/{id}/password`. This runs on the
  server for every request, so a regular user gets `403` on those endpoints
  regardless of what the SPA displays. Product, brand, order and analytics
  endpoints require a signed-in user (`get_current_user`) but not the admin role.
- **Last-admin protection.** The last remaining admin cannot be demoted or
  deleted. In `update_user`, demoting an admin is refused with
  `400 "The last remaining admin cannot be demoted."` when the target is an
  admin, the new role is not admin, and the admin count is 1. In `delete_user`,
  `400 "The last remaining admin cannot be deleted."` under the same condition.
  Both count admins with `SELECT COUNT(*) FROM users WHERE role = 'admin'`.
- **Self-delete protection.** `delete_user` refuses to delete the account you
  are signed in with: `400 "You cannot delete yourself."`
  (`user_id == admin["id"]`).
- **Password change versus reset.** The self-service change
  (`POST /api/auth/password`) requires the current password
  (`check_password_hash`), while the admin reset
  (`POST /api/users/{id}/password`) sets a new hash without the old password,
  matching the intended split.

## Password storage

- Passwords are hashed with `werkzeug.security.generate_password_hash` and
  verified with `check_password_hash`. The result is a salted string stored in
  `users.password_hash`; the plaintext is never stored or logged. Hashing is
  applied in every write path: first-run setup, admin create, admin reset, and
  self-service change.
- Minimum length is **8 characters** (`Field(min_length=8)` on the create, change
  and reset schemas, and an explicit check in `setup`).
- The hashing method is not named in `main.py`; it relies on the Werkzeug default
  for the pinned version (`Werkzeug>=3.1.9`). The README describes the stored
  hash as bcrypt, while the README now states salted Werkzeug hashes
  (`generate_password_hash`), which is what `main.py` uses. Treat the Werkzeug
  wording as correct and this note as resolved.

## Input handling

- **Parameterized SQL.** Database access goes through psycopg with `%s`
  placeholders and bound parameter tuples. No user-supplied value is concatenated
  into a SQL statement.
- The one dynamic identifier in a query is the product sort key. `sort` is
  checked against a fixed `SORT_COLUMNS` whitelist and falls back to `"name"`
  when it is not recognised; `direction` is coerced to only `ASC` or `DESC`
  (`direction_sql = "DESC" if direction == "desc" else "ASC"`). The `ORDER BY`
  clause is therefore built from a whitelisted column name plus a fixed keyword,
  never from raw input.
- **LIKE-wildcard escaping.** Search escapes wildcards before matching.
  `_escape_like` escapes backslash, `%` and `_`
  (`term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")`), and
  `list_products` binds the term into
  `p.name ILIKE %s ESCAPE '\' OR b.name ILIKE %s ESCAPE '\'`. A user-supplied
  `%` or `_` is matched literally instead of acting as a wildcard.
- **Validation.** Request bodies are validated by Pydantic models with `Field`
  constraints: `username` 1 to 80, brand name 1 to 120, product name 1 to 200,
  `price` > 0, `quantity` >= 0, `lead_time_days` >= 1, `reason` up to 200,
  `qty` > 0, and `min_quantity` >= 0. CSV import enforces a 1 MB size cap and
  reports per-row errors instead of failing the whole upload.

## Security headers

- What the application sets today is **CORS**. `main.py` adds `CORSMiddleware`
  with `allow_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]`,
  `allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`. The
  code comment notes these origins must be extended for production deployments.
- **Security headers are implemented.** The regression found in the previous
  audit (README claimed them, code did not set them) is closed: the middleware at
  `main.py` (~105-134) is registered before the routers, so it is the outermost
  layer and touches API responses, the SPA shell and the in-app error pages
  alike. Every response carries `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer` and a
  `Content-Security-Policy`. The CSP is sufficient for the built SPA: the
  production `dist/index.html` loads only same-origin `/assets/*` scripts and
  stylesheets. Remaining hardening, not yet done: `object-src 'none'`,
  `upgrade-insecure-requests`, `Cross-Origin-Opener-Policy`,
  `Cross-Origin-Resource-Policy` and `Permissions-Policy`.

## Secrets handling

- `SECRET_KEY` is required and validated at startup: if it is unset the process
  raises `SECRET_KEY is not set...`, and if it is shorter than 32 characters it
  raises `SECRET_KEY is too short...`. It signs the JWTs (HS256). Generate one
  with `python -c "import secrets; print(secrets.token_hex(32))"`.
- `.env` is gitignored, and so is `backups/`, so real values and dumps are not
  committed.
- The committed template is `.env.template`, the single source of truth: it lists
  every variable `main.py`, `database.py` and `compose.yml` read and says which
  are required. `.env.example` is only a pointer to it and deliberately lists
  nothing, so the two files cannot drift apart. `.env` itself must never be
  committed.
- Other secrets: `NVIDIA_API_KEY` (optional, for the LLM) and
  `GRAFANA_ADMIN_PASSWORD` (the Compose default is `admin`, so override it before
  exposing port 3000). Neither is printed by the scripts, and no secret value is
  needed in this document.

## What CI enforces

Two GitHub Actions workflows run on this repository.

The **Security workflow** (`.github/workflows/security.yml`) runs on pushes and
pull requests to `main` and on a weekly schedule (Mondays at 02:00 UTC):

- **Ruff** (`ruff check .` and `ruff format --check .`): blocking.
- **Mypy** (`mypy main.py database.py`): blocking.
- **Bandit (SAST)**: blocking, and deliberately scoped. It scans `main.py` and
  `database.py` only; tests and scripts are out of scope by policy (demo seeds
  use `random` by design; tests use asserts and fixture passwords). `B608` is
  skipped on the grounds that all SQL uses parameterized values and the
  f-strings only interpolate compile-time constants (column names, static
  `WHERE` clauses), never user input. The SARIF report is uploaded into the
  GitHub Security tab.
- **pip-audit (SCA)**: blocking. It audits the declared dependency tree
  (`requirements.txt`) against the OSV database and fails the build on a new
  vulnerability; the report is uploaded as the `pip-audit-report` JSON artifact.
  Dev dependencies are not audited here, and the earlier claim that this step was
  non-blocking via `continue-on-error` is stale: that flag was removed when the
  job became a real gate.
- **There is no CodeQL analysis.** The workflow uses
  `github/codeql-action/upload-sarif` only to publish Bandit's SARIF into the
  Security tab. It does not run `codeql-action/init` or `analyze` on any
  language, so the code is not analyzed by CodeQL itself. If CodeQL analysis is
  expected, it is not configured.

The **Tests workflow** runs `pytest --cov` against a throwaway `postgres:16`
service (the database in `.env` is not used), plus the frontend typecheck, unit
tests and build, plus a production image build and a `docker compose config`
validation. Dependabot checks `pip`, `npm` and `github-actions` weekly, and the
same Ruff rules run locally through `pre-commit`.

## LLM integration (optional AI forecast refinement)

Forecasts are linear regression. NVIDIA Build is an optional refinement step on
top of it.

- **What leaves the machine.** When `NVIDIA_API_KEY` is set, the forecast and
  the recommendations endpoints send only the **current page** (the most urgent
  slice), never the full catalog, to
  `https://integrate.api.nvidia.com/v1/chat/completions` (OpenAI-compatible wire
  format). Each item carries `product_id`, `name`, `current_qty`,
  `days_until_stockout` and `recommended_restock_qty`. Requests send
  `Authorization: Bearer $NVIDIA_API_KEY`. The model defaults to
  `openai/gpt-oss-20b` (`NVIDIA_MODEL` overrides it), with `max_tokens: 4000` and
  `temperature: 0.2`. No user credentials are sent.
- **Timeout and stall guard.** The HTTP call uses a 240 second socket timeout
  (`LLM_TIMEOUT` in `.env` overrides it; an unparsable value keeps the default)
  and runs inside a daemon thread with a hard join bound of
  `LLM_TIMEOUT + LLM_GRACE_SECONDS = 240 + 5 = 245 seconds`. This exists because
  a DNS or connect stall can hang well beyond the socket timeout, so the join
  bound keeps the request path bounded; on expiry the request returns the
  regression numbers and the abandoned thread dies with the call.
- **Circuit breaker.** A `429` response sets an in-process cooldown of
  `LLM_COOLDOWN_SECONDS = 5 * 60` (5 minutes) during which the LLM step is
  skipped entirely, to avoid a retry storm against the provider.
- **Neither endpoint depends on the LLM.** Every failure keeps the regression
  values (fallback): no key set (skip with a log line), cooldown active, timeout,
  a response that is not a JSON array, an HTTP error, or any other exception.
  Only matched rows are marked `ai_refined=true`, and only the values that came
  back are applied.
- **One call per window, shared by both tabs.** The refinement runs at most
  once per forecast-cache window (10-minute TTL), so it is not per-request. The
  first endpoint to refine in a window stores the result per product; every
  later call in that window replays it, which is what keeps the forecast and the
  recommendations tabs from disagreeing about the same product's numbers or
  badge. A product write drops the cached list and the stored refinements
  together, so refined values never outlive the data they refine.

## Known and accepted limitations (observed)

- **Security headers are implemented.** The middleware at `main.py` (~105-134)
  is registered before the routers, so it is the outermost layer and sets
  `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` and the CSP on
  every response. Remaining hardening, not yet done: `object-src 'none'`,
  `upgrade-insecure-requests`, `Cross-Origin-Opener-Policy`,
  `Cross-Origin-Resource-Policy` and `Permissions-Policy`. An earlier revision of
  this document called them unimplemented; that was fixed in the docs alignment
  pass and this stale copy is removed with it.
- **Login lockout is per-process and in-memory.** It limits online guessing on a
  single instance, but it resets when the process restarts and is not shared
  across multiple app replicas. Scaling past one replica weakens it.
- **Token invalidation is by existence, not revocation.** There is no logout and
  no token blocklist. A valid 12-hour token stays usable until it expires unless
  the account is deleted. Changing or resetting a password does not by itself
  revoke that user's existing tokens, because the account still exists.
- **Single symmetric key, no rotation.** JWTs use one `SECRET_KEY` with HS256.
  Rotating the key invalidates all outstanding tokens; there is no key-version or
  rotation mechanism.
- **Password algorithm.** It uses Werkzeug's `generate_password_hash` default for
  the pinned Werkzeug version, so it is a salted Werkzeug hash and not bcrypt.
  The README was corrected to say exactly that, and the earlier "bcrypt"
  wording in this document is now stale and should not be repeated.
- **CORS is configured for the two Vite dev origins** with `allow_credentials`
  and wildcard methods/headers. Any other deployment origin must be added to
  `allow_origins` before it is used, or the browser blocks cross-origin calls.
- **`/metrics` and the auth bootstrap endpoints are unauthenticated.**
  `/api/health`, `/api/ready`, `/metrics`, `/api/auth/status`,
  `/api/auth/login` and `/api/auth/setup` carry no auth. `/metrics` is served on
  the published host port 8000 as well as the internal network, so restrict or
  firewall it if the host is exposed. `setup` only works while no user exists.
- **Schema drift was a real defect, now fixed.** `schema.sql` and the migration
  files described different schemas: a fresh volume created from `schema.sql`
  silently lost both `stock_movements` indexes that `migrations/001` defines,
  so the analytics queries that filter and ORDER BY on `timestamp` would
  degrade to sequential scans. `schema.sql` also declared `min_quantity`'s CHECK
  inline (unnamed) while migration 005 names it, so the two sources could not
  produce the same schema. Both are aligned and two tests assert the alignment
  holds, so a fresh volume and a migrated database now match.
- **Migrations are manual.** There is no migration tool and no version table;
  the files in `migrations/` are applied by hand in numeric order, and only
  `schema.sql` is applied automatically, on a fresh volume's first init. A
  migration applied out of order or skipped is not detected by anything.
- **Branch protection is on.** `main` requires the ten CI status checks with
  strict mode, one approving review, resolved conversations, and blocks force
  pushes and deletions. `enforce_admins` is off, so an emergency direct push
  remains possible while the checks still run and report.
- **No TLS in the app container.** The image runs plain HTTP on port 8000; the
  application does not terminate TLS. Put a TLS reverse proxy in front for any
  non-local deployment.
- **LLM configuration.** The forecast refinement talks to the NVIDIA Build
  API. The code reads `NVIDIA_API_KEY` / `NVIDIA_MODEL` and `compose.yml`
  passes those same names (default model `openai/gpt-oss-20b`). The earlier
  OPENROUTER references in this document were stale: the OpenRouter path is
  gone from the templates and the code. Refinement sends product names,
  quantities and derived rates to an external provider when a key is set, so
  it is off by default (no key, regression only) and degrades to the
  regression path on any failure.
