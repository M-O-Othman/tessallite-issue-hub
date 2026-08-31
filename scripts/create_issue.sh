#!/bin/bash
# ==============================================================================
# Tessallite Issue Hub - API Issue Creation Wrapper
#
# Usage: ./create_issue.sh --title "..." --severity "..." --description "..." [OPTIONS]
# Options:
#   --project      Optional project code (defaults to server setting)
#   --repository   Optional repository name
#   --branch       Optional branch name
#   --area         Optional area classification
#   --refs         Optional references (file/lines)
# ==============================================================================
set -e

# Source central shell configuration file (scripts/config.sh)
source "$(dirname "$0")/config.sh"

# Load config values
URL="${ISSUE_HUB_URL}"
TOKEN="${ISSUE_HUB_TOKEN}"

usage() {
    echo "Tessallite Issue Creator"
    echo "Usage:"
    echo "  $0 --title \"...\" --severity \"...\" --description \"...\" [OPTIONS]"
    echo ""
    echo "Required Arguments:"
    echo "  --title          Descriptive summary of the issue"
    echo "  --severity       Issue severity (e.g. HIGH, CRITICAL, MEDIUM, LOW)"
    echo "  --description    Complete description of the issue (Markdown supported)"
    echo ""
    echo "Optional Arguments:"
    echo "  --project        Project context code"
    echo "  --repository     Repository name"
    echo "  --branch         Branch name"
    echo "  --area           Area classification"
    echo "  --refs           References (files / lines)"
    exit 2
}

TITLE=""
SEVERITY=""
DESC=""
PROJECT=""
REPO=""
BRANCH=""
AREA=""
REFS=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        --title) TITLE="$2"; shift 2 ;;
        --severity) SEVERITY="$2"; shift 2 ;;
        --description) DESC="$2"; shift 2 ;;
        --project) PROJECT="$2"; shift 2 ;;
        --repository) REPO="$2"; shift 2 ;;
        --branch) BRANCH="$2"; shift 2 ;;
        --area) AREA="$2"; shift 2 ;;
        --refs) REFS="$2"; shift 2 ;;
        *) echo "Error: Unknown argument '$1'."; usage ;;
    esac
done

if [ -z "$TITLE" ] || [ -z "$SEVERITY" ] || [ -z "$DESC" ]; then
    echo "Error: Missing required arguments (--title, --severity, --description are all required)."
    usage
fi

# Apply default values from config if omitted (Gate 6)
PROJECT="${PROJECT:-$ISSUE_HUB_DEFAULT_PROJECT}"
REPO="${REPO:-$ISSUE_HUB_DEFAULT_REPOSITORY}"
BRANCH="${BRANCH:-$ISSUE_HUB_DEFAULT_BRANCH}"

# Construct JSON payload dynamically using a safe, single-line Python JSON helper
PAYLOAD=$(python3 -c "
import json, sys
data = {
    'title': sys.argv[1],
    'severity': sys.argv[2],
    'description': sys.argv[3]
}
if sys.argv[4]: data['project'] = sys.argv[4]
if sys.argv[5]: data['repository'] = sys.argv[5]
if sys.argv[6]: data['branch'] = sys.argv[6]
if sys.argv[7]: data['area'] = sys.argv[7]
if sys.argv[8]: data['refs'] = sys.argv[8]
print(json.dumps(data))
" "$TITLE" "$SEVERITY" "$DESC" "$PROJECT" "$REPO" "$BRANCH" "$AREA" "$REFS")

# Send POST request via curl
curl -s -X POST "$URL/api/v1/issues" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer $TOKEN" \
     -d "$PAYLOAD" | python3 -m json.tool
