# Tessallite Issue Hub
## Solution Specification

**Status:** Proposed implementation specification  
**Version:** 1.0  
**Date:** 29 August 2026  
**Decision owner:** MO  
**Recommended repository:** `tessallite-issue-hub`  
**Initial migration source:** `M-O-Othman/tessallite-workspace`

---

## 1. Executive summary

Tessallite Issue Hub is a small, independent issue-recording service that replaces the existing Git and Markdown-based issue-intake, number-allocation, promotion, active-registry, and closed-registry mechanisms.

The current process was designed to reduce conflicts inside one checkout: an agent writes an intake Markdown file, a promoter takes a filesystem lock, reads a counter, assigns `Bug-N`, inserts a one-line registry entry, and moves the intake to a promoted directory. That lock and counter exist inside each Git worktree. They therefore cannot coordinate agents working in different isolated worktrees, repositories, local machines, or remote environments. Two agents can independently create references that later collide after those identifiers have already entered code comments, tests, plans, commits, and reviews.

The new solution makes one service and one PostgreSQL database the sole authority for issue identity and issue data. It provides:

- one global database sequence for the numeric suffix;
- a configurable server-owned issue-key template whose last segment is always the sequence number;
- preservation of every existing `Bug-N` reference during migration;
- a compact HTTP API;
- a non-interactive cross-platform command-line client named `issue`;
- a simple server-rendered web application for humans;
- exact lookup, text search, filtering, editing, description appending, and retirement;
- one live issue table and one issue-history table;
- small lookup and settings tables for configurable values;
- local Docker deployment and a Cloud Run deployment profile using the same application image and PostgreSQL schema.

The Hub is deliberately not a Jira replacement, workflow engine, project-progress tracker, control framework, worktree coordinator, or agent identity system. Its purpose is narrower: allocate durable issue IDs without collisions, hold the current issue record, preserve change history, and make every issue easy to find and edit.

The only operation that receives strong concurrency protection is issue creation. PostgreSQL allocates the global sequence and inserts the issue in one transaction. All later updates use last-write-wins semantics, as requested. The history table retains before-and-after snapshots so overwritten values remain recoverable without adding optimistic locking or merge logic.

---

## 2. Confirmed design decisions

| Topic | Decision |
|---|---|
| Product name | **Tessallite Issue Hub** |
| Scope | Generic issue service for any project and repository |
| Project/repository | First-class issue dimensions |
| Authority | Database is the sole source of truth |
| Existing mechanisms | Replaced, then frozen or retired |
| Preferred deployment | Central cloud service on Cloud Run |
| Portability | Same container and schema run locally or in the cloud |
| GitHub Issues | Not used |
| Issue identity | Immutable text business key ending in a global sequential number |
| Default ID format | `Bug-{number}` |
| Prefix ownership | Rendered by the server from centrally configured rules; agents do not construct it |
| Existing IDs | Imported unchanged; code references remain valid |
| UUID | Not used |
| Number gaps | Allowed; numbers are never reused |
| Direct create | Supported |
| Number reservation | Supported by creating a real `RESERVED` issue row |
| Drafts | Not supported |
| Temporary IDs | Discontinued after cutover |
| Historical aliases | Retained in one scalar `AKA` field |
| Duplicate detection | No automatic or AI processing |
| Duplicate records | Allowed and may later be retired |
| Deletion | Not exposed in normal operation |
| Retirement | Retired flag plus reason; record remains visible and searchable |
| Update conflicts | Last committed write wins |
| Optimistic locking | Not used |
| Comments | Appended to the issue description; no comments table |
| Relationships | `duplicate_of` and `related_to` only |
| Attachments | Not supported |
| Owner | One optional free-text owner field |
| Releases/milestones | Represented as tags |
| Expected effort | `XS`, `S`, `M`, `L`, `XL`, `XXL`, or `UNKNOWN` |
| Status controls | Seeded and configurable; no enforced transition rules |
| Referential integrity | No foreign keys between issue, lookup, history, or relationship values |
| CLI executable | `issue` |
| CLI interaction | Non-interactive |
| CLI operations | `create`, `find`, and `update` |
| CLI output | JSON |
| Human use | Web application |
| Agent identity | Not modelled or required |
| Offline writes | Not supported |
| Multi-master sync | Not supported |

---

## 3. Judgement calls resolved by this specification

The following implementation choices were not explicitly fixed by the questionnaire and are resolved here in favour of simplicity:

1. The Hub lives in its own private repository, `tessallite-issue-hub`.
2. One global sequence is shared across all projects and repositories in a Hub installation.
3. The initial production key template remains `Bug-{number}` to preserve the established convention.
4. Per-project key-template overrides are stored as metadata in the generic lookup table rather than introducing a dedicated project configuration subsystem.
5. The server uses FastAPI, PostgreSQL, SQLAlchemy, Alembic, and server-rendered Jinja templates with minimal JavaScript.
6. The CLI is a small Python package, installable through `pipx`, with no repository-local secrets.
7. Agent access uses one shared bearer token; the human UI uses one configured administrator password and a signed session cookie. There is no user or role database.
8. The old registries remain frozen historical snapshots after cutover. New issues are not generated back into Git.
9. Normal operational CLI functionality is limited to three commands. Migration and configuration administration are exposed through the server and web UI, with a separate one-time migration module.
10. PostgreSQL is used both locally and in the cloud. SQLite is not used, avoiding two different consistency models.

---

## 4. Source basis and current state

This design is grounded in the current Tessallite issue mechanism:

- `docs/execution/execution_issue-registry.md`
- `docs/execution/execution_issue-registry-closed.md`
- `docs/execution/issue-intake/README.md`
- `docs/execution/issue-intake/promoted/`
- `scripts/promote_issue_intake.py`
- `scripts/new-issue-id.sh`
- `scripts/new-issue-id.bat`
- `scripts/issue_stats.py`
- `scripts/issue-stats.sh`
- `scripts/issue-stats.bat`

The current intake shape contains these concepts:

```text
status
severity
area
domain
category
title
refs
source
aka
temp_id
note
```

The canonical registry additionally contains:

- a permanent `Bug-N` identifier;
- a free-form issue and closeout narrative;
- active and terminal statuses;
- area headings;
- domain and category suffixes;
- a mutable next-number counter;
- one physical line per issue.

The promoter intentionally preserves the Markdown registry as the source of truth, takes a filesystem lock next to that registry, reads and increments `NEXT CANONICAL NUMBER`, writes issue lines, and moves intake files. Temporary `TMP-*` values exist because canonical allocation may be delayed. Those choices are internally coherent for one filesystem, but the lock, queue, counter, and registry are copied into every isolated worktree. The mechanism therefore cannot provide a shared authority across worktrees.

The architectural correction is not a stronger file lock. Identity allocation must leave Git and move to a central transactional store.

---

## 5. Problem statement

Multiple autonomous agents work concurrently in isolated Git worktrees and may also operate from different repositories, machines, or cloud execution environments. Agents discover issues while implementing or reviewing code and need a permanent identifier immediately so they can refer to the issue in:

- source-code comments;
- tests;
- plans;
- review findings;
- handoff documents;
- commit messages;
- related issue records;
- user discussions.

The current model permits this failure sequence:

1. Two worktrees observe the same registry counter or independently create temporary IDs.
2. Two agents produce different issue records that later map to the same apparent identifier.
3. Both identifiers enter durable code and documentation.
4. Git reports conflicts only after the identifier has spread.
5. Renumbering cannot reliably repair every reference.
6. The same `Bug-N` can appear to mean two different defects.
7. Search and reporting become unreliable because state is divided among active registry lines, closed registry lines, pending intakes, promoted intakes, plans, and code comments.

The required solution must provide a permanent, server-allocated issue ID at creation or reservation time while remaining much simpler than Jira or a full work-management platform.

---

## 6. Goals

### 6.1 Primary goals

1. Eliminate duplicate canonical number allocation across worktrees, repositories, machines, and Cloud Run instances.
2. Return a permanent issue ID immediately when an issue is created or reserved.
3. Preserve every existing `Bug-N` reference exactly during migration.
4. Replace the active registry, closed registry, intake queue, temporary-ID generator, promoter, and counter as authoritative mechanisms.
5. Support any project and repository without coupling the service to Tessallite source layout.
6. Support exact issue lookup, text search, and filtering across both open and closed issues.
7. Let agents freely update status, severity, description, tags, and all other mutable issue fields.
8. Let agents append implementation, review, or closeout text directly to the description.
9. Preserve every mutation in one history table.
10. Provide a simple web interface for humans.
11. Run from the same codebase on a local workstation and on Cloud Run.
12. Keep the operational CLI small, predictable, non-interactive, and JSON-only.

### 6.2 Secondary goals

- Allow centrally configured issue-ID formats for future projects.
- Retain editable value vocabularies without constraining issue rows through foreign keys.
- Support JSON and legacy-Markdown export for backup and inspection.
- Make migration repeatable and reconcilable.
- Allow future reporting without redesigning identity or storage.

---

## 7. Non-goals

The first release will not provide:

- Jira-style workflow enforcement;
- evidence or review gates;
- closing authority or separation of duties;
- automated duplicate classification;
- AI-assisted issue analysis;
- agent registration, check-in, or identity tracking;
- worktree leasing, file locking, or lane coordination;
- boards, epics, roadmaps, sprints, or progress reporting;
- time tracking;
- pull-request management;
- GitHub Issues integration;
- attachments or binary evidence;
- separate comment entities;
- notification or email delivery;
- offline canonical issue creation;
- synchronization between independent databases;
- optimistic concurrency or automatic merge;
- automatic closure from commits;
- mandatory CI validation of code references;
- secret scanning of issue descriptions;
- customer-facing or regulated control functions.

These exclusions are deliberate. Tessallite Issue Hub is an authoritative issue ledger, not a governance control.

---

## 8. Architectural principles

### 8.1 One production authority

All production agents and humans target one Hub authority. The production authority is the Cloud Run deployment and its PostgreSQL database.

A local deployment is supported for development, testing, demos, or a fully separate standalone installation. It is not a replicated production peer. Two independent databases must never be treated as one numbering namespace.

A locally running application may connect to the central production database when required, but there is no bidirectional synchronization or multi-master mode.

### 8.2 Identity is server-owned

