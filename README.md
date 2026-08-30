# Tessallite Issue Hub

Tessallite Issue Hub is a lightweight, independent central issue-recording service and database sequence allocator. It replaces Markdown/Git-based issue-intake mechanisms with an authoritative central ledger and a non-interactive command-line client.

## Features
- **Central Authority:** Solves horizontal scaling and multiple worktree collision bugs.
- **Durable Identity:** Generates non-colliding numeric IDs via PostgreSQL sequences.
- **Dual Interfaces:** Provides a non-interactive CLI client (`issue`) for automated agents and a responsive Web UI for humans.
- **Audit Logging:** Keeps full history snapshots of all mutations.
- **Advisory Vocabularies:** Allows editable configuration parameters while keeping data flexible.

## Project Structure
- `src/issue_hub/`: FastAPI web server, API endpoints, Jinja2 templates, database schema, and migration logic.
- `src/issue_cli/`: Standard zero-dependency Python package exposing the CLI entry point `issue`.
- `tests/`: Comprehensive test suite including unit, integration, concurrency, CLI, and web tests.
