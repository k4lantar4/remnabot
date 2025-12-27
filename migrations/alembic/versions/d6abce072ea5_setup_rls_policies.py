"""Setup RLS policies for multi-tenant isolation

Revision ID: d6abce072ea5
Revises: dde359954cb4
Create Date: 2025-12-27 04:40:00.000000

This migration sets up Row Level Security (RLS) policies for tenant isolation.
RLS policies ensure that each tenant can only access their own data.

IMPORTANT: This migration should be tested thoroughly in staging before production.

MIGRATION DEPENDENCIES:
- This migration MUST run after dde359954cb4_add_bot_prd_fields.py
- dde359954cb4 adds bot_username, owner_telegram_id, and plan fields to bots table
- RLS policies depend on bot_id column which exists in all tenant-aware tables
- Migration order: cbd1be472f3d -> dde359954cb4 -> d6abce072ea5
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d6abce072ea5"
down_revision: Union[str, None] = "dde359954cb4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Enable RLS and create policies for tenant-aware tables.

    Tables with bot_id that need RLS:
    - users
    - subscriptions
    - transactions
    - bot_feature_flags
    - bot_configurations
    - tenant_payment_cards
    - bot_plans
    - card_to_card_payments
    - zarinpal_payments
    """

    # Enable RLS on tenant-aware tables
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE transactions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE bot_feature_flags ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE bot_configurations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_payment_cards ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE bot_plans ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE card_to_card_payments ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE zarinpal_payments ENABLE ROW LEVEL SECURITY")

    # Create RLS policies for each table
    # Policy: Users can only see their tenant's data
    op.execute("""
        CREATE POLICY tenant_isolation_users ON users
            FOR ALL
            USING (bot_id = current_setting('app.current_tenant', true)::integer)
    """)

    # Policy: Subscriptions
    op.execute("""
        CREATE POLICY tenant_isolation_subscriptions ON subscriptions
            FOR ALL
            USING (bot_id = current_setting('app.current_tenant', true)::integer)
    """)

    # Policy: Transactions
    op.execute("""
        CREATE POLICY tenant_isolation_transactions ON transactions
            FOR ALL
            USING (bot_id = current_setting('app.current_tenant', true)::integer)
    """)

    # Policy: Bot Feature Flags
    op.execute("""
        CREATE POLICY tenant_isolation_bot_feature_flags ON bot_feature_flags
            FOR ALL
            USING (bot_id = current_setting('app.current_tenant', true)::integer)
    """)

    # Policy: Bot Configurations
    op.execute("""
        CREATE POLICY tenant_isolation_bot_configurations ON bot_configurations
            FOR ALL
            USING (bot_id = current_setting('app.current_tenant', true)::integer)
    """)

    # Policy: Tenant Payment Cards
    op.execute("""
        CREATE POLICY tenant_isolation_tenant_payment_cards ON tenant_payment_cards
            FOR ALL
            USING (bot_id = current_setting('app.current_tenant', true)::integer)
    """)

    # Policy: Bot Plans
    op.execute("""
        CREATE POLICY tenant_isolation_bot_plans ON bot_plans
            FOR ALL
            USING (bot_id = current_setting('app.current_tenant', true)::integer)
    """)

    # Policy: Card to Card Payments
    op.execute("""
        CREATE POLICY tenant_isolation_card_to_card_payments ON card_to_card_payments
            FOR ALL
            USING (bot_id = current_setting('app.current_tenant', true)::integer)
    """)

    # Policy: Zarinpal Payments
    op.execute("""
        CREATE POLICY tenant_isolation_zarinpal_payments ON zarinpal_payments
            FOR ALL
            USING (bot_id = current_setting('app.current_tenant', true)::integer)
    """)

    # Create indexes on bot_id for performance (if not already exist)
    # These should already exist, but we check to be safe
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_users_bot_id ON users(bot_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_subscriptions_bot_id ON subscriptions(bot_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_transactions_bot_id ON transactions(bot_id)
    """)


def downgrade() -> None:
    """
    Drop RLS policies and disable RLS on tables.
    """

    # Drop policies
    op.execute("DROP POLICY IF EXISTS tenant_isolation_users ON users")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_subscriptions ON subscriptions")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_transactions ON transactions")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_bot_feature_flags ON bot_feature_flags")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_bot_configurations ON bot_configurations")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_tenant_payment_cards ON tenant_payment_cards")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_bot_plans ON bot_plans")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_card_to_card_payments ON card_to_card_payments")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_zarinpal_payments ON zarinpal_payments")

    # Disable RLS
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE subscriptions DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE transactions DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE bot_feature_flags DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE bot_configurations DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_payment_cards DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE bot_plans DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE card_to_card_payments DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE zarinpal_payments DISABLE ROW LEVEL SECURITY")
