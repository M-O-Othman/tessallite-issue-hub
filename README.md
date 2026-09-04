# Tessallite Issue Hub

Tessallite Issue Hub is an authoritative, independent central issue-recording service and database sequence allocator. It is designed specifically for autonomous AI coding agents working in parallel on a codebase in potentially overlapping areas, or in isolated code trees that need a unified, non-colliding common reference for issue registries. 

By replacing manual Markdown/Git-based issue-intake files, it permanently solves horizontal scaling race conditions, multiple worktree write locks, and duplicate ID merge collisions.

## Key Features
- **Central Authority for AI Agents:** Solves horizontal scaling, parallel git branching, and multiple worktree collision bugs.
- **Durable Identity:** Generates non-colliding numeric IDs via PostgreSQL sequences.
- **Dual Interfaces:** Provides a zero-dependency, non-interactive CLI client (`issue`) for automated agents and a responsive Web UI for humans.
- **High-Performance Indexed Search:** Full database indexing (GIN index on JSONB tags, B-Tree indexes on dimensions and date boundaries) with wide text scoring.
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
- `scripts/reassign_issue.sh`: A cross-platform [Issue ID Reassignment Script](scripts/reassign_issue.sh) to safely scan and rewrite legacy or temporary issue IDs across a codebase.
- `tests/`: Comprehensive self-contained test suite including unit, integration, concurrency, CLI, and web tests.
