"""subscription_public_serial_seq: global purchase serial from 1000

Replaces random hex remnawave_short_id suffixes with a monotonic decimal
serial (1000, 1001, …) allocated via PostgreSQL SEQUENCE.

Revision ID: 0101
Revises: 0100
Create Date: 2026-06-25
"""

from typing import Sequence, Union

from alembic import op

revision: str = '0101'
down_revision: Union[str, None] = '0100'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        'CREATE SEQUENCE IF NOT EXISTS subscription_public_serial_seq '
        'START WITH 1000 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1'
    )


def downgrade() -> None:
    op.execute('DROP SEQUENCE IF EXISTS subscription_public_serial_seq')
