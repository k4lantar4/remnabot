"""Bot purchase flows: a refunded debit gives back the promo offer it consumed (F-007 part c).

Each flow debits with ``consume_promo_offer=True`` (which zeroes the user's 20% offer in the debit's
commit), then its delivery step fails and the money is refunded. Before the fix the user kept the
money but lost the offer; ``handle_custom_confirm`` / ``confirm_tariff_purchase`` already restored it.
Numbers and harness from ``tests/services/test_tariff_purchase_toman.py``: 250,000 Toman balance,
200,000 Toman price (catalog 20,000,000).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.database.models import User
from app.services.pricing_engine import PricingEngine, TariffSwitchResult
from tests.fixtures.sqlite_memory import memory_session
from tests.services.test_tariff_purchase_toman import (  # noqa: F401 - bot_tariffs, simple, _isolate are fixtures
    PRICE_KOPEKS,
    PRICE_TOMAN,
    RICH_BALANCE,
    TABLES,
    _add_daily_tariff,
    _balance,
    _callback,
    _failing_commit,
    _isolate,
    _loaded_user,
    _payments,
    _seed,
    _simple_state,
    _state,
    bot_tariffs,
    simple,
)


OFFER_PERCENT = 20
OFFER_SOURCE = 'test_offer'
OFFER_EXPIRES = datetime.now(UTC).replace(microsecond=0) + timedelta(days=3)


def _pricing_with_offer(monkeypatch) -> None:
    """Every price engine answer says a promo offer was applied, so the flows debit with consume_promo_offer."""

    async def purchase_price(self, tariff, period_days, *, device_limit=None, user=None, **kwargs):
        return SimpleNamespace(
            final_total=PRICE_KOPEKS,
            original_total=PRICE_KOPEKS,
            promo_group_discount=0,
            promo_offer_discount=1,
            breakdown={'offer_discount_pct': OFFER_PERCENT},
        )

    def switch_cost(self, current_tariff, new_tariff, remaining_days, *, user=None):
        return TariffSwitchResult(
            upgrade_cost=PRICE_KOPEKS,
            is_upgrade=True,
            raw_cost=PRICE_KOPEKS,
            group_discount_pct=0,
            offer_discount_pct=OFFER_PERCENT,
        )

    monkeypatch.setattr(PricingEngine, 'calculate_tariff_purchase_price', purchase_price)
    monkeypatch.setattr(PricingEngine, 'calculate_tariff_switch_cost', switch_cost)


async def _seed_with_offer(db, *, with_subscription: bool = True, daily: bool = False) -> None:
    user = await _seed(db, balance_toman=RICH_BALANCE, with_subscription=with_subscription)
    user.promo_offer_discount_percent = OFFER_PERCENT
    user.promo_offer_discount_source = OFFER_SOURCE
    user.promo_offer_discount_expires_at = OFFER_EXPIRES
    await db.commit()
    if daily:
        await _add_daily_tariff(db)


async def _offer(db) -> tuple:
    db.expire_all()
    row = (
        await db.execute(
            select(
                User.promo_offer_discount_percent,
                User.promo_offer_discount_source,
                User.promo_offer_discount_expires_at,
            ).where(User.id == 1)
        )
    ).one()
    return tuple(row)


EXPECTED_OFFER = (OFFER_PERCENT, OFFER_SOURCE, OFFER_EXPIRES)


# ---------------------------------------------------------------- tariff_purchase.py


TARIFF_FLOWS = {
    # name: (handler, callback data, seed kwargs, how the delivery fails)
    'renewal': ('confirm_tariff_extend', 'tariff_ext_confirm:10:1:30', {}, 'extend'),
    'switch': ('confirm_tariff_switch', 'tariff_sw_confirm:2:30', {}, 'extend'),
    'instant switch upgrade': ('confirm_instant_switch', 'instant_sw_confirm:2', {}, 'commit'),
    'daily purchase': (
        'confirm_daily_tariff_purchase',
        'daily_tariff_confirm:3',
        {'with_subscription': False, 'daily': True},
        'create',
    ),
    'daily switch': ('confirm_daily_tariff_switch', 'daily_tariff_sw_confirm:3', {'daily': True}, 'commit'),
}


@pytest.mark.parametrize('flow', sorted(TARIFF_FLOWS))
@pytest.mark.asyncio
async def test_bot_tariff_flow_refund_restores_the_promo_offer(monkeypatch, bot_tariffs, flow):
    name, data, seed_kwargs, failure = TARIFF_FLOWS[flow]
    _pricing_with_offer(monkeypatch)
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_with_offer(db, **seed_kwargs)
        if failure == 'extend':
            monkeypatch.setattr(bot_tariffs, 'extend_subscription', AsyncMock(side_effect=RuntimeError('db down')))
        elif failure == 'create':
            monkeypatch.setattr(bot_tariffs, 'create_paid_subscription', AsyncMock(side_effect=RuntimeError('db down')))
        else:
            _failing_commit(monkeypatch, db, failing_call=2)  # 1: the debit, 2: the delivery
        await getattr(bot_tariffs, name)(_callback(data), await _loaded_user(db), db, _state())

        assert await _balance(db) == RICH_BALANCE
        assert await _payments(db) == [('refund', PRICE_TOMAN)]
        assert await _offer(db) == EXPECTED_OFFER


# ---------------------------------------------------------------- simple_subscription.py / purchase.py


SIMPLE_FLOWS = {
    # handler, with an existing subscription
    'pay with balance': ('handle_simple_subscription_pay_with_balance', False),
    'confirm over an active subscription': ('confirm_simple_subscription_purchase', True),
}


@pytest.mark.parametrize('shape', ['no subscription back', 'delivery raises'])
@pytest.mark.parametrize('flow', sorted(SIMPLE_FLOWS))
@pytest.mark.asyncio
async def test_simple_subscription_refund_restores_the_promo_offer(monkeypatch, simple, flow, shape):
    import app.database.crud.subscription as subscription_crud

    name, with_subscription = SIMPLE_FLOWS[flow]
    if shape == 'no subscription back':  # the inline add_user_balance refund
        monkeypatch.setattr(subscription_crud, 'create_paid_subscription', AsyncMock(return_value=None))
        with_subscription = False
    else:  # the refund_undelivered_debit refund in the except
        failing = AsyncMock(side_effect=RuntimeError('db down'))
        monkeypatch.setattr(subscription_crud, 'create_paid_subscription', failing)
        monkeypatch.setattr(subscription_crud, 'extend_subscription', failing)
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_with_offer(db, with_subscription=with_subscription)
        await getattr(simple, name)(_callback('pay'), await _loaded_user(db), _simple_state(), db)

        assert await _balance(db) == RICH_BALANCE
        assert ('refund', PRICE_TOMAN) in await _payments(db)
        assert await _offer(db) == EXPECTED_OFFER


@pytest.mark.asyncio
async def test_simple_subscription_extension_refund_restores_the_promo_offer(monkeypatch, simple):
    from app.database.models import Subscription
    from app.handlers.subscription import purchase

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_with_offer(db)
        _failing_commit(monkeypatch, db, failing_call=2)  # 1: the debit, 2: the extension, 3: the refund
        await purchase._extend_existing_subscription(
            _callback('simple_subscription_purchase'),
            await _loaded_user(db),
            db,
            await db.get(Subscription, 10),
            30,
            1,
            0,
            'squad-1',
        )

        assert await _balance(db) == RICH_BALANCE
        assert await _payments(db) == [('refund', PRICE_TOMAN)]
        assert await _offer(db) == EXPECTED_OFFER
