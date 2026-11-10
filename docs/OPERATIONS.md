# Operations Runbook

> **Prototype runbook.** This stack is a **prototype**, not a production
> deployment. Follow it to run and inspect the demo locally. Do not treat the
> defaults as production hardening.

Day to day operation of the stack: starting it, health probes, logs, backup and
restore, migrations, upgrades, and troubleshooting. This runbook does not repeat
the feature list; see [README.md](../README.md) for what the application does and
[SECURITY.md](../SECURITY.md) for the security audit.

Everything below assumes the Compose stack in `compose.yml`, which runs two
services (`db` on PostgreSQL 16 and `app` on the production image) on one bridge
network. The project name is pinned to `ai-inventory-management`.

## Prerequisites

- Docker Engine with the Compose v2 plugin (the commands use `docker compose`).
- A `.env` file in the project root. It is gitignored, so create it on each host.
  Copy `.env.template` to `.env`: it is the single source of truth and lists
  every variable `compose.yml`, `main.py` and `database.py` read, with which
  ones are required. `.env.example` is only a pointer to the template and
  deliberately lists nothing, so copy the template itself, not the example.

```bash
cp .env.template .env
python -c "import secrets; print(secrets.token_hex(32))"   # paste into SECRET_KEY
```

`SECRET_KEY` must be at least 32 characters. If it is missing or shorter than
that, the application process refuses to start (it raises at import), so set it
before `docker compose up`.

Inside the Compose stack the application reaches the database at the service name
`db`. `compose.yml` sets `DATABASE_HOST: db` for the `app` service, so the
`DATABASE_HOST` value in `.env` is only used for local, non-Docker runs (where it
should be `localhost`). The template's default `db` matches the stack; change it
only for host-side tools that run without Docker. The template also lists the
optional variables for the two opt-in extras: `GRAFANA_ADMIN_PASSWORD` for the
monitoring profile and `NVIDIA_API_KEY` / `NVIDIA_MODEL` / `LLM_TIMEOUT` for the
AI forecast refinement.

## First run: setup and the first admin

On the very first launch there are no user accounts, so the app has no one to
sign in. Every page redirects to **/setup**, where you create the initial
account; that account becomes the **admin**. After `setup` completes the page
closes itself, and everyone, including the admin, signs in at **/login**.

```bash
docker compose up -d
# then open http://localhost:8000
```

You can confirm the state through the API before and after:

```bash
curl http://localhost:8000/api/auth/status          # {"setup_required": true} before
```

On the first run of a fresh `pgdata` volume the `db` service initializes from
`schema.sql` (compose mounts it into `docker-entrypoint-initdb.d`, applied only
on first volume initialization). The `app` service waits for `db` to report
healthy before it starts (`depends_on` with `condition: service_healthy`).

## Starting the stack

```bash
docker compose up -d            # app on http://localhost:8000
docker compose ps               # status of the services
```

`app` publishes port `8000` on the host. `db` has no published port: it is
reachable only on the `backend` network. Both services use
`restart: unless-stopped`.

### Observability (opt-in monitoring profile)

Prometheus and Grafana are behind a Compose profile and are not started by a
plain `docker compose up`. Add them with:

```bash
docker compose --profile monitoring up -d
```

- **Prometheus** (`prom/prometheus:v3.15.0`) scrapes the `app` target
  `app:8000/metrics` (job name `inventory-app`) and itself at `localhost:9090`,
  with a 15 second scrape and evaluation interval.
- **Grafana** (`grafana/grafana:13.2.4`) is published on
  http://localhost:3000. The Prometheus datasource is provisioned to
  `http://prometheus:9090` (`isDefault`, not editable), so it is ready without
  manual setup.
- The Grafana admin password defaults to `admin`; override it with
  `GRAFANA_ADMIN_PASSWORD` in `.env` before exposing port 3000.

## Health probes: what each one means

The three endpoints are not interchangeable. They check different things, and the
healthcheck in `compose.yml` relies on that distinction.

