#!/bin/bash
set -e

# Automatically provision the whitelisted test database on container initialization (Gate 5 / TEST-001)
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE issue_hub_test;
EOSQL
echo "Successfully provisioned whitelisted test database 'issue_hub_test'!"
