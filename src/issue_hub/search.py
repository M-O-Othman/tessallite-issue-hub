"""Issue filtering, sorting, and pagination.

``build_issue_query`` owns filtering and nothing else. The issue list, the REST
API, and the analytics dashboard all build on it, so a filter added here reaches
every surface at once.
"""
import re
from datetime import datetime
from typing import List, Optional, Tuple, Union

from sqlalchemy import String, asc, cast, desc, func, inspect, nullslast, or_, select, text
from sqlalchemy.orm import Query, Session

from issue_hub.models import Issue, LookupValue
from issue_hub.ui_config import DEFAULT_SORT, FALLBACK_LIMIT, LOOKUP_BACKED_COLUMNS, MAX_LIMIT

# Only real mapped columns may be sorted on. Derived from the model rather than
# a hand-maintained list so it cannot drift and cannot expose non-columns.
SORTABLE_FIELDS = frozenset(attr.key for attr in inspect(Issue).mapper.column_attrs)

# Unique column appended to every ordering. Without it, rows tied on the sort key
# have no defined order, and LIMIT/OFFSET paging can repeat or skip rows.
TIEBREAKER = Issue.sequence_number

# Columns searched by the free-text query.
_TEXT_COLUMNS = (
    "issue_id", "aka", "title", "description", "area", "classification",
    "domain", "category", "refs", "source", "owner", "status", "severity",
    "priority", "expected_effort", "project", "repository", "branch",
    "worktree", "task", "duplicate_of", "related_to", "retire_reason",
    "retire_note", "legacy_raw", "recommended_next_step",
)


def _apply_in(query: Query, column, value: Optional[Union[str, List[str]]]) -> Query:
    """Filter on a column that accepts either one value or several."""
    if not value:
        return query
    if isinstance(value, (list, tuple, set)):
        return query.filter(column.in_(list(value)))
    return query.filter(column == value)


def build_issue_query(
    db: Session,
    id_: Optional[str] = None,
    q: Optional[str] = None,
    project: Optional[Union[str, List[str]]] = None,
    repository: Optional[Union[str, List[str]]] = None,
    branch: Optional[str] = None,
    worktree: Optional[str] = None,
    task: Optional[str] = None,
    status: Optional[Union[str, List[str]]] = None,
    severity: Optional[Union[str, List[str]]] = None,
    priority: Optional[Union[str, List[str]]] = None,
    expected_effort: Optional[Union[str, List[str]]] = None,
    area: Optional[str] = None,
    domain: Optional[Union[str, List[str]]] = None,
    category: Optional[Union[str, List[str]]] = None,
    classification: Optional[str] = None,
    owner: Optional[str] = None,
    tag: Optional[str] = None,
    is_retired: Optional[bool] = None,
    is_terminal: Optional[bool] = None,
    created_from: Optional[datetime] = None,
    created_to: Optional[datetime] = None,
    updated_from: Optional[datetime] = None,
    updated_to: Optional[datetime] = None,
    closed_from: Optional[datetime] = None,
    closed_to: Optional[datetime] = None,
) -> Query:
    """Return the filtered, unordered, unpaginated issue query."""
    query = db.query(Issue)

    # Exact ID lookup, matching either the canonical id or an alias in `aka`.
    if id_:
        clauses = []
        for value in (part.strip() for part in id_.split(",")):
            if not value:
                continue
            clauses.append(func.lower(Issue.issue_id) == value.lower())
            # Word-boundary match so 'Bug-10' does not match 'Bug-100'.
            clauses.append(Issue.aka.op("~*")(rf"\y{re.escape(value)}\y"))
        if clauses:
            query = query.filter(or_(*clauses))

    query = _apply_in(query, Issue.project, project)
    query = _apply_in(query, Issue.repository, repository)
    query = _apply_in(query, Issue.status, status)
    query = _apply_in(query, Issue.severity, severity)
    query = _apply_in(query, Issue.priority, priority)
    query = _apply_in(query, Issue.expected_effort, expected_effort)
    query = _apply_in(query, Issue.domain, domain)
    query = _apply_in(query, Issue.category, category)
    query = _apply_in(query, Issue.branch, branch)
    query = _apply_in(query, Issue.worktree, worktree)
    query = _apply_in(query, Issue.task, task)
    query = _apply_in(query, Issue.area, area)
    query = _apply_in(query, Issue.classification, classification)
    query = _apply_in(query, Issue.owner, owner)

    # Tag membership against the JSONB array (served by issues_tags_gin_idx).
    if tag:
        query = query.filter(Issue.tags.contains([tag]))

    if is_retired is not None:
        query = query.filter(Issue.is_retired.is_(is_retired))

    if is_terminal is not None:
        terminal = [
            value for value, in db.query(LookupValue.value).filter(
                LookupValue.lookup_type == "STATUS",
                LookupValue.is_terminal.is_(True),
            ).all()
        ]
        query = query.filter(Issue.status.in_(terminal) if is_terminal else ~Issue.status.in_(terminal))

    if created_from is not None:
        query = query.filter(Issue.created_at >= created_from)
    if created_to is not None:
        query = query.filter(Issue.created_at <= created_to)
    if updated_from is not None:
        query = query.filter(Issue.updated_at >= updated_from)
    if updated_to is not None:
        query = query.filter(Issue.updated_at <= updated_to)
    if closed_from is not None:
        query = query.filter(Issue.retired_at >= closed_from)
    if closed_to is not None:
        query = query.filter(Issue.retired_at <= closed_to)

    if q:
        escaped = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        clauses = [getattr(Issue, name).ilike(pattern) for name in _TEXT_COLUMNS]
        clauses.append(cast(Issue.sequence_number, String).ilike(pattern))
        clauses.append(cast(Issue.tags, String).ilike(pattern))
        query = query.filter(or_(*clauses))

    return query


