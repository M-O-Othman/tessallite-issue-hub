# Tessallite Issue Hub - Open Questions

The following questions must be answered to guide the development and implementation details of the Tessallite Issue Hub.

### 1. Legacy Migration Inputs
The solution specification (Section 23) mentions importing existing legacy registries and intake files, such as:
* `docs/execution/execution_issue-registry.md`
* `docs/execution/execution_issue-registry-closed.md`
* `docs/execution/issue-intake/*.md`

These files are not present in the current empty repository workspace. 
* Should we design the migration parser based on mock legacy files/fixtures for now, or is there an existing repository we should look at to import actual files?
* If we are using mock files for tests, are there specific format samples we must match, or should we define a standardized representation matching Section 23 of the spec?

### 2. Database Environment
For local testing, verification, and Docker Compose setup:
* Can we assume a local PostgreSQL instance can be run inside a Docker container via `docker compose`?
* Are there any specific external database requirements or connection details we should prepare for, or is standard Docker-based PostgreSQL sufficient?

### 3. Web UI Styling and CSS Framework
Section 19 describes the server-rendered web application using Jinja2 templates and minimal JavaScript (optionally HTMX).
* Since the spec mentions modern, polished UI design (and GEMINI.md asks for corporate-grade, simple, and clean interfaces with no funky/childish styling):
  * Is it acceptable to use a standard modern CSS framework like **Bootstrap 5** or **Tailwind CSS** (via CDN or vendored) to build a beautiful, professional, and responsive admin-like interface?
  * Or would you prefer pure custom CSS?

### 4. Sequence Initialization Baseline
If there are no actual legacy files to parse in the initial migration, what baseline number should the PostgreSQL sequence start with (e.g., should we default the NEXT CANONICAL NUMBER to `1` or a specific baseline such as `9627` mentioned in the spec)?
