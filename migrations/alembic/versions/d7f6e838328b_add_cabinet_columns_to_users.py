"""Add Cabinet authentication columns to users table

Revision ID: a1b2c3d4e5f6
Revises: 1f5f3a3f5a4d
Create Date: 2026-01-07 12:00:00.000000

This migration adds 7 Cabinet authentication columns to the users table:
- cabinet_email: User's email for Cabinet authentication
- cabinet_email_verified: Whether email is verified
- cabinet_password_hash: Hashed password for Cabinet
- cabinet_email_verification_token: Token for email verification
- cabinet_email_verification_expires_at: Expiration for verification token
- cabinet_password_reset_token: Token for password reset
- cabinet_password_reset_expires_at: Expiration for reset token

All columns are nullable for backward compatibility.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d7f6e838328b"
down_revision: Union[str, None] = "1f5f3a3f5a4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add Cabinet columns to users table."""
    # Add Cabinet authentication columns
    op.add_column("users", sa.Column("cabinet_email", sa.String(255), nullable=True))
    op.add_column(
        "users",
        sa.Column("cabinet_email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("users", sa.Column("cabinet_password_hash", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("cabinet_email_verification_token", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("cabinet_email_verification_expires_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("cabinet_password_reset_token", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("cabinet_password_reset_expires_at", sa.DateTime(), nullable=True))

    # Create index on cabinet_email for faster lookups
    op.create_index("idx_users_cabinet_email", "users", ["cabinet_email"], unique=False)


def downgrade() -> None:
    """Remove Cabinet columns from users table."""
    # Drop index first
    op.drop_index("idx_users_cabinet_email", table_name="users")

    # Drop columns
    op.drop_column("users", "cabinet_password_reset_expires_at")
    op.drop_column("users", "cabinet_password_reset_token")
    op.drop_column("users", "cabinet_email_verification_expires_at")
    op.drop_column("users", "cabinet_email_verification_token")
    op.drop_column("users", "cabinet_password_hash")
    op.drop_column("users", "cabinet_email_verified")
    op.drop_column("users", "cabinet_email")
