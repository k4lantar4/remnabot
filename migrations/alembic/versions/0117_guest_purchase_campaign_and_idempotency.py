"""0117: the two ``guest_purchases`` columns the fork at 0095 left behind

Our Alembic lineage forked from upstream's at 0095 under the same numbers, and upstream's
``0106_guest_purchase_campaign`` / ``0107_guest_purchase_idempotency`` were archived rather than
grafted. The *code* for both columns came in with later upstream syncs: ``GuestPurchase``
(app/database/models.py) maps ``campaign_slug`` and ``idempotency_key``, declares the unique index
``ux_guest_purchases_idempotency_key``, and ``app/cabinet/routes/gift.py`` /
``app/handlers/subscription/gift.py`` read the key to keep a gift purchase from being charged twice.

Because an ORM ``SELECT`` names every mapped column, a migrated database — unlike a fresh install,
which ``create_all`` builds from the model — answers those queries with ``UndefinedColumnError``:
the cabinet dashboard and ``/admin/users`` log a 500 on every load (FINDINGS F-066), and guest/gift
purchases cannot be made idempotent at all.

Both columns are nullable and carry no default, so existing rows keep NULL and the unique index —
which in Postgres does not collide on NULLs — only constrains purchases created from now on.

Ported from upstream ``0106`` and ``0107`` (same column types and index name, one revision here);
the guards are kept so the revision is a no-op on a database that already has them.

Revision ID: 0117
Revises: 0116
Create Date: 2026-09-12
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = '0117'
down_revision: Union[str, None] = '0116'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = 'guest_purchases'
UNIQUE_INDEX = 'ux_guest_purchases_idempotency_key'


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE not in inspector.get_table_names():
        return

    existing_columns = {col['name'] for col in inspector.get_columns(TABLE)}
    if 'campaign_slug' not in existing_columns:
        op.add_column(TABLE, sa.Column('campaign_slug', sa.String(length=64), nullable=True))
    if 'idempotency_key' not in existing_columns:
        op.add_column(TABLE, sa.Column('idempotency_key', sa.String(length=64), nullable=True))

    existing_indexes = {idx['name'] for idx in sa.inspect(bind).get_indexes(TABLE)}
    if UNIQUE_INDEX not in existing_indexes:
        op.create_index(UNIQUE_INDEX, TABLE, ['idempotency_key'], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE not in inspector.get_table_names():
        return

    existing_indexes = {idx['name'] for idx in inspector.get_indexes(TABLE)}
    if UNIQUE_INDEX in existing_indexes:
        op.drop_index(UNIQUE_INDEX, table_name=TABLE)

    existing_columns = {col['name'] for col in sa.inspect(bind).get_columns(TABLE)}
    for column in ('idempotency_key', 'campaign_slug'):
        if column in existing_columns:
            op.drop_column(TABLE, column)
