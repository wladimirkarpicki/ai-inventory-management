# ADR-0002: Token revocation by per-user `token_version`

- Status: **Proposed**
- Date: 2026-11-12
- Closes: `SECURITY.md` 242–245 — "Token invalidation is by existence, not
  revocation. There is no logout and no token blocklist. A valid 12-hour token
  stays usable until it expires unless the account is deleted. Changing or
  resetting a password does not by itself revoke that user's existing tokens,
  because the account still exists."

## Context

`create_token` (`main.py` 217–223) signs `sub`, `username` and
`exp = now + 12 hours` (`TOKEN_TTL_HOURS = 12`, `main.py` 50) with HS256.
`get_current_user` (226–258) decodes with `SECRET_KEY`, coerces `sub` to an
int and re-reads the account from the database on every request (250–253), so
a deleted account is rejected on its next request (255–256). A password change
(`change_password`, 385–409) or an admin reset (`reset_user_password`,
526–544) leaves the account in place, so every token issued before the change
keeps working for up to 12 more hours. There is no logout endpoint and no
revocation list.

## Decision

Add a monotonic counter to the user row and bind it into the token. Revocation
is a bump.

**Schema** (`migrations/007_token_version.sql`, mirrored in `schema.sql`
alongside the `users` table at `schema.sql` 35–40):

```sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 0;
```

**Issue.** `create_token(user_id, username, token_version)` adds the claim
`tv` (integer) to the payload, alongside the existing claims. The login path
already selects the user row (362–365) — it gains `token_version` in that
`SELECT`. First-run setup (312–346) inserts a fresh admin and therefore issues
at the column default, `0`.

**Verify.** The existing per-request re-read in `get_current_user`
(250–253) becomes
`SELECT id, username, role, token_version FROM users WHERE id = %s`, and after
the `sub` coercion:

```python
if _token_version_of(payload) != row[3]:
    raise HTTPException(status_code=401, detail="Invalid or expired token.")
```

`_token_version_of(payload)` reads `payload.get("tv", 0)` and must tolerate a
non-integer the same way the `sub` conversion does (243–248): a token signed
by whoever holds the key can carry `tv = "not-a-number"`, and that has to be a
`401`, not a `500`. No extra query is added — the re-read already happens.

**Revoke.** Both write paths bump in the same transaction as the hash:

```sql
UPDATE users SET password_hash = %s, token_version = token_version + 1 WHERE id = %s
```

One statement, so the new hash and the invalidation commit together and no
token can survive a half-applied change. It covers the self-service change and
the admin reset — exactly the two paths `SECURITY.md` 242–245 names.

**Deletion needs no bump.** The account re-read already rejects a deleted
account (255–256), which is the behaviour the audit records at 28–32. The last
admin cannot be deleted (`main.py` 511–518) and self-deletion is refused
(`main.py` 503–504), so there is no
path that deletes a row while its tokens should keep working.

**Backward compatibility.** A token issued before the migration carries no
`tv` and is treated as version `0`, which is the column default, so nobody is
logged out by the deploy itself. Tokens older than the first bump simply keep
their remaining lifetime — that is what the TTL is for.

### How logout interacts with the 12-hour TTL

Logout stays client-side: the SPA discards the token it holds. A 12-hour cap
bounds the exposure of a token that was captured before logout, and there is
no refresh token, so there is no long-lived credential to leave behind.

A **blocklist is the follow-up, not this decision.** To close the
"logout must actually kill the token" case the incremental design is a
`revoked_tokens(jti UUID PRIMARY KEY, user_id INTEGER, expires_at)` table,
which requires a `jti` claim in every token, a lookup (or a cache) on every
request, and a garbage collector for expired rows. That buys protection
against a token already in someone else's hands, at the cost of one extra
table and a per-request read forever. It is recorded here so the decision is
not lost, and it should be revisited if multi-device logout becomes a
requirement.

## Consequences

- A password change or admin reset revokes every outstanding token of that
  user immediately, which is the stated requirement.
- One new column, one migration, no new table for the common path, no growth
  and no cleanup job.
- The `SELECT` in `get_current_user` and `login` gains one column; the
  `UPDATE` in both password paths gains one term. Nothing else moves.
- `README.md` 177 and `SECURITY.md` 242–245 must be corrected in the same
  patch.
- Revocation is account-wide, not per-device. See the follow-up above.

## Rejected alternatives

- **Blocklist of `jti` values alone.** It cannot satisfy the requirement: to
  revoke a user's tokens on password change you must enumerate their
  outstanding tokens, and there is no server-side session store to enumerate.
  It is only ever an addition to a version counter, never a substitute.
- **Shorten `TOKEN_TTL_HOURS` + refresh tokens.** Out of scope for this wave
  (a new endpoint, a new token type, a new storage decision), and it does not
  close the password-change gap by itself.
- **Store a `password_changed_at` and compare it against the token's `iat`.**
  Same effect as a version counter for this case, but `iat` is not currently
  issued, every comparison becomes a timestamp comparison, and a clock change
  on either side can wrongly invalidate or wrongly accept. A monotonic integer
  has no clock dependency.
- **Revoke by re-issuing the account's tokens.** The server does not hold
  sessions; there is nothing to re-issue.
