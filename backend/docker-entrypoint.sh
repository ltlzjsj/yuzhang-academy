#!/bin/sh
set -e

case "$1" in
  api)
    echo "[entrypoint] running DB migrations..."
    alembic upgrade head || echo "[entrypoint] WARNING: alembic upgrade failed, continuing"
    echo "[entrypoint] starting API on :8000"
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
    ;;
  worker)
    echo "[entrypoint] starting Celery worker"
    exec celery -A app.workers.celery_app worker --loglevel=info --concurrency=2
    ;;
  *)
    exec "$@"
    ;;
esac
