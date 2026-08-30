"""create_initial_schema

Revision ID: 35908fccae73
Revises: 
Create Date: 2026-08-29 02:48:56.710547

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '35908fccae73'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create sequence
    op.execute("CREATE SEQUENCE issue_number_seq AS BIGINT")

    # Create tables
    op.create_table('hub_settings',
    sa.Column('setting_key', sa.String(), nullable=False),
    sa.Column('setting_value', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('setting_key')
    )
    op.create_table('issue_history',
    sa.Column('history_id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('issue_id', sa.String(), nullable=False),
    sa.Column('operation', sa.String(), nullable=False),
    sa.Column('changed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('before_record', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('after_record', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('note', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('history_id')
    )
    op.create_table('issues',
    sa.Column('issue_id', sa.String(), nullable=False),
    sa.Column('sequence_number', sa.BigInteger(), nullable=False),
    sa.Column('project', sa.String(), server_default='tessallite', nullable=False),
    sa.Column('repository', sa.String(), nullable=True),
    sa.Column('branch', sa.String(), server_default='main', nullable=False),
    sa.Column('worktree', sa.String(), nullable=True),
    sa.Column('task', sa.String(), nullable=True),
    sa.Column('status', sa.String(), server_default='OPEN', nullable=False),
    sa.Column('severity', sa.String(), nullable=True),
    sa.Column('priority', sa.String(), nullable=True),
    sa.Column('expected_effort', sa.String(), server_default='UNKNOWN', nullable=True),
    sa.Column('title', sa.String(), server_default='', nullable=False),
    sa.Column('description', sa.String(), server_default='', nullable=False),
    sa.Column('area', sa.String(), nullable=True),
    sa.Column('classification', sa.String(), nullable=True),
    sa.Column('domain', sa.String(), nullable=True),
    sa.Column('category', sa.String(), nullable=True),
    sa.Column('refs', sa.String(), nullable=True),
    sa.Column('source', sa.String(), nullable=True),
    sa.Column('aka', sa.String(), nullable=True),
    sa.Column('owner', sa.String(), nullable=True),
    sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('duplicate_of', sa.String(), nullable=True),
    sa.Column('related_to', sa.String(), nullable=True),
    sa.Column('is_retired', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('retire_reason', sa.String(), nullable=True),
    sa.Column('retire_note', sa.String(), nullable=True),
    sa.Column('retired_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('legacy_raw', sa.String(), nullable=True),
    sa.Column('recommended_next_step', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('issue_id'),
    sa.UniqueConstraint('sequence_number')
    )
    op.create_table('lookup_values',
    sa.Column('lookup_type', sa.String(), nullable=False),
    sa.Column('value', sa.String(), nullable=False),
    sa.Column('label', sa.String(), nullable=True),
    sa.Column('display_order', sa.Integer(), server_default='0', nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('is_terminal', sa.Boolean(), nullable=True),
    sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.PrimaryKeyConstraint('lookup_type', 'value')
    )

    # Create indexes as specified in the spec
    op.create_index('issues_sequence_desc_idx', 'issues', [sa.text('sequence_number DESC')])
    op.create_index('issues_status_idx', 'issues', ['status'])
    op.create_index('issues_project_repo_idx', 'issues', ['project', 'repository'])
    op.create_index('issues_updated_desc_idx', 'issues', [sa.text('updated_at DESC')])
    op.create_index('issues_retired_idx', 'issues', ['is_retired'])
    op.create_index('issue_history_issue_idx', 'issue_history', ['issue_id', sa.text('history_id DESC')])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('issue_history_issue_idx')
    op.drop_index('issues_retired_idx')
    op.drop_index('issues_updated_desc_idx')
    op.drop_index('issues_project_repo_idx')
    op.drop_index('issues_status_idx')
    op.drop_index('issues_sequence_desc_idx')

    op.drop_table('lookup_values')
    op.drop_table('issues')
    op.drop_table('issue_history')
    op.drop_table('hub_settings')

    # Drop sequence
    op.execute("DROP SEQUENCE issue_number_seq")
