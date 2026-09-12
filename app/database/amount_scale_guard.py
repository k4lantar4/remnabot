"""Startup guard: refuse to serve unless the database declares the Toman amount scale.

Since Toman Phase C the code reads every stored amount as Toman 1:1, and revision ``0115`` is what
put the rows there. A Phase C image on a database that never ran ``0115`` (``SKIP_MIGRATION``, a
restored pre-Phase-C dump) would charge and credit 100x without any error, so startup checks the
declaration instead of trusting the chain: only the latest ``amount_scale_state`` row counts — the
table existing means nothing (``0114`` creates it empty, a downgrade to ``0114`` empties it).

Rollback order and verification queries: ``docs/deploy/phase-c-runbook.md``.
"""

from datetime import UTC, datetime

import sqlalchemy as sa
import structlog
from sqlalchemy import inspect, text

from app.utils.amount_columns import AMOUNT_SCALE_ROUNDING_LOG_TABLE, AMOUNT_SCALE_STATE_TABLE, TOMAN_SCALE


logger = structlog.get_logger(__name__)

#: The revision whose code and data this guard pairs; ``0116`` finished what ``0115`` started.
TOMAN_SCALE_HEAD_REVISION = '0116'

# Same shape as revision 0114 creates. Not in ``app.database.models`` on purpose: they are migration
# bookkeeping, and a fresh database only needs them so the declaration below has somewhere to live.
_metadata = sa.MetaData()
_state_table = sa.Table(
    AMOUNT_SCALE_STATE_TABLE,
    _metadata,
    sa.Column('id', sa.Integer(), primary_key=True),
    sa.Column('scale', sa.String(length=16), nullable=False),
    sa.Column('applied_at', sa.DateTime(timezone=True), nullable=False),
)
sa.Table(
    AMOUNT_SCALE_ROUNDING_LOG_TABLE,
    _metadata,
    sa.Column('id', sa.Integer(), primary_key=True),
    sa.Column('table_name', sa.String(length=64), nullable=False),
    sa.Column('column_name', sa.String(length=64), nullable=False),
    sa.Column('row_id', sa.Integer(), nullable=False),
    sa.Column('before_value', sa.BigInteger(), nullable=False),
)


class AmountScaleMismatchError(RuntimeError):
    """The database does not declare the Toman scale the running code assumes."""


async def _declared_scale(conn) -> str | None:
    has_table = await conn.run_sync(lambda sync_conn: inspect(sync_conn).has_table(AMOUNT_SCALE_STATE_TABLE))
    if not has_table:
        return None
    result = await conn.execute(text(f'SELECT scale FROM {AMOUNT_SCALE_STATE_TABLE} ORDER BY id DESC LIMIT 1'))
    return result.scalar()


async def assert_toman_amount_scale() -> None:
    """Raise :class:`AmountScaleMismatchError` unless the latest declaration is ``toman``."""
    from app.database.database import engine

    async with engine.connect() as conn:
        scale = await _declared_scale(conn)

    if scale == TOMAN_SCALE:
        return

    message = (
        f'Refusing to start: the database declares amount scale {scale!r}, but this code stores and '
        f'reads every amount as {TOMAN_SCALE!r} (Toman Phase C). Serving would charge and credit 100x. '
        f'Run `alembic upgrade head` (Phase C needs revision {TOMAN_SCALE_HEAD_REVISION}) without '
        'SKIP_MIGRATION, or deploy the pre-Phase-C image for this database. '
        'See docs/deploy/phase-c-runbook.md.'
    )
    logger.critical(message, declared_scale=scale, expected_scale=TOMAN_SCALE)
    raise AmountScaleMismatchError(message)


async def declare_toman_scale_on_fresh_db() -> None:
    """Declare the Toman scale on a database created from the models and stamped at head.

    No revision runs on such a database, so nothing else would write the row — yet its amounts are
    Toman by construction, because the only code that can write them is this code. An existing
    declaration is never overridden.
    """
    from app.database.database import engine

    async with engine.begin() as conn:
        await conn.run_sync(_metadata.create_all)
        if await _declared_scale(conn) is None:
            await conn.execute(_state_table.insert().values(scale=TOMAN_SCALE, applied_at=datetime.now(UTC)))
            logger.info('Fresh database declared on the Toman amount scale')
