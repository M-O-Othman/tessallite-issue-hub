#!/bin/bash
# ==============================================================================
# Tessallite Issue Hub - Administrative Legacy Migration Wrapper
#
# Usage: ./run_migration.sh [DATABASE_URL]
# If DATABASE_URL is omitted, it will read from your local .env file.
# ==============================================================================
set -e

# Load local .env if present
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

DB_URL="${1:-$DATABASE_URL}"

if [ -z "$DB_URL" ]; then
    echo "Error: DATABASE_URL is not set. Please supply it as an argument or set it in your .env file."
    echo "Usage: $0 [DATABASE_URL]"
    exit 1
fi

# Verify migration sources exist
if [ ! -d "migration_sources" ] || [ ! -f "migration_sources/active-registry.md" ] || [ ! -f "migration_sources/closed-registry.md" ]; then
    echo "Error: 'migration_sources' directory or registry files are missing."
    echo "Please ensure 'migration_sources/active-registry.md' and 'migration_sources/closed-registry.md' are present."
    exit 1
fi

echo "========================================================="
echo " Initiating Authoritative Legacy Migration"
echo "========================================================="
echo "  Database: $(echo "$DB_URL" | sed 's/:[^:@]*@/:******@/')" # mask password in print
echo "========================================================="

# Execute the migration script securely
DATABASE_URL="$DB_URL" ALLOW_DESTRUCTIVE_IMPORT=1 python3 scripts/run_legacy_import.py

echo "========================================================="
echo " Migration completed successfully!"
echo "========================================================="
