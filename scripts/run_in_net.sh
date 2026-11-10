#!/usr/bin/env bash
# Run a host-side command inside the compose network.
#
#   ./scripts/run_in_net.sh python -m pytest -q
#   ./scripts/run_in_net.sh python -m scripts.seed_demo_data
#
# The database service is intentionally NOT published to the host, because
# a port through the Docker userland proxy timed out under test-suite load
# (psycopg ConnectionTimeout on every connect). Everything that needs the
# database therefore runs inside the network, where it is an ordinary
# container-to-container connection.
#
# The dev image carries both the runtime and the dev dependencies. The
# repository is bind-mounted so edits are visible and a throwaway database
# is never written into the real one by accident.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Pull the connection settings out of .env so the documented command works on
# a clean clone. A .env alone used to be useless here: the file was never
# sourced, so DATABASE_PASSWORD had to be exported by hand while the error
# message suggested a .env would do.
if [ -f "$ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$ROOT/.env"
  set +a
fi

DEV_IMAGE="ai-inventory-management-dev"

if ! docker image inspect "$DEV_IMAGE" >/dev/null 2>&1; then
  echo "[run_in_net] building $DEV_IMAGE from Dockerfile.dev (first run only)"
  docker build -f Dockerfile.dev --network=host -t "$DEV_IMAGE" "$ROOT" >&2
fi

# DATABASE_HOST=db is the compose service name. DATABASE_PORT is left unset
# so the connection string uses the container default of 5432.
# DATABASE_NAME defaults to "inventory", which is what compose.yml and the
# README use; the old default was "ecommerce", which matches neither.
exec docker run --rm -it \
  --network "${COMPOSE_PROJECT_NAME:-ai-inventory-management}_backend" \
  -v "$ROOT:/app" -w /app \
  -e DATABASE_HOST=db \
  -e DATABASE_NAME="${DATABASE_NAME:-inventory}" \
  -e DATABASE_USER="${DATABASE_USER:-postgres}" \
  -e DATABASE_PASSWORD="${DATABASE_PASSWORD:?DATABASE_PASSWORD is not set: add it to .env or export it}" \
  -e SECRET_KEY="${SECRET_KEY:-}" \
  -e LLM_TIMEOUT="${LLM_TIMEOUT:-}" \
  "$DEV_IMAGE" "$@"
