"""
Integration tests for Row Level Security (RLS) policies.

These tests verify that RLS policies correctly isolate tenant data.
IMPORTANT: These tests require a real PostgreSQL database with RLS enabled.

To run these tests:
1. Ensure migrations are applied (especially d6abce072ea5_setup_rls_policies.py)
2. Set up test database with RLS enabled
3. Run: pytest tests/integration/test_rls_policies.py -v
"""

import pytest
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Bot, User, Subscription, Transaction, BotFeatureFlag, BotConfiguration
from app.core.tenant_context import set_current_tenant, clear_current_tenant


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def test_db_session():
    """
    Create a test database session.

    NOTE: This requires a real PostgreSQL database.
    For CI/CD, use a test database with RLS enabled.
    """
    # This should be configured via environment variable
    import os
    database_url = os.getenv("TEST_DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test_db")

    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def test_bots(test_db_session: AsyncSession):
    """Create test bots (tenants) for isolation testing."""
    bot1 = Bot(
        name="Test Bot 1",
        telegram_bot_token="test_token_1",
        is_active=True,
        bot_username="test_bot_1",
        plan="free"
    )
    bot2 = Bot(
        name="Test Bot 2",
        telegram_bot_token="test_token_2",
        is_active=True,
        bot_username="test_bot_2",
        plan="premium"
    )

    test_db_session.add(bot1)
    test_db_session.add(bot2)
    await test_db_session.commit()
    await test_db_session.refresh(bot1)
    await test_db_session.refresh(bot2)

    yield {"bot1": bot1, "bot2": bot2}

    # Cleanup
    await test_db_session.execute(text("DELETE FROM users WHERE bot_id IN (:id1, :id2)").bindparams(
        id1=bot1.id, id2=bot2.id
    ))
    await test_db_session.execute(text("DELETE FROM bots WHERE id IN (:id1, :id2)").bindparams(
        id1=bot1.id, id2=bot2.id
    ))
    await test_db_session.commit()


@pytest.mark.asyncio
async def test_rls_users_isolation(test_db_session: AsyncSession, test_bots):
    """
    Test that users table RLS policy isolates tenant data.

    Given: Two bots with different users
    When: Querying users with tenant context set
    Then: Only users for that tenant are returned
    """
    bot1 = test_bots["bot1"]
    bot2 = test_bots["bot2"]

    # Create users for bot1
    user1_bot1 = User(
        telegram_id=1001,
        bot_id=bot1.id,
        username="user1_bot1"
    )
    user2_bot1 = User(
        telegram_id=1002,
        bot_id=bot1.id,
        username="user2_bot1"
    )

    # Create users for bot2
    user1_bot2 = User(
        telegram_id=2001,
        bot_id=bot2.id,
        username="user1_bot2"
    )

    test_db_session.add_all([user1_bot1, user2_bot1, user1_bot2])
    await test_db_session.commit()

    # Set tenant context for bot1
    set_current_tenant(bot1.id)
    await test_db_session.execute(
        text("SET app.current_tenant = :bot_id"),
        {"bot_id": bot1.id}
    )
    await test_db_session.commit()

    # Query users - should only see bot1's users
    result = await test_db_session.execute(select(User))
    users = result.scalars().all()

    assert len(users) == 2, f"Expected 2 users for bot1, got {len(users)}"
    assert all(user.bot_id == bot1.id for user in users), "All users should belong to bot1"

    # Switch to bot2
    clear_current_tenant()
    set_current_tenant(bot2.id)
    await test_db_session.execute(
        text("SET app.current_tenant = :bot_id"),
        {"bot_id": bot2.id}
    )
    await test_db_session.commit()

    # Query users - should only see bot2's users
    result = await test_db_session.execute(select(User))
    users = result.scalars().all()

    assert len(users) == 1, f"Expected 1 user for bot2, got {len(users)}"
    assert users[0].bot_id == bot2.id, "User should belong to bot2"

    # Cleanup
    clear_current_tenant()
    await test_db_session.execute(text("DELETE FROM users WHERE bot_id IN (:id1, :id2)").bindparams(
        id1=bot1.id, id2=bot2.id
    ))
    await test_db_session.commit()


