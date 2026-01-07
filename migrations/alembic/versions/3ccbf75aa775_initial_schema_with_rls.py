"""Initial schema from models.py with RLS policies

Revision ID: 3ccbf75aa775
Revises: None
Create Date: 2026-01-07 12:00:00.000000

This is the initial migration that creates all tables from models.py
and sets up Row Level Security (RLS) policies for multi-tenant isolation.

For fresh installations in dev/staging, this single migration replaces
all previous migrations. All tables are created from models.py definitions
via Alembic autogenerate.

NOTE: This migration should be generated using:
    alembic revision --autogenerate -m "Initial schema with RLS"

But for dev/staging without existing database, we create it manually.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Import Base to create tables from models.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.database.models import Base

# revision identifiers, used by Alembic.
revision: str = "3ccbf75aa775"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create all tables from models.py and set up RLS policies.
    
    This migration:
    1. Creates all tables defined in models.py using Base.metadata
    2. Sets up RLS policies for tenant isolation
    3. Creates necessary indexes
    
    For dev/staging without existing database, this single migration
    creates the complete schema from models.py.
    """
    
    # Create all tables from models.py
    # Use Base.metadata to create all tables defined in models.py
    bind = op.get_bind()
    Base.metadata.create_all(bind, checkfirst=True)
    
    # Enable RLS on tenant-aware tables
    tenant_aware_tables = [
        "users",
        "subscriptions",
        "transactions",
        "bot_feature_flags",
        "bot_configurations",
        "tenant_payment_cards",
        "bot_plans",
        "card_to_card_payments",
        "zarinpal_payments",
        "cryptobot_payments",
        "cloudpayments_payments",
        "promocodes",
        "promo_groups",
        "user_promo_groups",
        "subscription_events",
        "sent_notifications",
        "pinned_messages",
        "polls",
        "poll_questions",
        "poll_options",
        "poll_responses",
        "poll_answers",
        "advertising_campaigns",
        "advertising_campaign_registrations",
        "subscription_servers",
        "subscription_conversions",
        "referral_earnings",
        "referral_contests",
        "referral_contest_events",
        "discount_offers",
        "promo_offer_templates",
        "promo_offer_logs",
        "subscription_temporary_access",
    ]
    
    for table_name in tenant_aware_tables:
        try:
            op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        except Exception:
            # Table might not exist or RLS already enabled
            pass
    
    # Create RLS policies for tenant isolation
    # Policy: Users can only see rows where bot_id matches current_setting('app.current_tenant')
    
    # Policy for users table
    op.execute("""
        CREATE POLICY tenant_isolation_users ON users
            FOR ALL
            USING (bot_id = current_setting('app.current_tenant', true)::integer)
    """)

    # Policy for subscriptions table
    op.execute("""
        CREATE POLICY tenant_isolation_subscriptions ON subscriptions
            FOR ALL
            USING (bot_id = current_setting('app.current_tenant', true)::integer)
    """)

    # Policy for transactions table
    op.execute("""
        CREATE POLICY tenant_isolation_transactions ON transactions
            FOR ALL
            USING (bot_id = current_setting('app.current_tenant', true)::integer)
    """)

    # Policy for bot_feature_flags table
    op.execute("""
        CREATE POLICY tenant_isolation_bot_feature_flags ON bot_feature_flags
            FOR ALL
            USING (bot_id = current_setting('app.current_tenant', true)::integer)
    """)

    # Policy for bot_configurations table
    op.execute("""
        CREATE POLICY tenant_isolation_bot_configurations ON bot_configurations
            FOR ALL
            USING (bot_id = current_setting('app.current_tenant', true)::integer)
    """)

    # Policy for tenant_payment_cards table
    op.execute("""
        CREATE POLICY tenant_isolation_tenant_payment_cards ON tenant_payment_cards
            FOR ALL
            USING (bot_id = current_setting('app.current_tenant', true)::integer)
    """)

    # Policy for bot_plans table
    op.execute("""
        CREATE POLICY tenant_isolation_bot_plans ON bot_plans
            FOR ALL
            USING (bot_id = current_setting('app.current_tenant', true)::integer)
    """)

    # Policy for card_to_card_payments table
    op.execute("""
        CREATE POLICY tenant_isolation_card_to_card_payments ON card_to_card_payments
            FOR ALL
            USING (bot_id = current_setting('app.current_tenant', true)::integer)
    """)

    # Policy for zarinpal_payments table
    op.execute("""
        CREATE POLICY tenant_isolation_zarinpal_payments ON zarinpal_payments
            FOR ALL
            USING (bot_id = current_setting('app.current_tenant', true)::integer)
    """)

    # Policy for cryptobot_payments table
    op.execute("""
        CREATE POLICY tenant_isolation_cryptobot_payments ON cryptobot_payments
            FOR ALL
            USING (bot_id = current_setting('app.current_tenant', true)::integer)
    """)

    # Policy for cloudpayments_payments table
    op.execute("""
        CREATE POLICY tenant_isolation_cloudpayments_payments ON cloudpayments_payments
            FOR ALL
            USING (bot_id = current_setting('app.current_tenant', true)::integer)
    """)

    # Policy for promocodes table
    op.execute("""
        CREATE POLICY tenant_isolation_promocodes ON promocodes
            FOR ALL
            USING (bot_id = current_setting('app.current_tenant', true)::integer)
    """)

    # Policy for promo_groups table
    op.execute("""
        CREATE POLICY tenant_isolation_promo_groups ON promo_groups
            FOR ALL
            USING (bot_id = current_setting('app.current_tenant', true)::integer)
    """)

    # Create indexes on bot_id for performance (if not already exist)
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_bot_id ON users(bot_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_bot_id ON subscriptions(bot_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_transactions_bot_id ON transactions(bot_id)")


def downgrade() -> None:
    """
    Drop RLS policies, disable RLS, and drop all tables.
    
    WARNING: This will delete all data and tables!
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
    op.execute("DROP POLICY IF EXISTS tenant_isolation_cryptobot_payments ON cryptobot_payments")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_cloudpayments_payments ON cloudpayments_payments")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_promocodes ON promocodes")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_promo_groups ON promo_groups")

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
    op.execute("ALTER TABLE cryptobot_payments DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE cloudpayments_payments DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE promocodes DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE promo_groups DISABLE ROW LEVEL SECURITY")
    
    # Drop all tables (in reverse dependency order)
    # Use Base.metadata to drop all tables
    bind = op.get_bind()
    Base.metadata.drop_all(bind, checkfirst=True)