# Documentation and Help Center

[Next: REST APIs](apis.md)

---

## Welcome to the Tessallite Issue Hub Help Center

The Tessallite Issue Hub is an authoritative, independent central issue-recording service and database sequence allocator. It is designed specifically for autonomous AI coding agents working in parallel on a codebase in potentially overlapping areas, or in isolated code trees that need a unified, non-colliding common reference for issue registries.

### Documented Sections

1. [1. REST API Specification](apis.md)
   Endpoints, request/response JSON schemas, authentication mechanics, and custom HTTP error code contracts.
2. [2. Non-Interactive CLI (`issue`)](cli.md)
   Local user configuration precedence, commands, flags, advisory Git environment discovery, and exit code mappings.
3. [3. Interactive Web UI Portal](frontend.md)
   Dashboard navigation, summary metrics, Markdown-rendered issue detail panels, description appending, and security session cookies.
4. [4. Legacy Migration Tooling](migration.md)
   Parsing active and closed registry Markdown lines, YAML frontmatter file intake, dry-run reconciliation, and sequence baselining.
5. [5. Deployment & Single Container](deployment.md)
   Single-container architecture, entrypoint startup script, PostgreSQL process initialization, volume mapping, and scaling details.

---

[Next: REST APIs](apis.md)
