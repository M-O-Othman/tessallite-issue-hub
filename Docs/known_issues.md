# Tessallite Issue Hub — Known Issues and Defect Registry

## Active Known Issues

### A1. Legacy-Import Records Carry Oversized `aka` Values
- **File Reference:** `src/issue_hub/migration/registry_parser.py`, `src/issue_hub/migration/import_service.py`
- **Symptom:** 11 of 3,372 non-null `aka` values in the production database exceed 2,704 bytes, the largest being 10,495 bytes (for example `Bug-3611`). The field is specified to hold a short alternate identifier such as `Bug-1045`, but these rows contain entire registry description bodies. This blocked creation of a B-Tree index on the column (see Resolved item 6) and inflates every row that carries one.
- **Root Cause:** The legacy registry parser captures the AKA group as `[^—]+` (`registry_parser.py:7`), which absorbs trailing prose when a source line does not terminate the alias with an em-dash. `import_service.py:89` then concatenates further aliases with `" / "` on re-import, compounding the length. 9 of the 11 oversized values contain the `" / "` separator.
- **Status:** OPEN. Production data has not been modified. Requires a parser fix plus a one-off backfill to truncate affected `aka` values to their leading identifier.

---

## Resolved Issues

### 1. Missing Datetime Import in Web Route Date Parsing
- **File Reference:** `src/issue_hub/web/routes.py`
- **Symptom:** `NameError: name 'datetime' is not defined` occurred inside `parse_user_date` when filtering issues by date ranges, causing 500 errors and test failures.
- **Root Cause:** Standard library `datetime` import was omitted while `datetime.strptime` was invoked.
- **Resolution:** Added `from datetime import datetime` to `routes.py`. Verified via `tests/web/test_web_routes.py`.

### 2. External Server Dependency in CLI Integration Tests
- **File Reference:** `tests/cli/test_cli_operations.py`
- **Symptom:** Subprocess CLI tests failed with `Connection refused` (exit code 5) whenever pytest ran without an external server listening on port 8080.
- **Root Cause:** Test runner lacked an automated server lifecycle fixture for subprocess tests.
- **Resolution:** Implemented an in-process, background `uvicorn` test server fixture in `tests/cli/test_cli_operations.py` bound to an ephemeral port.

### 3. Missing Indexes on High-Frequency Filter Dimensions and JSONB Tags
- **File Reference:** `migrations/versions/f1127bbc1194_add_performance_indexes.py`
- **Symptom:** Querying `Issue.tags.contains([tag])` and filtering on `severity`, `priority`, `domain`, `category`, `owner`, `created_at`, and `retired_at` caused sequential table scans.
- **Root Cause:** Initial database migration lacked GIN indexing for JSONB tags and B-Tree indexes for categorical filter columns.
- **Resolution:** Created and applied Alembic migration `f1127bbc1194_add_performance_indexes` adding GIN index `issues_tags_gin_idx` and B-Tree indexes on all filtered columns.

### 4. REST API Parity Gaps on Multi-Select Dimensions and Closed Date Ranges
- **File Reference:** `src/issue_hub/api/issues.py`
- **Symptom:** While the search layer supported multi-value lists and closed date ranges, the REST endpoint `GET /api/v1/issues` only accepted scalar values and lacked `closed_from`/`closed_to`.
- **Root Cause:** API route signature had not been updated following the Phase 4 search engine enhancements.
- **Resolution:** Updated `api_list_issues` to accept `List[str] = Query(None)` for categorical dimensions and added `closed_from`/`closed_to` query parameters.

### 5. N+1 Database Query Overhead on History Retrieval
- **File Reference:** `src/issue_hub/api/issues.py`
- **Symptom:** Requesting issues with `include_history=True` executed an individual database query per returned issue row.
- **Root Cause:** History records were retrieved inside a loop rather than batched.
- **Resolution:** Implemented batch querying via `IssueHistory.issue_id.in_(issue_ids)` and in-memory grouping, reducing database round-trips to a single query.

### 6. Unusable and Uncreatable B-Tree Index on `issues.aka`
- **File Reference:** `migrations/versions/f1127bbc1194_add_performance_indexes.py`
- **Symptom:** Applying migration `f1127bbc1194` to the production database failed with `index row size 3016 exceeds btree version 4 maximum 2704 for index "issues_aka_idx"`. Because Alembic wraps a migration in a transaction, the failure would have rolled the entire migration back and, since `entrypoint.sh` runs `alembic upgrade head` on start, crash-looped the container on deploy. The defect was invisible locally because the test database holds only short `aka` values.
- **Root Cause:** Two independent faults. First, production `aka` data exceeds the B-Tree row limit (see Active item A1). Second, and decisive, a raw B-Tree on `aka` cannot serve any query the application issues against that column: `search.py:51` filters with a `~*` regex, `search.py:156` filters with a leading-wildcard `ILIKE '%q%'`, and `search.py:191` ranks with `LOWER(aka) = LOWER(q)`. None of these are B-Tree-satisfiable, so the index was dead weight even on clean data.
- **Resolution:** Removed `issues_aka_idx` from migration `f1127bbc1194` (upgrade and downgrade) and documented the exclusion in the migration docstring. The remaining eight indexes are unaffected. The stale index was also dropped from the local test database so both environments match the migration.

