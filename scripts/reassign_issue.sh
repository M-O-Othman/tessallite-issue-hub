#!/bin/bash
# ==============================================================================
# Tessallite Issue Hub - Issue ID Reassignment Script
#
# Usage: ./reassign_issue.sh <OLD_ID> <NEW_ID> <PATH_TO_SCOPE>
# Example: ./reassign_issue.sh Bug-9999 Bug-1000 src/
# ==============================================================================
set -e

# Print usage instructions
usage() {
    echo "Tessallite Issue ID Reassigner"
    echo "Usage:"
    echo "  $0 <OLD_ID> <NEW_ID> <FILE_OR_DIR>"
    echo ""
    echo "Arguments:"
    echo "  OLD_ID       The legacy or temporary issue ID to replace (e.g., Bug-9999)"
    echo "  NEW_ID       The new canonical allocated issue ID (e.g., Bug-1000)"
    echo "  FILE_OR_DIR  The file or directory folder scope to scan and rewrite"
    exit 2
}

# Check argument count
if [ "$#" -lt 3 ]; then
    echo "Error: Missing required arguments."
    usage
fi

OLD_ID="$1"
NEW_ID="$2"
TARGET_PATH="$3"

# Validate that the target path exists
if [ ! -e "$TARGET_PATH" ]; then
    echo "Error: Target path '$TARGET_PATH' does not exist."
    exit 1
fi

echo "========================================================="
echo " Reassigning Issue ID in Codebase"
echo "========================================================="
echo "  Old ID: $OLD_ID"
echo "  New ID: $NEW_ID"
echo "  Scope:  $TARGET_PATH"
echo "========================================================="

# Perform the replacement using cross-platform perl (safer and more consistent than sed -i)
reassign_file() {
    local file="$1"
    # Match exact word boundaries of the ID (case-insensitive) to prevent accidental partial matches
    if grep -qi "$OLD_ID" "$file"; then
        echo "  Rewriting: $file"
        # Case-insensitive replacement of the old ID with the new ID
        perl -pi -e "s/\b$OLD_ID\b/$NEW_ID/gi" "$file"
    fi
}

export -f reassign_file
export OLD_ID
export NEW_ID

if [ -f "$TARGET_PATH" ]; then
    # Target is a single file
    reassign_file "$TARGET_PATH"
elif [ -d "$TARGET_PATH" ]; then
    # Target is a directory. Find and process all text files recursively.
    # We ignore binary/build folders (.git, __pycache__, .pytest_cache, pgdata)
    find "$TARGET_PATH" -type f \
        ! -path '*/.*' \
        ! -path '*/__pycache__/*' \
        ! -path '*/.pytest_cache/*' \
        ! -path '*/pgdata/*' \
        -exec bash -c 'reassign_file "$0"' _ {} \;
fi

echo "========================================================="
echo " Reassignment complete!"
echo "========================================================="