@pytest.mark.asyncio
async def test_rls_no_tenant_context_returns_nothing(test_db_session: AsyncSession, test_bots):
    """
    Test that RLS policies block all data when tenant context is not set.

    Given: Users exist in database
    When: Querying without tenant context
    Then: No users are returned (isolation enforced)
    """
    bot1 = test_bots["bot1"]

    # Create a user
    user = User(
        telegram_id=3001,
        bot_id=bot1.id,
        username="test_user"
    )
    test_db_session.add(user)
    await test_db_session.commit()

    # Clear tenant context
    clear_current_tenant()
    await test_db_session.execute(text("SET app.current_tenant = NULL"))
    await test_db_session.commit()

    # Query users - should return nothing due to RLS
    result = await test_db_session.execute(select(User))
    users = result.scalars().all()

    assert len(users) == 0, "RLS should block all data when tenant context is not set"

    # Cleanup
    await test_db_session.execute(text("DELETE FROM users WHERE bot_id = :bot_id").bindparams(
        bot_id=bot1.id
    ))
    await test_db_session.commit()


@pytest.mark.asyncio
async def test_rls_subscriptions_isolation(test_db_session: AsyncSession, test_bots):
    """
    Test that subscriptions table RLS policy isolates tenant data.
    """
    bot1 = test_bots["bot1"]
    bot2 = test_bots["bot2"]

    # Create users first
    user1 = User(telegram_id=4001, bot_id=bot1.id, username="user1")
    user2 = User(telegram_id=4002, bot_id=bot2.id, username="user2")
    test_db_session.add_all([user1, user2])
    await test_db_session.commit()
    await test_db_session.refresh(user1)
    await test_db_session.refresh(user2)

    # Create subscriptions
    sub1 = Subscription(bot_id=bot1.id, user_id=user1.id, is_active=True)
    sub2 = Subscription(bot_id=bot2.id, user_id=user2.id, is_active=True)
    test_db_session.add_all([sub1, sub2])
    await test_db_session.commit()

    # Set tenant context for bot1
    set_current_tenant(bot1.id)
    await test_db_session.execute(
        text("SET app.current_tenant = :bot_id"),
        {"bot_id": bot1.id}
    )
    await test_db_session.commit()

    # Query subscriptions - should only see bot1's
    result = await test_db_session.execute(select(Subscription))
    subscriptions = result.scalars().all()

    assert len(subscriptions) == 1, "Should only see bot1's subscriptions"
    assert subscriptions[0].bot_id == bot1.id

    # Cleanup
    clear_current_tenant()
    await test_db_session.execute(text("DELETE FROM subscriptions WHERE bot_id IN (:id1, :id2)").bindparams(
        id1=bot1.id, id2=bot2.id
    ))
    await test_db_session.execute(text("DELETE FROM users WHERE bot_id IN (:id1, :id2)").bindparams(
        id1=bot1.id, id2=bot2.id
    ))
    await test_db_session.commit()


@pytest.mark.asyncio
async def test_rls_bot_feature_flags_isolation(test_db_session: AsyncSession, test_bots):
    """
    Test that bot_feature_flags table RLS policy isolates tenant data.
    """
    bot1 = test_bots["bot1"]
    bot2 = test_bots["bot2"]

    # Create feature flags
    flag1 = BotFeatureFlag(bot_id=bot1.id, feature_key="test_feature", is_enabled=True)
    flag2 = BotFeatureFlag(bot_id=bot2.id, feature_key="test_feature", is_enabled=False)
    test_db_session.add_all([flag1, flag2])
    await test_db_session.commit()

    # Set tenant context for bot1
    set_current_tenant(bot1.id)
    await test_db_session.execute(
        text("SET app.current_tenant = :bot_id"),
        {"bot_id": bot1.id}
    )
    await test_db_session.commit()

    # Query feature flags - should only see bot1's
    result = await test_db_session.execute(select(BotFeatureFlag))
    flags = result.scalars().all()

    assert len(flags) == 1, "Should only see bot1's feature flags"
    assert flags[0].bot_id == bot1.id
    assert flags[0].is_enabled is True

    # Cleanup
    clear_current_tenant()
    await test_db_session.execute(text("DELETE FROM bot_feature_flags WHERE bot_id IN (:id1, :id2)").bindparams(
        id1=bot1.id, id2=bot2.id
    ))
    await test_db_session.commit()


