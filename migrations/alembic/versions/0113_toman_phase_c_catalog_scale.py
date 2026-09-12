"""0113: Toman Phase C — store catalog amounts in Toman 1:1

Balances have been stored in Toman 1:1 since Phase B, while catalog prices stayed on the x100
``price_kopeks`` scale. Every hop that mixed the two produced the same 100x bug over and over
(remnabot #32…#56). This revision moves the catalog columns onto the balance scale, so the whole
database speaks one unit and the conversion helpers can be deleted (plan Task 3).

Which columns are catalog, which are already Toman and which belong to a payment provider's own
currency is decided once, in ``app/utils/amount_columns.py``, and guarded by
``tests/utils/test_amount_columns.py``.

Division truncates toward zero, exactly what the display layer already does, so no user-visible
number changes. The few rows that are not divisible by 100 keep their pre-image in
``amount_scale_rounding_log`` so ``downgrade()`` restores them byte-for-byte.

Pre-Phase-B (ruble-era) rows must be *converted*, not silently divided (user decision 2026-09-12),
and converting them needs a ruble→Toman rate, which is a business number nobody has given yet.
So the upgrade refuses to run while such rows exist instead of guessing.

Revision ID: 0113
Revises: 0112
Create Date: 2026-09-12
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.utils.amount_columns import CATALOG_SCALE_COLUMNS, ColumnRef


revision: str = '0113'
down_revision: Union[str, None] = '0112'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SCALE_STATE_TABLE = 'amount_scale_state'
ROUNDING_LOG_TABLE = 'amount_scale_rounding_log'
TOMAN_SCALE = 'toman'

#: Mirrors ``settings.BALANCE_TOMAN_CUTOFF_UTC``; kept as a literal so the revision imports no
#: configuration. ``tests/database/test_0113_catalog_scale.py`` pins the two together.
PRE_TOMAN_CUTOFF_UTC = datetime(2026, 6, 5, tzinfo=UTC)

#: Tables whose rows would be ruble-era if they predate the cutoff.
PRE_CUTOFF_GUARD_TABLES: tuple[tuple[str, str], ...] = (
    ('transactions', 'created_at'),
    ('users', 'created_at'),
)

_state_table = sa.table(
    SCALE_STATE_TABLE,
    sa.column('scale', sa.String),
    sa.column('applied_at', sa.DateTime(timezone=True)),
)

_log_table = sa.table(
    ROUNDING_LOG_TABLE,
    sa.column('table_name', sa.String),
    sa.column('column_name', sa.String),
    sa.column('row_id', sa.Integer),
    sa.column('before_value', sa.BigInteger),
)


def _json_table(ref: ColumnRef) -> sa.TableClause:
    return sa.table(ref.table, sa.column('id', sa.Integer), sa.column(ref.column, sa.JSON))


def _present_columns(inspector: sa.Inspector, tables: set[str], ref: ColumnRef) -> bool:
    if ref.table not in tables:
        return False
    return ref.column in {col['name'] for col in inspector.get_columns(ref.table)}


def _row_filter(ref: ColumnRef) -> str:
    return f' AND ({ref.where})' if ref.where else ''


def _guard_pre_cutoff_rows(bind: sa.engine.Connection, tables: set[str]) -> None:
    offenders: dict[str, int] = {}
    cutoff = sa.bindparam('cutoff', PRE_TOMAN_CUTOFF_UTC, type_=sa.DateTime(timezone=True))
    for table, column in PRE_CUTOFF_GUARD_TABLES:
        if table not in tables:
            continue
        statement = sa.text(f'SELECT count(*) FROM {table} WHERE {column} < :cutoff').bindparams(cutoff)
        count = bind.execute(statement).scalar() or 0
        if count:
            offenders[table] = int(count)

    if offenders:
        raise RuntimeError(
            'Toman Phase C (revision 0113) refuses to run: this database still holds rows from '
            f'before {PRE_TOMAN_CUTOFF_UTC.isoformat()} ({offenders}), i.e. pre-Phase-B amounts '
            'that are neither catalog kopeks nor Toman. They must be converted with a '
            'ruble-to-Toman rate, which is a business number that has to be supplied before this '
            'migration can run. See docs/superpowers/plans/2026-09-11-toman-phase-c.md, decision 2.'
        )


def _log_lossy_rows(bind: sa.engine.Connection, ref: ColumnRef) -> None:
    """Remember values that are not divisible by 100, so the downgrade can restore them exactly."""
    rows = bind.execute(
        sa.text(
            f'SELECT id, {ref.column} AS value FROM {ref.table} '
            f'WHERE {ref.column} IS NOT NULL AND {ref.column} % 100 <> 0{_row_filter(ref)}'
        )
    ).fetchall()
    if not rows:
        return
    bind.execute(
        _log_table.insert(),
        [
            {
                'table_name': ref.table,
                'column_name': ref.column,
                'row_id': int(row.id),
                'before_value': int(row.value),
            }
            for row in rows
        ],
    )


def _rescale_int_column(bind: sa.engine.Connection, ref: ColumnRef, *, divide: bool) -> None:
    operator = '/' if divide else '*'
    bind.execute(
        sa.text(
            f'UPDATE {ref.table} SET {ref.column} = {ref.column} {operator} 100 '
            f'WHERE {ref.column} IS NOT NULL{_row_filter(ref)}'
        )
    )


def _scaled_number(value: Any, *, divide: bool) -> Any:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return value
    try:
        number = int(value)
    except (TypeError, ValueError):
        return value
    sign = -1 if number < 0 else 1
    magnitude = abs(number) // 100 if divide else abs(number) * 100
    return sign * magnitude


def _scaled_payload(payload: Any, *, divide: bool) -> Any:
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (TypeError, ValueError):
            return payload
    if isinstance(payload, dict):
        return {key: _scaled_number(value, divide=divide) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_scaled_number(value, divide=divide) for value in payload]
    return payload


def _rescale_json_column(bind: sa.engine.Connection, ref: ColumnRef, *, divide: bool) -> None:
    table = _json_table(ref)
    rows = bind.execute(sa.text(f'SELECT id, {ref.column} AS value FROM {ref.table}')).fetchall()
    for row in rows:
        if row.value in (None, '', {}, []):
            continue
        scaled = _scaled_payload(row.value, divide=divide)
        bind.execute(table.update().where(table.c.id == row.id).values({ref.column: scaled}))


def _rescale_all(bind: sa.engine.Connection, tables: set[str], *, divide: bool) -> None:
    inspector = sa.inspect(bind)
    for ref in CATALOG_SCALE_COLUMNS:
        if not _present_columns(inspector, tables, ref):
            continue
        if ref.kind == 'json_values':
            _rescale_json_column(bind, ref, divide=divide)
        else:
            if divide:
                _log_lossy_rows(bind, ref)
            _rescale_int_column(bind, ref, divide=divide)


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if SCALE_STATE_TABLE in tables:
        # Already on the Toman scale — never divide twice.
        return

    _guard_pre_cutoff_rows(bind, tables)

    op.create_table(
        SCALE_STATE_TABLE,
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('scale', sa.String(length=16), nullable=False),
        sa.Column('applied_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        ROUNDING_LOG_TABLE,
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('table_name', sa.String(length=64), nullable=False),
        sa.Column('column_name', sa.String(length=64), nullable=False),
        sa.Column('row_id', sa.Integer(), nullable=False),
        sa.Column('before_value', sa.BigInteger(), nullable=False),
    )

    _rescale_all(bind, tables, divide=True)

    bind.execute(_state_table.insert().values(scale=TOMAN_SCALE, applied_at=datetime.now(UTC)))


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if SCALE_STATE_TABLE not in tables:
        return

    _rescale_all(bind, tables, divide=False)

    if ROUNDING_LOG_TABLE in tables:
        logged = bind.execute(
            sa.text(f'SELECT table_name, column_name, row_id, before_value FROM {ROUNDING_LOG_TABLE}')
        ).fetchall()
        for entry in logged:
            bind.execute(
                sa.text(f'UPDATE {entry.table_name} SET {entry.column_name} = :value WHERE id = :row_id').bindparams(
                    value=int(entry.before_value), row_id=int(entry.row_id)
                )
            )
        op.drop_table(ROUNDING_LOG_TABLE)

    op.drop_table(SCALE_STATE_TABLE)
