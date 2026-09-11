"""Cabinet purchase and background services: a refunded debit gives back the consumed promo offer.

F-007 part c, the non-handler paths. The cabinet ``/purchase-tariff`` is the one users actually hit
(the bot runs in cabinet mode): its delivery fails after the debit committed, ``_refund_charge``
returns the 200,000 Toman, and the 20% offer the debit zeroed must come back with it. Same for the
scheduled autopay and the daily-tariff auto-purchase after a top-up.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.database.models import User
from tests.fixtures.sqlite_memory import memory_session
from tests.handlers.test_promo_offer_refund_restore import (
    EXPECTED_OFFER,
    OFFER_EXPIRES,
    OFFER_PERCENT,
    OFFER_SOURCE,
    _offer,
    _pricing_with_offer,
)
from tests.services.test_affordability_toman import (  # noqa: F401 - _isolate is an autouse fixture
    PRICE_TOMAN,
    RICH_BALANCE,
    TABLES,
    _autopay_service,
    _balance,
    _isolate,
    _loaded_user,
    _payments,
    _seed,
    _seed_autopay,
)
from tests.services.test_tariff_purchase_toman import _seed_auto, auto  # noqa: F401 - auto is a fixture


async def _give_offer(db) -> None:
    user = await db.get(User, 1)
    user.promo_offer_discount_percent = OFFER_PERCENT
    user.promo_offer_discount_source = OFFER_SOURCE
    user.promo_offer_discount_expires_at = OFFER_EXPIRES
    await db.commit()


# ---------------------------------------------------------------- cabinet /purchase-tariff


@pytest.mark.parametrize(
    ('error', 'status_code'),
    [(RuntimeError('db down'), 500), (IntegrityError('insert', {}, Exception('uq')), 409)],
    ids=['creation fails', 'tariff already active'],
)
@pytest.mark.asyncio
async def test_cabinet_purchase_refund_restores_the_promo_offer(monkeypatch, error, status_code):
    from app.cabinet.routes.subscription_modules import purchase as cabinet_purchase
    from app.cabinet.schemas.subscription import TariffPurchaseRequest

    _pricing_with_offer(monkeypatch)
    monkeypatch.setattr(cabinet_purchase, 'create_paid_subscription', AsyncMock(side_effect=error))
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=RICH_BALANCE, with_subscription=False)
        await _give_offer(db)
        with pytest.raises(HTTPException) as caught:
            await cabinet_purchase.purchase_tariff(
                TariffPurchaseRequest(tariff_id=2, period_days=30), user=await _loaded_user(db), db=db
            )

        assert caught.value.status_code == status_code
        assert await _balance(db) == RICH_BALANCE
        assert ('refund', PRICE_TOMAN) in await _payments(db)
        assert await _offer(db) == EXPECTED_OFFER


# ---------------------------------------------------------------- monitoring_service._process_autopayments


@pytest.mark.asyncio
async def test_autopay_refund_restores_the_promo_offer(monkeypatch):
    monitoring, service = _autopay_service(monkeypatch)
    monkeypatch.setattr(monitoring, 'extend_subscription', AsyncMock(side_effect=RuntimeError('db down')))
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_autopay(db, balance_toman=RICH_BALANCE)
        await _give_offer(db)
        await service._process_autopayments(db)

        assert await _balance(db) == RICH_BALANCE
        assert await _payments(db) == [('refund', PRICE_TOMAN)]
        assert await _offer(db) == EXPECTED_OFFER


# ---------------------------------------------------------------- subscription_auto_purchase_service


@pytest.mark.asyncio
async def test_auto_daily_tariff_refund_restores_the_promo_offer(monkeypatch, auto):
    import app.database.crud.subscription as subscription_crud

    monkeypatch.setattr(subscription_crud, 'create_paid_subscription', AsyncMock(side_effect=RuntimeError('db down')))
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_auto(db, balance_toman=RICH_BALANCE, with_subscription=False)
        await _give_offer(db)
        assert await auto._auto_purchase_daily_tariff(db, await _loaded_user(db), {'tariff_id': 3}) is False

        assert await _balance(db) == RICH_BALANCE
        # the first day carries the 20% offer: 200,000 - 20% = 160,000 debited and refunded
        assert await _payments(db) == [('refund', PRICE_TOMAN * (100 - OFFER_PERCENT) // 100)]
        assert await _offer(db) == EXPECTED_OFFER
