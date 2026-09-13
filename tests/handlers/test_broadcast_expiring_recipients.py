"""F-045: an admin broadcast to "expiring" reaches a user once, however many subscriptions expire."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.database.models import PromoGroup, Subscription, SubscriptionStatus, Tariff, User, UserStatus
from app.handlers.admin.messages import get_target_users
from tests.fixtures.sqlite_memory import memory_session


TABLES = (User.__table__, Subscription.__table__, Tariff.__table__, PromoGroup.__table__)


@pytest.mark.parametrize(('target', 'days'), [('expiring', 2), ('expiring_subscribers', 5)])
async def test_user_with_two_expiring_subscriptions_is_one_recipient(monkeypatch, target, days):
    now = datetime.now(UTC)
    async with memory_session(monkeypatch, TABLES) as db:
        user = User(telegram_id=1, username='u1', first_name='U', status=UserStatus.ACTIVE.value, balance_kopeks=0)
        db.add(user)
        await db.commit()
        db.add_all(
            [
                Subscription(
                    user_id=user.id,
                    status=SubscriptionStatus.ACTIVE.value,
                    is_trial=False,
                    start_date=now - timedelta(days=30),
                    end_date=now + timedelta(days=days, hours=index),
                    remnawave_short_id=f'short{index}',
                )
                for index in (1, 2)
            ]
        )
        await db.commit()

        recipients = await get_target_users(db, target)

        assert [recipient.id for recipient in recipients] == [user.id]
