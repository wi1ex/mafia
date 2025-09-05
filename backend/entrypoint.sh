#!/usr/bin/env bash
set -Eeuo pipefail
cd /app

echo "Waiting for Postgres at ${POSTGRES_HOST}:${POSTGRES_PORT}..."
python - <<'PY'
import os, time, socket
h=os.environ['POSTGRES_HOST']; p=int(os.environ.get('POSTGRES_PORT','5432'))
deadline=time.time()+60
while time.time()<deadline:
    try:
        with socket.create_connection((h,p), timeout=3):
            print("Postgres is ready"); break
    except OSError:
        time.sleep(1)
else:
    raise SystemExit("Postgres not reachable")
PY

echo "Applying migrations..."
alembic upgrade head

echo "Starting app..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'
