"""M4-T3: Alembic 0111 remnawave_id + ORM-boot extras on the remnabot lineage.

Semantics from M3-ID (panel ``users.id`` bigint, not a uuid hash). Extras from
M4-T1 are schema-only on existing tables. This revision must not create
deferred payment/product tables.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

ROOT = Path(__file__).resolve().parents[2]
VERSIONS = ROOT / 'migrations' / 'alembic' / 'versions'
REVISION_FILE = VERSIONS / '0111_remnawave_id_and_boot_extras.py'
FORBIDDEN_TABLES = (
    'cispay_payments',
    'platega_subscriptions',
    'lava_subscriptions',
    'recurrent_payments',
    'coupon_batches',
    'coupons',
    'legal_consents',
    'referral_reward_levels',
    'grace_access_sessions',
)


def _script_directory() -> ScriptDirectory:
    return ScriptDirectory.from_config(Config(str(ROOT / 'alembic.ini')))


def _load_revision():
    spec = importlib.util.spec_from_file_location('rev_0111', REVISION_FILE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_0111_is_the_single_head() -> None:
    heads = _script_directory().get_heads()
    assert heads == ['0111'], heads


def test_0111_revises_grafted_remnabot_0104() -> None:
    rev = _load_revision()
    assert rev.revision == '0111'
    assert rev.down_revision == '0104'


def test_0111_source_does_not_create_deferred_tables() -> None:
    source = REVISION_FILE.read_text(encoding='utf-8')
    for table in FORBIDDEN_TABLES:
        assert f"create_table('{table}'" not in source
        assert f'create_table("{table}"' not in source


def _remnabot_like_schema(conn) -> None:
    statements = (
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            wholesale_discount_bps INTEGER NOT NULL DEFAULT 0,
            business_role VARCHAR(32),
            panel_brand_prefix VARCHAR(64)
        )
        """,
        """
        CREATE TABLE subscriptions (
            id INTEGER PRIMARY KEY,
            remnawave_short_uuid VARCHAR(255),
            user_disabled BOOLEAN NOT NULL DEFAULT 0,
            account_sequence INTEGER,
            panel_username VARCHAR(255),
            purchase_note TEXT
        )
        """,
        'CREATE TABLE payment_method_configs (id INTEGER PRIMARY KEY, method_id VARCHAR(50))',
        'CREATE TABLE tariffs (id INTEGER PRIMARY KEY)',
        'CREATE TABLE promocodes (id INTEGER PRIMARY KEY, code VARCHAR(50), type VARCHAR(50))',
        'CREATE TABLE c2c_receipts (id INTEGER PRIMARY KEY, approved_amount_kopeks INTEGER)',
        'INSERT INTO users (id, wholesale_discount_bps) VALUES (1, 2500)',
        "INSERT INTO subscriptions (id, remnawave_short_uuid, user_disabled) VALUES (1, 'short-1', 0)",
        'INSERT INTO c2c_receipts (id, approved_amount_kopeks) VALUES (1, 100)',
        "INSERT INTO promocodes (id, code, type) VALUES (1, 'ABC', 'balance')",
    )
    for statement in statements:
        conn.execute(text(statement))


def _run_0111(fn_name: str, conn) -> None:
    rev = _load_revision()
    ctx = MigrationContext.configure(conn)
    with Operations.context(ctx):
        getattr(rev, fn_name)()


def test_0111_upgrade_adds_identity_and_boot_extras() -> None:
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        _remnabot_like_schema(conn)
        _run_0111('upgrade', conn)
        inspector = inspect(conn)
        user_cols = {c['name'] for c in inspector.get_columns('users')}
        sub_cols = {c['name'] for c in inspector.get_columns('subscriptions')}
        assert 'remnawave_id' in user_cols
        assert 'referral_days_subscription_id' in user_cols
        assert 'referral_reward_preference' in user_cols
        assert 'wholesale_discount_bps' in user_cols
        assert 'remnawave_id' in sub_cols
        assert 'grace_candidate_at' in sub_cols
        assert 'grace_candidate_reason' in sub_cols
        assert 'grace_suppressed_until' in sub_cols
        assert 'user_disabled' in sub_cols
        assert 'description' in {c['name'] for c in inspector.get_columns('payment_method_configs')}
        assert 'lava_product_id' in {c['name'] for c in inspector.get_columns('tariffs')}
        assert 'traffic_gb' in {c['name'] for c in inspector.get_columns('promocodes')}
        assert 'ix_users_remnawave_id' in {idx['name'] for idx in inspector.get_indexes('users')}
        sub_indexes = {idx['name'] for idx in inspector.get_indexes('subscriptions')}
        assert 'uq_subscriptions_remnawave_id' in sub_indexes
        assert 'ix_subscriptions_remnawave_short_uuid' in sub_indexes
        tables = set(inspector.get_table_names())
        for table in FORBIDDEN_TABLES:
            assert table not in tables
        assert conn.execute(text('SELECT wholesale_discount_bps FROM users WHERE id = 1')).scalar_one() == 2500
        assert conn.execute(text('SELECT approved_amount_kopeks FROM c2c_receipts WHERE id = 1')).scalar_one() == 100
        assert conn.execute(text('SELECT traffic_gb FROM promocodes WHERE id = 1')).scalar_one() == 0


def test_0111_upgrade_is_idempotent() -> None:
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        _remnabot_like_schema(conn)
        _run_0111('upgrade', conn)
        _run_0111('upgrade', conn)
        inspector = inspect(conn)
        assert 'remnawave_id' in {c['name'] for c in inspector.get_columns('users')}


def test_0111_downgrade_round_trip_keeps_protected_columns() -> None:
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        _remnabot_like_schema(conn)
        _run_0111('upgrade', conn)
        _run_0111('downgrade', conn)
        inspector = inspect(conn)
        user_cols = {c['name'] for c in inspector.get_columns('users')}
        sub_cols = {c['name'] for c in inspector.get_columns('subscriptions')}
        assert 'remnawave_id' not in user_cols
        assert 'referral_days_subscription_id' not in user_cols
        assert 'referral_reward_preference' not in user_cols
        assert 'wholesale_discount_bps' in user_cols
        assert 'remnawave_id' not in sub_cols
        assert 'grace_candidate_at' not in sub_cols
        assert 'user_disabled' in sub_cols
        assert 'description' not in {c['name'] for c in inspector.get_columns('payment_method_configs')}
        assert 'lava_product_id' not in {c['name'] for c in inspector.get_columns('tariffs')}
        assert 'traffic_gb' not in {c['name'] for c in inspector.get_columns('promocodes')}
        assert 'c2c_receipts' in inspector.get_table_names()
        assert conn.execute(text('SELECT approved_amount_kopeks FROM c2c_receipts WHERE id = 1')).scalar_one() == 100
        _run_0111('upgrade', conn)
        assert 'remnawave_id' in {c['name'] for c in inspect(conn).get_columns('users')}
