"""Admin purchase notification: first vs returning purchaser labels."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.admin_notification_service import AdminNotificationService


@pytest.mark.asyncio
async def test_returning_purchaser_with_multiple_subscriptions() -> None:
    service = AdminNotificationService(MagicMock())
    db = AsyncMock()
    db.scalar = AsyncMock(side_effect=[5, 0])  # 5 subs, 0 txns queried after early return... wait

    # sub_count > 1 returns True before txn query
    db.scalar = AsyncMock(return_value=5)
    user = MagicMock(id=89)
    assert await service._is_returning_purchaser(db, user) is True


@pytest.mark.asyncio
async def test_first_purchaser_single_subscription_and_txn() -> None:
    service = AdminNotificationService(MagicMock())
    db = AsyncMock()
    db.scalar = AsyncMock(side_effect=[1, 1])  # 1 sub, 1 completed payment
    user = MagicMock(id=1)
    assert await service._is_returning_purchaser(db, user) is False


@pytest.mark.asyncio
async def test_returning_purchaser_by_payment_history() -> None:
    service = AdminNotificationService(MagicMock())
    db = AsyncMock()
    db.scalar = AsyncMock(side_effect=[1, 3])  # 1 sub row, 3 prior payments
    user = MagicMock(id=2)
    assert await service._is_returning_purchaser(db, user) is True


@pytest.mark.asyncio
async def test_resolve_effective_purchase_type_new_sub_for_returning() -> None:
    service = AdminNotificationService(MagicMock())
    service._is_returning_purchaser = AsyncMock(return_value=True)  # type: ignore[method-assign]
    db = MagicMock()
    user = MagicMock(id=89)
    assert await service._resolve_effective_purchase_type(db, user, 'first_purchase') == 'new_subscription'


@pytest.mark.asyncio
async def test_resolve_effective_purchase_type_first_for_new_user() -> None:
    service = AdminNotificationService(MagicMock())
    service._is_returning_purchaser = AsyncMock(return_value=False)  # type: ignore[method-assign]
    db = MagicMock()
    user = MagicMock(id=1)
    assert await service._resolve_effective_purchase_type(db, user, 'first_purchase') == 'first_purchase'


@pytest.mark.asyncio
async def test_resolve_effective_purchase_type_renewal_unchanged() -> None:
    service = AdminNotificationService(MagicMock())
    service._is_returning_purchaser = AsyncMock(return_value=True)  # type: ignore[method-assign]
    db = MagicMock()
    user = MagicMock(id=89)
    assert await service._resolve_effective_purchase_type(db, user, 'renewal') == 'renewal'
