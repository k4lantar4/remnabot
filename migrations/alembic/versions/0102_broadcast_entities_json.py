"""broadcast_entities_json: preserve Telegram entities on broadcast/pinned

Revision ID: 0102
Revises: 0101
Create Date: 2026-07-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0102'
down_revision: Union[str, None] = '0101'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('broadcast_history', sa.Column('entities_json', sa.Text(), nullable=True))
    op.add_column('pinned_messages', sa.Column('entities_json', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('pinned_messages', 'entities_json')
    op.drop_column('broadcast_history', 'entities_json')
