# Tessallite Issue Hub - Development Action Plan

This document outlines the step-by-step implementation plan for building the **Tessallite Issue Hub**, adhering to the provided solution specification.

## Core Assumptions
1. **Migration Inputs:** As legacy files are not in the current workspace, we will implement the parsers and verify them using test fixtures/mocks that match the legacy formats specified in Section 23.
2. **Database:** Standard local PostgreSQL via Docker Compose will be utilized for both local development and testing.
3. **Web UI:** Standard Bootstrap 5 (CDN) + minimal vanilla JS/HTMX for a clean, corporate-grade, responsive user interface.
4. **Initial Sequence Baseline:** Default to `1000` or `1` if no legacy issues exist, but the migration tool will dynamically determine the baseline from maximum imported numeric suffix or old counter.

---

## Phase-by-Phase Roadmap

### Phase 0: Repository and Executable Skeleton (Done)
- [ ] Create repository layout according to Section 33:
  - `src/issue_hub/`
  - `src/issue_cli/`
  - `tests/`
  - `docs/`
- [ ] Establish Python environment via `pyproject.toml` using `poetry` or `pip` with `setuptools`. We will use standard `pyproject.toml` with `setuptools` or standard python tooling.
- [ ] Create `Dockerfile` and `docker-compose.yml` to run application and PostgreSQL.
- [ ] Implement initial `main.py` (FastAPI app) and a basic CLI script (`issue`).
- [ ] Add basic health endpoints (`/health/live`, `/health/ready`).

### Phase 1: Core Schema, Allocation, and API
- [ ] Set up SQLAlchemy database configuration and Alembic migration environment.
- [ ] Create database models in `models.py`:
  - `issues` (Primary live table)
  - `issue_history` (Audit and mutation history)
  - `lookup_values` (Advisory vocabularies)
  - `hub_settings` (Application configuration)
- [ ] Implement global PostgreSQL sequence `issue_number_seq`.
- [ ] Write key-template selection and rendering logic in `key_generation.py`.
- [ ] Implement core issue service in `issue_service.py` to handle creation/reservation inside a single atomic transaction.
- [ ] Implement read/search logic in `search.py` (exact, text, filter ranking).
- [ ] Implement API endpoints under `/api/v1/`:
  - `POST /issues` (Create/reserve)
  - `GET /issues` (Exact search, text search, filter list)
  - `PATCH /issues/{issue_id}` (Update fields, append description, retire)
  - `GET /issues/{issue_id}/history` (Audit history)
  - `/config/lookups` and `/config/settings` (Metadata administration)
- [ ] Implement simple bearer-token authentication for the API.

### Phase 2: Operational CLI and Agent README
- [ ] Implement the `issue` CLI package with zero-dependency HTTP and standard `argparse`.
- [ ] Add CLI commands:
  - `issue create` (options: metadata, `--reserve`, `--json`, `--description-file`)
  - `issue find` (by ID, text query, or filtering parameters)
  - `issue update` (options: `--set`, `--append-file`, `--add-tag`, `--retire`)
- [ ] Implement configuration precedence (CLI flag -> ENV var -> `config.json`).
- [ ] Verify execution in Linux Bash and Windows CMD/PowerShell environments.
- [ ] Write the Agent-facing README at `docs/execution/issue-hub/README.md`.

### Phase 3: Web Application and Configuration
- [ ] Implement Jinja2 server-rendered views within the FastAPI app.
- [ ] Set up basic secure session cookies with admin credentials matching environment variables.
- [ ] Design and implement the following pages using Bootstrap 5:
  - **Login Page** (Simple admin credentials)
  - **Issue List and Search Page** (Filters, search bar, active/retired status indicators)
  - **Create/Reserve Issue Page** (Form, live key preview, validation)
  - **Issue Detail/Edit/History Page** (Markdown rendering, description appending, retirement controls, history logs)
  - **Configuration Page** (Editable statuses, template strings, seed data lists)
- [ ] Implement HTML sanitization for rendered Markdown to prevent security risks.

### Phase 4: Migration Tooling and Dry Run
- [ ] Implement `registry_parser.py` (Parsing markdown active/closed registries).
- [ ] Implement `intake_parser.py` (Parsing markdown intake files).
- [ ] Implement `import_service.py` and `reconcile.py` to read, parse, validate, and dry-run import.
- [ ] Write sequence initialization logic to baseline the sequence number after importing.
- [ ] Build migration fixtures to thoroughly test all edge cases (duplicate IDs, AKA aliases, conflict blocking).

### Phase 5: Verification and Testing
- [ ] Write comprehensive Unit Tests (`tests/unit/`).
- [ ] Write Database Integration Tests (`tests/integration/`).
- [ ] Write Core Concurrency Test (`tests/concurrency/`) launching 100 simultaneous create requests to prove zero-collision allocation.
- [ ] Write CLI Compatibility Tests (`tests/cli/`).
- [ ] Write Web UI Tests (`tests/web/`).

---

## Definition of Done (Phase Gate Verification)
Before finalizing:
1. Verify all 100% test coverage and ensure all tests pass cleanly.
2. Run database migration tests to confirm PostgreSQL schema upgrades successfully.
3. Validate that no hardcoded credentials exist.
4. Ensure code passes linters/type checkers (`ruff`, `mypy` or standard options).
