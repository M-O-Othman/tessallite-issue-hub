# Tessallite Issue Hub

Tessallite Issue Hub is an authoritative, independent central issue-recording service and database sequence allocator. It is designed specifically for autonomous AI coding agents working in parallel on a codebase in potentially overlapping areas, or in isolated code trees that need a unified, non-colliding common reference for issue registries. 

By replacing manual Markdown/Git-based issue-intake files, it permanently solves horizontal scaling race conditions, multiple worktree write locks, and duplicate ID merge collisions.

## Key Features
- **Central Authority for AI Agents:** Solves horizontal scaling, parallel git branching, and multiple worktree collision bugs.
- **Durable Identity:** Generates non-colliding numeric IDs via PostgreSQL sequences.
- **Dual Interfaces:** Provides a zero-dependency, non-interactive CLI client (`issue`) for automated agents and a responsive Web UI for humans.
- **High-Performance Indexed Search:** Full database indexing (GIN index on JSONB tags, B-Tree indexes on dimensions and date boundaries) with wide text scoring.
- **One Filter Surface:** The REST API, the issue list, and the analytics dashboard bind to a single shared filter definition, so the same query string returns the same result set on every surface.
- **Sortable, Stably Paginated Lists:** Any mapped column can order the list in either direction, with lookup-backed columns ordered by their configured rank. Every ordering carries a unique tiebreaker, so paging never repeats or skips a row.
- **Server-Side Analytics:** Charts and KPIs are driven by a SQL-filtered set, with a two-dimension treemap and the full filter vocabulary of the issue list.
- **Audit Logging:** Keeps full history snapshots of all mutations with single-query batch retrieval.
- **Advisory Vocabularies:** Allows editable configuration parameters while keeping data flexible.

## Project Structure
- `src/issue_hub/`: FastAPI web server, API endpoints, Jinja2 templates, database schema, and migration logic.
- `src/issue_cli/`: Standard zero-dependency Python package exposing the CLI entry point `issue`.
- `docs/Agent.md`: The official [AI Agent Handbook](docs/Agent.md) explaining integration protocols for parallel AI coding agents.
- `docs/Compatibility-Matrix.md`: The official [Compatibility & Parity Matrix](docs/Compatibility-Matrix.md) establishing visual form-to-API consistency.
- `docs/help/home.md`: The chained [Markdown Help Center](docs/help/home.md) covering APIs, CLI, web portal, migration, and deployment.
- `Docs/user-guide.md`: The comprehensive [User Guide](Docs/user-guide.md).
- `Docs/known_issues.md`: The [Known Issues and Defect Registry](Docs/known_issues.md).
- `Docs/future_features.md`: The [Future Features and Enhancements](Docs/future_features.md) backlog of deferred, out-of-scope items.
- `src/issue_hub/resources/ui_config.json`: Non-secret presentation and parsing configuration (accepted date formats, page size and ceiling, sortable columns, analytics dimensions, palettes).
- `scripts/reassign_issue.sh`: A cross-platform [Issue ID Reassignment Script](scripts/reassign_issue.sh) to safely scan and rewrite legacy or temporary issue IDs across a codebase.
- `tests/`: Comprehensive self-contained test suite including unit, integration, concurrency, CLI, and web tests.

## Configuration
Secrets and environment-specific values come from the environment (see `.env.example`). Non-secret presentation and parsing settings live in `src/issue_hub/resources/ui_config.json` and can be changed without touching code:

| Key | Purpose |
| :--- | :--- |
| `date_input_formats` | Date formats accepted from users and API clients, in addition to ISO 8601. |
| `date_display_format` | Format used when a date is rendered back into a form field. |
| `pagination.fallback_limit` | Page size used when neither the request nor the `search_default_limit` hub setting supplies one. |
| `pagination.max_limit` | Hard ceiling on page size, enforced by API validation. |
| `pagination.page_window` | Number of page links shown around the current page. |
| `default_sort` | Ordering applied when no sort is requested and no text search is active. |
| `lookup_backed_columns` | Columns ordered by `lookup_values.display_order` rather than alphabetically. |
| `list_sort_columns` | Sortable columns of the issue table, with labels and widths. |
| `analytics_dimensions` | Dimensions offered by the treemap and distribution charts. |
| `analytics_projection_fields` | Columns sent to the analytics page. Keeps heavy text columns out of the payload. |
| `severity_colors`, `treemap_palette` | Chart colours. |
| `lookup_lists` | Lookup vocabularies exposed to the filter UI. |

## Running the Tests
```bash
python -m pytest
```
Tests run against a database whose name must contain `test`; the suite refuses to start otherwise.
