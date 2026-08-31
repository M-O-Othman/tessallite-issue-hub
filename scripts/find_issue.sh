#!/bin/bash
# ==============================================================================
# Tessallite Issue Hub - API Issue Search Wrapper
#
# Usage: ./find_issue.sh [SEARCH_TEXT] [OPTIONS]
# Example: ./find_issue.sh "XMLA Dax timeout" --status OPEN
# Example: ./find_issue.sh --id Bug-9655
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
    echo "Tessallite Issue Finder"
    echo "Usage:"
    echo "  $0 [SEARCH_TEXT] [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --id             Search for exact case-insensitive Issue ID or AKA (comma-separated)"
    echo "  --status         Filter by status"
    echo "  --severity       Filter by severity"
    echo "  --history        Include full mutation history inline (true/false)"
    exit 2
}

Q=""
ID=""
STATUS=""
SEVERITY=""
HISTORY=""

# If first arg doesn't start with --, treat as search text Q
if [ "$#" -gt 0 ] && [[ ! "$1" =~ ^-- ]]; then
    Q="$1"
    shift
fi

while [ "$#" -gt 0 ]; do
    case "$1" in
        --id) ID="$2"; shift 2 ;;
        --status) STATUS="$2"; shift 2 ;;
        --severity) SEVERITY="$2"; shift 2 ;;
        --history) HISTORY="$2"; shift 2 ;;
        *) echo "Error: Unknown argument '$1'."; usage ;;
    esac
done

# Construct Query String Parameters
PARAMS=""
if [ -n "$Q" ]; then PARAMS="$PARAMS&q=$(python3 -c "import urllib.parse, sys; print(urllib.parse.quote(sys.argv[1]))" "$Q")"; fi
if [ -n "$ID" ]; then PARAMS="$PARAMS&id=$(python3 -c "import urllib.parse, sys; print(urllib.parse.quote(sys.argv[1]))" "$ID")"; fi
if [ -n "$STATUS" ]; then PARAMS="$PARAMS&status=$STATUS"; fi
if [ -n "$SEVERITY" ]; then PARAMS="$PARAMS&severity=$SEVERITY"; fi
if [ -n "$HISTORY" ]; then PARAMS="$PARAMS&include_history=$HISTORY"; fi

# Clean leading '&'
PARAMS="${PARAMS#&}"

# Send GET request and pretty print JSON
curl -s -X GET "$URL/api/v1/issues?$PARAMS" \
     -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
