# Tessallite Issue Hub

Tessallite Issue Hub is an authoritative, independent central issue-recording service and database sequence allocator. It is designed **specifically for autonomous AI coding agents** working in parallel on a codebase in potentially overlapping areas, or in isolated code trees that need a unified, non-colliding common reference for issue registries. 

By replacing manual Markdown/Git-based issue-intake files, it permanently solves horizontal scaling race conditions, multiple worktree write locks, and duplicate ID merge collisions.

## Key Features
- **Central Authority for AI Agents:** Solves horizontal scaling, parallel git branching, and multiple worktree collision bugs.
- **Durable Identity:** Generates non-colliding numeric IDs via PostgreSQL sequences.
- **Dual Interfaces:** Provides a zero-dependency, non-interactive CLI client (`issue`) for automated agents and a highly polished, responsive Web UI for humans.
- **Wide Search Capabilities:** High-performance, all-inclusive query search that checks every single text, number, array, and JSON attribute of an issue record via OR operators.
- **Audit Logging:** Keeps full history snapshots of all mutations.
- **Advisory Vocabularies:** Allows editable configuration parameters while keeping data flexible.

## Project Structure
- `src/issue_hub/`: FastAPI web server, API endpoints, Jinja2 templates, database schema, and migration logic.
- `src/issue_cli/`: Standard zero-dependency Python package exposing the CLI entry point `issue`.
- `docs/Agent.md`: The official [AI Agent Handbook](docs/Agent.md) explaining integration protocols for parallel AI coding agents.
- `scripts/reassign_issue.sh`: A cross-platform [Issue ID Reassignment Script](scripts/reassign_issue.sh) to safely scan and rewrite legacy or temporary issue IDs across a codebase.
- `tests/`: Comprehensive test suite including unit, integration, concurrency, CLI, and web tests.