Agents submit issue data and dimensions. They do not construct the permanent prefix or numeric suffix. The server:

1. obtains the next global sequence number;
2. selects the configured template for the project or the global default;
3. renders and normalizes the prefix;
4. validates that the final segment is the allocated number;
5. inserts the live issue row;
6. inserts the initial history row;
7. commits and returns the permanent ID.

### 8.3 Minimal issue model

The issue domain uses:

- one live `issues` table;
- one `issue_history` table;
- one generic `lookup_values` table;
- one small `hub_settings` table;
- one PostgreSQL sequence.

There are no issue-comment, attachment, assignment, workflow, approval, actor, or relationship tables.

### 8.4 Configurable values are advisory

Status, severity, domain, category, priority, classification, effort, owner, and relationship targets are stored as ordinary values on the issue row. Lookup records supply UI options, labels, ordering, and terminal-status classification. A write is not rejected merely because its value is absent from a lookup table.

### 8.5 History instead of conflict prevention

Updates do not require a version number. The latest committed update wins. Before and after snapshots are stored in `issue_history`, allowing a human to inspect or manually restore overwritten content.

### 8.6 Retirement instead of deletion

No normal API or UI operation deletes an issue. A record can be retired with a reason such as `DUPLICATE` or `NOT_AN_ISSUE`. It remains visible and searchable forever.

### 8.7 Configuration affects future IDs only

Changing an ID template never renames an existing issue. Existing IDs are immutable because they may already exist in code comments and documents.

---

## 9. Recommended technology stack

### 9.1 Application

- **Language:** Python 3.12 or later
- **HTTP framework:** FastAPI
- **Database access:** SQLAlchemy 2.x with psycopg 3
- **Schema migrations:** Alembic
- **Validation and OpenAPI:** Pydantic through FastAPI
- **Web rendering:** Jinja2 templates
- **Browser interaction:** minimal vanilla JavaScript or vendored HTMX; no SPA framework
- **CLI:** Python package with an `issue` console entry point

### 9.2 Storage and infrastructure

- **Production database:** PostgreSQL; Cloud SQL is the reference GCP profile
- **Local database:** PostgreSQL container through Docker Compose
- **Object storage:** none
- **Cache:** none
- **Message queue:** none
- **Search service:** none; PostgreSQL search is sufficient
- **Background worker:** none

### 9.3 Deployment

One container image serves both API and web UI. Cloud Run is the preferred production runtime. PostgreSQL remains external to the container. The same image runs locally through Docker Compose.

### 9.4 Rationale

This stack matches the wider Tessallite Python environment, supports Windows and Unix clients, provides a native concurrent sequence, avoids a front-end build pipeline, and remains portable across local and cloud deployments.

---

## 10. Logical architecture

```text
+----------------------+       HTTPS / JSON       +-------------------------+
| Agent in worktree    | -----------------------> | Tessallite Issue Hub    |
| local, VM, or cloud  |       Bearer token       | FastAPI application     |
|                      |                           |                         |
| `issue` CLI          | <----------------------- | API + web UI            |
+----------------------+                           +------------+------------+
                                                               |
                                                               | SQL
                                                               v
                                                  +-------------------------+
                                                  | PostgreSQL              |
                                                  |                         |
                                                  | issue_number_seq        |
                                                  | issues                  |
                                                  | issue_history           |
                                                  | lookup_values           |
                                                  | hub_settings            |
                                                  +-------------------------+

+----------------------+       HTTPS / forms
| Human browser        | ------------------------>
| search and editing   |
+----------------------+
```

The API, UI, and ID allocator are one deployable service. There is no separate front-end service, API gateway, message broker, cache, event bus, or numbering microservice.

---

## 11. Issue identity and numbering

### 11.1 Business key

The permanent business key is `issue_id`, a text value such as:

```text
Bug-9627
```

No UUID is exposed or required. `issue_id` is immutable and is the primary key of the live table.

The numeric suffix is stored separately as `sequence_number` to support allocation, sorting, migration, and diagnostics. It is not independently chosen by a client.

### 11.2 Global sequence

One PostgreSQL sequence allocates numbers across every project and repository in a Hub installation:

```sql
CREATE SEQUENCE issue_number_seq AS BIGINT;
```

The sequence is global, not per project, repository, branch, task, status, or prefix. This guarantees that the numeric suffix is never allocated twice by the same Hub authority.

### 11.3 Configurable key template

The initial global default is:

```text
Bug-{number}
```

Supported placeholders are:

```text
{project}
{repository}
{branch}
{task}
{type}
{number}
```

Examples of valid templates:

```text
Bug-{number}
{project}-Bug-{number}
{project}-{repository}-{number}
{project}-{branch}-{task}-{number}
```

Template rules:

1. `{number}` occurs exactly once.
2. `{number}` is the last rendered segment.
3. The final ID ends with `-<digits>`.
4. Empty optional placeholders are removed without repeated separators.
5. Placeholder values are normalized by the server, not the agent.
6. Existing IDs are never re-rendered.
7. Imported `Bug-N` values remain exactly as written.
8. A project lookup may contain a `key_template` value in metadata; otherwise the global template applies.

The recommended initial production template remains `Bug-{number}`. Branch and task are temporary concepts and usually should not be embedded in a permanent ID, but the configuration supports them when a project deliberately chooses that convention.

### 11.4 Allocation transaction

Creation uses one short database transaction:

```text
BEGIN
  number := nextval(issue_number_seq)
  issue_id := render configured template with number
  INSERT issues
  INSERT issue_history(operation = CREATE or RESERVE)
COMMIT
RETURN issue
```

This is the only operation for which strong atomicity is mandatory. It is native to PostgreSQL and works across any number of Cloud Run instances without a distributed lock.

If a transaction consumes a sequence value and then fails, the number may be skipped. Gaps are allowed and numbers are never reused.

### 11.5 Direct creation

A normal create request allocates an ID and inserts a live issue. Status defaults to `OPEN` when omitted.

For a complete issue, the API requires:

```text
severity
description
```

`title` is optional. When omitted, the server derives it from the first non-empty description line, truncated to a configurable display length. `status`, `area`, `classification`, `domain`, `category`, `refs`, and `source` are optional, although the agent README recommends supplying them whenever known.

### 11.6 Reservation

A client may request a permanent number before the full issue text exists:

```bash
issue create --reserve
```

A reservation is not a draft. It creates a normal live issue with:

```text
status = RESERVED
```

The row may contain only project, repository, branch, worktree, task, or a short description. It remains visible and searchable. It never expires automatically and its number is never reused.

### 11.7 Creation with an existing ID

An agent may supply an existing ID only to complete or update a previously reserved issue. A caller-supplied ID that does not already exist is rejected unless the server is running an explicit administrative import or repair operation.

This preserves the requested “with or without ID” flow without allowing agents to manufacture prefixes or numeric values.

### 11.8 Retry behaviour

The Hub intentionally does not implement idempotency keys.

If a client loses a successful response after commit and retries a create request without the original ID, a second issue may be created. This is accepted. Search can identify the duplicate and `issue update --retire DUPLICATE` can retire it.

This trade-off keeps the design simple while preserving the essential guarantee: the two records receive different canonical numbers.

---

## 12. Data model

### 12.1 `issues` — one live issue table

