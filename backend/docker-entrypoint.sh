#!/bin/sh
# Runs once per container start, before gunicorn takes over (exec "$@" at the end).
set -e

echo "[entrypoint] Waiting for Postgres..."
python - <<'PY'
import os
import time
import psycopg2

url = os.environ["DATABASE_URL"]
for attempt in range(30):
    try:
        conn = psycopg2.connect(url)
        conn.close()
        print("[entrypoint] Postgres is up.")
        break
    except psycopg2.OperationalError as exc:
        print(f"[entrypoint] Postgres not ready yet ({attempt + 1}/30): {exc}")
        time.sleep(2)
else:
    raise SystemExit("[entrypoint] Postgres never became reachable, aborting.")
PY

echo "[entrypoint] Ensuring tables exist (db.create_all — no Alembic migrations in repo yet)..."
python - <<'PY'
from app import create_app
from extensions import db

app = create_app()
with app.app_context():
    db.create_all()
print("[entrypoint] Tables ready.")
PY

echo "[entrypoint] Seeding equipment / muscle groups / exercise library (idempotent)..."
python -m flask --app app seed

echo "[entrypoint] Starting app: $@"
exec "$@"
