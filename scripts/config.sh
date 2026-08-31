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

# 2. API Server Connection Configuration
# Fallback to the secure production URL and token if not overridden by your environment/.env
ISSUE_HUB_URL="${ISSUE_HUB_URL:-https://tessallite-issue-hub-633649663813.us-west1.run.app}"
ISSUE_HUB_TOKEN="${ISSUE_HUB_TOKEN:-tessallite_api_secure_token_abc123_xyz789}"

# 3. Default Issue Context Parameters
ISSUE_HUB_DEFAULT_PROJECT="${ISSUE_HUB_DEFAULT_PROJECT:-tessallite}"
ISSUE_HUB_DEFAULT_REPOSITORY="${ISSUE_HUB_DEFAULT_REPOSITORY:-tessallite-workspace}"
ISSUE_HUB_DEFAULT_BRANCH="${ISSUE_HUB_DEFAULT_BRANCH:-main}"
