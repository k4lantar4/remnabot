"""Tests for renew pin keep/drop when catalog tariff was replaced."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.renewal_pin import resolve_renewal_target_subscription


@pytest.mark.asyncio
async def test_keep_pin_when_same_tariff():
    sub = SimpleNamespace(id=10, tariff_id=9)
    with patch(
        'app.services.renewal_pin.get_subscription_by_id_for_user',
        new=AsyncMock(return_value=sub),
    ):
        got = await resolve_renewal_target_subscription(
            db=None,
            user_id=1,
            pinned_subscription_id=10,
            requested_tariff_id=9,
        )
    assert got is sub


@pytest.mark.asyncio
async def test_keep_pin_when_old_tariff_inactive():
    sub = SimpleNamespace(id=10, tariff_id=4)
    old = SimpleNamespace(id=4, is_active=False)
    with (
        patch(
            'app.services.renewal_pin.get_subscription_by_id_for_user',
            new=AsyncMock(return_value=sub),
        ),
        patch(
            'app.services.renewal_pin.get_tariff_by_id',
            new=AsyncMock(return_value=old),
        ),
    ):
        got = await resolve_renewal_target_subscription(
            db=None,
            user_id=1,
            pinned_subscription_id=10,
            requested_tariff_id=9,
        )
    assert got is sub


@pytest.mark.asyncio
async def test_drop_pin_when_old_tariff_still_active():
    sub = SimpleNamespace(id=10, tariff_id=2)
    old = SimpleNamespace(id=2, is_active=True)
    with (
        patch(
            'app.services.renewal_pin.get_subscription_by_id_for_user',
            new=AsyncMock(return_value=sub),
        ),
        patch(
            'app.services.renewal_pin.get_tariff_by_id',
            new=AsyncMock(return_value=old),
        ),
    ):
        got = await resolve_renewal_target_subscription(
            db=None,
            user_id=1,
            pinned_subscription_id=10,
            requested_tariff_id=9,
        )
    assert got is None


@pytest.mark.asyncio
async def test_keep_pin_when_legacy_no_tariff():
    sub = SimpleNamespace(id=10, tariff_id=None)
    with patch(
        'app.services.renewal_pin.get_subscription_by_id_for_user',
        new=AsyncMock(return_value=sub),
    ):
        got = await resolve_renewal_target_subscription(
            db=None,
            user_id=1,
            pinned_subscription_id=10,
            requested_tariff_id=9,
        )
    assert got is sub


def test_bot_renew_pick_callback_registered():
    from pathlib import Path

    source = Path('app/handlers/subscription/tariff_purchase.py').read_text(encoding='utf-8')
    assert 'tariff_renew_pick:' in source
    assert 'select_tariff_for_renew' in source
    assert "startswith('tariff_renew_pick:')" in source
    # Inactive renew must use renew_pick, not catalog purchase select
    inactive_start = source.find('# Скрытый/неактивный тариф')
    assert inactive_start >= 0
    inactive_block = source[inactive_start : inactive_start + 1200]
    assert 'tariff_renew_pick:' in inactive_block
    assert 'tariff_select:' not in inactive_block
