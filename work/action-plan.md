# Tessallite Issue Hub - Remediation Action Plan

This document details the step-by-step remediation plan to resolve every single critical and major finding from the Deep-Review Report, organized into six gates.

---

## Gate 1: Database Topology & Health Readiness
- [ ] **Remove Embedded Database:**
  - Update `Dockerfile` to NOT install PostgreSQL or start any PostgreSQL processes.
  - Remove all database initialization, cluster setup, and `pg_ctl` background run logic from `entrypoint.sh`.
  - Let `entrypoint.sh` run ONLY `alembic upgrade head` (against the configured external database) and then `uvicorn`.
- [ ] **Restore Multi-Service Compose:**
  - Configure `docker-compose.yml` with two separate services: `app` (FastAPI app) and `db` (PostgreSQL container using `postgres:16-alpine`).
  - DO NOT publish the database port `5432` to the host by default. Keep it strictly internal to the compose network for security.
- [ ] **Robust Health Readiness:**
  - Update `/health/ready` endpoint inside `src/issue_hub/api/health.py` to:
    - Check database connectivity.
    - Check that `alembic_version` table exists and contains the latest revision.
    - Check that the `issues` table and `issue_number_seq` sequence exist and are queryable.

## Gate 2: Security & Fail-Closed Behavior
- [ ] **Enforce Secret Settings & Fail-Closed Startup:**
  - Remove all default/hardcoded values for sensitive variables in production:
    - `api_token` (fail startup if not provided unless in local dev mode)
    - `session_secret` (fail startup if default or absent in production)
    - `web_password_hash` (require explicit hash, fail if default is active)
  - Define an explicit development profile variable (e.g. `ISSUE_HUB_ENV=development`). If not in development mode, refuse startup if default credentials are detected.
  - Default administrative import `import_enabled` setting to `False` in production.
- [ ] **Markdown Sanitization & Stored XSS Mitigation:**
  - Introduce an HTML sanitization helper inside the Jinja2 Markdown filter. Escape raw HTML or strip unsafe tags before rendering description and next step markdown.
- [ ] **CSRF Protection & Cookie Hardening:**
  - Add CSRF token generation and validation to all state-changing Web UI forms.
  - Configure the session cookie inside `starlette.middleware.sessions.SessionMiddleware` with `https_only=True` (in production), `httponly=True`, and `samesite="lax"`.
- [ ] **Body and Request Size Limits:**
  - Add a custom middleware to FastAPI to reject requests exceeding a safe limit (e.g., max 10MB) with a 413 Payload Too Large error.

## Gate 3: Domain Contracts & Inconsistencies
- [ ] **Fix Reservation Completion:**
  - In `create_issue` (when completing a previously reserved ID):
    - Retrieve the existing issue.
    - Apply ONLY fields explicitly supplied by the caller (using `exclude_unset=True` or checking request payload keys).
    - Prevent Pydantic defaults (like `project = tessallite`) from silently overwriting existing, custom-saved reserved issue values.
    - Perform a complete schema validation on the merged result, enforcing that `severity` and `description` are non-empty before transitioning the status from `RESERVED` to `OPEN`.
- [ ] **Forbid Extra Request Fields:**
  - Set Pydantic `model_config` to `extra="forbid"` on all request schemas (`CreateIssueRequest`, `UpdateIssueRequestSet`) to reject typos like `sttaus=FIXED`.
- [ ] **Explicit Field-Clearing Contract:**
  - Support setting fields to empty string `""` or a custom null marker to explicitly clear optional fields (such as `owner`, `area`, `source`, `aka`, `related_to`, etc.).
- [ ] **Enforce Database Settings:**
  - Update `create_issue`, `update_issue`, and `query_issues` services to dynamically load and utilize active settings (like `default_project`, `search_default_limit`, `title_max_length`) from the `hub_settings` table instead of using hardcoded fallbacks.
- [ ] **Key Template Validation:**
  - Enforce validation on `key_template` updates inside `/settings` or `/api/v1/config/settings`:
    - Ensure exactly one `{number}` placeholder is present.
    - Ensure only supported placeholder names are used.
    - Verify maximum rendered length is safe.
- [ ] **Implement `include_history` & Case-Insensitive Lookup:**
  - Support `include_history` in list queries.
  - Implement case-insensitive lookup for both exact ID and AKA queries.
- [ ] **Standardized Error Envelopes:**
  - Implement a global exception handler in FastAPI for both `RequestValidationError` and `HTTPException` to catch and normalize all validation and HTTP errors into the stable, flat JSON envelope: `{"ok": false, "error": {"code": "...", "message": "...", "details": "..."}}`.

## Gate 4: High-Fidelity Migration Tooling
- [ ] **Support Real Non-Frontmatter Intake Format:**
  - Upgrade `intake_parser.py` to parse files that begin directly with keys (like `status:`, `severity:`, `area:`) without requiring the `---` frontmatter block.
- [ ] **Correct Intake IDs:**
  - Parse legacy `TMP-*` intake files as pending items, allocating them a fresh canonical `Bug-N` while storing the original temporary ID inside `aka` (or aliases), as required.
- [ ] **Preserve Terminal Statuses & Aliases:**
  - Retain original statuses from the closed registry (e.g. `FIXED`, `RESOLVED`, `BY-DESIGN`, `ACCEPTED-RISK`) instead of forcibly flattening them to `CLOSED`.
  - Preserve all repeated AKA values as comma-separated aliases instead of stripping or ignoring them.
- [ ] **Complete Sequence Reconciliation:**
  - The migration baseline must correctly consider:
    - Max imported canonical ID suffix.
    - The old registry's "next number" minus one.
    - Any newly allocated pending intake numbers.

## Gate 5: Trustworthy Verification Suite
- [ ] **Safe Test-Database Guard:**
  - Ensure test fixtures refuse execution and throw an error if `DATABASE_URL` is pointing to a production-like database name or is not explicitly set as a test environment.
- [ ] **Comprehensive Test Cases:**
  - Write test cases for reservation completion edge-cases, CSRF validation, XSS sanitization, body limits, extra-fields forbidden rejection, and case-insensitive exact queries.
- [ ] **Robust Concurrency Validation:**
  - Ensure the concurrency gate launches 100 parallel clients across separate processes to verify zero-collision sequences.

## Gate 6: Codebase ID Reassignment Script
- [ ] **Fix find-exec syntax:**
  - Correct the bash find execution syntax to `bash -c 'reassign_file "$1"' _ {}` to pass filenames correctly.
- [ ] **Sanitize and Escape Input IDs:**
  - Escape old and new IDs inside regular expressions and Perl replacement scripts.
- [ ] **Add Dry-Run & Git-Clean Guards:**
  - Implement `--dry-run` flag support and check `git status --porcelain` to reject execution on dirty trees unless forced.