def _score_expression(q: str):
    """Relevance score for a free-text search (exact id beats prefix beats body)."""
    q_clean = q.strip()
    escaped = q_clean.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return text(
        """
        CASE
            WHEN LOWER(issues.issue_id) = LOWER(:q_clean) THEN 100
            WHEN LOWER(issues.aka) = LOWER(:q_clean) THEN 90
            WHEN LOWER(issues.issue_id) LIKE LOWER(:q_prefix) THEN 80
            WHEN LOWER(issues.title) ILIKE LOWER(:q_like) THEN 70
            WHEN LOWER(issues.description) ILIKE LOWER(:q_like) THEN 60
            WHEN LOWER(issues.area) ILIKE LOWER(:q_like)
                 OR LOWER(issues.classification) ILIKE LOWER(:q_like)
                 OR LOWER(issues.domain) ILIKE LOWER(:q_like)
                 OR LOWER(issues.category) ILIKE LOWER(:q_like)
                 OR LOWER(issues.refs) ILIKE LOWER(:q_like)
                 OR LOWER(issues.source) ILIKE LOWER(:q_like)
                 OR LOWER(issues.owner) ILIKE LOWER(:q_like) THEN 50
            ELSE 1
        END
        """
    ).bindparams(q_clean=q_clean, q_prefix=f"{escaped}%", q_like=f"%{escaped}%")


def parse_sort(sort: Optional[str]) -> Optional[Tuple[str, str]]:
    """Parse a sort expression into ``(field, direction)``.

    Accepts ``field``, ``field asc``, ``field desc``, ``field:desc`` and
    ``-field``. Unknown or non-column fields are rejected rather than silently
    ignored, so a typo cannot quietly change the result order.
    """
    if not sort or not sort.strip():
        return None
    raw = sort.strip().replace(":", " ")
    direction = "asc"
    if raw.startswith("-"):
        raw, direction = raw[1:].strip(), "desc"
    parts = raw.split()
    if not parts:
        return None
    field = parts[0].lower()
    if len(parts) > 1:
        direction = "desc" if parts[1].lower().startswith("desc") else "asc"
    if field not in SORTABLE_FIELDS:
        return None
    return field, direction


def _order_terms(field: str, direction: str) -> list:
    """Build the ORDER BY terms for one sort field.

    Columns backed by ``lookup_values`` are ordered by the configured
    ``display_order`` so severity reads CRITICAL, HIGH, MEDIUM, LOW rather than
    alphabetically.
    """
    column = getattr(Issue, field)
    wrap = desc if direction == "desc" else asc

    lookup_type = LOOKUP_BACKED_COLUMNS.get(field)
    if lookup_type:
        ordinal = (
            select(LookupValue.display_order)
            .where(
                LookupValue.lookup_type == lookup_type,
                LookupValue.value == column,
            )
            .scalar_subquery()
        )
        return [nullslast(wrap(ordinal)), nullslast(wrap(column))]
    return [nullslast(wrap(column))]


def apply_sort(query: Query, sort: Optional[str], q: Optional[str] = None) -> Query:
    """Order the query deterministically.

    Relevance leads when a text search is active, then any explicit sort, then
    the unique tiebreaker that makes pagination stable.
    """
    terms = []
    if q:
        terms.append(desc(_score_expression(q)))

    parsed = parse_sort(sort)
    if parsed:
        terms.extend(_order_terms(*parsed))
    elif not q:
        default = parse_sort(DEFAULT_SORT)
        if default:
            terms.extend(_order_terms(*default))

    terms.append(desc(TIEBREAKER))
    return query.order_by(*terms)


def resolve_limit(db: Session, limit: Optional[int] = None) -> int:
    """Return the page size that will actually be applied.

    The single place the limit is decided, so the number a page renders is the
    number the query used.
    """
    if limit is None:
        from issue_hub.issue_service import get_hub_setting
        limit = get_hub_setting(db, "search_default_limit", FALLBACK_LIMIT)
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = FALLBACK_LIMIT
    return max(1, min(limit, MAX_LIMIT))


def query_issues(
    db: Session,
    limit: Optional[int] = None,
    offset: int = 0,
    sort: Optional[str] = None,
    **filters,
) -> Tuple[List[Issue], int]:
    """Filter, sort, and paginate issues. Returns the page and the total count."""
    query = build_issue_query(db, **filters)

    # Counted before ordering: the sort cannot change how many rows match.
    total = query.count()

    query = apply_sort(query, sort, filters.get("q"))
    return query.limit(resolve_limit(db, limit)).offset(max(0, offset)).all(), total
