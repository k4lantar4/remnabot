"""Add PRD fields to Bot model

Revision ID: dde359954cb4
Revises: cbd1be472f3d
Create Date: 2025-12-27 04:35:31.000000

This migration adds three PRD-required fields to the Bot model:
- bot_username: String(255), nullable - Bot username for display in admin panel
- owner_telegram_id: BigInteger, nullable - Telegram ID of bot owner
- plan: String(50), default='free', not null - Tenant plan (free, basic, premium, etc.)

MIGRATION DEPENDENCIES:
- This migration revises cbd1be472f3d
- Next migration: d6abce072ea5_setup_rls_policies.py (depends on this one)
- Migration order: cbd1be472f3d -> dde359954cb4 -> d6abce072ea5
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "dde359954cb4"
down_revision: Union[str, None] = "cbd1be472f3d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add bot_username field (nullable, can be set later)
    op.add_column("bots", sa.Column("bot_username", sa.String(255), nullable=True))

    # Add owner_telegram_id field (nullable, can be set later)
    op.add_column("bots", sa.Column("owner_telegram_id", sa.BigInteger(), nullable=True))

    # Add plan field (default 'free', not nullable after migration)
    op.add_column("bots", sa.Column("plan", sa.String(50), nullable=True))

    # Update existing data:
    # - Set bot_username = name WHERE bot_username IS NULL
    op.execute("UPDATE bots SET bot_username = name WHERE bot_username IS NULL")

    # - Set plan = 'free' WHERE plan IS NULL
    op.execute("UPDATE bots SET plan = 'free' WHERE plan IS NULL")

    # Now make plan NOT NULL with default
    op.alter_column("bots", "plan", nullable=False, server_default="'free'")

    # Remove server_default after data is set (optional, but cleaner)
    op.alter_column("bots", "plan", server_default=None)


def downgrade() -> None:
    # Remove the columns
    op.drop_column("bots", "plan")
    op.drop_column("bots", "owner_telegram_id")
    op.drop_column("bots", "bot_username")
