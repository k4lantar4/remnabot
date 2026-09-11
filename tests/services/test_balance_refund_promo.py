"""A refunded purchase gives back the promo offer its debit consumed (F-007 part c).

``subtract_user_balance(..., consume_promo_offer=True)`` zeroes the three promo-offer fields in the
same commit as the debit. When the purchase then fails and ``refund_undelivered_debit`` returns the
money, the offer must come back too, or the user pays for a failure with their discount.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.database.crud.user import subtract_user_balance
from app.database.models import (
    PromoGroup,
    Subscription,
    Tariff,
    Transaction,
    TransactionType,
    User,
    UserPromoGroup,
)
from app.services import balance_refund
from app.services.balance_refund import (
    PromoOfferSnapshot,
    refund_undelivered_debit,
    restore_promo_offer,
    snapshot_promo_offer,
)
from tests.fixtures.sqlite_memory import memory_session


TABLES = (
    User.__table__,
    Subscription.__table__,
    Tariff.__table__,
    PromoGroup.__table__,
    UserPromoGroup.__table__,
    Transaction.__table__,
)

PRICE_TOMAN = 50_000
EXPIRES = datetime.now(UTC).replace(microsecond=0) + timedelta(days=3)


async def _user_with_offer(db, *, balance: int = 1_000_000, percent: int = 20) -> User:
    user = User(
        telegram_id=777,
        balance_kopeks=balance,
        promo_offer_discount_percent=percent,
        promo_offer_discount_source='test_offer' if percent else None,
        promo_offer_discount_expires_at=EXPIRES if percent else None,
    )
    db.add(user)
    await db.commit()
    return user


async def _reload(db, user_id: int) -> User:
    db.expire_all()
    return (await db.execute(select(User).where(User.id == user_id))).scalar_one()


def test_snapshot_is_none_without_consume_or_offer():
    user = User(promo_offer_discount_percent=20, promo_offer_discount_source='x')
    assert snapshot_promo_offer(user, consume=False) is None
    assert snapshot_promo_offer(User(promo_offer_discount_percent=0), consume=True) is None
    assert snapshot_promo_offer(User(promo_offer_discount_percent=None), consume=True) is None


def test_snapshot_keeps_the_three_fields():
    user = User(
        promo_offer_discount_percent=20, promo_offer_discount_source='s', promo_offer_discount_expires_at=EXPIRES
    )
    assert snapshot_promo_offer(user, consume=True) == PromoOfferSnapshot(percent=20, source='s', expires_at=EXPIRES)


@pytest.mark.asyncio
async def test_restore_with_none_snapshot_changes_nothing(monkeypatch):
    async with memory_session(monkeypatch, TABLES) as db:
        user = await _user_with_offer(db, percent=0)
        await restore_promo_offer(db, user, None)
        assert user.promo_offer_discount_percent == 0


@pytest.mark.asyncio
async def test_refund_with_snapshot_returns_money_and_offer(monkeypatch):
    async with memory_session(monkeypatch, TABLES) as db:
        user = await _user_with_offer(db)
        user_id = user.id
        snapshot = snapshot_promo_offer(user, consume=True)

        assert await subtract_user_balance(db, user, PRICE_TOMAN, 'buy', consume_promo_offer=True)
        charged = await _reload(db, user_id)
        assert charged.balance_kopeks == 950_000
        assert charged.promo_offer_discount_percent == 0

        assert await refund_undelivered_debit(db, charged, PRICE_TOMAN, 'refund', promo_snapshot=snapshot)

        after = await _reload(db, user_id)
        assert after.balance_kopeks == 1_000_000
        assert after.promo_offer_discount_percent == 20
        assert after.promo_offer_discount_source == 'test_offer'
        assert after.promo_offer_discount_expires_at == EXPIRES
        rows = (await db.execute(select(Transaction).where(Transaction.user_id == user_id))).scalars().all()
        assert [(r.type, r.amount_kopeks) for r in rows] == [(TransactionType.REFUND.value, PRICE_TOMAN)]


@pytest.mark.asyncio
async def test_refund_without_snapshot_leaves_offer_consumed(monkeypatch):
    async with memory_session(monkeypatch, TABLES) as db:
        user = await _user_with_offer(db)
        user_id = user.id

        assert await subtract_user_balance(db, user, PRICE_TOMAN, 'buy', consume_promo_offer=True)
        assert await refund_undelivered_debit(db, await _reload(db, user_id), PRICE_TOMAN, 'refund')

        after = await _reload(db, user_id)
        assert after.balance_kopeks == 1_000_000
        assert after.promo_offer_discount_percent == 0
        assert after.promo_offer_discount_source is None


@pytest.mark.asyncio
async def test_failed_refund_is_still_recorded(monkeypatch):
    async with memory_session(monkeypatch, TABLES) as db:
        user = await _user_with_offer(db)
        snapshot = snapshot_promo_offer(user, consume=True)

        async def _refuse(*args, **kwargs):
            return False

        recorded = []

        async def _record(user_id, amount_toman, reason, error):
            recorded.append((user_id, amount_toman, reason))

        monkeypatch.setattr('app.database.crud.user.add_user_balance', _refuse)
        monkeypatch.setattr(balance_refund, '_record_failed_refund', _record)

        assert not await refund_undelivered_debit(db, user, PRICE_TOMAN, 'refund', promo_snapshot=snapshot)
        assert recorded == [(user.id, PRICE_TOMAN, 'refund')]
