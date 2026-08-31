# Tessallite Issue Hub — Action Plan (Phase 4)

## Status: Completed

---

## Phase 4: Advanced Search, Filtering, and Site-Wide UX

### Objectives
1. [x] **Closed Date Range to Filter**: Support filtering issues by `retired_at` date ranges (`closed_after` and `closed_before`).
2. [x] **Enhanced Filter Block Design**: Modernize and redesign the filter block in `list.html` to be cleaner, collapsible, and beautifully organized into logic columns (e.g., Core Dimensions, Dates, Meta Attributes).
3. [x] **Site-wide Global Project Selector**:
   - Add a project selector to the top navbar in `base.html`.
   - Implement a backend endpoint (`/set-project`) that sets a cookie `global_project` with the selected project.
   - Filter all pages (Dashboard/Visualization, Issues List, Create Form) to default to or restrict by this selected project.
4. [x] **All Meta Fields in Filter**: Add Domain, Category, Area, Classification, Priority, Owner, Task, Worktree, and Expected Effort to the filter panel.
5. [x] **Multi-Select Filters**: Use custom, modern, lightweight Bootstrap checkbox dropdown menus for `status`, `severity`, `priority`, `domain`, `category`, `project`, and `repository` to allow filtering by multiple values at once (using SQL `IN` operator on the backend).

---

### Step-by-Step Implementation Strategy

#### 1. Backend Search Logic (`src/issue_hub/search.py`)
- [x] Update `query_issues` signature to allow `List[str]` (or `Optional[List[str]]`) for: `project`, `repository`, `status`, `severity`, `priority`, `domain`, `category`.
- [x] Update field filtering to use `column.in_(value)` if `value` is a list, falling back to `column == value` if it's a scalar string.
- [x] Add `closed_from` and `closed_to` (`datetime`) to query `Issue.retired_at`.

#### 2. Backend Web Routes (`src/issue_hub/web/routes.py`)
- [x] Implement a route `/set-project` which accepts a `project` query parameter, sets a `global_project` cookie, and redirects back to the previous page (`Referer`).
- [x] On `/issues` (`get_issues_list`), retrieve `global_project` from cookies. If a global project is set and no explicit `project` filter is in the request query parameters, default the `project` query parameter to the cookie value.
- [x] Update `get_issues_list` signature to receive lists of strings for multi-select fields (FastAPI `Query(None)`).
- [x] Parse `closed_after` and `closed_before` form/query parameters into `datetime` objects and pass them to `query_issues`.
- [x] Inject `global_project_cookie` into template responses so that the UI can highlight/select the correct active global project.

#### 3. Base Layout & Site-Wide Project Selector (`src/issue_hub/web/templates/base.html`)
- [x] Display a modern site-wide "Project Context" dropdown in the navbar.
- [x] List all active projects in this dropdown (fetched from database lookup values or context).
- [x] Clicking a project makes a GET request to `/set-project?project=PROJECT_VALUE` to update the active context.

#### 4. Web UI List & Filters (`src/issue_hub/web/templates/list.html`)
- [x] Completely redesign the filter block into an elegant, collapsible panel.
- [x] Style multi-selects as custom Bootstrap dropdown buttons that display checkable lists of options.
- [x] Add standard single inputs/date fields for Area, Classification, Task, Worktree, and the new Closed Date Range.
- [x] Provide clear "Reset Filters" and "Apply Filters" buttons.

#### 5. Verification & Testing
- [x] Write test cases for multi-select, date filtering, and global project context to ensure complete correctness.
- [x] Run ruff to keep the code perfectly clean.