### 7. Production Index Migration Was Not Idempotent and Blocked Writes
- **File Reference:** `migrations/versions/f1127bbc1194_add_performance_indexes.py`
- **Symptom:** `op.create_index` emits plain `CREATE INDEX`, which takes a `SHARE` lock on `issues` and blocks all INSERT/UPDATE/DELETE for the duration of the build. It also aborts outright if an index already exists, which is exactly the state left behind when the same indexes are built out-of-band on a live database.
- **Root Cause:** The migration was authored against a small local test database, where neither the write stall nor the pre-existing-index case ever arises.
- **Resolution:** Rewrote the migration to emit `CREATE INDEX IF NOT EXISTS` / `DROP INDEX IF EXISTS`, so an out-of-band rollout and the migration converge instead of colliding. Verified against three states: indexes already present, clean slate, and already at head. The production rollout itself was performed with `CREATE INDEX CONCURRENTLY` (no write lock) and validated via `pg_index.indisvalid`. See `Docs/future_features.md` for making the migration itself concurrency-safe.

### 8. Production Outage: Database Stamped to a Revision the Deployed Image Did Not Contain
- **File Reference:** `entrypoint.sh`, `migrations/versions/f1127bbc1194_add_performance_indexes.py`
- **Symptom:** Cloud Run served HTTP 503/500 for roughly four minutes. Container logs showed `ERROR [alembic.util.messaging] Can't locate revision identified by 'f1127bbc1194'` followed by `Container called exit(255)` and a failed startup probe. The service has `min-instances 0`, so the fault stayed latent until the first cold start rather than appearing at the moment it was introduced.
- **Root Cause:** After building the performance indexes out-of-band, the `alembic_version` table was stamped to `f1127bbc1194` while the *deployed image* still predated that migration and therefore had no such revision file. `entrypoint.sh` runs `alembic upgrade head` on every container start; alembic aborts when the recorded revision is absent from its script directory. The change was made on the assumption that an older image would simply treat the newer revision as a no-op, which is wrong: alembic errors rather than ignoring an unknown revision. Ordering was the real fault -- the database was moved ahead of the code that understood it.
- **Resolution:** Reverted `alembic_version` to `35908fccae73`, which restored service immediately on the next request. Made the migration idempotent (item 7) so the indexes already present would not collide, then built the image, verified it start-to-finish against a database in production's exact state (indexes present, version `35908fccae73`), and deployed. The migration then advanced the version itself as part of the rollout.
- **Prevention:** Never stamp a database to a revision the currently deployed image does not contain. Advance the schema version by deploying the image that carries the migration, and keep index-adding migrations idempotent so an out-of-band build and the migration converge.

### 9. Global CLI Context Options Silently Dropped by the `find` Subcommand
- **File Reference:** `src/issue_cli/main.py`
- **Symptom:** `issue --project X find` returned results for every project. The same applied to `--repository`, and to `--branch`/`--worktree` once those were added as filters. Values supplied before the subcommand were discarded without warning.
- **Root Cause:** `find_parser` redeclares options that also exist on the global parser. argparse applies the subparser's own default (`None`) after the global parser has already set the attribute, overwriting the caller's value.
- **Resolution:** Set `default=argparse.SUPPRESS` on the redeclared options so the subparser leaves the attribute untouched unless the flag is actually supplied. A value given after the subcommand still wins. Covered by `tests/cli/test_cli_parser.py`.

### 10. Issue List Could Not Be Sorted
- **File Reference:** `src/issue_hub/web/routes.py`, `src/issue_hub/web/templates/list.html`
- **Symptom:** The issue list offered no way to change the ordering. Results were always newest-first.
- **Root Cause:** `search.py` accepted a `sort` argument but `get_issues_list` neither declared nor forwarded one, and the table had no sortable headers. The sort field was also resolved with an unvalidated `getattr(Issue, field)`, which accepted any attribute name rather than only real columns.
- **Resolution:** Added `sort` to the shared filter dependency and sortable column headers to the table. Sortable fields are now derived from the SQLAlchemy mapper, so only mapped columns are accepted and the set cannot drift from the model. Columns backed by `lookup_values` sort by `display_order`, so severity reads CRITICAL, HIGH, MEDIUM, LOW rather than alphabetically.

