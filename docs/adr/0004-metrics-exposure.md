# ADR-0004: Fence `/metrics` off the published host port

- Status: **Proposed**
- Date: 2026-11-12
- Closes: `SECURITY.md` 256–260 — "`/metrics` and the auth bootstrap endpoints
  are unauthenticated. `/api/health`, `/api/ready`, `/metrics`,
  `/api/auth/status`, `/api/auth/login` and `/api/auth/setup` carry no auth.
  `/metrics` is served on the published host port 8000 as well as the internal
  network, so restrict or firewall it if the host is exposed."

## Context

`Instrumentator().instrument(app).expose(app)` registers `GET /metrics` on the
same application that serves the API and the built SPA (`main.py` 137–138).
The `app` service publishes `127.0.0.1:8000:8000` (`compose.yml` 62–63) — the
host port is loopback-bound today, and the container itself listens on
`0.0.0.0:8000` (`Dockerfile` `CMD`). Prometheus, on the `backend` network
behind the `monitoring` profile, scrapes `app:8000/metrics`
(`monitoring/prometheus.yml` 12–15), and `scripts/monitor.sh` probes
`$BASE_URL/metrics` on the host (line 21).

So the exposure named in the audit is: anything that can reach
`127.0.0.1:8000` on the host, plus anything on the `backend` network, plus any
future deployment where an operator widens the publish (a plain
`8000:8000`, or a reverse proxy that forwards every path). The endpoint leaks
request counts, latencies and in-progress counts — no user data, but the
operational shape of a private instance.

## Decision

Serve the exposition on a **dedicated port that is never published to the
host**, and take it off the API application. The API and the SPA keep the one
port they have; metrics move to `METRICS_PORT` (default `8001`) inside the
container, reachable only from the `backend` network where Prometheus already
lives.

- `main.py` 137–138 keeps `Instrumentator().instrument(app)` and drops
  `.expose(app)`; at startup it calls
  `prometheus_client.start_http_server(METRICS_PORT)`, which serves its
  registry on its own thread. The Instrumentator records into the default
  registry and `start_http_server` serves that same default registry (both
  behaviours read from the installed
  `prometheus-fastapi-instrumentator` 8.1.0 — the floor `requirements.txt`
  pins at `>=8.1.0` — and `prometheus_client` 0.26 sources), so no metric is
  lost and no registry is duplicated.
- `Dockerfile` gains `EXPOSE 8001` (documentation of the internal port).
- `compose.yml` gains **no** `ports` entry for 8001 — that is the whole point:
  publishing is what exposes, and container-to-container reachability on the
  `backend` bridge is unchanged.
- `monitoring/prometheus.yml` scrapes `app:8001` with the same
  `metrics_path: /metrics`.
- `.env.template` gains `METRICS_PORT=8001` (optional), keeping that file the
  single source of truth.
- `scripts/monitor.sh` drops the metrics probe: it targets the host-published
  base URL, and the point of this change is that metrics are no longer
  host-reachable. Liveness and readiness probes stay, and the script's exit
  code semantics are unchanged.
- Tests: `tests/test_api.py` 605–608 (`test_metrics_exposed`) must stop
  asserting a Prometheus body on the API app. The correct assertion is that the
  API port does **not** serve the exposition — a `404` when `frontend/dist` is
  absent (the SPA catch-all at `main.py` 2094–2108 only mounts when the
  directory exists, 2086), or the SPA shell when it is present. Never a
  `Content-Type: text/plain; version=0.0.4` body.
- Documentation: `README.md` 151 and 153, `docs/OPERATIONS.md` 87 and
  109–111, and `SECURITY.md` 256–260 must be corrected in the same patch.

### The auth-bootstrap endpoints stay open, deliberately

`/api/health` returns `{"status": "ok"}` with no database access
(`main.py` 2061–2064) and is the `Dockerfile` HEALTHCHECK target;
`/api/ready` runs a trivial `SELECT 1` (2067–2074) and is the `compose.yml`
healthcheck target (82); `/api/auth/status` returns `{"setup_required": bool}`
(303–309) and is what the SPA reads to choose between `/login` and `/setup`
(`frontend/src/pages/LoginPage.tsx` 30–31); `/api/auth/login` and
`/api/auth/setup` must be unauthenticated by definition. They disclose no user
data — one boolean, one liveness word, one readiness object, and whether the
database answers. Gating them would break the healthchecks and the first-run
flow, so they are accepted as required-unauthenticated and their exposure is
bounded by the network: the loopback-only publish today, and the E3 TLS proxy
(reachable only through the proxy, never directly) later. This ADR decides
`/metrics` only; the bootstrap list is recorded here so no one re-opens it
looking for an auth gate.

## Consequences

- `/metrics` is no longer reachable from the host at all, and stays that way
  if someone later publishes `8000:8000` or puts a proxy in front — the drift
  that would otherwise silently re-open the audit finding.
- Prometheus keeps scraping with no credentials, so no new secret and no new
  rotation duty; monitoring cannot silently break over a stale token.
- One extra listening socket in the app container, and a behaviour change on
  the API port that `monitor.sh` and one test must absorb.
- `docker compose --profile monitoring up -d` keeps working; a plain
  `docker compose up` never listens on 8001 publicly either way.

## Rejected alternatives

- **Auth-gate the route.** It is a one-line change — `expose()` forwards its
  keyword arguments to `app.get()`, so `dependencies=[Depends(require_admin)]`
  works — but it has to authenticate Prometheus, which means a bearer secret in
  `.env` and in `monitoring/prometheus.yml`'s scrape config. That trades a
  published-endpoint exposure for a credential that must be provisioned,
  rotated, and kept in sync across two files, and its failure mode is silent:
  a stale token turns every scrape into a 403 and monitoring dies quietly
  while looking healthy. It also does not survive a later `8000:8000`
  publish, which the fence does. It remains available as defence in depth if
  the owner ever wants both.
- **Host firewall rules (iptables/nftables).** Not expressible in the
  repository, not managed by Compose, not reviewable in this workflow, and not
  portable to the delivery host.
- **Leave it and rely on the loopback bind.** That is today's posture and it
  is the audit finding: it holds only until the publish is widened, and
  nothing in the repo records that it must not be.
- **Move metrics behind the monitoring profile with a separate container.**
  New infrastructure for no gain; the port split achieves the same fence.
