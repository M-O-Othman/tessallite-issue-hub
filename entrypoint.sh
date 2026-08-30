#!/bin/bash
set -e

DB_DATA_DIR="/var/lib/postgresql/data"

# Ensure log directory exists and is owned by postgres
mkdir -p /var/log/postgresql
chown -R postgres:postgres /var/log/postgresql

# Ensure the database data directory exists and is owned by the postgres user
mkdir -p "$DB_DATA_DIR"
chown -R postgres:postgres "$DB_DATA_DIR"
chmod 700 "$DB_DATA_DIR"

# Initialize PostgreSQL database cluster if not already initialized
if [ -z "$(ls -A "$DB_DATA_DIR")" ]; then
    echo "Initializing PostgreSQL database cluster..."
    su - postgres -c "/usr/lib/postgresql/*/bin/initdb -D $DB_DATA_DIR --encoding=UTF8"
    
    # Configure postgres to trust connections from local and host
    echo "host all all 127.0.0.1/32 trust" >> "$DB_DATA_DIR/pg_hba.conf"
    echo "host all all 0.0.0.0/0 trust" >> "$DB_DATA_DIR/pg_hba.conf"
    echo "local all all trust" >> "$DB_DATA_DIR/pg_hba.conf"
    echo "listen_addresses = '*'" >> "$DB_DATA_DIR/postgresql.conf"
fi

# Start PostgreSQL using pg_ctl as postgres user
echo "Starting PostgreSQL..."
su - postgres -c "/usr/lib/postgresql/*/bin/pg_ctl -D $DB_DATA_DIR -l /var/log/postgresql/server.log start"

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to start..."
until su - postgres -c "/usr/lib/postgresql/*/bin/pg_isready" > /dev/null 2>&1; do
    sleep 1
done
echo "PostgreSQL is active and ready!"

# Create database and user if they don't exist
echo "Configuring database and permissions..."
su - postgres -c "psql -tc \"SELECT 1 FROM pg_database WHERE datname = 'issue_hub'\" | grep -q 1 || psql -c \"CREATE DATABASE issue_hub;\""
su - postgres -c "psql -tc \"SELECT 1 FROM pg_roles WHERE rolname = 'issue_hub'\" | grep -q 1 || psql -c \"CREATE USER issue_hub WITH PASSWORD 'secret_password';\""
su - postgres -c "psql -c \"GRANT ALL PRIVILEGES ON DATABASE issue_hub TO issue_hub;\""
su - postgres -c "psql -d issue_hub -c \"GRANT ALL ON SCHEMA public TO issue_hub;\""

# Run Alembic migrations to apply latest schema, sequences, and preseed lookup data
echo "Applying database migrations..."
DATABASE_URL="postgresql+psycopg://issue_hub:secret_password@127.0.0.1:5432/issue_hub" alembic upgrade head

# Start FastAPI application
echo "Starting FastAPI application on port 8080..."
exec uvicorn issue_hub.main:app --host 0.0.0.0 --port 8080
