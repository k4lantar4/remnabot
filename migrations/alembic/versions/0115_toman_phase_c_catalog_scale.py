"""0115: Toman Phase C — store catalog amounts in Toman 1:1

Balances have been stored in Toman 1:1 since Phase B, while catalog prices stayed on the x100
``price_kopeks`` scale. Every hop that mixed the two produced the same 100x bug over and over
(remnabot #32…#56). This revision moves the catalog columns onto the balance scale, so the whole
database speaks one unit and the conversion helpers can be deleted.

**Staged, not yet in the chain.** This file deliberately lives in ``migrations/phase_c/`` and not in
``migrations/alembic/versions/``: Alembic only scans the latter, and the bot runs
``alembic upgrade head`` at start, so a data revision sitting in ``versions/`` would be applied by
the next restart no matter what the code does. Plan Task 3 ships it with a single

    git mv migrations/phase_c/0115_toman_phase_c_catalog_scale.py migrations/alembic/versions/

in the same commit as the code that reads Toman. Until then it is fully reviewed and exercised by
``tests/database/test_0115_catalog_scale.py`` (SQLite round-trip) while being unreachable in
production. The structural tables it fills were created separately by ``0114``, which is safe alone.

Which columns are catalog, which are already Toman and which belong to a payment provider's own
currency is decided once, in ``app/utils/amount_columns.py``, and guarded by
``tests/utils/test_amount_columns.py``.

Division keeps the sign and floors the magnitude, exactly what the display layer already does, so no
user-visible number changes. The few rows that are not divisible by 100 keep their pre-image in
``amount_scale_rounding_log`` so ``downgrade()`` restores them byte-for-byte.

Pre-Phase-B (ruble-era) rows must be *converted*, not silently divided (user decision 2026-09-12),
and converting them needs a ruble→Toman rate, which is a business number nobody has given yet.
So the upgrade refuses to run while such rows exist instead of guessing.

Revision ID: 0115
Revises: 0114
Create Date: 2026-09-12
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.utils.amount_columns import (
    AMOUNT_SCALE_ROUNDING_LOG_TABLE,
    AMOUNT_SCALE_STATE_TABLE,
    CATALOG_SCALE_COLUMNS,
    COLUMNS_RESCALED_AFTER_0115,
    TOMAN_SCALE,
    ColumnRef,
)


revision: str = '0115'
down_revision: Union[str, None] = '0114'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


#: Mirrors ``settings.BALANCE_TOMAN_CUTOFF_UTC``; kept as a literal so the revision imports no
#: configuration. ``tests/database/test_0115_catalog_scale.py`` pins the two together.
PRE_TOMAN_CUTOFF_UTC = datetime(2026, 6, 5, tzinfo=UTC)

#: Tables whose rows would be ruble-era if they predate the cutoff.
PRE_CUTOFF_GUARD_TABLES: tuple[tuple[str, str], ...] = (
    ('transactions', 'created_at'),
    ('users', 'created_at'),
)

_state_table = sa.table(
    AMOUNT_SCALE_STATE_TABLE,
    sa.column('scale', sa.String),
    sa.column('applied_at', sa.DateTime(timezone=True)),
)

_log_table = sa.table(
    AMOUNT_SCALE_ROUNDING_LOG_TABLE,
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


def _already_on_toman_scale(bind: sa.engine.Connection, tables: set[str]) -> bool:
    if AMOUNT_SCALE_STATE_TABLE not in tables:
        return False
    current = bind.execute(sa.text(f'SELECT scale FROM {AMOUNT_SCALE_STATE_TABLE} ORDER BY id DESC LIMIT 1')).scalar()
    return current == TOMAN_SCALE


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
            'Toman Phase C (revision 0115) refuses to run: this database still holds rows from '
            f'before {PRE_TOMAN_CUTOFF_UTC.isoformat()} ({offenders}), i.e. pre-Phase-B amounts '
            'that are neither catalog kopeks nor Toman. They must be converted with a '
            'ruble-to-Toman rate, which is a business number that has to be supplied before this '
            'migration can run. See docs/superpowers/plans/done/2026-09-11-toman-phase-c.md, decision 2.'
        )


def _ensure_bookkeeping_tables(tables: set[str]) -> None:
    """0114 creates these; recreate them defensively if a database arrives without them."""
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
        if (ref.table, ref.column) in COLUMNS_RESCALED_AFTER_0115:
            # Classified as catalog only after this revision had shipped, so a later revision owns
            # it. Skipping it here is what keeps a replay of the chain from dividing it twice.
            continue
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

    if _already_on_toman_scale(bind, tables):
        # Never divide twice.
        return

    _guard_pre_cutoff_rows(bind, tables)
    _ensure_bookkeeping_tables(tables)

    _rescale_all(bind, tables, divide=True)

    bind.execute(_state_table.insert().values(scale=TOMAN_SCALE, applied_at=datetime.now(UTC)))


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if not _already_on_toman_scale(bind, tables):
        return

    _rescale_all(bind, tables, divide=False)

    if AMOUNT_SCALE_ROUNDING_LOG_TABLE in tables:
        logged = bind.execute(
            sa.text(f'SELECT table_name, column_name, row_id, before_value FROM {AMOUNT_SCALE_ROUNDING_LOG_TABLE}')
        ).fetchall()
        for entry in logged:
            bind.execute(
                sa.text(f'UPDATE {entry.table_name} SET {entry.column_name} = :value WHERE id = :row_id').bindparams(
                    value=int(entry.before_value), row_id=int(entry.row_id)
                )
            )
        bind.execute(sa.text(f'DELETE FROM {AMOUNT_SCALE_ROUNDING_LOG_TABLE}'))

    # The tables themselves belong to 0114; only the declaration of the new scale is undone here.
    bind.execute(sa.text(f'DELETE FROM {AMOUNT_SCALE_STATE_TABLE}'))
