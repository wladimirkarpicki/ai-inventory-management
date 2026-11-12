# ADR-0003: SECRET_KEY rotation with a `kid` and a dual-key window

- Status: **Proposed**
- Date: 2026-11-12
- Closes: `SECURITY.md` 246–248 — "Single symmetric key, no rotation. JWTs use
  one `SECRET_KEY` with HS256. Rotating the key invalidates all outstanding
  tokens; there is no key-version or rotation mechanism."

## Context

`SECRET_KEY` is read from the environment and validated at startup
(`main.py` 39–48): unset is fatal, shorter than 32 characters is fatal. It is
the only signing and verification key, and `create_token` (217–223) and
`get_current_user` (239) both reference it directly. Rotating it today means
every user is signed out at once and no one can rotate it without knowing
that. There is no key identifier in the token, so a verifier cannot tell which
key a token expects.

## Decision

Keep HS256 and the single-environment model, and add an optional **previous
key** that verifies but does not sign, selected by a `kid` in the JWT header.
Tokens stay the same size and shape; the verification path learns to pick a
key instead of assuming one.

**New environment variables** (all optional except the existing rule that
`SECRET_KEY` must remain set and ≥ 32 characters):

| Variable | Role |
|----------|------|
| `SECRET_KEY` | current signing key (unchanged meaning) |
| `SECRET_KEY_ID` | `kid` label for the current key; defaults to `current` |
| `SECRET_KEY_PREVIOUS` | verification-only key from the previous rotation; unset means none |
| `SECRET_KEY_PREVIOUS_ID` | `kid` label for that key; defaults to `previous` |

**Startup validation**, next to the existing checks at `main.py` 41–48: if
`SECRET_KEY_PREVIOUS` is set it must also be ≥ 32 characters, must differ from
`SECRET_KEY`, and its label must differ from `SECRET_KEY_ID`. A collision is a
configuration error and must fail startup rather than silently map two labels
to one key. The set of accepted keys is exactly what the environment defines —
nothing in a token can widen it.

**Issue.** `create_token` passes
`headers={"kid": SECRET_KEY_ID}` to `jwt.encode`, which accepts extra headers
(PyJWT ≥ 2.15.1, pinned in `requirements.txt`).

**Verify.** In `get_current_user`, before the existing `jwt.decode` at 239:

```python
header = jwt.get_unverified_header(credentials.credentials)
key = _KEYS.get(header.get("kid", SECRET_KEY_ID))
if key is None:
    raise HTTPException(status_code=401, detail="Invalid or expired token.")
payload = jwt.decode(credentials.credentials, key, algorithms=["HS256"])
```

`_KEYS` is built once at import time
(`{SECRET_KEY_ID: SECRET_KEY}` plus `{SECRET_KEY_PREVIOUS_ID: SECRET_KEY_PREVIOUS}`
when the previous key is set). An unknown or absent-with-unknown-label `kid`
selects no key and is a `401`; a missing `kid` falls back to the current key,
so tokens issued before this change keep verifying. `algorithms` stays
hardcoded to `["HS256"]` and is never derived from the token.

### Rotation runbook

Rotate with **no session loss**, in this order:

1. Generate the new key:
   `python -c "import secrets; print(secrets.token_hex(32))"`
2. Edit `.env` — move the current key into the previous slot and install the
   new one:
   ```
   SECRET_KEY_PREVIOUS=<old SECRET_KEY>
   SECRET_KEY_PREVIOUS_ID=<old SECRET_KEY_ID, or "current" if it was unset>
   SECRET_KEY=<new key>
   SECRET_KEY_ID=<new label, e.g. k2>
   ```
3. Recreate the app container: `docker compose up -d app`. Both key sets are
   in the environment, so a rolling restart never has a replica that rejects
   the other's tokens.
4. From this point new tokens carry the new `kid`; old tokens keep verifying
   against the previous key. Users are not disturbed.
5. After `TOKEN_TTL_HOURS` plus margin — 24 hours is comfortable for a 12-hour
   TTL — delete the two `SECRET_KEY_PREVIOUS*` lines and restart. Every token
   signed with the old key has expired by then, so nothing is force-logged-out.

**Emergency revocation (kill every session now):** set a fresh `SECRET_KEY`
and leave the previous variables **unset**, then restart. No outstanding token
verifies. This is deliberately the "break glass" lever and belongs in an
incident, not in routine rotation.

## Consequences

- Routine rotation is a non-event for users: the only visible effect is that
  new tokens carry a new `kid`.
- Four new optional environment variables, documented in `.env.template` (the
  single source of truth, `SECURITY.md` 158–162).
- `get_current_user` grows a key-selection step; `mypy main.py database.py`
  and `bandit -r main.py database.py -s B608` are blocking in CI
  (`SECURITY.md` 175–183), so the helper needs annotations that satisfy mypy
  and must not trip Bandit.
- The README's token description and `SECURITY.md` 242–248 should mention the
  `kid` header in the same patch that implements it; the `/metrics` wording at
  `README.md` 153 is ADR-0004's to change, not this one's.

## Rejected alternatives

- **Asymmetric keys (RS256/ES256) with a JWKS endpoint.** Nothing else
  verifies these tokens — the app is its own only verifier — so the benefit
  (public keys for third parties) does not exist here, the token format
  changes, and every outstanding token dies at the switch.
- **Rotate by simply replacing `SECRET_KEY`.** That is the gap: an all-session
  mass logout with no way to stage it.
- **A scheduled automatic rotation job.** The runbook covers rotation on
  demand, on a schedule the owner controls. A scheduler is new infrastructure
  and new failure modes for no added security on a single host.
- **Storing keys in Vault/KMS.** New infrastructure, excluded by the delivery
  goal. The environment is the existing secret boundary (`.env` is gitignored,
  `SECURITY.md` 156–157).
- **Using rotation as the revocation mechanism.** It cannot be: rotation
  revokes *every* user, while ADR-0002 needs per-user revocation on a password
  change. The two are orthogonal and must not be conflated.
