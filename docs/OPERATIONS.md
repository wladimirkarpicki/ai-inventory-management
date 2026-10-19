# Operations Runbook

Everything needed to run, observe, back up and restore the stack locally.

## Prerequisites

Copy `.env.template` to `.env` and fill it in. `SECRET_KEY` is required (≥ 32 chars):

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Never commit the real `.env` — it is gitignored.

## Start / stop

```bash
docker compose up -d          # db + app, app on http://localhost:8000
docker compose down            # stop (volumes kept)
```

The app container waits for the database healthcheck before starting. Every service runs under resource caps (0.5 CPU / 512 MB) and log rotation (10 MB × 3 files).

### Monitoring stack (optional)

```bash
docker compose --profile monitoring up -d
```

Adds **Prometheus** (scrapes `app:8000/metrics` every 15s, config in `monitoring/prometheus.yml`) and **Grafana** on http://localhost:3000 (admin password from `GRAFANA_ADMIN_PASSWORD` in `.env`, datasource auto-provisioned to Prometheus).

## Health endpoints

| Endpoint | Meaning | Checks DB? |
|----------|---------|------------|
| `GET /api/health` | **Liveness** — the API process is up | No |
| `GET /api/ready` | **Readiness** — the database answers a query; `503` otherwise | Yes |
| `GET /metrics` | Prometheus exposition (request counts, latency, in-progress) | — |

The compose app healthcheck uses `/api/ready` (stack readiness); the image's own `HEALTHCHECK` uses `/api/health` (container liveness). Docker healthchecks inside the app use stdlib `urllib` — the runtime image has no curl.

## Quick health report

```bash
scripts/monitor.sh          # probes health/ready/metrics, compose ps, disk
BASE_URL=http://other-host:8000 scripts/monitor.sh
```

Exits non-zero if any probe fails.

## Backup and restore

```bash
scripts/backup.sh           # pg_dump -> backups/inventory-<timestamp>.sql
scripts/backup.sh 30         # keep 30 days instead of the default 14
```

Dumps land in `backups/` (gitignored) and older files are pruned automatically.

Restore a dump into the compose database:

```bash
docker compose exec -T db psql -U "$DATABASE_USER" "$DATABASE_NAME" \
  < backups/inventory-<timestamp>.sql
```

## Demo data

Optional seed scripts (run against a local, non-containerized setup or via `docker compose exec app python`):

- `scripts/seed_demo_data.py` / `seed_data_part1.py` + `seed_data_part2.py` — sample brands/products
- `scripts/verify_seed.py` — sanity-check the seeded data

## Logs

```bash
docker compose logs -f app          # follow the API
docker compose logs -f db           # follow PostgreSQL
```

## Development image

`Dockerfile.dev` adds dev dependencies and runs `uvicorn --reload` for hot-reload development (bind mounts not included — rebuild on dependency change).

## Design notes

- **Single-instance by design**: the login rate-limiter keeps counters in process memory. Running 2+ app replicas would require moving that state to a shared store (e.g. Redis) — deliberately out of scope (YAGNI) while the app runs as one local container.
- **nginx/TLS**: not deployed — the app serves everything (API + built SPA) from a single origin on port 8000. Add a reverse proxy when a public domain appears.
