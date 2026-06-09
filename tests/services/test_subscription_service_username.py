"""Regression: multi-tariff update_user must not include username (PR #49)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.database.models import Subscription, User
from app.external.remnawave_api import RemnaWaveUser, TrafficLimitStrategy, UserStatus
from app.services.subscription_service import SubscriptionService


def _make_user() -> User:
    user = MagicMock(spec=User)
    user.id = 42
    user.telegram_id = 1713374557
    user.username = 'testuser'
    user.full_name = 'Test User'
    user.email = None
    return user


def _make_subscription() -> Subscription:
    sub = MagicMock(spec=Subscription)
    sub.id = 99
    sub.remnawave_uuid = 'uuid-existing-123'
    sub.remnawave_short_id = '41103d'
    sub.account_sequence = 1
    sub.end_date = datetime(2026, 7, 17, 16, 22, tzinfo=UTC)
    sub.traffic_limit_gb = 86
    sub.connected_squads = ['squad-uuid']
    sub.tariff = None
    return sub


def _make_remnawave_user(*, username: str = 'user_unknown_41103d') -> RemnaWaveUser:
    now = datetime(2026, 6, 9, 12, 0, tzinfo=UTC)
    return RemnaWaveUser(
        uuid='uuid-existing-123',
        short_uuid='41103d',
        username=username,
        status=UserStatus.ACTIVE,
        expire_at=datetime(2026, 7, 17, 16, 22, tzinfo=UTC),
        traffic_limit_bytes=86 * 1024**3,
        traffic_limit_strategy=TrafficLimitStrategy.NO_RESET,
        telegram_id=1713374557,
        email=None,
        hwid_device_limit=None,
        description='Bot user: Test',
        tag=None,
        subscription_url='https://example.com/sub',
        active_internal_squads=[],
        created_at=now,
        updated_at=now,
        user_traffic=None,
    )


@pytest.mark.asyncio
async def test_multi_tariff_update_does_not_pass_username() -> None:
    service = SubscriptionService()
    user = _make_user()
    subscription = _make_subscription()

    existing = _make_remnawave_user()
    updated = _make_remnawave_user()

    api = AsyncMock()
    api.get_user_by_uuid = AsyncMock(return_value=existing)
    api.reset_user_devices = AsyncMock()
    api.update_user = AsyncMock(return_value=updated)

    with patch('app.services.subscription_service.settings') as mock_settings:
        mock_settings.is_multi_tariff_enabled.return_value = True
        mock_settings.format_remnawave_user_description.return_value = 'Bot user: Test'
        mock_settings.build_remnawave_subscription_username = MagicMock(
            return_value='user_1713374557_41103d'
        )

        await service._create_or_update_remnawave_user_multi(
            api,
            user,
            subscription,
            user_tag=None,
            hwid_limit=None,
            ext_squad_uuid=None,
            reset_traffic=False,
            reset_reason=None,
        )

    api.update_user.assert_awaited_once()
    _, kwargs = api.update_user.await_args
    assert 'username' not in kwargs, 'username must not be sent on update_user (prevents mass panel rename)'
