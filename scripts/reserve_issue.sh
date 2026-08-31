#!/bin/bash
# ==============================================================================
# Tessallite Issue Hub - API ID Reservation Wrapper
#
# Usage: ./reserve_issue.sh [OPTIONS]
# Options:
#   --project      Optional project code (defaults to server setting)
#   --repository   Optional repository name
#   --branch       Optional branch name
#   --task         Optional task ID
# ==============================================================================
set -e

# Load local .env if present
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Fallback defaults
URL="${ISSUE_HUB_URL:-https://tessallite-issue-hub-633649663813.us-west1.run.app}"
TOKEN="${ISSUE_HUB_TOKEN:-tessallite_api_secure_token_abc123_xyz789}"

usage() {
    echo "Tessallite ID Reserver"
    echo "Usage:"
    echo "  $0 [OPTIONS]"
    echo ""
    echo "Optional Arguments:"
    echo "  --project        Project context code"
    echo "  --repository     Repository name"
    echo "  --branch         Branch name"
    echo "  --task           Task ID"
    exit 2
}

PROJECT=""
REPO=""
BRANCH=""
TASK=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        --project) PROJECT="$2"; shift 2 ;;
        --repository) REPO="$2"; shift 2 ;;
        --branch) BRANCH="$2"; shift 2 ;;
        --task) TASK="$2"; shift 2 ;;
        *) echo "Error: Unknown argument '$1'."; usage ;;
    esac
done

# Construct JSON payload dynamically
PAYLOAD=$(python3 -c "
import json, sys
data = { 'reserve': True }
if sys.argv[1]: data['project'] = sys.argv[1]
if sys.argv[2]: data['repository'] = sys.argv[2]
if sys.argv[3]: data['branch'] = sys.argv[3]
if sys.argv[4]: data['task'] = sys.argv[4]
print(json.dumps(data))
" "$PROJECT" "$REPO" "$BRANCH" "$TASK")

# Send POST request and print only the newly allocated Issue ID!
RESPONSE=$(curl -s -X POST "$URL/api/v1/issues" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer $TOKEN" \
     -d "$PAYLOAD")

# Parse and print ID cleanly to console
python3 -c "
import json, sys
data = json.loads(sys.argv[1])
if data.get('ok') and 'issue' in data:
    print(f'RESERVATION SUCCESS: Allocated ID is {data[\"issue\"][\"issue_id\"]}')
else:
    print('RESERVATION FAILED:', data)
" "$RESPONSE"
