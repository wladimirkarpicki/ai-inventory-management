#!/usr/bin/env bash
# Backup the compose PostgreSQL database: scripts/backup.sh [keep_days]
# Dumps land in ./backups/ (gitignored). Restore with:
#   docker compose exec -T db psql -U "$DATABASE_USER" "$DATABASE_NAME" < backups/inventory-<stamp>.sql
set -euo pipefail

KEEP_DAYS="${1:-14}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="$ROOT/backups"
STAMP="$(date +%Y%m%d-%H%M%S)"
DB_NAME="${DATABASE_NAME:-inventory}"
DB_USER="${DATABASE_USER:-postgres}"

mkdir -p "$BACKUP_DIR"

DUMP_FILE="$BACKUP_DIR/inventory-$STAMP.sql"
echo "[backup] dumping db:$DB_NAME -> $DUMP_FILE"
docker compose -f "$ROOT/compose.yml" exec -T db pg_dump -U "$DB_USER" "$DB_NAME" > "$DUMP_FILE"

SIZE="$(du -h "$DUMP_FILE" | cut -f1)"
echo "[backup] done ($SIZE)"

echo "[backup] pruning dumps older than $KEEP_DAYS day(s)"
find "$BACKUP_DIR" -name 'inventory-*.sql' -mtime "+$KEEP_DAYS" -delete
echo "[backup] kept: $(ls -1 "$BACKUP_DIR" | wc -l) file(s)"
