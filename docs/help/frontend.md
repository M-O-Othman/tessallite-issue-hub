# 3. Interactive Web UI Portal

[Previous: Agent CLI](cli.md) | [Home: Help Home](home.md) | [Next: Legacy Migration Tooling](migration.md)

---

The Issue Hub provides a secure, server-rendered Web UI built using Python FastAPI, Jinja2 template engines, and Bootstrap 5, allowing administrators to audit and manage the issue registry.

### A. Security and Sessions
Web access requires logging in with admin credentials configured through environment secrets (`ISSUE_HUB_WEB_USERNAME` and `ISSUE_HUB_WEB_PASSWORD_HASH`). Upon authentication, an encrypted, signed session cookie (`issue_hub_session`) is created using Starlette's `SessionMiddleware` to track state securely and statelessly.

### B. Portal Pages

#### 1. Summary Dashboard & Global Project Context
Displays real-time metric counter cards (All Issues, Open, Closed, Reserved, Retired) and provides a top-navbar global project selector. Selecting a project stores a cookie preference and filters all dashboard statistics, lists, and forms accordingly.

#### 2. Advanced Collapsible Filters
Organizes search parameters into logical groups with multi-select dropdown menus (supporting multiple checkboxes simultaneously via SQL `IN` operators), granular text filters (Issue ID, Branch, Owner, Tag, Area, Classification, Task, Worktree), and timestamp boundaries for created, updated, and closed dates. Multi-value filters accept repeated parameters or a comma-separated list interchangeably.

The filter controls are rendered from Jinja macros shared with the analytics dashboard, and both pages bind to the same server-side filter definition as the REST API, so the three surfaces cannot offer different filtering vocabularies.

#### 3. Sorting and Pagination
Every column header sorts the list by that column, reversing direction on a second click and showing an arrow for the active column. Sorting keeps the active filters and returns to the first page. Lookup-backed columns sort by their configured rank rather than alphabetically, and a unique tiebreaker beneath every ordering guarantees that paging never repeats or skips an issue.

The footer reports the rows actually on the page, the total matches, and the page number, with first, previous, numbered, next, and last links that carry the filters and sort. A new search always starts at page 1, and an offset past the end of the results falls back to the last page that exists.

#### 4. Analytics Dashboard
Offers the same filter vocabulary as the issue list, applied in SQL. Every KPI and chart is drawn from that single filtered set, so a filter always applies to all graphs. Filters live in the URL and can be shared. The treemap segments by two independently chosen dimensions, the second optional, rendered as a genuine nested hierarchy.

#### 5. Creation and Reservation Form
Allows creating full issues or pre-allocating reserved IDs instantly. The form normalizes input parameters, strips illegal characters, and displays a dynamic preview of the generated canonical ID based on project key templates.

#### 6. Markdown Rendering and Audit Timelines
Displays issue descriptions with styled Markdown rendering. Includes controls to edit metadata fields, append discussion notes with automatic server timezone stamps, and inspect chronological mutation histories with side-by-side JSON snapshot deltas.

---

[Previous: Agent CLI](cli.md) | [Home: Help Home](home.md) | [Next: Legacy Migration Tooling](migration.md)
