# ==============================================================================
# Tessallite Issue Hub - Shell Wrapper Configuration File (scripts/config.sh)
#
# This file unifies target URLs, security tokens, and context defaults for all
# terminal shell wrapper scripts. It automatically sources your private project
# .env file from the root directory as the highest priority context.
# ==============================================================================

# 1. Source local private .env from project root if present (Gate 2 / Section 4)
ROOT_ENV="$(dirname "$0")/../.env"
if [ -f "$ROOT_ENV" ]; then
    # Parse and export variables safely without shell-expansion bugs
    export $(grep -v '^#' "$ROOT_ENV" | xargs)
fi

# 2. Strict Fail-Closed API Server Connection Configuration (Gate 2 / SEC-001)
# Production URLs and secure tokens are strictly forbidden to be committed to Git.
# Sourcing scripts will instantly fail-closed if URL or Token is missing.
if [ -z "$ISSUE_HUB_URL" ]; then
    echo "CRITICAL SECURITY ERROR: ISSUE_HUB_URL environment variable is not defined."
    echo "Please set ISSUE_HUB_URL in your environment or local .env file."
    exit 1
fi

if [ -z "$ISSUE_HUB_TOKEN" ]; then
    echo "CRITICAL SECURITY ERROR: ISSUE_HUB_TOKEN environment variable is not defined."
    echo "Please set ISSUE_HUB_TOKEN in your environment or local .env file."
    exit 1
fi

# 3. Default Issue Context Parameters
ISSUE_HUB_DEFAULT_PROJECT="${ISSUE_HUB_DEFAULT_PROJECT:-tessallite}"
ISSUE_HUB_DEFAULT_REPOSITORY="${ISSUE_HUB_DEFAULT_REPOSITORY:-tessallite-workspace}"
ISSUE_HUB_DEFAULT_BRANCH="${ISSUE_HUB_DEFAULT_BRANCH:-main}"
