from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select

from app.database.models import Subscription, SubscriptionStatus, User


async def validate_migration(
    db,
    *,
    expected_subscriber_users: int = 761,
    expected_campaign_users: int = 5893,
    migration_run: datetime | None = None,
) -> dict:
    if migration_run is None:
        migration_run = datetime.now(UTC)

    user_count = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    sub_count = (await db.execute(select(func.count()).select_from(Subscription))).scalar_one()
    missing_panel = (
        await db.execute(
            select(func.count())
            .select_from(Subscription)
            .join(User, User.id == Subscription.user_id)
            .where(Subscription.remnawave_uuid.is_(None))
            .where(User.telegram_id.is_not(None))
            .where(Subscription.status.in_([
                SubscriptionStatus.ACTIVE.value,
                SubscriptionStatus.TRIAL.value,
                SubscriptionStatus.LIMITED.value,
            ]))
        )
    ).scalar_one()
    partners = (
        await db.execute(select(func.count()).select_from(User).where(User.partner_status == 'approved'))
    ).scalar_one()

    subs_with_used = (
        await db.execute(
            select(func.count())
            .select_from(Subscription)
            .where(Subscription.traffic_used_gb != 0.0)
        )
    ).scalar_one()

    expired_subs = (
        await db.execute(
            select(func.count())
            .select_from(Subscription)
            .where(Subscription.end_date <= migration_run)
            .where(Subscription.status.in_([
                SubscriptionStatus.ACTIVE.value,
                SubscriptionStatus.TRIAL.value,
                SubscriptionStatus.LIMITED.value,
            ]))
        )
    ).scalar_one()

    min_expected_users = expected_subscriber_users + expected_campaign_users - 500

    checks = {
        'users_meet_minimum': user_count >= min_expected_users,
        'subscriptions_positive': sub_count > 0,
        'traffic_used_zero': subs_with_used == 0,
        'no_expired_active_subs': expired_subs == 0,
        'subscribers_have_panel_uuid': missing_panel == 0,
    }

    return {
        'users': user_count,
        'subscriptions': sub_count,
        'missing_remnawave_uuid': missing_panel,
        'approved_partners': partners,
        'subs_with_nonzero_traffic_used': subs_with_used,
        'expired_active_subs': expired_subs,
        'checks': checks,
        'passed': all(checks.values()),
    }
