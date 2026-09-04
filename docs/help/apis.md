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
| `GET /api/v1/issues` | Wide search / list issues. Passing `q=search_phrase` executes an all-inclusive query matching against every single attribute joined via OR operators. Supports multi-select arrays (`status`, `severity`, `priority`, `domain`, `category`, `project`, `repository`) and closed date ranges (`closed_from`, `closed_to`). | Query Params: `q=search_phrase`, `id=Bug-9627`, `status=OPEN&status=RESERVED`, `closed_from=2026-08-01`, `limit=100`, `offset=0` |
| `PATCH /api/v1/issues/{issue_id}` | Modify fields, append logs to description, or retire entries. | `{"set": {"status": "FIXED"}, "append_description": "Comment text...", "retire": {"reason": "DUPLICATE"}}` |
| `GET /api/v1/issues/{issue_id}/history` | Retrieve chronological audit log snapshots with before/after states. | None (Response: JSON array of log state entries) |

### C. Flat Error Shape Contract
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
