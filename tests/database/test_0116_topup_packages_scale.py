"""0116 rescales the one catalog column 0115 could not see, and does it exactly once.

The risk this file guards is not the division itself but double division: ``tariffs.
traffic_topup_packages`` now sits in ``CATALOG_SCALE_COLUMNS``, which ``0115`` iterates over, so
without the ``COLUMNS_RESCALED_AFTER_0115`` skip a replay of the chain on a pre-Phase-C dump would
divide it in 0115 *and* in 0116 and leave every package priced at 1/100 of its real value.
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import sqlalchemy as sa
from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from app.utils.amount_columns import CATALOG_SCALE_COLUMNS, COLUMNS_RESCALED_AFTER_0115


ROOT = Path(__file__).resolve().parents[2]
VERSIONS = ROOT / 'migrations' / 'alembic' / 'versions'
REVISION_FILE = VERSIONS / '0116_topup_packages_toman_scale.py'
PHASE_C_FILE = VERSIONS / '0115_toman_phase_c_catalog_scale.py'
TABLES_FILE = VERSIONS / '0114_toman_phase_c_scale_tables.py'

AFTER_CUTOFF = datetime(2026, 8, 1, tzinfo=UTC)

# 10 GB for 30,000 Toman and 50 GB for 150,000 Toman, on the pre-Phase-C x100 scale.
PACKAGES_X100 = {'10': 3_000_000, '50': 15_000_000}
PACKAGES_TOMAN = {'10': 30_000, '50': 150_000}


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_metadata = sa.MetaData()

_tariffs = sa.Table(
    'tariffs',
    _metadata,
    sa.Column('id', sa.Integer, primary_key=True),
    sa.Column('traffic_topup_packages', sa.JSON),
    sa.Column('period_prices', sa.JSON),
    sa.Column('device_price_kopeks', sa.Integer),
    sa.Column('traffic_price_per_gb_kopeks', sa.Integer),
    sa.Column('daily_price_kopeks', sa.Integer),
    sa.Column('price_per_day_kopeks', sa.Integer),
)
_users = sa.Table(
    'users',
    _metadata,
    sa.Column('id', sa.Integer, primary_key=True),
    sa.Column('balance_kopeks', sa.Integer),
    sa.Column('auto_promo_group_threshold_kopeks', sa.BigInteger),
    sa.Column('created_at', sa.DateTime(timezone=True)),
)


def _seeded_connection():
    engine = create_engine('sqlite:///:memory:')
    conn = engine.connect()
    _metadata.create_all(conn)
    conn.execute(
        _tariffs.insert(),
        [
            {
                'id': 1,
                'traffic_topup_packages': PACKAGES_X100,
                'period_prices': {'30': 5_000_000},
                'device_price_kopeks': 100_000,
                'traffic_price_per_gb_kopeks': 700_000,
                'daily_price_kopeks': 0,
                'price_per_day_kopeks': 0,
            },
            {
                'id': 2,
                'traffic_topup_packages': {},
                'period_prices': {},
                'device_price_kopeks': 0,
                'traffic_price_per_gb_kopeks': 0,
                'daily_price_kopeks': 0,
                'price_per_day_kopeks': 0,
            },
        ],
    )
    conn.execute(
        _users.insert(),
        [{'id': 1, 'balance_kopeks': 250_000, 'auto_promo_group_threshold_kopeks': None, 'created_at': AFTER_CUTOFF}],
    )
    conn.commit()
    return conn


def _run(conn, module, direction: str) -> None:
    ctx = MigrationContext.configure(conn)
    with Operations.context(ctx):
        getattr(module, direction)()
    conn.commit()


def _packages(conn, tariff_id: int):
    raw = conn.execute(text('SELECT traffic_topup_packages FROM tariffs WHERE id = :i').bindparams(i=tariff_id))
    return _load('rev_0116', REVISION_FILE)._scaled_payload(raw.scalar(), divide=False)


def _value(conn, tariff_id: int, gb: str) -> int:
    return _packages(conn, tariff_id)[gb] // 100


# ── chain ─────────────────────────────────────────────────────────────────────


def test_0116_is_the_head_and_follows_0115() -> None:
    rev = _load('rev_0116', REVISION_FILE)
    assert rev.revision == '0116'
    assert rev.down_revision == '0115'

    script = ScriptDirectory.from_config(Config(str(ROOT / 'alembic.ini')))
    assert script.get_heads() == ['0117']


def test_the_column_is_classified_as_catalog_and_owned_by_this_revision() -> None:
    key = ('tariffs', 'traffic_topup_packages')
    assert key in {(ref.table, ref.column) for ref in CATALOG_SCALE_COLUMNS}
    assert key in COLUMNS_RESCALED_AFTER_0115


# ── data ──────────────────────────────────────────────────────────────────────


def test_upgrade_divides_every_package_price() -> None:
    conn = _seeded_connection()
    _run(conn, _load('rev_0116', REVISION_FILE), 'upgrade')

    assert _value(conn, 1, '10') == PACKAGES_TOMAN['10']
    assert _value(conn, 1, '50') == PACKAGES_TOMAN['50']


def test_upgrade_leaves_an_empty_map_alone() -> None:
    conn = _seeded_connection()
    _run(conn, _load('rev_0116', REVISION_FILE), 'upgrade')

    assert _packages(conn, 2) == {}


def test_round_trip_restores_the_original_prices() -> None:
    conn = _seeded_connection()
    module = _load('rev_0116', REVISION_FILE)
    _run(conn, module, 'upgrade')
    _run(conn, module, 'downgrade')

    assert _packages(conn, 1) == {gb: price * 100 for gb, price in PACKAGES_X100.items()}


def test_replaying_the_whole_chain_divides_the_column_exactly_once() -> None:
    """0115 must skip the column it never knew about, or a dump replay lands on 1/100."""
    conn = _seeded_connection()
    for name, path in (('rev_0114', TABLES_FILE), ('rev_0115', PHASE_C_FILE), ('rev_0116', REVISION_FILE)):
        _run(conn, _load(name, path), 'upgrade')

    assert _value(conn, 1, '10') == PACKAGES_TOMAN['10']
    # the columns 0115 does own are still divided exactly once
    assert conn.execute(text('SELECT device_price_kopeks FROM tariffs WHERE id = 1')).scalar() == 1_000
