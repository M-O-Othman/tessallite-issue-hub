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
To create a complete issue, both severity and description are required. You can also specify domain, category, priority, expected effort, owner, area, refs, and multiple tags:
```bash
issue create \
  --severity CRITICAL \
  --priority P0 \
  --expected-effort M \
  --title "Null pointer in scheduler" \
  --description "The scheduler crashes on null values." \
  --domain scheduler \
  --category product \
  --owner agent-1 \
  --tag core \
  --tag perf
```

### Reserving an ID
To pre-allocate a sequence number without detail fields:
```bash
issue create --reserve
```

### Finding an Issue
Finding an issue by text query executes an all-inclusive wide search across every database column simultaneously (using SQL OR matching). You can search for a sequence number (e.g. `9627`), a status (e.g. `PARTIAL`), a tag, an owner, or a description word. You can also filter by domain, category, priority, effort, owner, tag, and chronological boundaries:
```bash
issue find Bug-1000
issue find "9627"
issue find "scheduler crashes" --domain scheduler --priority P0
issue find --tag perf --closed-after 2026-08-01
```

Results can be ordered and paged. `--sort` takes a column name followed by an
optional direction (`asc` is assumed). Columns backed by a lookup vocabulary --
status, severity, priority, expected effort -- sort by their configured rank
rather than alphabetically, so severity reads CRITICAL, HIGH, MEDIUM, LOW:
```bash
issue find --sort "severity desc"
issue find --sort "updated_at desc" --limit 20
issue find --sort "-created_at" --limit 20 --offset 40
```

Branch, worktree, task, and update-time boundaries are also available:
```bash
issue find --branch main --task task-123
issue find --updated-after 01-09-2026 --updated-before 30-09-2026
```

Context options given before the subcommand apply to the search, so
`issue --project tessallite find --sort "severity desc"` searches only that
project.

To view the audit and modification history of an issue:
```bash
issue find Bug-1000 --history
```

### Updating or Retiring an Issue
Modify fields on an existing issue:
```bash
issue update Bug-1000 --set status=RESOLVED
```

You can also update the full description (via direct text or a file) and add or remove tags:
```bash
issue update Bug-1000 --description "New issue description" --add-tag core --remove-tag temp
# Or load the description from a file:
issue update Bug-1000 --description-file path/to/description.md
```

Retire duplicates or invalid entries:
```bash
issue update Bug-1000 --retire DUPLICATE --duplicate-of Bug-999 --retire-note "Duplicate of Bug-999"
```

---

## 2. Server-Rendered Web Application Portal

The web portal is accessible at `http://localhost:8080/` (or your configured URL) and requires administrative login.

### Site-Wide Global Project Selector
The top navigation bar features a site-wide **Project Context Dropdown**. Selecting a project from this context automatically stores your preference in a local cookie, dynamically pre-filtering and customizing:
- The running issue counter statistics on the Dashboard.
- The default selected project on the "Create Issue" form.
- The active results shown in the central Issue Ledger.
- The statistical charts and visualizations on the Analytics page.

You can toggle back to `[ALL PROJECTS]` at any time to clear the session cookie.

### Collapsible Filter Control & Multi-Select Dimensions
The homepage features a highly styled, collapsible **Advanced Filters Section** that organizes search parameters into cohesive logic grids:
- **Multi-Select Dropdowns**: Projects, Repositories, Statuses, Severities, Priorities, Efforts, Domains, and Categories support selecting *multiple checkboxes simultaneously*. The backend processes these selections using high-performance SQL `IN` operators to display combined results. The dropdown triggers dynamically highlight selected items and summarize active criteria.
- **Granular Text Filters**: Input precise sub-searches for Tag, Owner, Area/Module, Classification, Task ID, or Worktree Path.
- **Identity and Location Filters**: Search by Issue ID (accepting several comma-separated IDs, and matching alternate identifiers), Branch, Task ID, or Worktree Path.
- **Chronological Boundaries**: Search for issues created (`Created After` / `Created Before`), updated (`Updated After` / `Updated Before`), or retired/closed (`Closed After` / `Closed Before`) within specific dates.

Multi-value filters accept either repeated parameters or a comma-separated list, so `?status=OPEN&status=RESERVED` and `?status=OPEN,RESERVED` are equivalent. The **Analytics** button carries the current filters straight to the dashboard, and the **Issues** button on the dashboard carries them back.

### Sorting the Issue List
Every column header in the issue table is a sort control. Clicking a header sorts by that column ascending; clicking it again reverses the direction. The active column shows an arrow indicating the current direction. Sorting preserves all active filters and returns to the first page.

Ordering is always deterministic: a unique tiebreaker is applied beneath whichever sort is active, so paging through results never repeats or skips an issue even when many rows share the same sort value.

### Pagination
The footer reports the rows actually on the current page, the total number of matches, and the current page number, alongside first, previous, numbered, next, and last controls. Page links carry the active filters and sort.

Changing any filter or running a new search returns to the first page rather than holding the previous page position. Requesting a page beyond the end of the results -- which can happen after narrowing a filter -- shows the last page that exists instead of an empty table.

Page size follows the `search_default_limit` hub setting unless a `limit` is supplied, and is capped by `pagination.max_limit` in `ui_config.json`.

### Creating and Completing Issues
Humans can create issues or reserve IDs using the interactive form. The form automatically normalizes parameters and previews the generated ID structure dynamically based on the project template.

### Detail and Audit Logs
The detail view renders Markdown descriptions, supports description appending with automated server timestamps, handles retirement, and displays a complete chronological audit log of all mutations with before/after snapshot deltas.

### Analytics Dashboard
The dashboard offers the same filter vocabulary as the issue list, applied in SQL on the server. Every KPI and every chart is drawn from that one filtered set, so a filter cannot reach some charts and miss others. Filters live in the URL, so a filtered view can be shared or bookmarked.

- **KPI cards**: total scope, open backlog, closed, and closure rate.
- **Timescale burndown**, **daily technical debt movement**, **aging work in progress**, and **investment allocation** charts.
- **Treemap**: segments by two independently chosen dimensions. The first groups the outer tiles; the second, which is optional, subdivides each group into nested tiles. Severity is one dimension among many rather than a fixed second axis. No minimum tile size is imposed, so small segments remain visible.
- **Distribution analysis** and **project contribution volume** charts.
- **Date presets** (Today, This Week, This Month, Last 30 Days, This Year, All Time) fill the created-date filters and resubmit.

Dimensions offered by the treemap and distribution charts are configured in `analytics_dimensions` in `ui_config.json`.

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

