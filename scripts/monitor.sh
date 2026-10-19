#!/usr/bin/env bash
# Quick stack health report: scripts/monitor.sh
# Exit code 1 if any probe fails. BASE_URL overrides the target.
set -uo pipefail

BASE="${BASE_URL:-http://localhost:8000}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FAIL=0

check() { # $1 = label, $2 = url
  if curl -fsS --max-time 5 "$2" >/dev/null 2>&1; then
    echo "OK    $1"
  else
    echo "FAIL  $1"
    FAIL=1
  fi
}

check "liveness   GET $BASE/api/health" "$BASE/api/health"
check "readiness  GET $BASE/api/ready"   "$BASE/api/ready"
check "metrics    GET $BASE/metrics"     "$BASE/metrics"

echo
echo "--- compose services ---"
docker compose -f "$ROOT/compose.yml" ps --format 'table {{.Service}}\t{{.Status}}' 2>/dev/null || true

echo
echo "--- disk usage ---"
df -h "$ROOT" | tail -1

exit "$FAIL"
