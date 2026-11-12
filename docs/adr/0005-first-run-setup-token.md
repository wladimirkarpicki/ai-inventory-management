# ADR-0005: Opt-in `SETUP_TOKEN` for first-run `/api/auth/setup`

- Status: **Proposed**
- Date: 2026-11-12
- Closes: `SECURITY.md` 48–57 — "First-run setup is a race, not a guessing
  problem … it will do so for *anyone* who reaches it with any password of 8+
  characters … an attacker does not brute-force anything, they simply POST
  their own and win a race with the legitimate operator. The control is
  operational: run setup promptly on an instance reachable by anyone else, and
  add a setup token if a shared deployment ever needs one."

## Context

`POST /api/auth/setup` (`main.py` 312–346) creates the initial admin while no
user exists (327–328) and accepts any password of at least 8 characters
(330–331). It returns an `access_token` immediately (342–346). The audit
already rejected rate limiting for it (51–54) and for the right reason: there
is nothing to brute-force, so a limiter only slows a race it cannot close. The
SPA sends `username` and `password` from `frontend/src/pages/SetupPage.tsx`
(39–42) with no extra field, and `frontend/src/api.ts`'s `api()` helper
(18–52) carries no per-request header option.

Today the exposure is narrow: the app publishes `127.0.0.1:8000:8000`
(`compose.yml` 62–63), so only host-local callers reach the endpoint, and the
window closes itself forever after the first admin exists. That stops being
true the moment the E3 TLS proxy makes the app reachable from outside, or an
operator widens the publish before running setup. This ADR decides the control
now so the proxy is not what forces the decision.

## Decision

Implement the token the audit itself names, **opt-in and off by default**, so a
single-host install changes nothing.

- **New optional environment variable** `SETUP_TOKEN`, documented in
  `.env.template` with the other optional values (that file is the single
  source of truth, `SECURITY.md` 158–162).
- **When `SETUP_TOKEN` is set**, `/api/auth/setup` requires a matching
  `setup_token` in the request body and answers `401` with a generic detail
  when it is missing or wrong.  `SetupIn` (`main.py` 164–165, which currently only inherits
  `CredentialsIn`) gains an optional field. Compare with
  `secrets.compare_digest`, not `==`, so a wrong token is not distinguishable
  by timing. The token is never logged.
- **When it is unset**, behaviour is byte-for-byte what it is today: open
  first-run, any 8-character password. `tests/test_api.py` 125–139
  (`test_setup_creates_first_admin_and_then_closes`) keeps passing with no
  fixture change, and that is the acceptance signal that the default is intact.
- **`/api/auth/status`** (`main.py` 303–309`) gains
  `setup_token_required: bool`, true only while setup is still open *and* a
  token is configured, so the SPA can show the extra field only when it is
  needed. It reports a boolean, never the token's value. `AuthStatus` in
  `frontend/src/api.ts` (143–145) gains an optional field, so the existing
  `LoginPage.test.tsx` mock (line 9, `{ setup_required: false }`) still
  typechecks and passes.
- **SetupPage** renders a token input when the status tells it to and sends
  `{ username, password, setup_token }`. Because the token rides in the body,
  `api()` needs no signature change — no edit to `frontend/src/api.ts`.
- **Operational control, still documented** (`docs/OPERATIONS.md` 43–52): run
  setup promptly, and on a host reachable by anyone else set `SETUP_TOKEN` in
  `.env` before the first `docker compose up`. The token is single-use by
  construction — setup closes itself — so it needs no rotation and no
  revocation path.

## Consequences

- The race becomes "whoever holds the operator's token wins", which the
  attacker does not: they can no longer simply POST their own password.
- Roughly fifteen lines in `main.py` plus one conditional input in
  `SetupPage.tsx`; no new table, no new service, no new endpoint.
- `.env.template` and `README.md` 157–159 gain the token; `SECURITY.md`
  48–57 and 256–260 gain the resolution.
- Until the E3 TLS proxy lands, the default-off setting means the practical
  exposure is still bounded by the loopback publish — the token is the control
  that makes widening the publish safe.

## Rejected alternatives

- **Accept the operational control only (status quo, token never built).**
  Reasonable while the app is loopback-only, and it is the fallback for anyone
  who leaves `SETUP_TOKEN` unset — but it leaves the fix undone at exactly the
  moment the exposure widens, and it is the one remedy the audit already
  recorded as needed for shared deployments. The token is cheap enough that
  deferring it has no upside.
- **Rate limiting.** Already rejected in the audit (51–54): setup registers no
  failed attempt for the limiter to count, and it would only slow the race.
- **A setup grace window (refuse setup N minutes after boot).** An attacker
  who can reach the endpoint still wins the race inside the window, and an
  unattended deployment closes its own setup before the operator gets to it.
- **Require the token in the `Authorization` header.** Cleaner in the
  abstract, but `api()` has no per-request header option, so it needs a
  signature change to a shared helper, and a setup token in `Authorization` is
  easy to confuse with a user token in logs and error paths.
- **Bind setup to the caller's address.** No trusted-proxy handling exists in
  the app, so the address is not reliable, and it would break the legitimate
  remote-setup flow the token is meant to enable.
