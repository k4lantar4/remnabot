"""User-initiated subscription disable/enable (no payment on re-enable)."""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud.subscription import deactivate_subscription, reactivate_subscription
from app.database.models import Subscription, User
from app.services.subscription_service import SubscriptionService


logger = structlog.get_logger(__name__)


class SubscriptionToggleError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _panel_id(subscription: Subscription) -> int | None:
    raw = getattr(subscription, 'remnawave_id', None)
    if raw is None:
        return None
    try:
        panel_id = int(raw)
    except (TypeError, ValueError):
        return None
    return panel_id or None


async def _raise_panel_error(db: AsyncSession, message: str) -> None:
    await db.rollback()
    raise SubscriptionToggleError('panel_error', message)


async def disable_user_subscription(
    db: AsyncSession,
    subscription: Subscription,
    user: User,
) -> Subscription:
    actual = subscription.actual_status
    if actual not in ('active', 'trial', 'limited'):
        raise SubscriptionToggleError('not_active', 'Only active subscriptions can be disabled')

    panel_id = _panel_id(subscription)
    if not panel_id:
        await _raise_panel_error(db, 'Failed to disable VPN access on panel')

    ok = await SubscriptionService().disable_remnawave_user(int(panel_id), db=db)
    if not ok:
        await _raise_panel_error(db, 'Failed to disable VPN access on panel')

    now = datetime.now(UTC)
    subscription.last_webhook_update_at = now
    subscription.user_disabled = True
    await deactivate_subscription(db, subscription, commit=False)

    if subscription.is_daily_tariff:
        subscription.is_daily_paused = True

    await db.commit()
    await db.refresh(subscription)
    logger.info(
        'User disabled subscription',
        subscription_id=subscription.id,
        user_id=user.id,
    )
    return subscription


async def enable_user_subscription(
    db: AsyncSession,
    subscription: Subscription,
    user: User,
) -> Subscription:
    now = datetime.now(UTC)
    if not getattr(subscription, 'user_disabled', False):
        raise SubscriptionToggleError('not_user_disabled', 'Subscription was not disabled by user')
    if subscription.status != 'disabled':
        raise SubscriptionToggleError('not_disabled', 'Subscription is not in disabled state')
    if not subscription.end_date or subscription.end_date <= now:
        raise SubscriptionToggleError('expired', 'Subscription has expired; renew instead')

    service = SubscriptionService()
    panel_id = _panel_id(subscription)
    panel_ok = False
    if panel_id:
        panel_ok = await service.enable_remnawave_user(int(panel_id), db=db)

    if not panel_ok:
        subscription.last_webhook_update_at = now
        subscription.user_disabled = False
        await reactivate_subscription(db, subscription, commit=False)
        if subscription.is_daily_tariff:
            subscription.is_daily_paused = False

        result = await service.create_remnawave_user(db, subscription, reset_traffic=False)
        if not result:
            await _raise_panel_error(db, 'Failed to enable VPN access on panel')
    else:
        subscription.last_webhook_update_at = now
        subscription.user_disabled = False
        await reactivate_subscription(db, subscription, commit=False)
        if subscription.is_daily_tariff:
            subscription.is_daily_paused = False

    await db.commit()
    await db.refresh(subscription)
    logger.info(
        'User enabled subscription',
        subscription_id=subscription.id,
        user_id=user.id,
    )
    return subscription
