#!/bin/bash
# ==============================================================================
# Tessallite Issue Hub - Safe Cross-Platform ID Reassignment Script
#
# Usage: ./reassign_issue.sh <OLD_ID> <NEW_ID> <PATH> [OPTIONS]
# Options:
#   --dry-run, -d    Only search and list files that would be modified, do not rewrite
#   --force, -f      Skip Git working tree cleanliness check
# ==============================================================================
set -e

usage() {
    echo "Tessallite Issue ID Reassigner"
    echo "Usage:"
    echo "  $0 <OLD_ID> <NEW_ID> <FILE_OR_DIR> [OPTIONS]"
    echo ""
    echo "Arguments:"
    echo "  OLD_ID       The legacy or temporary issue ID to replace (e.g., Bug-9999)"
    echo "  NEW_ID       The new canonical allocated issue ID (e.g., Bug-1000)"
    echo "  FILE_OR_DIR  The file or directory folder scope to scan and rewrite"
    echo ""
    echo "Options:"
    echo "  -d, --dry-run   Only display matches without applying modifications"
    echo "  -f, --force     Skip Git dirty-tree safety guard"
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
shift 3

DRY_RUN=false
FORCE=false

# Parse options
while [ "$#" -gt 0 ]; do
    case "$1" in
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -f|--force)
            FORCE=true
            shift
            ;;
        *)
            echo "Error: Unknown option '$1'."
            usage
            ;;
    esac
done

# Validate that the target path exists
if [ ! -e "$TARGET_PATH" ]; then
    echo "Error: Target path '$TARGET_PATH' does not exist."
    exit 1
fi

# Git-clean check including untracked files (Gate 6 / Section 11)
if [ "$FORCE" = false ] && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    if [ -n "$(git status --porcelain)" ]; then
        echo "Error: Your Git working tree is dirty (has modified or untracked files)."
        echo "Please commit, stash, or clean your changes before reassigning IDs,"
        echo "or run with '--force' to bypass this safety guard."
        exit 1
    fi
fi

echo "========================================================="
echo " Reassigning Issue ID in Codebase"
echo "========================================================="
echo "  Old ID:   $OLD_ID"
echo "  New ID:   $NEW_ID"
echo "  Scope:    $TARGET_PATH"
echo "  Dry Run:  $DRY_RUN"
echo "========================================================="

# Export IDs to environment for secure Perl access (Gate 6 / Section 11)
export OLD_ID
export NEW_ID
export DRY_RUN

reassign_file() {
    local file="$1"
    
    # 1. Verify file is a plain readable text file and NOT binary (Gate 6 / Section 11)
    if [ ! -f "$file" ] || [ ! -r "$file" ] || ! perl -e 'exit 0 if -T $ARGV[0]; exit 1' "$file"; then
        return 0
    fi
    
    # 2. Match exact word boundaries of the ID (case-insensitive)
    # Reference the environment variables strictly as literal values ($ENV{...}) with \Q...\E quoting
    if perl -0777 -ne 'exit 0 if /\b\Q$ENV{OLD_ID}\E\b/i; exit 1' "$file"; then
        if [ "$DRY_RUN" = true ]; then
            echo "  [Dry-Run Match]: $file"
        else
            echo "  Rewriting: $file"
            # Secure replacement referencing %ENV to completely block shell/regex injection
            perl -pi -e 's/\b\Q$ENV{OLD_ID}\E\b/$ENV{NEW_ID}/gi' "$file"
        fi
    fi
}

export -f reassign_file

if [ -f "$TARGET_PATH" ]; then
    reassign_file "$TARGET_PATH"
elif [ -d "$TARGET_PATH" ]; then
    # Target is a directory. Find and process all text files recursively.
    # We ignore binary/build folders (.git, __pycache__, .pytest_cache, pgdata)
    find "$TARGET_PATH" -type f \
        ! -path '*/.*' \
        ! -path '*/__pycache__/*' \
        ! -path '*/.pytest_cache/*' \
        ! -path '*/pgdata/*' \
        -exec bash -c 'reassign_file "$1"' _ {} \;
fi

echo "========================================================="
echo " Reassignment complete!"
echo "========================================================="
