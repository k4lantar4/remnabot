"""add subscription panel_username display cache

Revision ID: 0092
Revises: 0091
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0092'
down_revision: Union[str, None] = '0091'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'subscriptions',
        sa.Column('panel_username', sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('subscriptions', 'panel_username')
