#!/bin/bash
# ==============================================================================
# Tessallite Issue Hub - API Issue Modification Wrapper
#
# Usage: ./update_issue.sh <ISSUE_ID> [OPTIONS]
# Example: ./update_issue.sh Bug-9655 --status CLOSED --owner M-O-Othman
# Example: ./update_issue.sh Bug-9655 --append-file changelog.md
# Example: ./update_issue.sh Bug-9655 --retire DUPLICATE --duplicate-of Bug-9500
# ==============================================================================
set -e

# Source central shell configuration file (scripts/config.sh)
source "$(dirname "$0")/config.sh"

# Load config values
URL="${ISSUE_HUB_URL}"
TOKEN="${ISSUE_HUB_TOKEN}"

usage() {
    echo "Tessallite Issue Updater"
    echo "Usage:"
    echo "  $0 <ISSUE_ID> [OPTIONS]"
    echo ""
    echo "Required Arguments:"
    echo "  ISSUE_ID         The canonical case-insensitive ID of the target issue"
    echo ""
    echo "Options:"
    echo "  --status         Update status (e.g. FIXED, CLOSED, OPEN)"
    echo "  --severity       Update severity"
    echo "  --owner          Update owner assignment"
    echo "  --append-file    Append the contents of a markdown file as a discussion note"
    echo "  --append-text    Append raw text as a discussion note"
    echo "  --add-tag        Add a tag atomically"
    echo "  --remove-tag     Remove a tag atomically"
    echo "  --retire         Retire the issue (e.g. DUPLICATE, COMPLETED, OBSOLETE)"
    echo "  --duplicate-of   Target duplicate issue ID (Required for DUPLICATE retirement)"
    echo "  --retire-note    Optional explanation note for retiring"
    exit 2
}

if [ "$#" -lt 1 ] || [[ "$1" =~ ^-- ]]; then
    echo "Error: Missing target ISSUE_ID."
    usage
fi

ID="$1"
shift

STATUS=""
SEVERITY=""
OWNER=""
APPEND_TEXT=""
ADD_TAG=""
REMOVE_TAG=""
RETIRE_REASON=""
DUP_OF=""
RETIRE_NOTE=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        --status) STATUS="$2"; shift 2 ;;
        --severity) SEVERITY="$2"; shift 2 ;;
        --owner) OWNER="$2"; shift 2 ;;
        --append-text) APPEND_TEXT="$2"; shift 2 ;;
        --append-file)
            if [ -f "$2" ]; then
                APPEND_TEXT=$(cat "$2")
            else
                echo "Error: Append file '$2' does not exist."
                exit 1
            fi
            shift 2
            ;;
        --add-tag) ADD_TAG="$2"; shift 2 ;;
        --remove-tag) REMOVE_TAG="$2"; shift 2 ;;
        --retire) RETIRE_REASON="$2"; shift 2 ;;
        --duplicate-of) DUP_OF="$2"; shift 2 ;;
        --retire-note) RETIRE_NOTE="$2"; shift 2 ;;
        *) echo "Error: Unknown option '$1'."; usage ;;
    esac
done

# Construct payload JSON dynamically via Python
PAYLOAD=$(python3 -c "
import json, sys
data = {}
set_fields = {}

if sys.argv[1]: set_fields['status'] = sys.argv[1]
if sys.argv[2]: set_fields['severity'] = sys.argv[2]
if sys.argv[3]: set_fields['owner'] = sys.argv[3]
if sys.argv[4]: set_fields['add_tags'] = [sys.argv[4]]
if sys.argv[5]: set_fields['remove_tags'] = [sys.argv[5]]

if set_fields:
    data['set'] = set_fields

if sys.argv[6]:
    data['append_description'] = sys.argv[6]

if sys.argv[7]:
    data['retire'] = {
        'reason': sys.argv[7],
        'duplicate_of': sys.argv[8] or None,
        'note': sys.argv[9] or None
    }

print(json.dumps(data))
" "$STATUS" "$SEVERITY" "$OWNER" "$ADD_TAG" "$REMOVE_TAG" "$APPEND_TEXT" "$RETIRE_REASON" "$DUP_OF" "$RETIRE_NOTE")

# Send PATCH request and pretty print JSON
curl -s -X PATCH "$URL/api/v1/issues/$ID" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer $TOKEN" \
     -d "$PAYLOAD" | python3 -m json.tool
