#!/bin/bash
set -e

# Wait for external database to be ready (if DATABASE_URL is configured)
if [ -n "$DATABASE_URL" ]; then
    echo "Applying database migrations..."
    alembic upgrade head
fi

# Start FastAPI application
echo "Starting FastAPI application on port 8080..."
exec uvicorn issue_hub.main:app --host 0.0.0.0 --port 8080
