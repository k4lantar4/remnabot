"""Partner wholesale inventory stats for cabinet earn tab."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import and_, func, select

from app.config import settings
from app.database.crud.subscription import get_all_subscriptions_by_user_id
from app.database.models import Transaction, TransactionType
from app.services.remnawave_service import RemnaWaveService
from app.utils.price_display import storage_sum_to_display_toman


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.database.models import Subscription, User


logger = structlog.get_logger(__name__)

NEAR_EXPIRY_DAYS = 7
ONLINE_WINDOW_MINUTES = 15
ACTIVE_STATUSES = frozenset({'active', 'trial'})


@dataclass(frozen=True)
class SubscriptionInventoryCounts:
    total: int
    active: int
    expired: int
    near_expiry: int


def summarize_subscription_inventory(subscriptions: list[Subscription]) -> SubscriptionInventoryCounts:
    """Count partner-owned subscriptions by lifecycle bucket."""
    total = len(subscriptions)
    active = 0
    expired = 0
    near_expiry = 0

    for sub in subscriptions:
        status = sub.actual_status
        if status in ACTIVE_STATUSES:
            active += 1
            if sub.days_left <= NEAR_EXPIRY_DAYS:
                near_expiry += 1
        elif status == 'expired':
            expired += 1

    return SubscriptionInventoryCounts(
        total=total,
        active=active,
        expired=expired,
        near_expiry=near_expiry,
    )


def _parse_panel_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return None
    return None


def is_device_online(last_seen: Any, *, now: datetime | None = None) -> bool:
    """True when device was seen within ONLINE_WINDOW_MINUTES."""
    parsed = _parse_panel_timestamp(last_seen)
    if parsed is None:
        return False
    current = now or datetime.now(UTC)
    return parsed >= current - timedelta(minutes=ONLINE_WINDOW_MINUTES)


def _resolve_panel_uuid(subscription: Subscription, user: User) -> str | None:
    if settings.is_multi_tariff_enabled() and subscription.remnawave_uuid:
        return subscription.remnawave_uuid
    return user.remnawave_uuid


async def _count_online_users(
    db: AsyncSession,
    user: User,
    subscriptions: list[Subscription],
) -> int:
    """Subscriptions with at least one recently seen device."""
    active_subs = [s for s in subscriptions if s.actual_status in ACTIVE_STATUSES]
    if not active_subs:
        return 0

    online_count = 0
    now = datetime.now(UTC)

    try:
        service = RemnaWaveService()
        async with service.get_api_client() as api:
            for sub in active_subs:
                panel_uuid = _resolve_panel_uuid(sub, user)
                if not panel_uuid:
                    continue
                try:
                    response = await api.get_user_devices_all(panel_uuid)
                except Exception as exc:
                    logger.warning(
                        'partner inventory: device fetch failed',
                        subscription_id=sub.id,
                        error=str(exc)[:200],
                    )
                    continue

                devices = response.get('devices', [])
                if any(
                    is_device_online(
                        device.get('updatedAt') or device.get('lastSeen') or device.get('createdAt'),
                        now=now,
                    )
                    for device in devices
                ):
                    online_count += 1
    except Exception as exc:
        logger.warning('partner inventory: panel unavailable', error=str(exc)[:200])
        return 0

    return online_count


async def _sum_subscription_spend_kopeks(
    db: AsyncSession,
    user_id: int,
    *,
    since: datetime | None = None,
) -> int:
    """Sum completed subscription_payment debits for user, optionally since a date."""
    conditions = [
        Transaction.user_id == user_id,
        Transaction.is_completed.is_(True),
        Transaction.type == TransactionType.SUBSCRIPTION_PAYMENT.value,
    ]
    if since is not None:
        conditions.append(Transaction.created_at >= since)

    result = await db.execute(
        select(func.coalesce(func.sum(func.abs(Transaction.amount_kopeks)), 0)).where(and_(*conditions))
    )
    return int(result.scalar_one())


def _subscription_spend_display_toman(raw_kopeks: int) -> float:
    return float(storage_sum_to_display_toman(raw_kopeks, TransactionType.SUBSCRIPTION_PAYMENT.value))


async def get_partner_inventory_stats(db: AsyncSession, user: User) -> dict[str, int | float]:
    """Aggregate wholesale partner inventory metrics for cabinet UI."""
    subscriptions = await get_all_subscriptions_by_user_id(db, user.id)
    counts = summarize_subscription_inventory(subscriptions)
    now = datetime.now(UTC)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    total_spent_kopeks = await _sum_subscription_spend_kopeks(db, user.id)
    week_spent_kopeks = await _sum_subscription_spend_kopeks(db, user.id, since=week_ago)
    month_spent_kopeks = await _sum_subscription_spend_kopeks(db, user.id, since=month_ago)
    online_users = await _count_online_users(db, user, subscriptions)

    return {
        'total_subscriptions': counts.total,
        'active_subscriptions': counts.active,
        'expired_subscriptions': counts.expired,
        'near_expiry_subscriptions': counts.near_expiry,
        'total_spent_kopeks': total_spent_kopeks,
        'total_spent_rubles': _subscription_spend_display_toman(total_spent_kopeks),
        'spent_week_kopeks': week_spent_kopeks,
        'spent_week_rubles': _subscription_spend_display_toman(week_spent_kopeks),
        'spent_month_kopeks': month_spent_kopeks,
        'spent_month_rubles': _subscription_spend_display_toman(month_spent_kopeks),
        'online_users': online_users,
        'near_expiry_days': NEAR_EXPIRY_DAYS,
    }
