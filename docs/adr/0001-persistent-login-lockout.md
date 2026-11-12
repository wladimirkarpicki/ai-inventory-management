# ADR-0001: Persistent login lockout in PostgreSQL

- Status: **Proposed**
- Date: 2026-11-12
- Closes: `SECURITY.md` 239–241 — "Login lockout is per-process and in-memory.
  It limits online guessing on a single instance, but it resets when the
  process restarts and is not shared across multiple app replicas. Scaling
  past one replica weakens it."

## Context

Failed sign-ins are counted in a process-local dict, `_failed_logins`
(`main.py` 80), by three helpers: `_register_failed_login`
(`main.py` 267–274), `_login_is_locked` (277–289) and `_clear_failed_logins`
(292–293). `login` (349–377) checks the lock before touching the database,
registers a failure when the row is missing *or* the hash does not match
(367–369), and clears the counter on success (371). The limit is
`LOGIN_MAX_ATTEMPTS = 5` failures inside a fixed 15-minute window anchored at
the first failure (`main.py` 54–55), and a locked login returns
`429 "Too many failed attempts. Try again in 15 minutes."` (357–360).

The dict is lost on restart and not visible to a second replica. The delivery
goal is a single host, but the state must not depend on one process lifetime,
and a restart must not hand an attacker a fresh five attempts.

## Decision

Move the counter to a PostgreSQL table, keeping the semantics, the constants
and the observable HTTP behaviour identical. No new infrastructure: the
database is already there and `login` already holds a connection through
`Depends(get_db)` (`main.py` 143–153).

**Schema** (`migrations/006_login_attempts.sql`, mirrored in `schema.sql`,
idempotent in the style of `migrations/001_stock_movements.sql`):

```sql
CREATE TABLE IF NOT EXISTS login_attempts (
    username      VARCHAR(80) NOT NULL PRIMARY KEY,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    window_start  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
```

`VARCHAR(80)` matches `CredentialsIn.username` (`main.py` 160) so the key is
bounded by the request schema. There is **no foreign key to `users`**: a
failure is recorded for a username that may not exist (367–369), and a user
deleted mid-window must not take its counter with it.

**Read** — one statement, no client clock, no second write:

```sql
SELECT attempt_count >= %s AS locked
FROM login_attempts
WHERE username = %s
  AND window_start > now() - make_interval(secs => %s)
```

No row means not locked, which also disposes of expired rows on read.

**Register** — one atomic upsert, safe when two replicas fail the same
username at the same moment, and it resets a stale window exactly as
`_register_failed_login` does:

```sql
INSERT INTO login_attempts (username, attempt_count, window_start)
VALUES (%s, 1, now())
ON CONFLICT (username) DO UPDATE
SET attempt_count = CASE
        WHEN login_attempts.window_start < now() - make_interval(secs => %s)
        THEN 1 ELSE login_attempts.attempt_count + 1 END,
    window_start = CASE
        WHEN login_attempts.window_start < now() - make_interval(secs => %s)
        THEN now() ELSE login_attempts.window_start END
```

`make_interval(secs => %s)` takes `LOGIN_LOCKOUT_SECONDS` as a bound
parameter, so `main.py` 55 stays the single knob and the interval is never a
hardcoded literal.

**Clear** — `DELETE FROM login_attempts WHERE username = %s`, called on
success exactly where `_clear_failed_logins` is called today.

**Retention** — the same statement that registers a failure also runs
`DELETE FROM login_attempts WHERE window_start < now() - make_interval(secs => %s)`
in its transaction. Failed logins are rare and already database-bound, so the
extra statement costs nothing on the success path and keeps the table bounded
by active usernames under random-username flooding, with no scheduler.

**Commit discipline.** psycopg 3 is not autocommit (`requirements.txt` pins
`psycopg==3.3.8`; every write in `main.py` ends in `db.commit()`). The
register path runs inside a request that then raises `401`, and `get_db`
closes the connection in a `finally` (152–153), which rolls an open
transaction back. The increment **must be committed before the exception is
raised** or the failed attempt is silently not counted.

**Test-suite changes** (`tests/conftest.py`): add `login_attempts` to the
`TRUNCATE` list in `_clean_tables` (69–79) and replace the body of the
`_reset_failed_logins` fixture (103–116) with a `DELETE FROM login_attempts`,
since the module-level dict it clears will no longer exist. The test database
is built from `schema.sql` only (43–56), which is why the table must be
mirrored there. `tests/test_api.py` 151–179 (`test_login_locks_after_five_failures`,
`test_rate_limit_only_affects_target_account`) must keep passing unchanged —
that is the acceptance signal that the semantics survived the move.

## Consequences

- The counter survives a restart and is shared by every replica: both named
  limitations are closed.
- One or two extra statements on the failed-login path only.
- `README.md` 176 and `SECURITY.md` 239–241 must be corrected in the same
  patch.
- Unchanged and accepted: a lockout is still a self-DoS lever against a known
  username (five bad attempts lock the owner out too). Per-IP limiting,
  exponential backoff and CAPTCHA are not decided here.

## Rejected alternatives

- **Keep it in memory.** It is the gap. Rejected as the status quo being closed.
- **Redis (or any new service).** The constraint is "no new infrastructure";
  nothing else in the stack would use it and `compose.yml` has no place for it.
- **A file on disk.** The same failure as memory inside a container: the
  writable layer is per-container, so a restart or a second replica still
  starts from zero.
- **Per-IP keys instead of per-username.** There is no trusted-proxy
  handling in the app, so the client IP is not reliably available, and shared
  NAT would lock out an entire office for one attacker. It also changes the
  existing tests, which are specified per username.
- **PostgreSQL advisory locks.** The upsert is already atomic; a lock would
  add a failure mode (a leaked lock) without changing the result.
- **A counter column on `users`.** Impossible: failures must be counted for
  usernames that do not exist.
