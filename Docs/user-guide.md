# Tessallite Issue Hub - User Guide

Tessallite Issue Hub is the central authoritative issue registry service designed **specifically for parallel AI coding agents** working on overlapping codebase areas or isolated code trees. It establishes a centralized, non-colliding single source of truth, supporting automated AI agents via an HTTP API and a non-interactive command-line interface (`issue`), alongside human administration through a modern, responsive web application portal.

*For specific integration guidelines for AI coding agents, please read the [AI Agent Handbook](../docs/Agent.md). For a complete visual layout of every visual control and its API parity counterpart, read the [Compatibility & Parity Matrix](../docs/Compatibility-Matrix.md).*

---

## 1. Non-Interactive Command-Line Interface (`issue`)

The `issue` CLI is a zero-dependency python application using the standard library.

### Configuration Precedence
The CLI resolves settings in the following order:
1. **Command line flags** (e.g. `--url`, `--token`, `--project`, `--repository`)
2. **Environment variables** (e.g. `ISSUE_HUB_URL`, `ISSUE_HUB_TOKEN`, `ISSUE_HUB_PROJECT`, `ISSUE_HUB_REPOSITORY`)
3. **User configuration file**:
   - **Linux/macOS:** `~/.config/tessallite-issue-hub/config.json`
   - **Windows:** `%APPDATA%\Tessallite\IssueHub\config.json`

### Creating an Issue
To create a complete issue, both severity and description are required:
```bash
issue create --severity CRITICAL --title "Null pointer in scheduler" --description "The scheduler crashes on null values."
```

### Reserving an ID
To pre-allocate a sequence number without detail fields:
```bash
issue create --reserve
```

### Finding an Issue
Finding an issue by text query executes an all-inclusive wide search across every database column simultaneously (using SQL OR matching). You can search for a sequence number (e.g. `9627`), a status (e.g. `PARTIAL`), a tag, an owner, or a description word:
```bash
issue find Bug-1000
issue find "9627"
issue find "scheduler crashes"
```

To view the audit and modification history of an issue:
```bash
issue find Bug-1000 --history
```

### Updating or Retiring an Issue
Modify fields on an existing issue:
```bash
issue update Bug-1000 --set status=RESOLVED
```

Retire duplicates or invalid entries:
```bash
issue update Bug-1000 --retire DUPLICATE --duplicate-of Bug-999 --retire-note "Duplicate of Bug-999"
```

---

## 2. Server-Rendered Web Application Portal

The web portal is accessible at `http://localhost:8080/` (or your configured URL) and requires administrative login.

### Dashboard and Search
The homepage displays a summary card with running totals of issues (All, Open, Closed, Reserved, Retired), a text search input, and dimension filters (Project, Repository, Status, Severity, Tag, and Retirement state).

### Creating and Completing Issues
Humans can create issues or reserve IDs using the interactive form. The form automatically normalizes parameters and previews the generated ID structure dynamically based on the project template.

### Detail and Audit Logs
The detail view renders Markdown descriptions, supports description appending with automated server timestamps, handles retirement, and displays a complete chronological audit log of all mutations with before/after snapshot deltas.

### Lookup Vocabularies
Administrators can inspect lookup vocabularies (Statuses, Severities, Priorities, Efforts, Domains, Categories, and Retirement Reasons) and configure the global ID template under the Configuration section.

---

## 3. Terminal Shell Wrapper Scripts (`scripts/`)

To streamline administrative and operational tasks without requiring raw Python commands or manual JSON curls, a suite of lightweight, dependency-free Bash wrapper scripts is provided inside the `scripts/` directory.

### Centralized Configuration File (`scripts/config.sh`)
All wrapper scripts source a central configuration file `scripts/config.sh` to load default parameters, URLs, security tokens, and context settings:
- **Environment Integration:** It automatically sources your local private `.env` file from the project root as the highest priority context.
- **Connection Configuration:** Defines default API connection properties:
  - `ISSUE_HUB_URL="https://hub.yourdomain.com"`
  - `ISSUE_HUB_TOKEN="<your_api_bearer_token>"`
- **Context Defaults:** Defines default project context fields if omitted by commands:
  - `ISSUE_HUB_DEFAULT_PROJECT="tessallite"`
  - `ISSUE_HUB_DEFAULT_REPOSITORY="tessallite-workspace"`
  - `ISSUE_HUB_DEFAULT_BRANCH="main"`

### Operational Wrapper Scripts
- **`./scripts/run_migration.sh`:** Sourced config values, validates that the `migration_sources/` active and closed registries are ready, and executes the production-scale database migration cleanly and securely inside an empty database transaction block.
- **`./scripts/create_issue.sh`:** Takes standard CLI parameters (`--title`, `--severity`, `--description`, and optional overrides like `--project`, `--repository`, `--branch`, `--area`, `--refs`) and dynamically formats and posts the JSON payload.
- **`./scripts/reserve_issue.sh`:** Pre-allocates a sequential `Bug-N` ID immediately via the API and outputs only the cleanly allocated ID to the console.
- **`./scripts/find_issue.sh`:** Executes case-insensitive queries by text query, exact ID/AKA (`--id`), status, or severity, and pretty-prints the JSON output.
- **`./scripts/update_issue.sh`:** Patches metadata fields (`--status`, `--severity`, `--owner`), handles atomic tag additions/removals (`--add-tag`, `--remove-tag`), appends comments (`--append-file`), and retires issues (`--retire`).