@pytest.mark.asyncio
async def test_rls_transactions_isolation(test_db_session: AsyncSession, test_bots):
    """
    Test that transactions table RLS policy isolates tenant data.
    """
    bot1 = test_bots["bot1"]
    bot2 = test_bots["bot2"]

    # Create users first
    user1 = User(telegram_id=5001, bot_id=bot1.id, username="user1")
    user2 = User(telegram_id=5002, bot_id=bot2.id, username="user2")
    test_db_session.add_all([user1, user2])
    await test_db_session.commit()
    await test_db_session.refresh(user1)
    await test_db_session.refresh(user2)

    # Create transactions
    from app.database.models import TransactionType
    trans1 = Transaction(
        bot_id=bot1.id,
        user_id=user1.id,
        amount_toman=1000,
        transaction_type=TransactionType.DEPOSIT
    )
    trans2 = Transaction(
        bot_id=bot2.id,
        user_id=user2.id,
        amount_toman=2000,
        transaction_type=TransactionType.DEPOSIT
    )
    test_db_session.add_all([trans1, trans2])
    await test_db_session.commit()

    # Set tenant context for bot1
    set_current_tenant(bot1.id)
    await test_db_session.execute(
        text("SET app.current_tenant = :bot_id"),
        {"bot_id": bot1.id}
    )
    await test_db_session.commit()

    # Query transactions - should only see bot1's
    result = await test_db_session.execute(select(Transaction))
    transactions = result.scalars().all()

    assert len(transactions) == 1, "Should only see bot1's transactions"
    assert transactions[0].bot_id == bot1.id

    # Cleanup
    clear_current_tenant()
    await test_db_session.execute(text("DELETE FROM transactions WHERE bot_id IN (:id1, :id2)").bindparams(
        id1=bot1.id, id2=bot2.id
    ))
    await test_db_session.execute(text("DELETE FROM users WHERE bot_id IN (:id1, :id2)").bindparams(
        id1=bot1.id, id2=bot2.id
    ))
    await test_db_session.commit()


@pytest.mark.asyncio
async def test_rls_all_tables_have_policies(test_db_session: AsyncSession):
    """
    Verify that all tenant-aware tables have RLS policies enabled.

    This test checks the database metadata to ensure RLS is enabled
    on all tables that should have tenant isolation.
    """
    tables_with_rls = [
        "users",
        "subscriptions",
        "transactions",
        "bot_feature_flags",
        "bot_configurations",
        "tenant_payment_cards",
        "bot_plans",
        "card_to_card_payments",
        "zarinpal_payments"
    ]

    for table_name in tables_with_rls:
        result = await test_db_session.execute(
            text("""
                SELECT tablename, rowsecurity
                FROM pg_tables
                WHERE schemaname = 'public' AND tablename = :table_name
            """),
            {"table_name": table_name}
        )
        row = result.fetchone()

        if row:
            assert row[1] is True, f"RLS should be enabled on {table_name}"
        else:
            pytest.skip(f"Table {table_name} does not exist (migration not applied?)")


@pytest.mark.asyncio
async def test_rls_policy_names_exist(test_db_session: AsyncSession):
    """
    Verify that RLS policies exist for all tenant-aware tables.
    """
    expected_policies = [
        "tenant_isolation_users",
        "tenant_isolation_subscriptions",
        "tenant_isolation_transactions",
        "tenant_isolation_bot_feature_flags",
        "tenant_isolation_bot_configurations",
        "tenant_isolation_tenant_payment_cards",
        "tenant_isolation_bot_plans",
        "tenant_isolation_card_to_card_payments",
        "tenant_isolation_zarinpal_payments"
    ]

    for policy_name in expected_policies:
        result = await test_db_session.execute(
            text("""
                SELECT policyname
                FROM pg_policies
                WHERE schemaname = 'public' AND policyname = :policy_name
            """),
            {"policy_name": policy_name}
        )
        row = result.fetchone()

        assert row is not None, f"RLS policy {policy_name} should exist"
