# 1. REST API Specification

[Previous: Help Home](home.md) | [Home: Help Home](home.md) | [Next: Agent CLI](cli.md)

---

The Issue Hub exposes a stateless HTTP REST API under `/api/v1/` designed for automated software agents and remote tooling.

### A. Authentication Model
All read and write API endpoints are authenticated using a shared Bearer Token configured in the server environment as `ISSUE_HUB_API_TOKEN` (default: `api_bearer_token_123`). Requests must supply this token in the header:
```http
Authorization: Bearer api_bearer_token_123
```

### B. Core API Endpoints

| Method & Path | Description | Request Body Schema |
| :--- | :--- | :--- |
| `POST /api/v1/issues` | Create complete issue or reserve a sequence number. | `{"reserve": bool, "project": "tessallite", "severity": "HIGH", "description": "Markdown text...", "priority": "P1", "expected_effort": "M", "domain": "shared", "category": "ci", "tags": ["tag1"]}` |
| `GET /api/v1/issues` | Wide search / list issues. Passing `q=search_phrase` executes an all-inclusive query matching against every single attribute joined via OR operators. Supports multi-select arrays, all three date ranges, ordering, and paging. | Query Params: `q=search_phrase`, `id=Bug-9627`, `status=OPEN,RESERVED`, `closed_from=2026-08-01`, `sort=severity desc`, `limit=100`, `offset=0` |
| `PATCH /api/v1/issues/{issue_id}` | Modify fields, append logs to description, or retire entries. | `{"set": {"status": "FIXED"}, "append_description": "Comment text...", "retire": {"reason": "DUPLICATE"}}` |
| `GET /api/v1/issues/{issue_id}/history` | Retrieve chronological audit log snapshots with before/after states. | None (Response: JSON array of log state entries) |

### C. Shared Filter Surface

The REST API, the web issue list, and the analytics dashboard bind to one shared filter definition (`issue_hub/filters.py`). The same query string therefore returns the same result set on all three surfaces.

| Parameter | Accepts | Notes |
| :--- | :--- | :--- |
| `id` | One or more issue IDs | Comma-separated. Also matches alternate identifiers held in `aka`. |
| `q` | Text | Wide search across every attribute. |
| `project`, `repository`, `status`, `severity`, `priority`, `expected_effort`, `domain`, `category` | One or more values | Repeat the parameter or comma-separate. Applied as SQL `IN`. |
| `branch`, `worktree`, `task`, `area`, `classification`, `owner`, `tag` | Single value | Exact match; `tag` tests JSONB array membership. |
| `is_retired`, `is_terminal` | `true` / `false` | Omit for no opinion. |
| `created_from`, `created_to`, `updated_from`, `updated_to`, `closed_from`, `closed_to` | Date or timestamp | ISO 8601 or any configured input format (`DD-MM-YYYY` by default). A date-only upper bound covers the whole day. |
| `sort` | `<field> [asc\|desc]` | Also accepts `field:desc` and `-field`. |
| `limit`, `offset` | Integers | `limit` is bounded by `pagination.max_limit`; requests above it are rejected with 422. |

Date bounds also accept the older `created_after` / `created_before`, `updated_after` / `updated_before`, and `closed_after` / `closed_before` spellings, so existing links keep working.

**Sorting.** Only mapped columns are sortable; the accepted set is derived from the model, and an unrecognised field falls back to the default ordering rather than erroring. Columns backed by a lookup vocabulary (`status`, `severity`, `priority`, `expected_effort`) sort by their configured `display_order`, so severity orders CRITICAL, HIGH, MEDIUM, LOW rather than alphabetically. A unique tiebreaker is applied beneath every ordering, so paging with `limit`/`offset` never repeats or skips a row.

**Paging.** The response echoes the limit that was actually applied, not the one requested. When no `limit` is supplied the `search_default_limit` hub setting is used.

### D. Flat Error Shape Contract
API errors bypass nested detail keys, returning a flat, predictable JSON error schema:
```json
{
  "ok": false,
  "error": {
    "code": "CALLER_SUPPLIED_ID_NOT_ALLOWED",
    "message": "Human-readable explanation",
    "details": {}
  }
}
```

Standard Error Codes:
- `INVALID_REQUEST`: Missing mandatory fields or malformed payload.
- `AUTHENTICATION_FAILED`: Token missing or invalid.
- `ISSUE_NOT_FOUND`: Referenced issue identifier does not exist.
- `DATABASE_UNAVAILABLE`: PostgreSQL unreachable.

---

[Previous: Help Home](home.md) | [Home: Help Home](home.md) | [Next: Agent CLI](cli.md)
