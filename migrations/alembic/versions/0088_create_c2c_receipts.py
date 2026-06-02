"""create c2c_receipts table for manual card-to-card top-ups

Revision ID: 0088
Revises: 0087
Create Date: 2026-06-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0088'
down_revision: Union[str, None] = '0087'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'c2c_receipts',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('amount_kopeks', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(32), nullable=False, server_default='pending', index=True),
        sa.Column('receipt_type', sa.String(32), nullable=True),
        sa.Column('receipt_file_id', sa.String(512), nullable=True),
        sa.Column('receipt_text', sa.Text(), nullable=True),
        sa.Column('user_receipt_message_id', sa.BigInteger(), nullable=True),
        sa.Column('card_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('card_label', sa.String(128), nullable=True),
        sa.Column('admin_chat_id', sa.BigInteger(), nullable=True),
        sa.Column('admin_message_id', sa.BigInteger(), nullable=True),
        sa.Column('reviewed_by_telegram_id', sa.BigInteger(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('transaction_id', sa.Integer(), sa.ForeignKey('transactions.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_c2c_receipts_status_created_at', 'c2c_receipts', ['status', 'created_at'])
    op.execute(
        """
        CREATE UNIQUE INDEX uq_c2c_receipts_user_pending
        ON c2c_receipts (user_id)
        WHERE status = 'pending'
        """
    )


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS uq_c2c_receipts_user_pending')
    op.drop_index('ix_c2c_receipts_status_created_at', table_name='c2c_receipts')
    op.drop_table('c2c_receipts')
