"""Tests for C2C submit_receipt TTL refresh on successful send."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.database.models import C2cReceiptStatus
from app.plugins.c2c.constants import C2C_RECEIPT_TYPE_PHOTO
from app.plugins.c2c.service import C2cPaymentService


@pytest.mark.asyncio
async def test_submit_receipt_refreshes_expires_at_on_success():
    receipt = SimpleNamespace(
        id=7,
        status=C2cReceiptStatus.PENDING.value,
        amount_kopeks=100_000,
        card_label='Card A',
        created_at=datetime(2026, 6, 20, 8, 0, tzinfo=UTC),
        receipt_type=None,
        receipt_file_id=None,
        receipt_text=None,
        user_receipt_message_id=None,
        admin_chat_id=None,
        admin_message_id=None,
        expires_at=datetime(2026, 6, 20, 8, 0, tzinfo=UTC),
        updated_at=datetime.now(UTC),
    )
    user = SimpleNamespace(id=1, language='fa', full_name='Test', telegram_id=123)
    db = AsyncMock()
    db.flush = AsyncMock()

    bot = MagicMock()
    admin_message = SimpleNamespace(chat=SimpleNamespace(id=-100123), message_id=55)
    service = C2cPaymentService(bot)

    fixed_now = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)

    with patch('app.plugins.c2c.service.settings') as mock_settings, patch(
        'app.plugins.c2c.service.datetime',
    ) as mock_datetime, patch(
        'app.plugins.c2c.service.send_with_admin_topic_fallback',
        new=AsyncMock(return_value=admin_message),
    ), patch(
        'app.plugins.c2c.service.build_delivery_kwargs',
        return_value={'chat_id': -100123},
    ), patch(
        'app.plugins.c2c.service.AdminNotificationService',
    ):
        mock_datetime.now.return_value = fixed_now
        mock_datetime.UTC = UTC
        mock_settings.get_c2c_admin_chat_id.return_value = -100123
        mock_settings.C2C_ADMIN_CHAT_ID = ''
        mock_settings.format_balance.return_value = '100,000 تومان'
        mock_settings.DEFAULT_LANGUAGE = 'fa'
        mock_settings.admin_forum_topics_apply_to_chat.return_value = True
        mock_settings.C2C_RECEIPT_TTL_HOURS = 24

        ok, msg, admin_msg_id = await service.submit_receipt(
            db,
            receipt=receipt,
            receipt_type=C2C_RECEIPT_TYPE_PHOTO,
            receipt_file_id='file123',
            receipt_text=None,
            user_receipt_message_id=42,
            user=user,
        )

    assert ok is True
    assert admin_msg_id == 55
    assert receipt.expires_at == fixed_now + timedelta(hours=24)
