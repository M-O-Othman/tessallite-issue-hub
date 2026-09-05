"""add_performance_indexes

Revision ID: f1127bbc1194
Revises: 35908fccae73
Create Date: 2026-09-04 01:48:58.874575

Written to be idempotent. On a large, live database these indexes are built
out-of-band with CREATE INDEX CONCURRENTLY to avoid holding a write lock, which
leaves them already present when this migration later runs; `IF NOT EXISTS`
makes that converge instead of aborting the whole upgrade.

No index is created on `issues.aka`. A B-Tree on that column cannot serve any
query the application issues against it -- search.py filters with a `~*` regex
and a leading-wildcard `ILIKE '%q%'`, and ranks with `LOWER(aka) = LOWER(q)`,
none of which a raw B-Tree can satisfy. It is also not creatable in every
environment: legacy-import records carry `aka` values far beyond the 2704-byte
B-Tree row limit (see Docs/known_issues.md).
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f1127bbc1194'
down_revision: Union[str, Sequence[str], None] = '35908fccae73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (index name, index definition) pairs.
INDEXES = [
    # GIN index for JSONB tag containment queries (Issue.tags.contains([tag])).
    ("issues_tags_gin_idx", "USING gin (tags)"),
    # B-Tree indexes for categorical filter dimensions.
    ("issues_severity_idx", "(severity)"),
    ("issues_priority_idx", "(priority)"),
    ("issues_domain_idx", "(domain)"),
    ("issues_category_idx", "(category)"),
    ("issues_owner_idx", "(owner)"),
    # B-Tree indexes for timestamp range queries.
    ("issues_created_at_idx", "(created_at)"),
    ("issues_retired_at_idx", "(retired_at)"),
]


def upgrade() -> None:
    """Add performance indexes, skipping any that already exist."""
    for name, definition in INDEXES:
        op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON issues {definition}")


def downgrade() -> None:
    """Remove the performance indexes."""
    for name, _ in reversed(INDEXES):
        op.execute(f"DROP INDEX IF EXISTS {name}")
