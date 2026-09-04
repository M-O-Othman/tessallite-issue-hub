# Tessallite Issue Hub — Known Issues and Defect Registry

## Active Known Issues
There are currently no active open bugs. All identified issues have been resolved, verified with automated tests, and closed.

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
