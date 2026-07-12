"""subscriptions: add user_disabled flag for manual user toggle

Revision ID: 0103
Revises: 0102
Create Date: 2026-07-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0103'
down_revision: Union[str, None] = '0102'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'subscriptions',
        sa.Column('user_disabled', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('subscriptions', 'user_disabled')
