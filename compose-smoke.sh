#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$ROOT_DIR"
TMP_ROOT="/tmp/catch-your-partner-compose-smoke"
TMP_PROJECT="$TMP_ROOT/project"
COMPOSE_CMD="docker compose"

PASS_MARK="PASS"
FAIL_MARK="FAIL"

fail() {
  printf '\n❌ %s\n' "$1"
  if command -v docker >/dev/null 2>&1; then
    echo
    echo "Last API logs:"
    if [ -d "$TMP_PROJECT" ]; then
      (cd "$TMP_PROJECT" && $COMPOSE_CMD logs --tail=200 api) || true
    else
      $COMPOSE_CMD logs --tail=200 api || true
    fi
  fi
  exit 1
}

if ! command -v docker >/dev/null 2>&1; then
  fail "docker is not installed or not on PATH"
fi

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

rm -rf "$TMP_ROOT"
mkdir -p "$TMP_ROOT"
rsync -a --delete \
  --exclude '.git/' \
  --exclude '.env' \
  --exclude '.DS_Store' \
  --exclude '._*' \
  --exclude '__pycache__/' \
  --exclude '.pytest_cache/' \
  "$ROOT_DIR"/ "$TMP_PROJECT"/
cp "$ROOT_DIR/.env" "$TMP_PROJECT/.env"

cd "$TMP_PROJECT"

echo "Starting stack..."
$COMPOSE_CMD up -d --build

echo "Waiting for postgres health..."
for _ in $(seq 1 60); do
  if $COMPOSE_CMD exec -T db pg_isready -U postgres -d catchyourpartner >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
$COMPOSE_CMD exec -T db pg_isready -U postgres -d catchyourpartner >/dev/null 2>&1 || fail "postgres did not become healthy in time"

echo "Running migration explicitly..."
$COMPOSE_CMD exec -T api alembic upgrade head || fail "alembic upgrade head failed"

echo "Waiting for /health..."
for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1 || fail "API health check failed"

echo "Running smoke flow..."
(cd beta_backend && PYTHONPATH=. python3 smoke_live.py) || fail "smoke flow failed"

printf '\n✅ %s: compose, migration and smoke flow succeeded\n' "$PASS_MARK"