- `GET /api/health` is **liveness**. It returns `{"status": "ok"}` and does not
  touch the database at all: the process is up and answering. This is also the
  target of the image HEALTHCHECK in the `Dockerfile`.
- `GET /api/ready` is **readiness**. It runs a trivial `SELECT 1` against the
  database. On success it returns `{"status": "ready", "database": "up"}`; when
  the database cannot answer it returns `503 {"detail": "Database unavailable"}`.
  This is the target of the `app` healthcheck in `compose.yml`
  (interval 30s, timeout 10s, retries 3, start_period 60s).
- `GET /metrics` is the **Prometheus exposition** endpoint (request counts,
  latency, in-progress), served by `prometheus-fastapi-instrumentator`. It is
  scraped by Prometheus and is not meant for humans.

One command runs all three and reports pass/fail, plus the Compose status and
disk usage:

```bash
scripts/monitor.sh
# or: BASE_URL=http://your-host:8000 scripts/monitor.sh
```

It prints `OK`/`FAIL` per probe, exits `1` if any probe fails, then lists the
Compose services and the filesystem usage of the project directory.

Important: `/api/health` and `/api/ready` probe the process and connectivity,
not the business queries. A green status does not prove the endpoints users hit
are working. See [Troubleshooting](#a-container-is-healthy-but-the-app-fails).

## Logs

```bash
docker compose logs -f app
docker compose logs -f db
docker compose logs -f prometheus     # only with --profile monitoring
docker compose logs -f grafana        # only with --profile monitoring
```

Every service is configured with the `json-file` logging driver and rotation:
`max-size: "10m"` and `max-file: "3"`. That means each container keeps at most
three log files of 10 MB each (about 30 MB); the oldest is dropped when the cap
is hit, so logs do not grow without bound.

## Backup and restore

`scripts/backup.sh` writes a logical `pg_dump` of the Compose database.

```bash
scripts/backup.sh            # default retention: 14 days
scripts/backup.sh 7          # override retention to 7 days
```

Behavior, exactly as the script implements it:

- Dumps land in `./backups/`, one file per run: `backups/inventory-<stamp>.sql`,
  where `<stamp>` is a `%Y%m%d-%H%M%S` timestamp. **The `backups/` directory is
  gitignored**, so dumps never enter version control.
- Retention: the first argument is the keep-days value, defaulting to **14**. At
  the end of a run the script prunes files matching `backups/inventory-*.sql`
  older than that many days (`find ... -mtime +<days> -delete`).
- The dump uses `DATABASE_NAME`/`DATABASE_USER` when set (falling back to
  `inventory` and `postgres`) and is taken by
  `docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME"`.

Restore with the command documented at the top of the script:

```bash
docker compose exec -T db psql -U "$DATABASE_USER" "$DATABASE_NAME" < backups/inventory-<stamp>.sql
```

Take a backup before any migration or upgrade. The dump is a single SQL file that
restores the database to exactly the state it was in when the dump was taken.

## Migrations

`schema.sql` is the schema for a **fresh** installation. It is applied
automatically only when the `pgdata` volume is first created and is not re-applied
to an existing database. Incremental schema changes live in `migrations/`:

| File | Change |
|------|--------|
| `001_stock_movements.sql` | the `stock_movements` history table |
| `002_reorder_point.sql` | `products.reorder_point` and `lead_time_days` |
| `003_dedupe_products.sql` | removes duplicate products, adds the `(brand, lower(name))` unique index |
| `004_orders.sql` | the `orders` table and its status index |
| `005_min_quantity.sql` | the `products.min_quantity` column |

A database created **before** a migration was added needs that migration applied
by hand; it will not appear on its own, because `schema.sql` and the entrypoint
auto-apply only cover an empty volume. The concrete example used here is
**migration 005, which adds `products.min_quantity`**
(`INTEGER NOT NULL DEFAULT 5`, plus a non-negative `CHECK`). A database built
from the current `schema.sql` already has the column, so this only matters for an
older database. Without it, stock-status classification and the inventory-health
report fail.

Apply a migration with `psql` (this is the pattern recorded in the header of
`migrations/001_stock_movements.sql`):

```bash
psql -d inventory -f migrations/005_min_quantity.sql
```

For the containerised database, pipe the file into the `db` service (the same
stdin form `backup.sh` uses for restore):

```bash
docker compose exec -T db psql -U "$DATABASE_USER" "$DATABASE_NAME" < migrations/005_min_quantity.sql
```

Replace `005_min_quantity.sql` with the migration you need and run them in
numeric order. The migrations are written to be idempotent
(`ADD COLUMN IF NOT EXISTS`, `CREATE ... IF NOT EXISTS`, named constraints), so a
re-run is a no-op. Take a backup first.

## Upgrading

Pull the new code, rebuild the images and recreate the containers:

```bash
git pull
docker compose up -d --build
```

- The `app` image is a two-stage build: the React SPA is built in a Node stage,
  then copied into a `python:3.13-slim` runtime that runs as a non-root user.
  `db` is recreated from `postgres:16`.
- Data lives in the named volume `pgdata` and **survives** container recreation.
  `docker compose down` keeps the volume; only `docker compose down -v` removes
  it, which drops all data. Never pass `-v` on a database you want to keep.
- `schema.sql` is not re-run on an existing volume. If the new version changed
  the schema, apply the matching migration(s) from `migrations/` by hand (see
  [Migrations](#migrations)) after taking a backup.

## Troubleshooting

### The Compose project name drifted and the data looks empty

`compose.yml` pins `name: ai-inventory-management` so the project name, the
volume names and the directory cannot drift apart. Without that pin, Compose
derives the project name from the directory, so running `docker compose` from a
differently named directory targets a different project and its own fresh
`pgdata` volume: the stack starts against an empty database, with no users, and
you are sent back to `/setup`. Nothing was deleted, you are just talking to a
different, new volume.

Check what Compose is actually targeting before you run anything destructive:

```bash
docker compose ls            # which projects exist
docker volume ls             # look for ai-inventory-management_pgdata
```

If the volume you want is under a different project prefix, either return to the
original directory name or start the stack with the pinned project so it reuses
the intended volume.

### A container is healthy but the app fails

The healthchecks probe the process and connectivity, not the business queries:
`/api/health` does not touch the database, and `/api/ready` only runs
`SELECT 1`. A container reports `healthy` when it answers that trivial probe. It
can still return `500` on real endpoints, most commonly because the schema is
behind the code: a database that predates a migration (for example, one missing
`products.min_quantity`) will fail `/api/inventory-health` and `/api/products`
while `/api/ready` stays green. `scripts/monitor.sh` probes the same connectivity
endpoints, so a green monitor report does not rule this out.

Diagnose from the logs, and hit an endpoint that actually reads data:

```bash
docker compose logs -f app                     # look for tracebacks
curl http://localhost:8000/api/auth/status     # this one reads the users table
```

If the logs show a missing column or a failing query, apply the matching
migration from `migrations/` (see [Migrations](#migrations)).

### The database exits at startup with a mount error

Keep `pgdata` a named volume (the default in this `compose.yml`) and keep the
directory name stable so the pinned project name continues to hold. If the
PostgreSQL data directory is instead a bind-mounted host path that changed, for
example after the project directory was renamed or moved, the `postgres` image
refuses to initialize a data directory that already contains a database or
unexpected files, and the `db` container exits during startup rather than coming
up.

Read the exact message before changing anything:

```bash
docker compose logs db
```

The fix is to point the service back at the correct data directory, or to go back
to the named volume, then bring the stack up again. Back up first, and do not
delete a volume you do not fully understand.

### Resource limits in use

Each service is capped by the Compose `deploy.resources.limits`, identical for
all four: `cpus: '0.5'` and `memory: 512M`. All four services (`db`, `app`,
`prometheus`, `grafana`) use `restart: unless-stopped`. These are the limits the
containers are held to; raise them in `compose.yml` if a service is
memory-killed or CPU-starved.
