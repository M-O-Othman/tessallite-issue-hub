# 4. Legacy Migration Tooling

[Previous: Web UI Portal](frontend.md) | [Home: Help Home](home.md) | [Next: Single Container Deployment](deployment.md)

---

The Tessallite Issue Hub includes integrated administrative migration modules to ingest, parse, validate, and baseline legacy Git/Markdown-based registries and intakes.

### A. Legacy Markdown List Parser
The `registry_parser.py` module contains regular expressions designed to parse legacy registry list lines:
```markdown
- **Bug-9627** — `[OPEN]` — AKA XMLA-9627 — `[HIGH -- XMLA title]` Description. Area: Gateway. Refs: src/xmla.py:45. Domain: gateway.
```
The parser extracts canonical issue IDs, statuses, AKA aliases, severity, title, and description text while isolating trailing inline metadata keys (Area, Refs, Domain, Category, Owner, Source) through regex pattern matching.

### B. Frontmatter Intake Parser
The `intake_parser.py` module reads legacy un-promoted Markdown files containing YAML-like frontmatter blocks:
```markdown
---
title: XMLA dax timeout
severity: CRITICAL
status: OPEN
---
## Description
Detailed trace logs...
```
It separates metadata from body text, extracts parameters, and resolves the description, omitting redundant title headers while preserving styled sectional descriptions.

### C. Reconciliation, Conflict Safety & Baselining
Before records are inserted:
1. `reconcile.py` validates imported records, tracks unique constraints within the import set, scans for duplication conflicts against the live database, and resolves AKA collisions by ignoring duplicate aliases while successfully importing primary data.
2. Following a successful validation dry-run, the database transaction is executed and the PostgreSQL sequence value is automatically baselined (using the maximum imported sequence index plus 1), ensuring that any subsequent allocation resumes after the highest legacy issue number.

---

[Previous: Web UI Portal](frontend.md) | [Home: Help Home](home.md) | [Next: Single Container Deployment](deployment.md)
