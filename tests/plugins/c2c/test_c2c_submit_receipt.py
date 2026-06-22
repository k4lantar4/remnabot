"""Tests for C2cPaymentService.submit_receipt persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.database.models import C2cReceiptStatus
from app.plugins.c2c.constants import C2C_RECEIPT_TYPE_PHOTO
from app.plugins.c2c.service import C2cPaymentService


@pytest.mark.asyncio
async def test_submit_receipt_does_not_persist_attachment_when_admin_send_fails():
    receipt = SimpleNamespace(
        id=7,
        status=C2cReceiptStatus.PENDING.value,
        amount_kopeks=100_000,
        card_label='Card A',
        created_at=datetime.now(UTC),
        receipt_type=None,
        receipt_file_id=None,
        receipt_text=None,
        user_receipt_message_id=None,
        admin_chat_id=None,
        admin_message_id=None,
        updated_at=datetime.now(UTC),
    )
    user = SimpleNamespace(id=1, language='fa', full_name='Test', telegram_id=12345)
    db = AsyncMock()
    db.flush = AsyncMock()

    bot = MagicMock()
    service = C2cPaymentService(bot)

    with patch('app.plugins.c2c.service.settings') as mock_settings, patch(
        'app.plugins.c2c.service.send_with_admin_topic_fallback',
        new=AsyncMock(side_effect=RuntimeError('telegram down')),
    ), patch(
        'app.plugins.c2c.service.build_delivery_kwargs',
        return_value={'chat_id': -100123},
    ), patch(
        'app.plugins.c2c.service.AdminNotificationService',
    ):
        mock_settings.get_c2c_admin_chat_id.return_value = -100123
        mock_settings.C2C_ADMIN_CHAT_ID = ''
        mock_settings.format_balance.return_value = '100,000 تومان'
        mock_settings.DEFAULT_LANGUAGE = 'fa'
        mock_settings.admin_forum_topics_apply_to_chat.return_value = True

        ok, msg, admin_msg_id = await service.submit_receipt(
            db,
            receipt=receipt,
            receipt_type=C2C_RECEIPT_TYPE_PHOTO,
            receipt_file_id='file123',
            receipt_text=None,
            user_receipt_message_id=42,
            user=user,
        )

    assert ok is False
    assert admin_msg_id is None
    assert receipt.receipt_type is None
    assert receipt.receipt_file_id is None
    assert receipt.admin_message_id is None
