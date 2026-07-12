"""Tests for subscription disable/enable API and toggle service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.cabinet.routes.subscription_modules import multi_tariff
from app.services.subscription_user_toggle_service import (
    SubscriptionToggleError,
    disable_user_subscription,
    enable_user_subscription,
)


def _active_sub(**overrides):
    base = dict(
        id=1,
        user_id=10,
        status='active',
        actual_status='active',
        end_date=datetime.now(UTC) + timedelta(days=10),
        remnawave_uuid='uuid-1',
        is_daily_tariff=False,
        is_daily_paused=False,
        user_disabled=False,
        updated_at=None,
        last_webhook_update_at=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_disable_sets_user_disabled_and_pauses_daily(monkeypatch: pytest.MonkeyPatch) -> None:
    subscription = _active_sub(is_daily_tariff=True, is_daily_paused=False)
    user = SimpleNamespace(id=10, remnawave_uuid=None)
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    deactivate = AsyncMock(return_value=subscription)
    monkeypatch.setattr(
        'app.services.subscription_user_toggle_service.deactivate_subscription',
        deactivate,
    )
    service = MagicMock()
    service.disable_remnawave_user = AsyncMock(return_value=True)
    monkeypatch.setattr(
        'app.services.subscription_user_toggle_service.SubscriptionService',
        lambda: service,
    )
    monkeypatch.setattr(
        'app.services.subscription_user_toggle_service._panel_uuid',
        lambda subscription, user: 'uuid-1',
    )

    result = await disable_user_subscription(db, subscription, user)

    assert result.user_disabled is True
    assert subscription.is_daily_paused is True
    assert subscription.last_webhook_update_at is not None
    deactivate.assert_awaited_once()
    service.disable_remnawave_user.assert_awaited_once_with('uuid-1')


@pytest.mark.asyncio
async def test_enable_reactivates_without_payment(monkeypatch: pytest.MonkeyPatch) -> None:
    subscription = _active_sub(
        status='disabled',
        actual_status='disabled',
        user_disabled=True,
    )
    user = SimpleNamespace(id=10, remnawave_uuid=None)
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    reactivate = AsyncMock(return_value=subscription)
    monkeypatch.setattr(
        'app.services.subscription_user_toggle_service.reactivate_subscription',
        reactivate,
    )
    service = MagicMock()
    service.enable_remnawave_user = AsyncMock(return_value=True)
    service.create_remnawave_user = AsyncMock(return_value={'uuid': 'new'})
    monkeypatch.setattr(
        'app.services.subscription_user_toggle_service.SubscriptionService',
        lambda: service,
    )
    monkeypatch.setattr(
        'app.services.subscription_user_toggle_service._panel_uuid',
        lambda subscription, user: 'uuid-1',
    )

    result = await enable_user_subscription(db, subscription, user)

    assert result.user_disabled is False
    reactivate.assert_awaited_once()
    service.enable_remnawave_user.assert_awaited_once_with('uuid-1')
    service.create_remnawave_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_enable_rejects_non_user_disabled() -> None:
    subscription = _active_sub(status='disabled', actual_status='disabled', user_disabled=False)
    user = SimpleNamespace(id=10)
    db = AsyncMock()

    with pytest.raises(SubscriptionToggleError) as exc:
        await enable_user_subscription(db, subscription, user)
    assert exc.value.code == 'not_user_disabled'


@pytest.mark.asyncio
async def test_disable_api_returns_toggle_state(monkeypatch: pytest.MonkeyPatch) -> None:
    subscription = _active_sub(user_disabled=True, status='disabled', actual_status='disabled')
    user = SimpleNamespace(id=10)

    monkeypatch.setattr(multi_tariff, '_get_owned_subscription', AsyncMock(return_value=subscription))
    monkeypatch.setattr(
        multi_tariff,
        'disable_user_subscription',
        AsyncMock(return_value=subscription),
    )

    response = await multi_tariff.disable_subscription(1, user=user, db=AsyncMock())
    assert response.user_disabled is True
    assert response.status == 'disabled'


def test_subscription_matches_search_on_purchase_note() -> None:
    sub = SimpleNamespace(
        id=3,
        panel_username='',
        tariff=SimpleNamespace(name='Pro'),
        purchase_note='فروشگاه مرکزی',
    )
    assert multi_tariff._subscription_matches_search(sub, 'مرکزی') is True
    assert multi_tariff._subscription_matches_search(sub, 'nomatch') is False
