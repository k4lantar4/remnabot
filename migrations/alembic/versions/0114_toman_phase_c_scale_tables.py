"""0114: Toman Phase C — bookkeeping tables only (no data change)

Phase C is split in two on purpose, so that **every commit on main is restart-safe**. The bot runs
``alembic upgrade head`` at start (``run_alembic_upgrade``), so a revision that rescales stored
amounts must never be reachable before the code that reads Toman is deployed: a restart in between
would leave divided data under catalog-scale code and every price would render 100x too small.

This revision is the structural half and changes no amount at all, so it is safe to apply alone, at
any time. The data half — dividing the catalog columns by 100, logging the rows that lose precision
and declaring the new scale — is revision ``0115``, which ships with the Phase C code (plan Task 3).

**The presence of these two tables means nothing.** Only a ``toman`` row in ``amount_scale_state``
(written by ``0115``) says the database is on the Toman scale; the startup guard of plan Task 6
reads that row, never the table.

Revision ID: 0114
Revises: 0113
Create Date: 2026-09-12
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.utils.amount_columns import AMOUNT_SCALE_ROUNDING_LOG_TABLE, AMOUNT_SCALE_STATE_TABLE


revision: str = '0114'
down_revision: Union[str, None] = '0113'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())

    if AMOUNT_SCALE_STATE_TABLE not in tables:
        op.create_table(
            AMOUNT_SCALE_STATE_TABLE,
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('scale', sa.String(length=16), nullable=False),
            sa.Column('applied_at', sa.DateTime(timezone=True), nullable=False),
        )

    if AMOUNT_SCALE_ROUNDING_LOG_TABLE not in tables:
        op.create_table(
            AMOUNT_SCALE_ROUNDING_LOG_TABLE,
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('table_name', sa.String(length=64), nullable=False),
            sa.Column('column_name', sa.String(length=64), nullable=False),
            sa.Column('row_id', sa.Integer(), nullable=False),
            sa.Column('before_value', sa.BigInteger(), nullable=False),
        )


def downgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())

    if AMOUNT_SCALE_ROUNDING_LOG_TABLE in tables:
        op.drop_table(AMOUNT_SCALE_ROUNDING_LOG_TABLE)
    if AMOUNT_SCALE_STATE_TABLE in tables:
        op.drop_table(AMOUNT_SCALE_STATE_TABLE)
