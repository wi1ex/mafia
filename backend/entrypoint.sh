#!/usr/bin/env bash
set -euo pipefail

echo "Waiting for Postgres at ${POSTGRES_HOST}:${POSTGRES_PORT}..."
python - <<'PY'
import asyncio, os
import asyncpg
async def main():
    for i in range(60):
        try:
            conn = await asyncpg.connect(
                user=os.environ["POSTGRES_USER"],
                password=os.environ["POSTGRES_PASSWORD"],
                database=os.environ["POSTGRES_DB"],
                host=os.environ["POSTGRES_HOST"],
                port=int(os.environ.get("POSTGRES_PORT","5432")),
            )
            await conn.close()
            print("Postgres is ready")
            return
        except Exception as e:
            await asyncio.sleep(1)
    raise SystemExit("Postgres not available after 60s")
asyncio.run(main())
PY

echo "Applying migrations..."
alembic upgrade head

echo "Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips="*"