### 11. Pagination Reported Wrong Bounds and Could Repeat or Skip Rows
- **File Reference:** `src/issue_hub/search.py`, `src/issue_hub/pagination.py`, `src/issue_hub/web/templates/list.html`
- **Symptom:** The footer showed counts like "Showing 201 to 150 of 150". Paging through a text search could show the same issue twice and never show others.
- **Root Cause:** Four distinct faults. The upper bound was computed as `offset + limit` instead of the rows actually returned. The template used the requested limit while the query silently clamped it to 1000. The web route hardcoded `limit=100`, bypassing the `search_default_limit` hub setting. Most seriously, ordering had no unique tiebreaker: with a text search the only sort key was a relevance score shared by most rows, and PostgreSQL does not guarantee a stable order for ties, so `LIMIT`/`OFFSET` windows overlapped.
- **Resolution:** Extracted pagination arithmetic into `pagination.py` and derived every rendered number from the rows returned and the limit actually applied. `resolve_limit` is now the single place the page size is decided. A unique tiebreaker (`sequence_number`) is appended to every ordering path. Out-of-range offsets snap to the last real page instead of rendering an empty table.

### 12. New Search Reused the Previous Page Offset
- **File Reference:** `src/issue_hub/web/templates/list.html`
- **Symptom:** Changing a filter while on page 5 ran the new search but kept offset 400, so the user landed deep inside, or past the end of, an unrelated result set.
- **Root Cause:** The filter form carried `offset` in a hidden input that persisted across submissions.
- **Resolution:** Removed the hidden input. Pagination is now ordinary links that carry an explicit offset, so any filter change submits without one and starts at page 1.

### 13. Analytics Treemap Segmented on One Dimension and Rendered Flat
- **File Reference:** `src/issue_hub/web/templates/visualization.html`
- **Symptom:** The card advertised a multi-dimensional treemap with nested tiles, but offered a single "Segment By" control and drew a flat chart.
- **Root Cause:** `updateTreemap` combined the chosen dimension and a hardcoded severity into one string key (`"${val} - ${sev}"`) and pushed the result into a flat array with no `children`, so no hierarchy existed. `visibleMin: 10` additionally hid any segment smaller than ten issues.
- **Resolution:** Two independent user-selected dimensions ("Segment by" and "then by", the second optional) building a real nested hierarchy with `children`. Severity is now one option among many rather than a fixed second axis. Removed `visibleMin` so small segments stay visible.

### 14. Analytics Filters Were Incomplete and Duplicated in Client-Side JavaScript
- **File Reference:** `src/issue_hub/web/routes.py`, `src/issue_hub/web/templates/visualization.html`
- **Symptom:** The dashboard offered five filters against the issue list's twenty-plus, and the filter logic existed twice in JavaScript, so the two copies could disagree about which charts saw which rows.
- **Root Cause:** `get_visualization` accepted no filter parameters at all. It loaded every issue and filtered in the browser, with the logic duplicated between `updateDashboard` and `getActiveFilteredIssues`.
- **Resolution:** Analytics now binds to the same `IssueFilterParams` dependency and the same `build_issue_query` builder as the issue list and the REST API, and renders its filter UI from the same Jinja macros. Filtering happens once, in SQL, so every chart and KPI reflects the same set by construction. Both duplicated JavaScript filter functions were deleted.

### 15. Analytics Inlined Every Column of Every Issue Into the Page
- **File Reference:** `src/issue_hub/web/routes.py`
- **Symptom:** `/visualization` serialised all 33 columns for every issue into the HTML, including `description`, `legacy_raw`, and `aka` -- the last of which holds values up to 10 KB (see Active item A1). The charts read only ten fields.
- **Root Cause:** The route dumped `Issue.to_dict()` for every row rather than projecting the columns the dashboard actually uses.
- **Resolution:** The query projects only the fields listed in `analytics_projection_fields`, and server-side filtering means only matching rows are sent at all.

### 16. REST API and Web Interface Exposed Different Filter Surfaces
- **File Reference:** `src/issue_hub/filters.py`, `src/issue_hub/api/issues.py`, `src/issue_hub/web/routes.py`
- **Symptom:** The same conceptual query produced different results depending on the surface. The web list had no `id`, `branch`, `updated_from`/`updated_to` or `sort`; it named date bounds `created_after`/`created_before` where the API used `created_from`/`created_to`; the API split comma-separated values while the web did not; and the API honoured the `search_default_limit` setting while the web hardcoded 100.
- **Root Cause:** Each surface declared and normalised its own query parameters independently, so they drifted apart with every change.
- **Resolution:** Introduced `issue_hub/filters.py` as one shared FastAPI dependency binding the API, the issue list, and analytics to a single filter surface. Historical web parameter spellings are accepted as aliases so existing bookmarks keep working. Parity is enforced by tests that assert identical totals across all three surfaces for the same query string.

