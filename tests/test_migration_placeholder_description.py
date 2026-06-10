from app.handlers.subscription.tariff_purchase import _is_migration_placeholder_description


def test_is_migration_placeholder_description():
    assert _is_migration_placeholder_description('Migration placeholder Basic') is True
    assert _is_migration_placeholder_description('Migration placeholder Premium') is True
    assert _is_migration_placeholder_description(None) is False
    assert _is_migration_placeholder_description('') is False
    assert _is_migration_placeholder_description('Real user-facing description') is False
