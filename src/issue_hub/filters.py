"""Shared issue filter parameters.

The REST API, the issue list page, and the analytics page all bind to the same
dependency, so their filter surfaces cannot drift apart. Canonical parameter
names are the API's (``created_from``/``created_to``); the historical web
spellings (``created_after``/``created_before``) are accepted as aliases so
existing bookmarks keep working.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from fastapi import Query

from issue_hub.ui_config import (
    DATE_DISPLAY_FORMAT,
    DATE_INPUT_FORMATS,
    MAX_LIMIT,
)

# Filter fields that accept multiple values.
MULTI_FIELDS = (
    "project", "repository", "status", "severity",
    "priority", "expected_effort", "domain", "category",
)

# Filter fields that accept a single value.
SCALAR_FIELDS = (
    "id", "q", "branch", "worktree", "task",
    "area", "classification", "owner", "tag",
)

# Tri-state fields: None, True, or False.
BOOL_FIELDS = ("is_retired", "is_terminal")

# Date-range fields, mapped to the alias accepted for backwards compatibility.
DATE_FIELDS = {
    "created_from": "created_after",
    "created_to": "created_before",
    "updated_from": "updated_after",
    "updated_to": "updated_before",
    "closed_from": "closed_after",
    "closed_to": "closed_before",
}


def split_values(values: Optional[List[str]]) -> Optional[List[str]]:
    """Normalise a repeated query parameter, splitting comma-separated entries.

    Applied identically for the API and the web UI so ``?status=OPEN,FIXED`` and
    ``?status=OPEN&status=FIXED`` behave the same everywhere.
    """
    if not values:
        return None
    out: List[str] = []
    for raw in values:
        if not raw:
            continue
        for part in raw.split(","):
            cleaned = part.strip()
            if cleaned and cleaned not in out:
                out.append(cleaned)
    return out or None


def clean(value: Optional[str]) -> Optional[str]:
    """Trim a scalar parameter, treating blank input as absent."""
    return value.strip() if value and value.strip() else None


def parse_date(value: Optional[str], end_of_day: bool = False) -> Optional[datetime]:
    """Parse a user- or API-supplied date.

    Accepts ISO 8601 (with or without a time component) and every format in
    ``date_input_formats``. A date without a time used as a range upper bound is
    widened to the end of that day, so ``closed_to=31-12-2026`` includes items
    closed during that day rather than only at midnight.
    """
    raw = clean(value)
    if not raw:
        return None

    parsed: Optional[datetime] = None
    has_time = ":" in raw
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        for fmt in DATE_INPUT_FORMATS:
            try:
                parsed = datetime.strptime(raw, fmt)
                break
            except ValueError:
                continue

    if parsed is None:
        return None
    if end_of_day and not has_time:
        return parsed.replace(hour=23, minute=59, second=59, microsecond=999999)
    return parsed


def parse_tristate(value: Optional[str]) -> Optional[bool]:
    """Parse a tri-state flag. Anything unrecognised means 'no opinion'."""
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized in ("true", "1", "yes"):
        return True
    if normalized in ("false", "0", "no"):
        return False
    return None


@dataclass
class IssueFilterParams:
    """One resolved filter set, shared by the API, issue list, and analytics."""

    values: Dict[str, Any] = field(default_factory=dict)
    dates: Dict[str, Optional[datetime]] = field(default_factory=dict)
    sort: Optional[str] = None
    limit: Optional[int] = None
    offset: int = 0

    def to_query_kwargs(self) -> Dict[str, Any]:
        """Build the keyword arguments accepted by ``search.build_issue_query``."""
        kwargs: Dict[str, Any] = {
            "id_": self.values.get("id"),
            **{name: self.values.get(name) for name in MULTI_FIELDS},
            **{name: self.values.get(name) for name in SCALAR_FIELDS if name != "id"},
            **{name: self.values.get(name) for name in BOOL_FIELDS},
            **{name: self.dates.get(name) for name in DATE_FIELDS},
        }
        return kwargs

    def display(self, name: str) -> str:
        """Render a filter value for redisplay in a form field."""
        if name in self.dates:
            value = self.dates.get(name)
            return value.strftime(DATE_DISPLAY_FORMAT) if value else ""
        value = self.values.get(name)
        if value is None:
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    def selected(self, name: str) -> List[str]:
        """Return the selected values of a multi-value filter."""
        return list(self.values.get(name) or [])

    def as_params(self) -> List[tuple]:
        """Flatten the active filters into canonical query-string pairs."""
        pairs: List[tuple] = []
        for name in MULTI_FIELDS:
            for item in self.values.get(name) or []:
                pairs.append((name, item))
        for name in SCALAR_FIELDS:
            value = self.values.get(name)
            if value:
                pairs.append((name, value))
        for name in BOOL_FIELDS:
            value = self.values.get(name)
            if value is not None:
                pairs.append((name, "true" if value else "false"))
        for name in DATE_FIELDS:
            value = self.dates.get(name)
            if value:
                pairs.append((name, value.strftime(DATE_DISPLAY_FORMAT)))
        return pairs

    def query_string(self, **overrides: Any) -> str:
        """Build a URL query string preserving every active filter.

        Used by sortable column headers and pagination links so navigating never
        silently drops the user's filters. ``None`` in ``overrides`` removes a
        parameter.
        """
        pairs = [(k, v) for k, v in self.as_params() if k not in overrides]
        for key in ("sort", "limit", "offset"):
            if key in overrides:
                continue
            value = getattr(self, key)
            if key == "offset" and not value:
                continue
            if value is not None:
                pairs.append((key, value))
        for key, value in overrides.items():
            if value is None:
                continue
            if isinstance(value, (list, tuple)):
                pairs.extend((key, item) for item in value)
            else:
                pairs.append((key, value))
        return urlencode(pairs)


def issue_filters(
    id: Optional[str] = Query(None, description="Exact issue ID(s), comma-separated"),
    q: Optional[str] = Query(None, description="Free-text search across all fields"),
    project: Optional[List[str]] = Query(None),
    repository: Optional[List[str]] = Query(None),
    status: Optional[List[str]] = Query(None),
    severity: Optional[List[str]] = Query(None),
    priority: Optional[List[str]] = Query(None),
    expected_effort: Optional[List[str]] = Query(None),
    domain: Optional[List[str]] = Query(None),
    category: Optional[List[str]] = Query(None),
    branch: Optional[str] = Query(None),
    worktree: Optional[str] = Query(None),
    task: Optional[str] = Query(None),
    area: Optional[str] = Query(None),
    classification: Optional[str] = Query(None),
    owner: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    is_retired: Optional[str] = Query(None),
    is_terminal: Optional[str] = Query(None),
    created_from: Optional[str] = Query(None),
    created_to: Optional[str] = Query(None),
    updated_from: Optional[str] = Query(None),
    updated_to: Optional[str] = Query(None),
    closed_from: Optional[str] = Query(None),
    closed_to: Optional[str] = Query(None),
    created_after: Optional[str] = Query(None, include_in_schema=False),
    created_before: Optional[str] = Query(None, include_in_schema=False),
    updated_after: Optional[str] = Query(None, include_in_schema=False),
    updated_before: Optional[str] = Query(None, include_in_schema=False),
    closed_after: Optional[str] = Query(None, include_in_schema=False),
    closed_before: Optional[str] = Query(None, include_in_schema=False),
    sort: Optional[str] = Query(None, description="Sort as '<field> [asc|desc]'"),
    limit: Optional[int] = Query(None, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
) -> IssueFilterParams:
    """FastAPI dependency resolving the shared issue filter surface."""
    local = locals()

    values: Dict[str, Any] = {}
    for name in MULTI_FIELDS:
        values[name] = split_values(local[name])
    for name in SCALAR_FIELDS:
        values[name] = clean(local[name])
    for name in BOOL_FIELDS:
        values[name] = parse_tristate(local[name])

    dates: Dict[str, Optional[datetime]] = {}
    for canonical, alias in DATE_FIELDS.items():
        supplied = local[canonical] if clean(local[canonical]) else local[alias]
        dates[canonical] = parse_date(supplied, end_of_day=canonical.endswith("_to"))

    return IssueFilterParams(
        values=values,
        dates=dates,
        sort=clean(sort),
        limit=limit,
        offset=offset,
    )
