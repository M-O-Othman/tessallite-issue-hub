# Action Plan — Issue List, Analytics, and API Parity Remediation

Supersedes the completed plan of 2026-09-04. Source of truth for this job.

## Scope

Six reported defects plus one performance defect found during investigation. All
six must be delivered; nothing may be deferred without explicit user approval.

| # | Reported defect | Root cause |
|---|---|---|
| 1 | No sort in issue list | `get_issues_list` has no `sort` parameter; `search.py` accepts one but the web route never passes it. `getattr(Issue, field)` is unvalidated. |
| 2 | Offset not reset on new search | `list.html:80` carries `offset` in a hidden input that survives filter changes. |
| 3 | Pagination is wrong | Upper bound computed as `offset+limit` not rows returned; template uses requested `limit` while `search.py:236` clamps to 1000; web hardcodes `limit=100` bypassing `search_default_limit`; no stable sort tiebreaker so paging can repeat/skip rows. |
| 4 | Treemap segments on one dimension | `updateTreemap` builds a flat `"${val} - ${sev}"` key list. Severity is hardcoded as the second dimension; no `children` nesting. |
| 5 | Analytics filters incomplete, not applied to all graphs | `get_visualization` accepts no filter params. 5 filters vs 20+ on the list page. Filter logic duplicated in `updateDashboard` and `getActiveFilteredIssues`. |
| 6 | API does not match web interface | Web lacks `id`, `branch`, `updated_from/to`, `sort`. Date params named differently. API splits comma-separated values, web does not. API honours `search_default_limit`, web does not. |
| 7 | (found) Analytics ships a multi-megabyte payload | `/visualization` serialises all 33 fields incl. `description`, `legacy_raw`, `aka` for every issue. Charts read only 10 fields. |

**Decision on record (user, this session):** analytics uses **server-side shared
filters** — `/visualization` accepts the same query parameters as the list page
and filters in SQL. Rejected: client-side expansion, hybrid.

**Decision on record (user, this session):** `issues_aka_idx` dropped from
migration `f1127bbc1194`. Not revisited here.

## Phase 1 — Shared filter and sort core

- [x] 1.1 Add `src/issue_hub/filters.py`: one `IssueFilterParams` FastAPI
      dependency owning every filter field, date parsing, comma-splitting, and
      list normalisation. Accepts both `created_from`/`created_after` spellings
      so existing bookmarks keep working. Single source of truth for web list,
      analytics, and API.
- [x] 1.2 Refactor `search.py`: extract `build_issue_query(db, ...)` returning an
      unordered, unpaginated `Query`. `query_issues` becomes sort + paginate on
      top of it. Analytics consumes the same builder — parity by construction.
- [x] 1.3 Derive sortable fields from the SQLAlchemy mapper
      (`inspect(Issue).mapper.column_attrs`) rather than a hardcoded list, so
      only real columns are sortable and the set cannot drift from the model.
- [x] 1.4 Append a stable unique tiebreaker (`sequence_number`) to every
      ordering path, including the text-search score path. Fixes the
      repeat/skip paging defect at its root.
- [x] 1.5 Add `resolve_limit(db, limit)` as the single place the effective limit
      is decided and clamped. Both API and web use it, so the number the UI
      renders is the number the query used.

## Phase 2 — Issue list: sort, offset reset, pagination

- [x] 2.1 Add `sort` to `get_issues_list`; pass through to `query_issues`.
- [x] 2.2 Sortable column headers in `list.html` (ID, Status, Severity,
      Priority, Title, Project, Domain, Owner, Updated) with direction
      indicators, preserving all active filters in the link.
- [x] 2.3 Remove the persistent hidden `offset` input. Pagination injects offset
      at submit time only, so any filter or search change starts at page 1.
- [x] 2.4 Correct pagination: bound by rows actually returned, use the effective
      limit, clamp out-of-range offset, add numbered pages.
- [x] 2.5 Web `limit` defaults to `None` so `search_default_limit` applies, and
      is validated `ge=1, le=1000` instead of silently clamped.

## Phase 3 — Analytics: server-side filters and two-dimension treemap

- [x] 3.1 `get_visualization` accepts the full `IssueFilterParams` set, filters
      via `build_issue_query`, and projects only the columns the charts read.
- [x] 3.2 Full filter UI parity with the issue list, submitting as a form so
      filters are shareable in the URL and apply to every graph by construction.
