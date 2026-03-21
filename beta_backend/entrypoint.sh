#!/bin/sh
set -eu

if [ -n "${DATABASE_URL:-${POSTGRES_URL:-}}" ]; then
  export DATABASE_URL="${DATABASE_URL:-${POSTGRES_URL}}"
  echo "Waiting for database..."
  python - <<'PY'
import os
import time

from sqlalchemy import create_engine, text

database_url = os.environ["DATABASE_URL"]
engine = create_engine(database_url, pool_pre_ping=True)

for attempt in range(30):
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        print("Database ready")
        break
    except Exception as exc:
        if attempt == 29:
            raise
        print(f"Database not ready yet: {exc}")
        time.sleep(2)
PY
fi

alembic upgrade head
exec uvicorn app.app:app --host 0.0.0.0 --port 8000