```sql
CREATE TABLE issues (
    issue_id            TEXT PRIMARY KEY,
    sequence_number     BIGINT NOT NULL UNIQUE,

    project             TEXT,
    repository          TEXT,
    branch              TEXT NOT NULL DEFAULT 'main',
    worktree            TEXT,
    task                TEXT,

    status              TEXT NOT NULL DEFAULT 'OPEN',
    severity            TEXT,
    priority            TEXT,
    expected_effort     TEXT DEFAULT 'UNKNOWN',

    title               TEXT NOT NULL DEFAULT '',
    description         TEXT NOT NULL DEFAULT '',
    area                TEXT,
    classification      TEXT,
    domain              TEXT,
    category            TEXT,

    refs                TEXT,
    source              TEXT,
    aka                 TEXT,
    owner               TEXT,
    tags                JSONB NOT NULL DEFAULT '[]'::jsonb,

    duplicate_of        TEXT,
    related_to          TEXT,

    is_retired          BOOLEAN NOT NULL DEFAULT FALSE,
    retire_reason       TEXT,
    retire_note         TEXT,
    retired_at          TIMESTAMPTZ,

    legacy_raw          TEXT,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### Column rules

- `project` and `repository` are independent dimensions.
- `branch` defaults to `main`.
- `worktree` defaults to null.
- `task` is optional and primarily supports filtering or key-template placeholders.
- `classification` is a generic free-text classification for projects that do not use Tessallite’s domain/category structure.
- `domain` and `category` preserve the current registry concepts.
- `refs` remains free-form Markdown or text. Structured references are not required.
- `aka` is one scalar text field. Several historical values may be combined in the string during migration.
- `tags` is a JSON string array. Releases, milestones, plans, demo blockers, and other lightweight groupings are tags.
- `duplicate_of` holds one primary duplicate target.
- `related_to` is free text and may contain one or several issue IDs.
- Relationship values are not validated through foreign keys.
- `legacy_raw` preserves the exact original registry or intake record.
- No lookup-valued column has a foreign key.

### 12.2 `issue_history` — one history table

```sql
CREATE TABLE issue_history (
    history_id          BIGSERIAL PRIMARY KEY,
    issue_id            TEXT NOT NULL,
    operation           TEXT NOT NULL,
    changed_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    before_record       JSONB,
    after_record        JSONB,
    note                TEXT
);
```

There is deliberately no foreign key from history to the live table.

History operations include:

```text
CREATE
RESERVE
UPDATE
APPEND
RETIRE
IMPORT
REPAIR
```

For each mutation, the server reads the current row, applies the change, updates `updated_at`, and inserts before-and-after JSON snapshots in the same transaction.

The service does not require actor identity. An optional attribution may be included in the submitted description, source field, or history note.

### 12.3 `lookup_values` — generic editable vocabularies

```sql
CREATE TABLE lookup_values (
    lookup_type         TEXT NOT NULL,
    value               TEXT NOT NULL,
    label               TEXT,
    display_order       INTEGER NOT NULL DEFAULT 0,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    is_terminal         BOOLEAN,
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (lookup_type, value)
);
```

Lookup types initially include:

```text
PROJECT
REPOSITORY
STATUS
SEVERITY
PRIORITY
EFFORT
DOMAIN
CATEGORY
RETIRE_REASON
```

The table supplies UI options and filtering semantics. It does not constrain `issues`.

`metadata` may hold project-specific settings, for example:

```json
{
  "key_template": "Bug-{number}",
  "default_repository": "tessallite-workspace"
}
```

### 12.4 `hub_settings` — small configuration store

```sql
CREATE TABLE hub_settings (
    setting_key         TEXT PRIMARY KEY,
    setting_value       JSONB NOT NULL,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Initial settings:

```text
issue_key_template
default_project
default_repository
default_branch
search_default_limit
title_max_length
web_title
```

### 12.5 Indexes

Initial indexes remain deliberately small:

```sql
CREATE INDEX issues_sequence_desc_idx
    ON issues (sequence_number DESC);

CREATE INDEX issues_status_idx
    ON issues (status);

CREATE INDEX issues_project_repo_idx
    ON issues (project, repository);

CREATE INDEX issues_updated_desc_idx
    ON issues (updated_at DESC);

CREATE INDEX issues_retired_idx
    ON issues (is_retired);

CREATE INDEX issue_history_issue_idx
    ON issue_history (issue_id, history_id DESC);
```

PostgreSQL full-text indexing may be added over `issue_id`, `aka`, `title`, `description`, `refs`, `source`, `area`, `classification`, `domain`, `category`, and tags. An initial `ILIKE` implementation is acceptable if migration measurements show that it is already fast enough.

---

## 13. Seed data

### 13.1 Statuses

The initial status lookup is the union of values already recognized by the registry, intake promoter, closed registry, and statistics tooling:

```text
OPEN
FIXED-PENDING-VERIFICATION
DEFERRED
DESCOPED
PARTIAL
MITIGATED
SHELVED
FLAGGED
RESERVED
PARKED
BY-DESIGN
INFO
NOTED
ACCEPTED
ACCEPTED-RISK
ACCEPTED-FOR-DEMO
CLIENT-OPS
FIXED
CLOSED
DONE
RESOLVED
VERIFIED
SUPERSEDED
REMOVED
OBSOLETE
DUPLICATE
POSSIBLY DUPLICATE
REOPENED
WONTFIX
MOVED-TO-ENHANCEMENT-PLAN
FIXED_IN_REPLAY
FIXED_IN_INTEGRATION
```

The administrator may add, rename, activate, deactivate, reorder, or reclassify statuses through the web UI. Existing issue values are not rewritten when a lookup changes.

`PARTIAL` is seeded as non-terminal. `ACCEPTED-RISK` is seeded as terminal but carries no evidence, approval, or control requirement.

### 13.2 Severity

```text
CRITICAL
HIGH
MEDIUM
LOW
INFO
ENHANCEMENT
PERF
QUESTION
UNSPECIFIED
```

### 13.3 Priority

Priority is optional:

```text
P0
P1
P2
P3
P4
UNSCHEDULED
```

### 13.4 Expected effort

```text
XS
S
M
L
XL
XXL
UNKNOWN
```

### 13.5 Domains

Preseeded Tessallite values:

```text
gateway
query-router
model-service
optimizer
scheduler
agent-service
front-end
shared
seed
deploy
release-tooling
ci
uat
website
community-edition
documentation
cross-cutting
```

### 13.6 Categories

```text
product
ci
security
documentation
tessallite-website
community-edition
```

### 13.7 Retirement reasons

```text
DUPLICATE
NOT_AN_ISSUE
CREATED_IN_ERROR
SUPERSEDED
OTHER
```

All seed values are editable and advisory.

---

## 14. Lifecycle conventions

The Hub does not enforce a workflow graph. Any authorized client may set any status string.

Recommended conventions:

- `RESERVED`: a permanent number exists but the full record is not yet populated.
- `OPEN`: issue is recorded and may require work.
- `PARTIAL`: some scope is complete but the issue remains non-terminal.
- `FIXED-PENDING-VERIFICATION`: implementation claims a fix, but verification may still occur.
- terminal values such as `FIXED`, `CLOSED`, `RESOLVED`, or `ACCEPTED-RISK`: treated as closed for filtering according to lookup configuration.

These conventions affect display and filtering only. The API does not require evidence, reviewer identity, a closeout report, or an allowed transition.

### 14.1 Open and closed interpretation

A status lookup may carry `is_terminal=true` or `false`:

- “open” means the current status is not marked terminal;
- “closed” means the current status is marked terminal;
- an unknown status remains visible and is treated as non-terminal;
- retirement is a separate dimension.

No query hides deferred, parked, accepted, informational, terminal, or retired issues unless a caller explicitly filters them out.

### 14.2 Reopening

A terminal or retired issue is not reopened in place. The recommended operation is:

1. create a new issue;
2. set `related_to` to the old issue ID;
3. describe why the old disposition no longer applies.

The UI provides a “Create related issue” action that prepopulates the relationship.

### 14.3 Retirement

Retirement is separate from status:

```text
is_retired = true
retire_reason = DUPLICATE | NOT_AN_ISSUE | CREATED_IN_ERROR | SUPERSEDED | OTHER
retire_note = optional explanation
duplicate_of = optional canonical target
retired_at = server timestamp
```

Retired issues retain their ID, description, tags, relationships, and history. They remain visible in ordinary search results and can be explicitly filtered.

---

## 15. Description and append model

The issue has one Markdown `description` field. There is no separate comments table.

Clients may either replace the whole description or append to it. An append operation adds a server-generated timestamp and the submitted text:

```md

---

**Appended 2026-08-29T14:32:11Z**

<submitted text>
```

No agent identity is required. A client may include attribution in its text when useful.

The history table stores the complete before and after description, so an accidental overwrite remains inspectable.

The following structure is recommended but not enforced:

```md
## Problem

## Observed behaviour

## Expected behaviour

## Impact

## Evidence and reproduction

## Initial analysis

## Acceptance notes
```


---

## 16. HTTP API

### 16.1 General contract

- Base path: `/api/v1`
- Media type: `application/json`
- Character set: UTF-8
- Authentication: bearer token
- Date/time format: ISO 8601 UTC
- Errors: JSON
- Pagination: `limit` and `offset`
- Update semantics: last write wins
- Schema documentation: generated OpenAPI document

### 16.2 Create or reserve an issue

```http
POST /api/v1/issues
Authorization: Bearer <token>
Content-Type: application/json
```

Direct create request:

```json
{
  "project": "tessallite",
  "repository": "tessallite-workspace",
  "branch": "main",
  "status": "OPEN",
  "severity": "HIGH",
  "priority": "P1",
  "expected_effort": "M",
  "title": "XMLA hierarchy owner does not match the declared dimension",
  "description": "Excel cannot resolve the hierarchy owner and labels grouped attributes as (All).",
  "area": "Gateway / XMLA / Excel",
  "classification": "protocol-compatibility",
  "domain": "gateway",
  "category": "product",
  "refs": "tessallite/services/gateway/src/dax/xmla_server.py",
  "source": "independent review",
  "tags": ["excel", "xmla", "demo-blocker"]
}
```

Reserve request:

```json
{
  "reserve": true,
  "project": "tessallite",
  "repository": "tessallite-workspace",
  "branch": "main"
}
```

Response:

```json
{
  "ok": true,
  "issue": {
    "issue_id": "Bug-9627",
    "sequence_number": 9627,
    "status": "OPEN",
    "severity": "HIGH",
    "project": "tessallite",
    "repository": "tessallite-workspace",
    "branch": "main",
    "worktree": null,
    "created_at": "2026-08-29T14:30:00Z",
    "updated_at": "2026-08-29T14:30:00Z"
  }
}
```

#### Create rules

- When `reserve=true`, content fields may be empty and status defaults to `RESERVED`.
- When `reserve` is false or absent, `severity` and `description` are required.
- If `title` is empty, the first non-empty description line becomes the title.
- If `branch` is absent, it defaults to `main`.
- `worktree` is absent by default.
- `project` and `repository` may come from server or CLI defaults.
- The server ignores any caller attempt to choose `sequence_number`.
- A caller-supplied `issue_id` must identify an existing reserved row unless import mode is active.

### 16.3 Find, show, search, or list issues

One endpoint covers all ordinary reads:

```http
GET /api/v1/issues
```

Supported query parameters:

```text
id
q
project
repository
branch
worktree
task
status
severity
priority
expected_effort
area
domain
category
classification
owner
tag
is_retired
is_terminal
created_from
created_to
updated_from
updated_to
limit
offset
sort
include_history
```

Exact lookup:

```http
GET /api/v1/issues?id=Bug-9627
```

Text search:

```http
GET /api/v1/issues?q=hierarchy%20unique%20name
```

Filtered list:

```http
GET /api/v1/issues?repository=tessallite-workspace&status=OPEN&severity=HIGH
```

Response:

```json
{
  "ok": true,
  "items": [],
  "total": 0,
  "limit": 100,
  "offset": 0
}
```

Exact ID and `AKA` matches rank before text matches. Search covers:

```text
issue_id
aka
title
description
refs
source
area
classification
domain
category
owner
tags
project
repository
branch
worktree
task
duplicate_of
related_to
```

No AI, embeddings, similarity model, or automatic duplicate score is used.

### 16.4 Update, append, relate, or retire

One endpoint covers every mutation after creation:

```http
PATCH /api/v1/issues/{issue_id}
Authorization: Bearer <token>
Content-Type: application/json
```

Update request:

```json
{
  "set": {
    "status": "FIXED-PENDING-VERIFICATION",
    "priority": "P2",
    "owner": "MO",
    "tags": ["xmla", "excel", "implemented"]
  },
  "append_description": "Fix implemented in commit abc123. Focused tests passed."
}
```

Retire request:

```json
{
  "retire": {
    "reason": "DUPLICATE",
    "duplicate_of": "Bug-9584",
    "note": "Same root cause and affected code path."
  }
}
```

Relationship update:

```json
{
  "set": {
    "related_to": "Bug-9558, Bug-9584"
  }
}
```

Description replacement:

```json
{
  "set": {
    "description": "Complete replacement Markdown text."
  }
}
```

The request may set any writable field. It does not contain or require a row version. A request may combine field changes and a description append in one transaction.

### 16.5 History

History may be read through either of these forms:

```http
GET /api/v1/issues?id=Bug-9627&include_history=true
```

```http
GET /api/v1/issues/Bug-9627/history
```

The response returns newest-first before-and-after snapshots.

### 16.6 Configuration

```http
GET   /api/v1/config/lookups/{lookup_type}
PUT   /api/v1/config/lookups/{lookup_type}
GET   /api/v1/config/settings
PATCH /api/v1/config/settings
```

These endpoints are primarily used by the web configuration page. They use the same simple administrator authentication as other writes.

### 16.7 Import and export

Administrative endpoints:

```http
POST /api/v1/admin/import
GET  /api/v1/admin/export?format=json
GET  /api/v1/admin/export?format=legacy-markdown
```

Import is disabled after cutover unless explicitly enabled by environment configuration.

### 16.8 Error shape

```json
{
  "ok": false,
  "error": {
    "code": "ISSUE_NOT_FOUND",
    "message": "Issue Bug-9627 was not found",
    "details": {}
  }
}
```

Stable error codes:

```text
AUTHENTICATION_REQUIRED
AUTHENTICATION_FAILED
INVALID_REQUEST
INVALID_KEY_TEMPLATE
ISSUE_NOT_FOUND
CALLER_SUPPLIED_ID_NOT_ALLOWED
RESERVED_ISSUE_NOT_FOUND
DATABASE_UNAVAILABLE
IMPORT_CONFLICT
IMPORT_INVALID_RECORD
INTERNAL_ERROR
```

---

## 17. Command-line interface

### 17.1 Executable and installation

The executable is:

```text
issue
```

The recommended distribution is a small Python package installed through `pipx`:

```bash
pipx install tessallite-issue-hub-cli
```

The CLI should use the Python standard library for argument parsing and HTTP where practical, keeping runtime dependencies close to zero. The package exposes a console entry point and works in:

- Bash;
- Windows CMD;
- Windows PowerShell;
- macOS and other Python-capable environments.

The first release does not require standalone native binaries.

### 17.2 Configuration

Configuration precedence:

1. command-line option;
2. environment variable;
3. user-level configuration file.

Environment variables:

```text
ISSUE_HUB_URL
ISSUE_HUB_TOKEN
ISSUE_HUB_PROJECT
ISSUE_HUB_REPOSITORY
ISSUE_HUB_BRANCH
ISSUE_HUB_WORKTREE
```

Default branch is `main`. Worktree is null unless explicitly supplied or auto-detected.

User configuration locations:

```text
Linux/macOS: ~/.config/tessallite-issue-hub/config.json
Windows:     %APPDATA%\Tessallite\IssueHub\config.json
```

Tokens must not be written into a repository or worktree.

### 17.3 Three-command operational model

Only three normal commands exist:

```text
issue create
issue find
issue update
```

#### `issue create`

Creates a complete issue or reserves a number.

```bash
issue create \
  --severity HIGH \
  --title "XMLA hierarchy owner mismatch" \
  --description-file issue.md \
  --area "Gateway / XMLA" \
  --domain gateway \
  --category product
```

```bash
issue create --reserve
```

JSON input is supported:

```bash
issue create --json issue.json
```

Completing a reservation may use either `update` or a create request with the known ID:

```bash
issue update Bug-9627 --set severity=HIGH --description-file issue.md
```

```bash
issue create --id Bug-9627 --json issue.json
```

The second form succeeds only when `Bug-9627` already exists as a reserved row.

#### `issue find`

Shows one issue, searches text, or lists filtered issues.

```bash
issue find Bug-9627
```

```bash
issue find "hierarchy unique name"
```

```bash
issue find --status OPEN --severity HIGH --repository tessallite-workspace
```

```bash
issue find --is-retired true
```

```bash
issue find --is-terminal true --project tessallite
```

History is a read option rather than a separate command:

```bash
issue find Bug-9627 --history
```

When no query or filters are supplied, `find` lists issues ordered by descending sequence number.

#### `issue update`

Changes fields, appends text, manages tags, creates relationships, or retires the record.

```bash
issue update Bug-9627 --set status=FIXED-PENDING-VERIFICATION
```

```bash
issue update Bug-9627 --append-file closeout.md
```

```bash
issue update Bug-9627 \
  --set severity=MEDIUM \
  --set priority=P2 \
  --add-tag reviewed
```

```bash
issue update Bug-9627 \
  --retire DUPLICATE \
  --duplicate-of Bug-9584 \
  --retire-note "Same root cause"
```

JSON patch input is supported:

```bash
issue update Bug-9627 --json update.json
```

### 17.4 Output

Every successful and failed command emits JSON. Human-readable tables belong in the web UI.

Success:

```json
{
  "ok": true,
  "issue": {
    "issue_id": "Bug-9627"
  }
}
```

Failure:

```json
{
  "ok": false,
  "error": {
    "code": "ISSUE_NOT_FOUND",
    "message": "Issue Bug-9627 was not found"
  }
}
```

Exit codes:

```text
0  success
2  command or validation error
3  authentication failure
4  issue not found
5  service unavailable or network failure
6  server error
```

### 17.5 Automatic repository context

When available, the CLI may discover:

```text
repository name
current branch
worktree path
HEAD commit
```

Discovery is advisory. Every value can be overridden or omitted. No agent, session, or worktree registration occurs.

### 17.6 CLI implementation boundary

The CLI must not implement business rules for:

- number allocation;
- key-template rendering;
- status validation or normalization;
- retirement semantics;
- history generation;
- search ranking.

It is a thin JSON client over the HTTP API. This prevents local versions from creating different issue behaviour.

---

## 18. Agent-facing README

A concise repository-facing README replaces the current intake instructions. Recommended path:

```text
docs/execution/issue-hub/README.md
```

It must explain:

1. Tessallite Issue Hub is the sole issue authority.
2. Agents must not edit the old active or closed registry.
3. Agents must not create intake files or `TMP-*` IDs.
4. How to install and configure `issue`.
5. How to create a complete issue.
6. How to reserve a number.
7. How to find by ID, AKA, text, or filters.
8. How to update fields.
9. How to append implementation or closeout text.
10. How to retire a duplicate or invalid issue.
11. The recommended issue description skeleton.
12. Default project, repository, and branch settings for `tessallite-workspace`.
13. Bash and Windows CMD examples.
14. Network-failure behaviour: never invent a canonical ID.
15. Retry caveat: a lost successful response may create a duplicate on retry.
16. Retired issues remain visible and must not be deleted.

The README should be short enough for every agent to read fully and explicit enough that no legacy workflow remains ambiguous.

---

## 19. Web application

### 19.1 Design approach

The web application is rendered by the same FastAPI service using Jinja2. It does not use React, a separate API deployment, or a Node build pipeline.

The interface is desktop-first and responsive enough for simple mobile viewing and editing.

### 19.2 Pages

The first release contains five pages:

1. Login
2. Issue list and search
3. Create or reserve issue
4. Issue detail, edit, append, retire, and history
5. Configuration

### 19.3 Issue list/search page

The landing page combines summary counts, search, filters, and issue listing.

```text
+----------------------------------------------------------------------------+
| Tessallite Issue Hub                  [Create issue] [Reserve] [Settings]   |
+----------------------------------------------------------------------------+
| Search ID, AKA, title, description, refs...                     [Search]    |
+----------------------------------------------------------------------------+
| All  2,431 | Open 127 | Closed 2,281 | Reserved 4 | Retired 19             |
+----------------------------------------------------------------------------+
| Project [all]  Repo [all]  Status [all]  Severity [all]  Retired [all]     |
| Domain  [all]  Tag  [____________]  Updated [any]             [Clear]       |
+----------------------------------------------------------------------------+
| ID       Status    Sev   Title                    Project/Repo      Updated |
| Bug-9627 OPEN      HIGH  XMLA hierarchy owner... tessallite/...   14:32   |
| Bug-9626 FIXED     MED   ...                      tessallite/...   13:10   |
+----------------------------------------------------------------------------+
```

Header counts:

```text
All
Non-terminal
Terminal
Reserved
Retired
```

Filters:

```text
project
repository
branch
status
severity
priority
expected effort
area
domain
category
classification
owner
tag
retired
created date
updated date
```

The default view includes all issues and visually distinguishes terminal and retired records. No issue is silently hidden.

Columns:

```text
Issue ID
Status
Severity
Priority
Title
Project / repository
Area or domain
Updated
Retired
```

### 19.4 Create/reserve page

```text
+---------------------------------------------------------------+
| Create issue                                      [Reserve ID] |
+---------------------------------------------------------------+
| ID preview: Bug-<next allocated on save>                      |
| Project      [tessallite]                                     |
| Repository   [tessallite-workspace]                           |
| Branch       [main]                  Worktree [optional]       |
| Status       [OPEN]                  Severity [HIGH]           |
| Priority     [optional]              Effort [UNKNOWN]          |
| Title        [______________________________________________]  |
| Description  [Markdown editor..............................]   |
| Area         [________________]      Classification [_______]  |
| Domain       [gateway]               Category [product]        |
| Refs         [______________________________________________]  |
| Source       [______________________________________________]  |
| Tags         [xmla] [excel] [+]                               |
|                                                   [Create]     |
+---------------------------------------------------------------+
```

The page provides:

- create mode;
- reserve mode;
- key-template preview;
- all issue fields;
- tag editing;
- Markdown editing;
- validation feedback.

### 19.5 Issue detail/edit page

```text
+----------------------------------------------------------------------------+
| Bug-9627                         OPEN | HIGH | Active           [Save]       |
+----------------------------------------------------------------------------+
| Project: tessallite       Repository: tessallite-workspace                 |
| Branch: main              Worktree: —            Owner: —                  |
| Area: Gateway / XMLA      Domain: gateway         Category: product         |
| Tags: [xmla] [excel] [demo-blocker]                                      |
+----------------------------------------------------------------------------+
| Title                                                                      |
| XMLA hierarchy owner does not match the declared dimension                |
+----------------------------------------------------------------------------+
| Description [Rendered] [Edit Markdown]                                     |
| ...                                                                        |
+----------------------------------------------------------------------------+
| Append note                                                                |
| [......................................................................]   |
|                                                           [Append]         |
+----------------------------------------------------------------------------+
| Duplicate of: —        Related to: Bug-9558                                |
| [Retire issue]                                                             |
+----------------------------------------------------------------------------+
| History                                                                    |
| 14:32 UPDATE status OPEN -> FIXED-PENDING-VERIFICATION                     |
| 12:05 CREATE                                                              |
+----------------------------------------------------------------------------+
```

The page shows:

- immutable ID and sequence number;
- every editable field;
- rendered and raw Markdown modes;
- a separate append box;
- tags and relationships;
- retirement controls;
- history snapshots;
- “Create related issue” action.

Save operations use last-write-wins semantics. The page does not display or require record versions.

### 19.6 Configuration page

The page manages:

- global issue-key template;
- project-specific template metadata;
- default project, repository, and branch;
- statuses and terminal flags;
- severities;
- priorities;
- expected-effort values;
- domains;
- categories;
- retirement reasons.

Editing configuration affects suggestions and future issue IDs only. It does not rewrite existing issue values.

### 19.7 Markdown safety

The server sanitizes rendered Markdown and disallows executable HTML, scripts, event handlers, and unsafe URLs. Raw Markdown remains available for editing.

---

## 20. Authentication and security

### 20.1 Authentication model

The first release deliberately avoids users, roles, and per-agent identities.

#### Agent and CLI access

- one shared bearer token configured as a secret;
- token supplied through `ISSUE_HUB_TOKEN` or the user-level config file;
- no token stored in Git;
- all token-authenticated clients have read and write access.

#### Human web access

- one administrator username and password configured through environment secrets;
- password stored as a strong salted hash;
- successful login creates a signed, HTTP-only, secure session cookie;
- no user table.

Local development may disable authentication only when the application binds to loopback or runs in an explicit development profile.

### 20.2 Cloud security

- Cloud Run serves HTTPS only.
- The service is not anonymously writable.
- API and web secrets are stored in Google Secret Manager.
- The database is not exposed directly to the public internet.
- The application database account has access only to the Hub database or schema.
- SQL is parameterized through SQLAlchemy.
- Web forms include CSRF protection.
- Session cookies use `Secure`, `HttpOnly`, and `SameSite=Lax` or stricter settings.
- Request body limits prevent accidental very large descriptions.
- Tokens, passwords, and connection strings never appear in logs.

### 20.3 Deliberate limitations

The Hub is not a security evidence store or regulated control. It does not:

- identify which agent made each change;
- enforce separation of duties;
- require closure evidence;
- scan descriptions for secrets;
- prevent an authorized client from changing any status or description.

These limitations must be stated in the operational documentation.

---

## 21. Search and reporting

### 21.1 Exact lookup

Exact lookup is case-insensitive for:

```text
issue_id
aka
```

The canonical stored casing is returned.

### 21.2 Text search

Text search covers the current live issue record. Historical snapshots are not searched by default because that would make ordinary results noisy. The issue history remains directly inspectable.

A future optional `search_history=true` flag may be added without changing the core model.

### 21.3 Ranking

Recommended rank order:

1. exact issue ID;
2. exact AKA;
3. issue-ID prefix;
4. title match;
5. description match;
6. refs, source, area, domain, category, classification, owner, or tag match.

### 21.4 Reports

The first release supports filtered counts and JSON export rather than a separate analytics subsystem. The UI can show:

- count by terminal/non-terminal/retired state;
- count by status;
- count by severity;
- count by project and repository;
- count by domain and category;
- count by expected effort;
- recently created and recently updated issues.

This replaces the practical capability of `issue_stats.py` without reproducing its hard-coded actionable-status policy. The lookup table defines terminal status only; users choose their own filters.

### 21.5 No hidden issues

No default query excludes deferred, parked, accepted-risk, informational, closed, or retired records. Tabs and filters may narrow the view, but the all-issue ledger remains the default source.

---

## 22. Local and cloud deployment

### 22.1 Local deployment

Docker Compose starts:

```text
issue-hub application
PostgreSQL
```

Example:

```bash
docker compose up --build
```

The local profile:

- exposes the application on localhost;
- uses a named PostgreSQL volume;
- runs Alembic migrations;
- seeds lookups;
- may use development authentication settings;
- uses the same schema and application code as production.

### 22.2 Cloud Run deployment

Reference production topology:

```text
Cloud Run service
  -> Cloud SQL for PostgreSQL
  -> Secret Manager
  -> Cloud Logging
```

Recommended initial characteristics:

- minimum instances: `0`;
- bounded maximum instances to protect database connections;
- small per-instance connection pool;
- no persistent filesystem dependency;
- automatic HTTPS endpoint;
- liveness and readiness endpoints;
- no background worker;
- no Redis or other cache.

The service may scale horizontally because issue-number allocation is performed by PostgreSQL rather than application memory or local files.

### 22.3 Environment variables

```text
DATABASE_URL
ISSUE_HUB_API_TOKEN
ISSUE_HUB_WEB_USERNAME
ISSUE_HUB_WEB_PASSWORD_HASH
ISSUE_HUB_SESSION_SECRET
ISSUE_HUB_DEFAULT_PROJECT
ISSUE_HUB_DEFAULT_REPOSITORY
ISSUE_HUB_DEFAULT_BRANCH
ISSUE_HUB_IMPORT_ENABLED
PORT
```

### 22.4 Health endpoints

```text
GET /health/live
GET /health/ready
```

`ready` checks database connectivity and schema version. It does not allocate an issue number.

### 22.5 Backup and recovery

The initial operational posture is intentionally modest:

- daily managed PostgreSQL backup;
- at least seven days of retained backups;
- periodic JSON export as an independent logical backup;
- documented restore procedure;
- no multi-region replica requirement.

### 22.6 Single-authority rule

A local deployment with its own database is a separate Hub namespace. It must not be used concurrently as a production fallback for the cloud namespace. Production clients always target one configured URL.


---

## 23. Migration design

### 23.1 Migration objectives

Migration must:

1. preserve every canonical `Bug-N` exactly;
2. preserve historical `AKA` and `TMP-*` values;
3. preserve current status and severity as accurately as possible;
4. retain the complete original text when structured parsing is ambiguous;
5. import active and terminal issues into one live table;
6. allocate canonical IDs for still-pending intake files;
7. establish a safe global sequence;
8. prove that no identifier was lost or duplicated;
9. leave the old files read-only after cutover.

### 23.2 Migration inputs

The migration reads:

```text
docs/execution/execution_issue-registry.md
docs/execution/execution_issue-registry-closed.md
docs/execution/issue-intake/*.md
docs/execution/issue-intake/promoted/*.md
```

It also accepts explicit additional worktree paths so outstanding uncommitted intake files can be included before cutover.

Plans, handoffs, and review reports are not imported as separate record types. Their paths remain in `refs`, `description`, tags, or relationship text.

### 23.3 Source precedence

The importer applies this precedence:

1. canonical active or closed registry record establishes the issue ID and primary current values;
2. promoted intake enriches missing source, AKA, refs, area, domain, category, or note values;
3. pending intake has no canonical ID and receives a newly allocated ID;
4. raw text from every source remains available in `legacy_raw` or the migration report.

If the same canonical ID occurs in both active and closed registries, final cutover is blocked until the conflict is resolved.

### 23.4 Canonical registry parsing

For a one-line registry entry, the importer attempts to extract:

```text
issue_id
sequence_number
status
severity
title
description
area
refs
source
aka
domain
category
```

The exact source line is always stored in `legacy_raw`.

Status brackets can contain dates, hashes, or extra narrative. The importer extracts the leading recognized status when possible and preserves the complete original bracket in `legacy_raw` and description.

Markdown headings are used only as an area fallback when the row lacks an explicit `Area:` field.

### 23.5 Intake parsing

The importer supports the existing header shape:

```text
status
severity
area
domain
category
title
refs
source
aka
temp_id
note
```

Continuation lines and body content become description text. Missing optional fields remain null or empty.

Unlike the old promoter, the new service does not normalize terminal claims to `FIXED-PENDING-VERIFICATION`. Migration preserves the actual recorded status because the Hub is not a closing-control mechanism.

### 23.6 Duplicate source handling

The same issue may appear in several migration sources.

Rules:

1. same `issue_id` with equivalent content: import one live row and record all source paths in the reconciliation report;
2. same `issue_id` with conflicting content: do not guess; block final cutover and report the conflict;
3. same `AKA` on several issues: allow and report it;
4. similar titles or descriptions: allow without duplicate analysis;
5. duplicate pending intake content: allocate separate IDs unless a human removes or retires one later.

### 23.7 Pending intake allocation

Each valid pending intake file receives a new global sequence number during final import.

- `temp_id` is copied into `aka`.
- Existing `aka` and `temp_id` values are combined into the one scalar `aka` field.
- The original intake text is retained in `legacy_raw`.
- Invalid pending files are reported and must be corrected or intentionally excluded before final cutover.

### 23.8 Sequence initialization

The migration calculates:

```text
A = highest numeric suffix found in all imported canonical IDs
B = current registry NEXT CANONICAL NUMBER value minus one
C = highest number allocated to pending intakes during migration
```

The sequence is set so the next value is greater than `max(A, B, C)`.

The final report states all three inputs and the selected next value. Numeric gaps are informational and do not block migration.

### 23.9 Reconciliation report

The dry run produces JSON and Markdown reports containing:

- count by source file;
- total unique canonical IDs;
- minimum and maximum numeric suffix;
- missing numeric gaps;
- counts by status and severity;
- counts by project, repository, domain, category, and area when known;
- partially parsed rows;
- conflicting duplicate IDs;
- repeated AKA values;
- pending intake count;
- invalid intake count;
- proposed next sequence value;
- records requiring manual review.

The report is the migration acceptance artefact.

### 23.10 Cutover procedure

1. Create and deploy an empty Hub environment.
2. Run schema migrations and seed lookups.
3. Run a migration dry run against `main` and every known active worktree.
4. Resolve conflicting canonical IDs and malformed pending records.
5. Announce a brief freeze on issue creation through old files.
6. Run the final import.
7. Run reconciliation and compare counts.
8. Set the global sequence.
9. Smoke-test create, reserve, find, update, append, history, and retire.
10. Install and configure the CLI in agent environments.
11. Replace the old intake README with the Issue Hub agent README.
12. Mark active and closed registries as legacy read-only snapshots.
13. Disable the old promoter and temporary-ID commands.
14. Remove the write freeze and direct every agent to the Hub.

### 23.11 Legacy registry treatment

The old registries remain in Git as frozen historical snapshots and receive a prominent notice:

```text
LEGACY READ-ONLY SNAPSHOT.
Tessallite Issue Hub is the authoritative issue store.
Do not add or update issues in this file.
```

New issues are not generated back into these files. This avoids creating a second synchronization mechanism.

An administrative export can produce legacy-style Markdown on demand, but the export is not automatically committed.

### 23.12 Legacy script treatment

During one transition release:

- `new-issue-id.sh` and `new-issue-id.bat` exit with a message directing agents to `issue create --reserve`;
- `promote_issue_intake.py` and its wrappers exit with a message directing agents to the Hub;
- `issue_stats.py` may temporarily call the Hub read API or be replaced by documented `issue find` filters;
- no legacy script modifies the frozen registries.

After the transition release, obsolete scripts and intake directories may be removed once a repository-wide search proves no active prompt or document still references them.

### 23.13 Rollback boundary

The old files are retained as a pre-cutover snapshot, but dual-authoritative writes are forbidden.

A rollback, if required immediately after cutover, is a deliberate operational event:

1. stop Hub writes;
2. export all post-cutover Hub issues;
3. decide whether to import those records into the old registry or discard the trial cutover;
4. explicitly re-enable legacy tooling.

Normal operation never attempts bidirectional synchronization.

---

## 24. Legacy compatibility

### 24.1 Existing code comments and documents

No existing `Bug-N` reference is modified. The imported `issue_id` is exactly the value already used in code and documentation.

### 24.2 AKA compatibility

Historical aliases remain searchable through one `aka` string. Migration may combine values using a stable separator:

```text
F-029-07 / TMP-20260818125257571
```

No alias table is introduced.

### 24.3 Legacy Markdown export

The Hub can export a one-line representation for inspection or backup:

```md
- **Bug-9627** — `[OPEN]` — AKA <aliases> — `[HIGH -- title]` description. Area: ... Refs: ... Domain: gateway. Category: product.
```

This export is derived data and is never an authority.

### 24.4 New references

After cutover, agents may place the returned ID directly into code comments, plans, and reviews. They do not need an intake file or later renumbering step.

---

## 25. Concurrency and transaction behaviour

### 25.1 Number allocation

Number allocation and initial row insertion occur in one database transaction. This guarantees:

- two successful creates cannot receive the same sequence number;
- two successful creates cannot receive the same issue ID;
- a successful response always refers to a committed row;
- Cloud Run horizontal scaling does not change allocation behaviour.

### 25.2 Ordinary updates

Ordinary updates use this transaction:

```text
BEGIN
  SELECT current issue
  calculate updated issue
  UPDATE live row
  INSERT before/after history
COMMIT
```

No row version is required. Two concurrent updates may both succeed. The later commit determines the live row.

### 25.3 Append operations

An append reads the current description and writes the concatenated description in one transaction. Concurrent appends may still overwrite one another under last-write-wins behaviour. Both versions remain in history.

This is an accepted simplification. A separate append-only comments table is intentionally not introduced.

### 25.4 Network failures

If the service cannot be reached:

- the CLI returns a JSON network error;
- no local canonical ID is invented;
- no number block is preallocated;
- the agent may retry or record unnumbered notes outside the authoritative issue system;
- a retry after a lost successful response may create a duplicate issue.

### 25.5 No distributed locks

The application uses no filesystem, Redis, Cloud Storage, or distributed lock for numbering. PostgreSQL sequence semantics are sufficient.

---

## 26. History and manual recovery

### 26.1 Last-write-wins contract

If two agents update the same issue concurrently:

1. both requests may succeed;
2. the later commit becomes the live row;
3. no conflict response is returned;
4. both transitions remain visible in history.

### 26.2 Recovery

The web history panel displays before and after snapshots. A human may copy a prior field value into the normal edit form. Restoring a prior value is itself a normal update and creates a new history row.

The first release does not provide automatic rollback, field-level merge, or branch-like issue versions.

### 26.3 History retention

History is retained indefinitely unless a future explicit retention policy is introduced. Issue volume is expected to be small enough that full JSON snapshots remain practical.

---

## 27. Observability and operations

The first release includes only operationally useful observability:

- structured JSON application logs;
- request correlation IDs;
- create, update, search, and import error counts;
- database readiness failure logs;
- Cloud Run request metrics;
- Cloud SQL storage and connection monitoring;
- migration summary logs;
- backup-failure alerts.

It does not require a custom analytics platform, event stream, or distributed tracing backend.

Recommended log fields:

```text
timestamp
level
request_id
method
path
status_code
duration_ms
operation
issue_id when known
error_code when present
```

No token, password, session secret, or database connection string is logged.

---

## 28. Testing strategy

### 28.1 Unit tests

- key-template selection and rendering;
- placeholder normalization;
- final numeric-segment validation;
- title derivation from description;
- description append formatting;
- lookup seeding;
- terminal-status classification;
- search filter construction;
- retirement field handling;
- migration parsing for representative active and closed lines;
- intake parsing;
- CLI argument and JSON output behaviour.

### 28.2 Database integration tests

- create issue and history in one transaction;
- reserve issue;
- complete a reserved issue using its ID;
- reject a caller-invented nonexistent ID;
- update and history snapshot;
- append and history snapshot;
- retire without delete;
- query retired and terminal issues;
- accept unknown status despite no lookup row;
- accept relationship values without existing targets;
- tolerate sequence gaps;
- import explicit historical IDs;
- initialize sequence after import;
- preserve `AKA` and `legacy_raw`.

### 28.3 Core concurrency test

Launch at least one hundred simultaneous create requests through independent client processes and more than one application process.

Required result:

- every successful request returns a unique `sequence_number`;
- every successful request returns a unique `issue_id`;
- every returned ID exists in the database;
- every issue has an initial history row;
- numeric gaps are allowed;
- no filesystem lock is used.

This test must run against PostgreSQL, not an in-memory substitute.

### 28.4 Last-write-wins test

Two updates start from the same original row and commit in a controlled order.

Required result:

- both calls succeed;
- the later commit is live;
- both transitions are present in history;
- no version-conflict error exists.

### 28.5 Migration tests

Fixtures cover:

- active issues;
- closed issues;
- dated terminal status brackets;
- commit hashes embedded in status brackets;
- AKA values;
- temporary IDs;
- multiline intake values;
- free-form body notes;
- heading-based area fallback;
- missing optional fields;
- identical duplicate source records;
- conflicting canonical IDs;
- pending intake allocation;
- sequence reconciliation;
- malformed records and complete error reporting.

### 28.6 CLI compatibility tests

The same commands are tested in:

- Linux Bash;
- Windows CMD or PowerShell.

Tests verify JSON stdout, JSON stderr, exit codes, environment configuration, Unicode text, and paths containing spaces.

### 28.7 Web tests

- login and session handling;
- list all issues;
- exact and text search;
- filters;
- create and reserve;
- edit any field;
- append description;
- retire;
- view history;
- edit lookup values;
- edit key template;
- Markdown sanitization;
- CSRF rejection.

### 28.8 Cloud smoke test

After deployment:

1. create one issue through the CLI;
2. reserve one ID;
3. complete the reservation;
4. find both through CLI and web;
5. update status and append text;
6. retire a test issue;
7. verify history;
8. verify backup configuration and readiness endpoint.

---

## 29. Acceptance criteria

The solution is accepted when all of the following are true:

1. The Hub runs locally with Docker Compose and remotely on Cloud Run from the same codebase.
2. PostgreSQL is the only production issue authority.
3. One hundred concurrent creates through multiple client processes produce one hundred distinct canonical IDs.
4. The last segment of every newly generated ID is the allocated global sequence number.
5. Existing `Bug-N` issues are imported without changing their identifiers.
6. Existing code and document references require no renumbering.
7. Historical `AKA` and `TMP-*` values remain searchable.
8. Complete issue creation returns a permanent ID immediately.
9. Reservation returns a permanent ID and creates a visible `RESERVED` row.
10. Gaps do not cause allocation or migration failure.
11. The normal CLI exposes only `create`, `find`, and `update` command families.
12. CLI output is valid JSON in Bash and Windows CMD environments.
13. `find` performs exact lookup, text search, and filtered listing.
14. `update` can change status and every other writable field.
15. `update` can append Markdown to the description.
16. `update` can retire an issue with a reason and optional duplicate target.
17. No normal API or UI action deletes an issue.
18. Retired issues remain visible and searchable.
19. Status, severity, project, repository, domain, category, priority, effort, and retirement lookups are editable.
20. Issue writes accept values that are not present in lookup tables.
21. No foreign keys connect issue values to lookups, history, or relationship targets.
22. Concurrent ordinary updates use last-write-wins behaviour.
23. Every create, reserve, update, append, retire, import, and repair writes history.
24. The web UI supports search, list, create, reserve, edit, append, retire, history, and configuration.
25. The old registry, closed registry, intake queue, promoter, and temporary-ID generator are no longer authoritative.
26. The agent README directs all new issue operations to the Hub.
27. The migration reconciliation report accounts for every imported canonical ID and pending intake.
28. The final sequence is greater than every migrated numeric suffix and the old counter baseline.
29. GitHub Issues is not used.
30. No offline or multi-master numbering mechanism exists.
31. Branch defaults to `main`; worktree defaults to null.
32. Project and repository are independently searchable dimensions.
33. Description structure and source-reference structure remain optional.
34. No automatic duplicate or AI processing runs during create or search.
35. `PARTIAL` remains a valid non-terminal status.
36. `ACCEPTED-RISK` is usable as a terminal status without special evidence.
37. Reopening guidance creates a new related issue rather than mutating the old terminal issue.

---

## 30. Implementation phases

### Phase 0 — Repository and executable skeleton

**Scope**

- create `tessallite-issue-hub` repository;
- establish Python package, FastAPI app, CLI package, Dockerfile, Docker Compose, and test structure;
- add this specification and architecture decision records;
- add basic CI for linting, type checking, tests, and container build.

**Exit criteria**

- empty service starts locally;
- CLI calls a health endpoint;
- PostgreSQL migrations run in test and local environments;
- container image builds reproducibly.

### Phase 1 — Core schema, allocation, and API

**Scope**

- implement sequence and four tables;
- seed lookup values;
- implement key-template selection and rendering;
- implement create and reserve;
- implement find;
- implement update, append, and retire;
- implement history;
- implement bearer-token authentication;
- implement health endpoints.

**Exit criteria**

- core integration tests pass;
- multi-process concurrency test proves unique allocation;
- last-write-wins and history tests pass;
- OpenAPI contract is stable.

### Phase 2 — Operational CLI and agent README

**Scope**

- implement `issue create`;
- implement `issue find`;
- implement `issue update`;
- implement JSON output and stable exit codes;
- support environment and user-level configuration;
- test Bash and Windows CMD;
- write the agent README and examples.

**Exit criteria**

- agents can create, reserve, find, update, append, and retire through CLI;
- platform tests pass;
- no command requires an interactive prompt.

### Phase 3 — Web application and configuration

**Scope**

- implement login and session handling;
- implement combined list/search page;
- implement create/reserve page;
- implement detail/edit/history page;
- implement append and retirement controls;
- implement lookup and key-template configuration;
- sanitize Markdown.

**Exit criteria**

- a human can complete every normal operation without CLI;
- all web tests pass;
- no SPA or separate front-end deployment exists.

### Phase 4 — Migration tooling and dry run

**Scope**

- implement active/closed registry parser;
- implement pending/promoted intake parser;
- preserve raw source;
- produce reconciliation report;
- support supplied worktree paths;
- test sequence initialization;
- run dry migration against a copy of current source.

**Exit criteria**

- every canonical ID is accounted for;
- all conflicts are explicitly reported;
- no existing ID is transformed;
- proposed next sequence is proven safe;
- the reconciliation report is accepted.

### Phase 5 — Cloud deployment and cutover

**Scope**

- deploy Cloud Run and managed PostgreSQL;
- configure secrets, backups, and health checks;
- run final migration;
- install CLI configuration in agent environments;
- freeze old registries;
- replace old instructions;
- disable legacy writers.

**Exit criteria**

- all production agents target the central Hub;
- no new issue is written through Git files;
- post-cutover create/search/update smoke tests pass;
- final reconciliation is clean.

### Phase 6 — Legacy removal and hardening

**Scope**

- remove obsolete intake and promoter code after transition;
- retain frozen registry snapshots;
- verify no active prompt or documentation instructs agents to use the old mechanism;
- document restore and token rotation;
- add periodic logical export.

**Exit criteria**

- one authoritative mechanism remains;
- repository-wide searches find no active legacy instructions;
- backup restore has been rehearsed;
- operational documentation is complete.

---

## 31. Risks and mitigations

| Risk | Consequence | Mitigation |
|---|---|---|
| Client loses a successful create response | Retry creates a second issue | Duplicates are allowed; search and retire the duplicate |
| Last-write-wins update overwrites another change | Current text may lose content | Full history permits inspection and manual restoration |
| Flexible lookup values produce spelling variants | Filters become less tidy | UI autocomplete and editable seeds; no hard rejection |
| Key template contains branch or task data that later changes | Permanent ID contains stale context | Keep default `Bug-{number}` and document template permanence |
| Administrator changes key template incorrectly | New IDs become awkward or invalid | Server validates final numeric suffix and previews sample IDs |
| Migration parser cannot reliably split a legacy line | Structured fields may be incomplete | Always retain exact `legacy_raw` and report partial parses |
| Same canonical ID has conflicting legacy records | Wrong issue could be imported | Block final cutover until manually resolved |
| Independent local and cloud databases are both used as production | Number namespaces diverge | Document single-authority rule; no synchronization feature |
| Cloud database unavailable | Creates and updates fail | Return explicit errors; never fabricate offline IDs |
| Shared API token leaks | Unauthorized edits | Store in secrets/user config, use TLS, rotate token |
| Frozen registry is mistaken for current data | Humans read stale state | Add a prominent read-only notice and link to the Hub |
| Cloud SQL cost is disproportionate | Unnecessary operating cost | Keep app portable to any managed PostgreSQL provider |
| No agent identity in history | Attribution is unavailable | Accepted design choice; attribution may be included in description/source text |
| Description append races | One append may overwrite another live value | Both versions remain in history; separate comments table intentionally rejected |
| Unknown status is entered | Open/closed classification may be imperfect | Unknown values remain visible and default to non-terminal |

---

## 32. Rejected alternatives

### 32.1 Continue the Git lock and promoter

Rejected because isolated worktrees do not share one lock, one counter, or one mutable file. Additional file-lock complexity does not create a central authority.

### 32.2 Preallocate number ranges to agents

Rejected because range ownership, expiry, recovery, and unused-number handling create more coordination logic than the Hub itself.

### 32.3 Continue temporary IDs until merge

Rejected because temporary values become embedded in code and documents and still require later rewriting.

### 32.4 Use GitHub Issues

Rejected because repository-local numbering and GitHub workflow behaviour do not provide the required generic, configurable, predictable identifier namespace. It also introduces unnecessary product behaviour.

### 32.5 Use Jira or another work-management suite

Rejected because the requirement is a small issue ledger, not a workflow platform.

### 32.6 Use UUIDs as visible or internal identity

Rejected because the user prefers one business key and existing references use compact sequential IDs.

### 32.7 Add separate comments, relationships, attachments, and actor tables

Rejected because description plus history and two scalar relationship fields meet the requirement with far less complexity.

### 32.8 Use a React single-page application

Rejected because it adds a build pipeline, dependency surface, and separate front-end concerns without improving the core ledger.

### 32.9 Use SQLite in Cloud Run

Rejected because Cloud Run instances do not share durable local storage and may scale horizontally. PostgreSQL provides a shared sequence and durable writes.

### 32.10 Add offline synchronization

Rejected because multi-master numbering and conflict reconciliation would recreate the original problem in a more complex form.

### 32.11 Enforce foreign keys to configurable lookups

Rejected because status, severity, domain, and category must remain flexible and import must preserve historical values even when they are not in current seed lists.

### 32.12 Add idempotency keys

Rejected for the first release because the user accepts occasional duplicates after uncertain retries, and retirement provides a simple correction path.


---

## 33. Recommended repository structure

```text
tessallite-issue-hub/
├── README.md
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── alembic.ini
├── migrations/
├── src/
│   ├── issue_hub/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── key_generation.py
│   │   ├── issue_service.py
│   │   ├── search.py
│   │   ├── history.py
│   │   ├── auth.py
│   │   ├── api/
│   │   │   ├── issues.py
│   │   │   ├── config.py
│   │   │   ├── admin.py
│   │   │   └── health.py
│   │   ├── web/
│   │   │   ├── routes.py
│   │   │   ├── templates/
│   │   │   └── static/
│   │   └── migration/
│   │       ├── registry_parser.py
│   │       ├── intake_parser.py
│   │       ├── reconcile.py
│   │       └── import_service.py
│   └── issue_cli/
│       ├── main.py
│       ├── client.py
│       ├── config.py
│       └── output.py
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── concurrency/
│   ├── migration/
│   ├── cli/
│   └── web/
└── docs/
    ├── solution-spec.md
    ├── agent-readme-template.md
    ├── deployment-cloud-run.md
    ├── deployment-local.md
    └── migration-runbook.md
```

### 33.1 Module boundaries

- `key_generation.py` is the only module that renders new IDs.
- `issue_service.py` is the only module that performs issue mutations and writes history.
- API routes contain request translation only.
- Web routes call the same service functions as the API.
- The CLI calls HTTP and contains no persistence logic.
- Migration parsers produce normalized import records but use `issue_service.py` for insertion.

This boundary prevents numbering or update rules from diverging between API, UI, CLI, and migration.

---

## 34. Implementation details

### 34.1 Create service pseudocode

```python
def create_issue(request: CreateIssueRequest) -> Issue:
    with database.transaction() as tx:
        if request.issue_id:
            reserved = tx.get_issue(request.issue_id)
            if reserved is None or reserved.status != "RESERVED":
                raise CallerSuppliedIdNotAllowed(request.issue_id)
            before = reserved.to_dict()
            updated = apply_create_fields(reserved, request)
            tx.update_issue(updated)
            tx.insert_history(
                issue_id=updated.issue_id,
                operation="UPDATE",
                before_record=before,
                after_record=updated.to_dict(),
            )
            return updated

        number = tx.next_sequence_value("issue_number_seq")
        template = select_template(request.project)
        issue_id = render_issue_id(template, request, number)
        issue = build_issue(issue_id, number, request)
        tx.insert_issue(issue)
        tx.insert_history(
            issue_id=issue.issue_id,
            operation="RESERVE" if request.reserve else "CREATE",
            before_record=None,
            after_record=issue.to_dict(),
        )
        return issue
```

The sequence call, live insert, and history insert are one transaction. No application-level mutex is used.

### 34.2 Update service pseudocode

```python
def update_issue(issue_id: str, patch: UpdateIssueRequest) -> Issue:
    with database.transaction() as tx:
        current = tx.get_issue(issue_id)
        if current is None:
            raise IssueNotFound(issue_id)

        before = current.to_dict()
        updated = apply_set_fields(current, patch.set)

        if patch.append_description is not None:
            updated.description = append_markdown(
                updated.description,
                patch.append_description,
                tx.current_timestamp(),
            )

        if patch.retire is not None:
            updated.is_retired = True
            updated.retire_reason = patch.retire.reason
            updated.retire_note = patch.retire.note
            updated.retired_at = tx.current_timestamp()
            if patch.retire.duplicate_of:
                updated.duplicate_of = patch.retire.duplicate_of

        updated.updated_at = tx.current_timestamp()
        tx.update_issue(updated)
        tx.insert_history(
            issue_id=issue_id,
            operation=classify_operation(patch),
            before_record=before,
            after_record=updated.to_dict(),
        )
        return updated
```

No `WHERE version = ...` predicate is present.

### 34.3 Key rendering

Server normalization should be predictable and conservative:

1. trim whitespace;
2. convert path separators, spaces, and unsupported punctuation to `-`;
3. collapse repeated `-` characters;
4. preserve readable case according to configuration, defaulting to the supplied project spelling;
5. remove leading and trailing separators;
6. append the numeric sequence as the final segment;
7. reject an empty rendered prefix;
8. reject a final ID longer than a configured safe limit, initially 200 characters.

The server stores the final rendered ID only. It does not need a separate prefix column.

### 34.4 Tag behaviour

Tags are stored as a JSON array of strings.

- duplicate values are removed case-insensitively;
- original display casing of the first value is retained;
- empty strings are removed;
- no tag lookup or tag relationship table is required;
- `--add-tag` and `--remove-tag` are convenience operations translated into a complete updated array by the server.

### 34.5 Related issue behaviour

`duplicate_of` and `related_to` are advisory text fields. The server may return a warning when a referenced ID cannot be found, but it must not reject the update.

### 34.6 Search implementation

A simple first implementation may use parameterized `ILIKE` clauses and indexed exact fields. If migration measurements show text search above the performance target, add a PostgreSQL generated `tsvector` and GIN index. No external search service is introduced.

Recommended performance targets for a warm service:

```text
exact ID lookup        < 200 ms server-side
normal filtered list   < 500 ms server-side
text search            < 1 second server-side
issue create           < 1 second excluding cold start
issue update           < 1 second excluding cold start
```

These are engineering targets, not formal service-level commitments.

### 34.7 Pagination and limits

- default list limit: 100;
- maximum list limit: 1,000;
- exports stream all rows separately from the ordinary list endpoint;
- default sort: descending `sequence_number`;
- optional sorts: `updated_at`, `created_at`, `severity`, `status`, `project`, and `repository`.

### 34.8 Data-size limits

Recommended defaults:

```text
issue_id              200 characters
project               200 characters
repository            300 characters
branch                 500 characters
worktree               1,000 characters
title                  500 characters
description            2 MiB
refs                    1 MiB
source                  100 KiB
aka                     100 KiB
related_to              100 KiB
retire_note             100 KiB
tags                    500 values, 200 characters each
```

These limits prevent accidental abuse without imposing a rigid issue structure.

---

## 35. Agent quick reference

The final agent README can use this compact operational section.

### Create a complete issue

```bash
issue create \
  --severity HIGH \
  --description "Excel cannot resolve the hierarchy owner." \
  --area "Gateway / XMLA" \
  --domain gateway \
  --category product \
  --refs "tessallite/services/gateway/src/dax/xmla_server.py"
```

### Reserve an ID before details are ready

```bash
issue create --reserve
```

### Find an issue

```bash
issue find Bug-9627
```

### Search text

```bash
issue find "hierarchy owner"
```

### List by characteristics

```bash
issue find --status OPEN --severity HIGH --domain gateway
```

### Update any fields

```bash
issue update Bug-9627 \
  --set status=FIXED-PENDING-VERIFICATION \
  --set expected_effort=S
```

### Append implementation or review notes

```bash
issue update Bug-9627 --append-file closeout.md
```

### Retire a duplicate

```bash
issue update Bug-9627 \
  --retire DUPLICATE \
  --duplicate-of Bug-9584 \
  --retire-note "Same root cause"
```

### Rules for agents

```text
Do not edit the legacy registries.
Do not create issue-intake files.
Do not create TMP identifiers.
Do not invent a Bug number when the Hub is unavailable.
Use the returned issue_id in code and documents.
Retire duplicates; never delete or renumber them.
```

---

## 36. Definition of done

Tessallite Issue Hub is complete only when the entire old issue-creation path has been removed from normal agent behaviour, not merely when the new service exists.

Completion requires all of the following:

### Product

- central creation, reservation, find, update, append, retirement, history, and configuration work through API and web;
- CLI works in Bash and Windows CMD;
- every output is JSON;
- all issue records, including retired records, remain searchable.

### Data

- one global sequence is active;
- existing IDs are unchanged;
- one live issue table and one history table hold the issue domain;
- lookups are editable and not enforced by foreign keys;
- migration reconciliation is complete;
- backups and restore instructions exist.

### Repository cutover

- the old active and closed registries are marked read-only;
- intake creation and promotion instructions are removed;
- temporary-ID scripts no longer allocate IDs;
- promoter scripts no longer write registries;
- agent prompts and README files refer only to `issue` and the Hub;
- no deferred migration item or dual-write mechanism remains.

### Verification

- the multi-process uniqueness test passes against PostgreSQL;
- Cloud Run smoke tests pass;
- Windows and Bash CLI tests pass;
- migration counts reconcile;
- post-cutover issue creation produces the next safe number;
- a repository-wide search finds no active instructions to use the old workflow.

---

## 37. Final architectural recommendation

Implement Tessallite Issue Hub as one small FastAPI application, one PostgreSQL database, one three-command CLI, and one server-rendered web interface.

Keep the initial production identity format as:

```text
Bug-{number}
```

Use one global PostgreSQL sequence. Make the server the only component that renders IDs. Preserve every historical `Bug-N` and `AKA` during migration. Use a real `RESERVED` issue for bare-number allocation, not a temporary ID or draft. Keep all current fields as flexible text, store tags as a JSON array, append comments into the description, and preserve every mutation as before-and-after JSON in one history table.

Do not add Git synchronization, GitHub Issues, AI duplicate detection, workflow enforcement, optimistic locking, user accounts, attachments, comments tables, background workers, Redis, or offline numbering. Those features do not solve the stated problem and would move the solution toward the complexity the Hub is intended to avoid.

The permanent correctness boundary is simple:

> **One Hub database allocates every numeric suffix; every successful create produces one durable issue row; every existing identifier remains unchanged.**

---

## Appendix A — Initial JSON create document

```json
{
  "project": "tessallite",
  "repository": "tessallite-workspace",
  "branch": "main",
  "worktree": null,
  "task": null,
  "status": "OPEN",
  "severity": "HIGH",
  "priority": null,
  "expected_effort": "UNKNOWN",
  "title": "Short searchable title",
  "description": "Markdown issue description",
  "area": "Gateway / XMLA",
  "classification": null,
  "domain": "gateway",
  "category": "product",
  "refs": "path/to/file.py:123",
  "source": "review agent",
  "aka": null,
  "owner": null,
  "tags": [],
  "duplicate_of": null,
  "related_to": null
}
```

## Appendix B — Initial JSON update document

```json
{
  "set": {
    "status": "PARTIAL",
    "severity": "MEDIUM",
    "priority": "P2",
    "expected_effort": "S",
    "owner": "MO",
    "related_to": "Bug-9500",
    "tags": ["xmla", "reviewed"]
  },
  "append_description": "The primary path is fixed; one edge case remains."
}
```

## Appendix C — Initial JSON retire document

```json
{
  "retire": {
    "reason": "DUPLICATE",
    "duplicate_of": "Bug-9500",
    "note": "The reported behaviour is the same defect and code path."
  }
}
```

## Appendix D — Migration output example

```json
{
  "source_counts": {
    "active_registry": 1250,
    "closed_registry": 1100,
    "promoted_intakes": 900,
    "pending_intakes": 12
  },
  "unique_canonical_issues": 2350,
  "conflicting_issue_ids": [],
  "repeated_aka_values": [
    {
      "aka": "F-029-15",
      "issue_ids": ["Bug-9396", "Bug-9488"]
    }
  ],
  "partially_parsed_records": 7,
  "highest_imported_number": 9626,
  "old_counter_next_number": 9627,
  "highest_pending_allocated_number": 9638,
  "configured_next_sequence": 9639,
  "blocking_errors": []
}
```

## Appendix E — Environment configuration example

```text
DATABASE_URL=postgresql+psycopg://issue_hub:***@host/issue_hub
ISSUE_HUB_API_TOKEN=<secret>
ISSUE_HUB_WEB_USERNAME=admin
ISSUE_HUB_WEB_PASSWORD_HASH=<argon2-or-bcrypt-hash>
ISSUE_HUB_SESSION_SECRET=<random-secret>
ISSUE_HUB_DEFAULT_PROJECT=tessallite
ISSUE_HUB_DEFAULT_REPOSITORY=tessallite-workspace
ISSUE_HUB_DEFAULT_BRANCH=main
ISSUE_HUB_IMPORT_ENABLED=false
PORT=8080
```

## Appendix F — Traceability to the requested decisions

| Requested decision | Specification location |
|---|---|
| Generic across projects and repositories | Sections 2, 6, 11, 12 |
| Replace all old mechanisms | Sections 1, 23, 24, 36 |
| Local and Cloud Run portability | Sections 9, 10, 22 |
| No GitHub Issues | Sections 2, 7, 32 |
| Configurable nonnumeric ID prefix | Section 11 |
| Final segment is the sequence number | Section 11 |
| Single business key; no UUID | Sections 11 and 12 |
| Preserve existing references | Sections 11, 23, 24 |
| Gaps allowed | Sections 11, 25, 29 |
| Direct create and number reservation | Sections 11, 16, 17 |
| No drafts | Sections 2 and 11 |
| No idempotency complexity | Sections 11 and 32 |
| Retire rather than delete | Sections 14, 16, 29 |
| One scalar AKA field | Sections 12, 23, 24 |
| One live table and one history table | Sections 8 and 12 |
| No offline mode | Sections 7, 25, 29 |
| Duplicates allowed; no AI processing | Sections 7, 16, 29 |
| Configurable domain/category/status | Sections 12, 13, 19 |
| Priority optional | Sections 12 and 13 |
| Markdown recommended but not enforced | Sections 15 and 16 |
| Optional source/reference structure | Sections 12 and 16 |
| Optional repository context | Section 17 |
| One optional owner | Section 12 |
| Only duplicate/related relationships | Sections 12 and 16 |
| Description contains appended comments | Section 15 |
| No attachments | Section 7 |
| Release and milestone as tags | Section 12 |
| Expected fix effort | Sections 12 and 13 |
| Freely editable statuses | Sections 13 and 14 |
| No workflow or evidence enforcement | Sections 7, 14, 20 |
| Reopen as a new related issue | Section 14 |
| Partial is non-terminal | Sections 13 and 14 |
| No hidden issues | Sections 14, 19, 21 |
| Accepted risk terminal without controls | Sections 13 and 14 |
| Silent overwrite | Sections 8, 25, 26 |
| CLI named `issue` | Section 17 |
| Bash and Windows CMD | Sections 17, 28, 29 |
| Simplified create/find/update model | Section 17 |
| Non-interactive CLI and web for humans | Sections 17 and 19 |
| JSON output | Sections 16 and 17 |

