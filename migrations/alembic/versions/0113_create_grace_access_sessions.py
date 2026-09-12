"""0113: create the grace_access_sessions table deferred by the grafted 0111 lineage

Upstream's grace-access feature (restricted access for a short window after a paid subscription
expires or drains its traffic) is compiled into the fork but cannot run: 0111 added the grace
*marker columns* on ``subscriptions`` and deliberately deferred this table, so only databases
built fresh by ``Base.metadata.create_all`` ever had it.

Ported from the table part of upstream ``0097_add_grace_access`` (67d45b6a, fixes in 35206d7b /
PR #3075), adapted to ``GraceAccessSessionModel`` as it stands after upstream
``0104_remnawave_numeric_id``: ``remnawave_uuid`` is nullable (panel 3.0.0 no longer returns a
uuid) and the numeric ``remnawave_id`` is present and indexed.

Deliberately NOT here:
  * ``subscriptions`` — its grace columns and indexes already came with 0111;
  * the ``trg_guard_open_grace_subscription_delete`` trigger — ``_ensure_runtime_schema_guards``
    (app/database/migrations.py) is its single owner and installs it on the next start now that
    the table exists. Two owners would mean duplicate DDL and an ACCESS EXCLUSIVE lock per boot.

Idempotent by inspector guard: a no-op on a fresh DB that ``create_all`` already populated.

Our ``0113`` collides in number with upstream's ``0113_create_tabpay_payments`` — the same
situation as ``0097``–``0112``. Alembic keys on revision *ids*, so this is harmless in our
lineage, but it must be called out in any future upstream migration triage.

Revision ID: 0113
Revises: 0112
Create Date: 2026-09-12
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0113'
down_revision: Union[str, None] = '0112'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = 'grace_access_sessions'
_OPEN_STATES_SQL = "state IN ('pending', 'active', 'restoring')"
_ONE_OPEN_INDEX = 'uq_grace_access_sessions_one_open'
_STATE_UNTIL_INDEX = 'ix_grace_access_sessions_state_until'
_REMNAWAVE_ID_INDEX = 'ix_grace_access_sessions_remnawave_id'


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {str(item['name']) for item in inspector.get_indexes(table_name) if item.get('name')}


def _create_indexes(inspector: sa.Inspector) -> None:
    existing = _index_names(inspector, _TABLE)
    if _ONE_OPEN_INDEX not in existing:
        # Partial: at most one *open* session per subscription. Completed history stays
        # unconstrained, so a subscription may be granted grace again after paying.
        op.create_index(
            _ONE_OPEN_INDEX,
            _TABLE,
            ['subscription_id'],
            unique=True,
            postgresql_where=sa.text(_OPEN_STATES_SQL),
            sqlite_where=sa.text(_OPEN_STATES_SQL),
        )
    if _STATE_UNTIL_INDEX not in existing:
        op.create_index(_STATE_UNTIL_INDEX, _TABLE, ['state', 'grace_until'], unique=False)
    if _REMNAWAVE_ID_INDEX not in existing:
        op.create_index(_REMNAWAVE_ID_INDEX, _TABLE, ['remnawave_id'], unique=False)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _TABLE in inspector.get_table_names():
        # Fresh installs are built by ``create_all`` and already have the table; a partially
        # created one from a manual attempt still gets its missing indexes.
        _create_indexes(inspector)
        return

    op.create_table(
        _TABLE,
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('subscription_id', sa.Integer(), nullable=False),
        # Nullable while the panel identity is backfilled: the column cannot go NOT NULL on a
        # live table, the flip is a separate revision after checking for nulls.
        sa.Column('remnawave_id', sa.BigInteger(), nullable=True),
        # Relaxed to nullable by upstream 0104: panel 3.0.0 does not return a uuid, so new
        # sessions physically cannot fill it. Historical field.
        sa.Column('remnawave_uuid', sa.String(length=255), nullable=True),
        sa.Column('reason', sa.String(length=16), nullable=False),
        sa.Column('incident_key', sa.String(length=255), nullable=False),
        sa.Column('state', sa.String(length=16), nullable=False),
        sa.Column('snapshot_version', sa.Integer(), server_default=sa.text('2'), nullable=False),
        sa.Column('version', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('billing_before', sa.JSON(), nullable=False),
        sa.Column('panel_before', sa.JSON(), nullable=False),
        sa.Column('overlay', sa.JSON(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('grace_until', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completion_reason', sa.String(length=16), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.CheckConstraint(
            "reason IN ('expired', 'limited')",
            name='ck_grace_access_sessions_reason',
        ),
        sa.CheckConstraint(
            "state IN ('pending', 'active', 'restoring', 'completed')",
            name='ck_grace_access_sessions_state',
        ),
        sa.CheckConstraint(
            """
            (
                state = 'completed'
                AND completion_reason IS NOT NULL
                AND completion_reason IN ('paid', 'timeout', 'drained', 'conflict', 'revoked')
                AND completed_at IS NOT NULL
            )
            OR
            (
                state <> 'completed'
                AND completion_reason IS NULL
                AND completed_at IS NULL
            )
            """,
            name='ck_grace_access_sessions_completion',
        ),
        sa.CheckConstraint(
            'grace_until > started_at',
            name='ck_grace_access_sessions_dates',
        ),
        sa.CheckConstraint(
            'snapshot_version > 0',
            name='ck_grace_access_sessions_snapshot_version',
        ),
        sa.CheckConstraint(
            'version > 0',
            name='ck_grace_access_sessions_version',
        ),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        # Never re-grant grace for the same expiry/traffic incident.
        sa.UniqueConstraint(
            'subscription_id',
            'incident_key',
            name='uq_grace_access_sessions_incident',
        ),
    )
    _create_indexes(sa.inspect(bind))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _TABLE not in inspector.get_table_names():
        return

    open_count = bind.execute(
        sa.text(f'SELECT COUNT(*) FROM {_TABLE} WHERE {_OPEN_STATES_SQL}')  # noqa: S608 - no user input
    ).scalar_one()
    if open_count:
        raise RuntimeError(
            'Cannot downgrade while grace-access sessions are open. '
            'Switch to drain, restore/finish every open session, and retry.'
        )

    # The runtime guard reads this table; leaving the trigger behind would make every
    # subscription delete fail until the next boot drops it.
    dialect = bind.dialect.name
    if dialect == 'postgresql':
        op.execute('DROP TRIGGER IF EXISTS trg_guard_open_grace_subscription_delete ON subscriptions')
        op.execute('DROP FUNCTION IF EXISTS guard_open_grace_subscription_delete()')
    elif dialect == 'sqlite':
        op.execute('DROP TRIGGER IF EXISTS trg_guard_open_grace_subscription_delete')

    existing = _index_names(sa.inspect(bind), _TABLE)
    for name in (_REMNAWAVE_ID_INDEX, _STATE_UNTIL_INDEX, _ONE_OPEN_INDEX):
        if name in existing:
            op.drop_index(name, table_name=_TABLE)
    op.drop_table(_TABLE)
