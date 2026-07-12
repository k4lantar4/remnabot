"""Tests for subscription enable API guards."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.cabinet.routes.subscription_modules import multi_tariff
from app.services.subscription_user_toggle_service import SubscriptionToggleError


@pytest.mark.asyncio
async def test_enable_api_maps_expired_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    subscription = SimpleNamespace(
        id=3,
        actual_status='disabled',
        user_disabled=True,
    )
    monkeypatch.setattr(multi_tariff, '_get_owned_subscription', AsyncMock(return_value=subscription))
    monkeypatch.setattr(
        multi_tariff,
        'enable_user_subscription',
        AsyncMock(side_effect=SubscriptionToggleError('expired', 'expired')),
    )

    with pytest.raises(HTTPException) as exc:
        await multi_tariff.enable_subscription(3, user=SimpleNamespace(id=1), db=AsyncMock())
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_enable_api_success_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    subscription = SimpleNamespace(
        id=3,
        actual_status='active',
        user_disabled=False,
        end_date=datetime.now(UTC) + timedelta(days=5),
    )
    monkeypatch.setattr(multi_tariff, '_get_owned_subscription', AsyncMock(return_value=subscription))
    monkeypatch.setattr(
        multi_tariff,
        'enable_user_subscription',
        AsyncMock(return_value=subscription),
    )

    response = await multi_tariff.enable_subscription(3, user=SimpleNamespace(id=1), db=AsyncMock())
    assert response.success is True
    assert response.user_disabled is False
    assert response.status == 'active'
