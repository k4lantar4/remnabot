"""merge 0094 c2c and 0095 partner migration heads

Revision ID: 0096
Revises: 0094, 0095
Create Date: 2026-06-18
"""

from typing import Sequence, Union

revision: str = '0096'
down_revision: Union[str, Sequence[str], None] = ('0094', '0095')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
