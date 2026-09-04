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
Organizes search parameters into logical groups with multi-select dropdown menus (supporting multiple checkboxes simultaneously via SQL `IN` operators), granular text filters (Owner, Tag, Area, Classification, Task, Worktree), and timestamp boundaries (`Created After/Before`, `Closed After/Before`).

#### 3. Creation and Reservation Form
Allows creating full issues or pre-allocating reserved IDs instantly. The form normalizes input parameters, strips illegal characters, and displays a dynamic preview of the generated canonical ID based on project key templates.

#### 4. Markdown Rendering and Audit Timelines
Displays issue descriptions with styled Markdown rendering. Includes controls to edit metadata fields, append discussion notes with automatic server timezone stamps, and inspect chronological mutation histories with side-by-side JSON snapshot deltas.

---

[Previous: Agent CLI](cli.md) | [Home: Help Home](home.md) | [Next: Legacy Migration Tooling](migration.md)
