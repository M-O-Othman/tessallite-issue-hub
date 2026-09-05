"""Pagination arithmetic for the issue list.

Kept apart from the route so the bounds can be tested directly. Every number the
page renders is derived from the limit that was actually applied and the rows
actually returned, never from what the client requested.
"""
from dataclasses import dataclass, field
from typing import List

from issue_hub.ui_config import PAGE_WINDOW


@dataclass
class Page:
    """Resolved pagination state for one rendered page of results."""

    total: int
    limit: int
    offset: int
    count: int

    page: int = 0
    total_pages: int = 0
    pages: List[int] = field(default_factory=list)
    has_prev: bool = False
    has_next: bool = False
    prev_offset: int = 0
    next_offset: int = 0
    first_index: int = 0
    last_index: int = 0

    def offset_for(self, page: int) -> int:
        """Byte-offset of a 1-based page number."""
        return max(0, (page - 1) * self.limit)


def clamp_offset(offset: int, total: int, limit: int) -> int:
    """Snap an out-of-range offset back onto the last page that exists.

    Narrowing a filter can leave the browser asking for page 9 of a 2-page
    result. Rendering an empty table there looks like data loss, so fall back to
    the last real page instead.
    """
    offset = max(0, offset)
    if total <= 0:
        return 0
    if offset >= total:
        return ((total - 1) // limit) * limit
    return offset


def build_page(total: int, limit: int, offset: int, count: int, window: int = PAGE_WINDOW) -> Page:
    """Compute page numbers and bounds for the rendered result set."""
    limit = max(1, limit)
    offset = max(0, offset)

    total_pages = max(1, -(-total // limit)) if total else 0
    page = (offset // limit) + 1 if total else 0

    pages: List[int] = []
    if total_pages:
        half = max(0, window // 2)
        start = max(1, page - half)
        end = min(total_pages, start + window - 1)
        # Keep the window full when it runs off the end of the range.
        start = max(1, end - window + 1)
        pages = list(range(start, end + 1))

    return Page(
        total=total,
        limit=limit,
        offset=offset,
        count=count,
        page=page,
        total_pages=total_pages,
        pages=pages,
        has_prev=offset > 0,
        has_next=offset + count < total,
        prev_offset=max(0, offset - limit),
        next_offset=offset + limit,
        # 1-based inclusive bounds of the rows actually on this page.
        first_index=offset + 1 if count else 0,
        last_index=offset + count,
    )