- [x] 3.3 Delete the duplicated client-side filter functions
      (`updateDashboard`'s inline filter and `getActiveFilteredIssues`). Charts
      render the server-filtered set. Removes the drift that caused defect 5.
- [x] 3.4 Treemap: two independent user-selected dimensions (primary "Segment
      By", secondary "Then By" incl. a None option), rendered as a real nested
      hierarchy with `children`. Severity becomes one option among many rather
      than a hardcoded second axis.
- [x] 3.5 Remove `visibleMin: 10`, which silently hides small segments.
- [x] 3.6 Keep KPI cards and every chart driven by the same filtered set.

## Phase 4 — API and web parity

- [x] 4.1 Add `id`, `branch`, `updated_from`/`updated_to`, and `sort` to the web
      list route and UI.
- [x] 4.2 Web accepts comma-separated multi-values, matching API behaviour.
- [x] 4.3 API and web share `IssueFilterParams`, so the two cannot drift again.
- [x] 4.4 API `limit` echoed in the response is the effective limit actually
      applied.
- [x] 4.5 Document the canonical parameter set and the accepted aliases.

## Phase 5 — Tests

- [x] 5.1 Sort: each sortable field, both directions, rejection of unknown and
      non-column fields.
- [x] 5.2 Pagination: stable ordering across pages (no repeats, no gaps),
      correct bounds on the final partial page, out-of-range offset.
- [x] 5.3 Offset reset on filter change.
- [x] 5.4 Analytics: filters applied server-side; parity of results with the
      list page for an identical query string.
- [x] 5.5 API/web parity: identical filters return identical totals.
- [x] 5.6 Full suite green before deploy. No skips.

## Phase 6 — Documentation

- [x] 6.1 `README.md` and `Docs/user-guide.md` updated to current state.
- [x] 6.2 `docs/help/*.md` and `src/issue_hub/web/templates/help/*.html` updated,
      both kept chained via previous/home/next with no orphan pages.
- [x] 6.3 Every defect logged in `Docs/known_issues.md` with file references.

## Phase 7 — Deploy

- [x] 7.1 Full suite green locally.
- [x] 7.2 Build and push image to
      `us-west1-docker.pkg.dev/tessallite-io/tessallite/issue-hub`.
- [x] 7.3 Deploy to Cloud Run `tessallite-issue-hub` (us-west1).
- [x] 7.4 Verify `/health/ready`, list, sort, pagination, and analytics against
      production. Confirm `alembic upgrade head` is a no-op at `f1127bbc1194`.

## Scope Guard

Nothing below may be dropped without explicit user approval.

| Item | Phase | Risk of deferral |
|---|---|---|
| Sort UI in the list table | 2.2 | Backend-only sort would leave defect 1 user-invisible |
| Stable pagination tiebreaker | 1.4 | The subtle half of defect 3; easy to miss |
| Two-dimension nested treemap | 3.4 | Defect 4 |
| Full analytics filter parity | 3.2 | Defect 5 |
| Filters applied to every graph | 3.3 | Second half of defect 5 |
| Web `id`/`branch`/`updated`/`sort` | 4.1 | Defect 6 |
| Payload projection | 3.1 | Found defect 7 |
| Help pages chained, no orphans | 6.2 | Required by project rules |

## Outcome

All phases complete. Full suite green (68 tests). Deployed to Cloud Run
`tessallite-issue-hub` (us-west1) and verified against production.

### Incident during execution

Stamping `alembic_version` to `f1127bbc1194` while the deployed image predated
that migration took production down for roughly four minutes at the first cold
start (`Can't locate revision identified by 'f1127bbc1194'`). Reverting the stamp
restored service immediately. The migration was then made idempotent, verified
against a database in production's exact state, and the version advanced by
deploying the image that carries it. Logged as item 8 in `Docs/known_issues.md`.

### Additional defects found and fixed beyond the six reported

- Unvalidated sort field resolution (`getattr(Issue, field)`) accepted any attribute.
- Migration `f1127bbc1194` aborted when its indexes already existed.
- Global CLI context options (`--project`, `--repository`) were silently dropped
  by the `find` subcommand (pre-existing; `Docs/known_issues.md` item 9).
- `/visualization` inlined all 33 columns per issue when the charts read 10.

