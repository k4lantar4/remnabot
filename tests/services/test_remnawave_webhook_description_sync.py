"""Webhook description → subscription.purchase_note sync tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.database.models import SubscriptionStatus
from app.services.remnawave_webhook_service import RemnaWaveWebhookService
from app.utils.remnawave_panel_identity import PANEL_NOTE_DELIMITER


@pytest.mark.asyncio
async def test_user_modified_syncs_purchase_note_from_description() -> None:
    subscription = SimpleNamespace(
        id=1,
        purchase_note=None,
        traffic_limit_gb=100,
        traffic_used_gb=0.0,
        end_date=datetime.now(UTC) + timedelta(days=30),
        status=SubscriptionStatus.ACTIVE.value,
        subscription_url='https://example.com/sub',
        subscription_crypto_link=None,
        updated_at=None,
        last_webhook_update_at=None,
    )
    user = SimpleNamespace(id=10, language='fa')
    db = AsyncMock()
    db.commit = AsyncMock()

    service = RemnaWaveWebhookService(bot=MagicMock())
    data = {
        'description': f'Bot user: Ali{PANEL_NOTE_DELIMITER}فروشگاه موبایل',
    }

    await service._handle_user_modified(db, user, subscription, data)

    assert subscription.purchase_note == 'فروشگاه موبایل'
    db.commit.assert_awaited()
