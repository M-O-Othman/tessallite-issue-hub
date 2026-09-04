#!/bin/bash
set -e

echo "========================================================="
echo " Deploying Tessallite Issue Hub Standalone Stack"
echo "========================================================="
echo ""

# 1. Build and restart the container (DOES NOT wipe database volumes/data)
echo "Rebuilding and restarting standalone container in the background..."
docker compose up -d --build app

echo ""
echo "========================================================="
echo " DEPLOYMENT COMPLETED SUCCESSFULLY!"
echo "========================================================="
echo "The stack has been rebuilt and started in the background."
echo "No database persistent volumes were deleted or wiped."
echo ""
echo "Web UI Portal URL: http://localhost:8080/"
echo "Administrator Credentials:"
echo "    - Username: admin"
echo "    - Password: admin"
echo "API Bearer Token: api_bearer_token_123"
echo "========================================================="
