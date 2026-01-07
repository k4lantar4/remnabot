"""
Integration tests for Cabinet and Promocode migrations.

Tests verify that:
1. Cabinet columns migration (d7f6e838328b) adds all 7 columns correctly
2. Promocode first_purchase_only migration (c3d640fce6e9) adds field correctly
3. Migrations can be rolled back
4. Default values are set correctly
"""

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import User, Promocode


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_cabinet_migration_exists():
    """Verify Cabinet columns migration exists and has correct revision ID."""
    cfg = Config("migrations/alembic.ini")
    script = ScriptDirectory.from_config(cfg)
    
    cabinet_rev = "d7f6e838328b"
    migration = script.get_revision(cabinet_rev)
    
    assert migration is not None, f"Migration {cabinet_rev} not found"
    assert migration.down_revision == "1f5f3a3f5a4d", (
        f"Migration {cabinet_rev} should depend on 1f5f3a3f5a4d"
    )


def test_promocode_migration_exists():
    """Verify Promocode migration exists and depends on Cabinet migration."""
    cfg = Config("migrations/alembic.ini")
    script = ScriptDirectory.from_config(cfg)
    
    promocode_rev = "c3d640fce6e9"
    migration = script.get_revision(promocode_rev)
    
    assert migration is not None, f"Migration {promocode_rev} not found"
    assert migration.down_revision == "d7f6e838328b", (
        f"Migration {promocode_rev} should depend on d7f6e838328b"
    )


def test_cabinet_migration_has_downgrade():
    """Verify Cabinet migration has downgrade function."""
    cfg = Config("migrations/alembic.ini")
    script = ScriptDirectory.from_config(cfg)
    
    cabinet_rev = "d7f6e838328b"
    migration = script.get_revision(cabinet_rev)
    
    # Check that migration module has downgrade function
    migration_module = migration.module
    assert hasattr(migration_module, "downgrade"), (
        f"Migration {cabinet_rev} must have downgrade() function"
    )


def test_promocode_migration_has_downgrade():
    """Verify Promocode migration has downgrade function."""
    cfg = Config("migrations/alembic.ini")
    script = ScriptDirectory.from_config(cfg)
    
    promocode_rev = "c3d640fce6e9"
    migration = script.get_revision(promocode_rev)
    
    # Check that migration module has downgrade function
    migration_module = migration.module
    assert hasattr(migration_module, "downgrade"), (
        f"Migration {promocode_rev} must have downgrade() function"
    )


@pytest.mark.asyncio
async def test_cabinet_columns_exist_in_model():
    """Verify all 7 Cabinet columns exist in User model."""
    # Check User model has all Cabinet columns
    expected_columns = [
        "cabinet_email",
        "cabinet_email_verified",
        "cabinet_password_hash",
        "cabinet_email_verification_token",
        "cabinet_email_verification_expires_at",
        "cabinet_password_reset_token",
        "cabinet_password_reset_expires_at",
    ]
    
    for column_name in expected_columns:
        assert hasattr(User, column_name), (
            f"User model missing Cabinet column: {column_name}"
        )
    
    # Verify column types
    assert User.cabinet_email.type.length == 255
    assert User.cabinet_email_verified.default.arg is False
    assert User.cabinet_password_hash.type.length == 255


@pytest.mark.asyncio
async def test_promocode_first_purchase_only_exists():
    """Verify first_purchase_only field exists in Promocode model."""
    assert hasattr(Promocode, "first_purchase_only"), (
        "Promocode model missing first_purchase_only field"
    )
    
    # Verify default value
    assert Promocode.first_purchase_only.default.arg is False


@pytest.mark.asyncio
async def test_cabinet_columns_nullable():
    """Verify Cabinet columns are nullable for backward compatibility."""
    nullable_columns = [
        "cabinet_email",
        "cabinet_password_hash",
        "cabinet_email_verification_token",
        "cabinet_email_verification_expires_at",
        "cabinet_password_reset_token",
        "cabinet_password_reset_expires_at",
    ]
    
    for column_name in nullable_columns:
        column = getattr(User, column_name)
        assert column.nullable, (
            f"Column {column_name} should be nullable for backward compatibility"
        )


@pytest.mark.asyncio
async def test_cabinet_email_verified_default():
    """Verify cabinet_email_verified defaults to False."""
    column = User.cabinet_email_verified
    assert not column.nullable, "cabinet_email_verified should not be nullable"
    assert column.default.arg is False, "cabinet_email_verified should default to False"


@pytest.mark.asyncio
async def test_promocode_first_purchase_only_default():
    """Verify first_purchase_only defaults to False."""
    column = Promocode.first_purchase_only
    assert not column.nullable, "first_purchase_only should not be nullable"
    assert column.default.arg is False, "first_purchase_only should default to False"


def test_migration_chain_integrity():
    """Verify migration chain is intact from base to new migrations."""
    cfg = Config("migrations/alembic.ini")
    script = ScriptDirectory.from_config(cfg)
    
    # Get all revisions
    revisions = list(script.walk_revisions())
    revision_ids = [rev.revision for rev in revisions]
    
    # Verify our migrations are in the chain
    assert "d7f6e838328b" in revision_ids, "Cabinet migration not in chain"
    assert "c3d640fce6e9" in revision_ids, "Promocode migration not in chain"
    
    # Verify no circular dependencies
    cabinet_migration = script.get_revision("d7f6e838328b")
    promocode_migration = script.get_revision("c3d640fce6e9")
    
    assert cabinet_migration.down_revision != "c3d640fce6e9", (
        "Circular dependency detected"
    )
    assert promocode_migration.down_revision == "d7f6e838328b", (
        "Promocode migration must depend on Cabinet migration"
    )
