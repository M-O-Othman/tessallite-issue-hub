# Tessallite Issue Hub — Action Plan (Comprehensive Fixes & Enhancements)

## Status: Completed

---

### Objectives
1. [x] Fix active defects (`datetime` import in web routes, CLI test harness server coupling).
2. [x] Add performance database indexes (GIN on `tags`, B-tree on filter and date columns).
3. [x] Ensure strict local-only execution (do not touch GCP deployed service).
4. [x] Establish API and CLI feature parity (multi-select dimensions, closed date boundaries).
5. [x] Optimize query performance (eliminate N+1 query on history, batch DB readiness check).
6. [x] Fulfill all documentation standards (mirrored chained markdown help center, known issues tracking).
7. [x] Execute full validation pass and commit locally without pushing to remote.

---

### Phase 1: Local Environment & Safety Configuration
- [x] Update `.env` to point to local Docker PostgreSQL instance (`localhost:5432`) to ensure GCP VM (`34.82.232.232`) is never touched.
- [x] Create `.env.example` documenting all configuration keys with safe development defaults.

### Phase 2: Immediate Bug Fixes & Test Suite Decoupling
- [x] Add `from datetime import datetime` in `src/issue_hub/web/routes.py` to fix runtime `NameError` on `/issues` date filtering.
- [x] Add automated in-process test server fixture in `tests/cli/test_cli_operations.py` (spawning an ephemeral uvicorn instance on a dedicated test port) so that CLI integration tests run cleanly without external dependencies.
- [x] Run pytest to verify immediate pass on fixed modules.

### Phase 3: Database Indexing Optimization
- [x] Generate a new Alembic migration to add performance indexes:
  - GIN index on `issues.tags` (JSONB) for fast containment queries (`tags @> '["..."]'`).
  - B-tree indexes on `issues.severity`, `issues.priority`, `issues.domain`, `issues.category`, `issues.owner`, `issues.aka`, `issues.created_at`, `issues.retired_at`.
- [x] Apply Alembic migration locally to `issue_hub` and `issue_hub_test`.

### Phase 4: API, CLI, and Search Parity & Query Optimization
- [x] Update `GET /api/v1/issues` in `src/issue_hub/api/issues.py`:
  - Add `closed_from` and `closed_to` query parameters.
  - Support multi-value list queries (`Query(None)`) for `status`, `severity`, `priority`, `project`, `repository`, `domain`, `category`.
  - Eliminate N+1 query on `include_history=True` by batch-fetching history records in a single query.
- [x] Update CLI client in `src/issue_cli/main.py`:
  - Add `--domain`, `--category`, `--priority`, `--effort`, `--tag`, `--owner`, `--area`, `--closed-after`, `--closed-before` to `issue find`.
  - Add `--priority`, `--expected-effort`, `--tags`, `--refs`, `--owner`, `--branch`, `--worktree` to `issue create`.
- [x] Sanitize wildcard characters in search queries in `src/issue_hub/search.py`.
- [x] Consolidate table check in `src/issue_hub/database.py:check_db_connection` into a single SQL query.

### Phase 5: Documentation & Standards Compliance
- [x] Create mirrored markdown help files in `docs/help/`:
  - `home.md`, `apis.md`, `cli.md`, `frontend.md`, `migration.md`, `deployment.md`
  - Ensure all pages are logically chained with `(Previous) | (Home) | (Next)` links.
- [x] Remove emojis from `deploy.sh`.
- [x] Update `docs/Compatibility-Matrix.md` to reflect full CLI/API parity.
- [x] Update `Docs/known_issues.md` to document resolved issues.
- [x] Update `README.md` and `Docs/user-guide.md` to describe new CLI flags, API parameters, and indexes.

### Phase 6: Validation, Code Review & Local Commit
- [x] Run `ruff check .` and fix any static analysis warnings.
- [x] Run full test suite `pytest` across all test modules (unit, migration, web, integration, concurrency, cli).
- [x] Verify 100% tests pass.
- [x] Commit locally with corporate format `[scope] summary`.
- [x] Do not push to remote.
