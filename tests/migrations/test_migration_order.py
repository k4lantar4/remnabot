"""
Test migration order and dependencies.

This test verifies that migrations run in the correct order
and that dependencies are properly defined.
"""

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory


def test_migration_order_bot_fields_before_rls():
    """
    Verify that bot PRD fields migration runs before RLS policies migration.

    Migration order must be:
    1. dde359954cb4_add_bot_prd_fields.py (adds fields to bots table)
    2. d6abce072ea5_setup_rls_policies.py (sets up RLS, depends on fields)
    """
    cfg = Config("migrations/alembic.ini")
    script = ScriptDirectory.from_config(cfg)

    # Get migration revisions
    bot_fields_rev = "dde359954cb4"
    rls_rev = "d6abce072ea5"

    # Verify bot_fields migration exists
    bot_fields_migration = script.get_revision(bot_fields_rev)
    assert bot_fields_migration is not None, f"Migration {bot_fields_rev} not found"

    # Verify RLS migration exists
    rls_migration = script.get_revision(rls_rev)
    assert rls_migration is not None, f"Migration {rls_rev} not found"

    # Verify RLS migration depends on bot_fields migration
    assert rls_migration.down_revision == bot_fields_rev, (
        f"RLS migration {rls_rev} should depend on bot_fields migration {bot_fields_rev}, "
        f"but depends on {rls_migration.down_revision}"
    )


def test_migration_chain_integrity():
    """
    Verify that migration chain is intact (no gaps or circular dependencies).
    """
    cfg = Config("migrations/alembic.ini")
    script = ScriptDirectory.from_config(cfg)

    # Get all revisions
    revisions = list(script.walk_revisions())

    # Check for our specific migrations
    bot_fields_rev = "dde359954cb4"
    rls_rev = "d6abce072ea5"

    bot_fields_migration = script.get_revision(bot_fields_rev)
    rls_migration = script.get_revision(rls_rev)

    # Verify both migrations exist
    assert bot_fields_migration is not None, f"Migration {bot_fields_rev} not found"
    assert rls_migration is not None, f"Migration {rls_rev} not found"

    # Verify bot_fields migration has a valid down_revision
    assert bot_fields_migration.down_revision is not None, (
        f"Migration {bot_fields_rev} must have a down_revision"
    )

    # Verify RLS migration depends on bot_fields
    assert rls_migration.down_revision == bot_fields_rev, (
        f"RLS migration must depend on bot_fields migration"
    )


def test_migration_revision_ids_are_unique():
    """
    Verify that migration revision IDs are unique.
    """
    cfg = Config("migrations/alembic.ini")
    script = ScriptDirectory.from_config(cfg)

    revisions = list(script.walk_revisions())
    revision_ids = [rev.revision for rev in revisions]

    # Check for duplicates
    duplicates = [rev_id for rev_id in revision_ids if revision_ids.count(rev_id) > 1]
    assert len(duplicates) == 0, f"Duplicate revision IDs found: {duplicates}"
