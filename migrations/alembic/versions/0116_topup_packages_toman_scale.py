"""0116: the one catalog column revision 0115 could not see — ``tariffs.traffic_topup_packages``

``0115`` divided every column listed in ``app/utils/amount_columns.py`` by 100. That list is kept
honest by a guard test which only *requires* a column to be classified when its **name** looks like
money (``kopeks|price|amount``). ``traffic_topup_packages`` is a ``{gb: price}`` JSON map whose name
says nothing about money, so nothing forced a decision and the column was left out.

The code that shipped with ``0115`` reads it as Toman regardless: ``admin_tariffs`` multiplies it by
100 for the cabinet's frozen wire scale, and ``subscription_modules/traffic`` charges the stored
number straight from the Toman balance (it used to divide by 100 first). So on a database that has
already run ``0115`` every traffic top-up package is 100x its intended price — shown 100x too big in
the admin tariff editor, and charged 100x too much on purchase.

This revision divides that one column, with the same bookkeeping as ``0115``: it runs only once
(Alembic), it is reversible, and ``0115`` now skips the column (see ``COLUMNS_RESCALED_AFTER_0115``)
so replaying the whole chain on a pre-Phase-C dump still converts it exactly once.

Values are floored per entry, like every other Phase C division, so a package priced at an amount
that is not a multiple of 100 loses the remainder — the same truncation the display layer applied
before Phase C, so no shown price changes.

Revision ID: 0116
Revises: 0115
Create Date: 2026-09-12
"""

from __future__ import annotations

import json
from typing import Any, Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.utils.amount_columns import ColumnRef


revision: str = '0116'
down_revision: Union[str, None] = '0115'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


COLUMN = ColumnRef('tariffs', 'traffic_topup_packages', 'json_values')


def _table() -> sa.TableClause:
    return sa.table(COLUMN.table, sa.column('id', sa.Integer), sa.column(COLUMN.column, sa.JSON))


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


def _rescale(*, divide: bool) -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if COLUMN.table not in tables:
        return

    table = _table()
    rows = bind.execute(sa.text(f'SELECT id, {COLUMN.column} AS value FROM {COLUMN.table}')).fetchall()
    for row in rows:
        if row.value in (None, '', {}, []):
            continue
        scaled = _scaled_payload(row.value, divide=divide)
        bind.execute(table.update().where(table.c.id == row.id).values({COLUMN.column: scaled}))


def upgrade() -> None:
    _rescale(divide=True)


def downgrade() -> None:
    _rescale(divide=False)
