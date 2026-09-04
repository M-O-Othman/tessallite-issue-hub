"""add_performance_indexes

Revision ID: f1127bbc1194
Revises: 35908fccae73
Create Date: 2026-09-04 01:48:58.874575

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f1127bbc1194'
down_revision: Union[str, Sequence[str], None] = '35908fccae73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema with performance indexes."""
    # GIN index for JSONB tag containment queries (Issue.tags.contains([tag]))
    op.create_index('issues_tags_gin_idx', 'issues', ['tags'], postgresql_using='gin')

    # B-Tree indexes for categorical filter dimensions
    op.create_index('issues_severity_idx', 'issues', ['severity'])
    op.create_index('issues_priority_idx', 'issues', ['priority'])
    op.create_index('issues_domain_idx', 'issues', ['domain'])
    op.create_index('issues_category_idx', 'issues', ['category'])
    op.create_index('issues_owner_idx', 'issues', ['owner'])

    # B-Tree indexes for timestamp range queries (created_from/to, closed_from/to)
    op.create_index('issues_created_at_idx', 'issues', ['created_at'])
    op.create_index('issues_retired_at_idx', 'issues', ['retired_at'])

    # B-Tree index for alternate identity lookups
    op.create_index('issues_aka_idx', 'issues', ['aka'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('issues_aka_idx', table_name='issues')
    op.drop_index('issues_retired_at_idx', table_name='issues')
    op.drop_index('issues_created_at_idx', table_name='issues')
    op.drop_index('issues_owner_idx', table_name='issues')
    op.drop_index('issues_category_idx', table_name='issues')
    op.drop_index('issues_domain_idx', table_name='issues')
    op.drop_index('issues_priority_idx', table_name='issues')
    op.drop_index('issues_severity_idx', table_name='issues')
    op.drop_index('issues_tags_gin_idx', table_name='issues')
