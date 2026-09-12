"""F-081: get_subscription_by_id_for_user must not unload the user's promo groups.

The cabinet resolves the user with get_user_by_id (promo groups eagerly loaded), then
resolve_subscription -> get_subscription_by_id_for_user re-selects that same User with
populate_existing=True. Without loader chains for the promo relationships they come back
unloaded and pricing (_apply_addon_discount -> User.get_primary_promo_group) lazy-loads in
async -> MissingGreenlet -> 500 on /cabinet/subscription/traffic-packages.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.database.crud.subscription import get_subscription_by_id_for_user
from app.database.crud.user import get_user_by_id
from app.database.models import (
    PromoGroup,
    ServerSquad,
    Subscription,
    SubscriptionStatus,
    Tariff,
    User,
    UserPromoGroup,
    UserStatus,
    server_squad_promo_groups,
    tariff_promo_groups,
)
from tests.fixtures.sqlite_memory import memory_session


TABLES = (
    PromoGroup.__table__,
    # PromoGroup.server_squads is lazy='selectin'.
    ServerSquad.__table__,
    server_squad_promo_groups,
    Tariff.__table__,
    tariff_promo_groups,
    User.__table__,
    Subscription.__table__,
    UserPromoGroup.__table__,
)


async def _seed(db, *, via_link_table: bool) -> tuple[int, int, int]:
    group = PromoGroup(name='Resellers', traffic_discount_percent=20)
    db.add(group)
    await db.flush()

    user = User(
        telegram_id=7833,
        username='buyer',
        first_name='Buyer',
        status=UserStatus.ACTIVE.value,
        language='fa',
        balance_kopeks=1_000_000,
        promo_group_id=None if via_link_table else group.id,
    )
    db.add(user)
    await db.flush()

    if via_link_table:
        db.add(UserPromoGroup(user_id=user.id, promo_group_id=group.id))

    now = datetime.now(UTC)
    sub = Subscription(
        user_id=user.id,
        status=SubscriptionStatus.ACTIVE.value,
        is_trial=False,
        start_date=now - timedelta(days=1),
        end_date=now + timedelta(days=29),
    )
    db.add(sub)
    await db.commit()
    ids = (user.id, sub.id, group.id)
    db.expunge_all()
    return ids


@pytest.mark.asyncio
@pytest.mark.parametrize('via_link_table', [True, False], ids=['user_promo_groups', 'legacy_promo_group'])
async def test_promo_group_stays_loaded_after_fetching_subscription_by_id(monkeypatch, via_link_table):
    async with memory_session(monkeypatch, TABLES) as db:
        user_id, sub_id, group_id = await _seed(db, via_link_table=via_link_table)

        user = await get_user_by_id(db, user_id)
        assert user is not None

        subscription = await get_subscription_by_id_for_user(db, sub_id, user_id)

        assert subscription is not None
        assert subscription.user is user
        primary = user.get_primary_promo_group()
        assert primary is not None
        assert primary.id == group_id
        assert primary.get_discount_percent('traffic') == 20
