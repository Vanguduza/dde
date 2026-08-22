#!/bin/sh
set -eu

wait_for_db() {
  echo "Waiting for PostgreSQL..."
  attempts=0
  until uv run python - <<'PY'
import asyncio
import os
import sys

import asyncpg


async def main() -> None:
    url = os.environ["DDE_DATABASE_URL"]
    # asyncpg expects postgresql:// not postgresql+asyncpg://
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(dsn=dsn, timeout=2)
    await conn.close()


asyncio.run(main())
PY
  do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 60 ]; then
      echo "PostgreSQL not reachable after 60 attempts" >&2
      exit 1
    fi
    sleep 2
  done
  echo "PostgreSQL is reachable."
}

run_migrate() {
  wait_for_db
  echo "Applying database migrations..."
  uv run alembic upgrade head
  echo "Migrations complete."
}

run_serve() {
  wait_for_db
  run_migrate
  echo "Starting DDE Core..."
  exec uv run uvicorn interfaces.api:app --host 0.0.0.0 --port 8000
}

case "${1:-serve}" in
  migrate)
    run_migrate
    ;;
  serve)
    run_serve
    ;;
  *)
    echo "Unknown command: $1 (expected migrate or serve)" >&2
    exit 1
    ;;
esac
