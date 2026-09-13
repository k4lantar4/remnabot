"""A charge that was committed is reported as a success, whatever fails after the commit (F-061).

``subtract_user_balance(commit=True)`` used to return False when ``db.refresh`` failed after its
commit had already persisted the debit, so a caller saw "charge failed" while the money was gone.
The cabinet and miniapp tariff switches had the same shape one level up: the switch and the debit
were committed atomically, and an exception in a post-commit step (deferred transaction side
effects, a refresh) still turned into an HTTP 500 — so the user saw an error for a switch that had
happened and been paid for, and could pay again.

Figures: a 250,000-Toman balance, a 200,000-Toman switch — exactly 200,000 leaves the balance once.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.database.crud.user import subtract_user_balance
from app.database.models import Transaction, TransactionType, User
from tests.fixtures.sqlite_memory import memory_session
from tests.services.test_affordability_toman import (
    PRICE_TOMAN,
    RICH_BALANCE,
    TABLES,
    _balance,
    _cabinet_switch_request,
    _FakePanelSync,
    _isolate,  # noqa: F401 - autouse fixture: no panel, Redis, admin bot
    _miniapp_switch_cost,
    _payments,
    _seed,
    _switch_cost,
    _tariff_id,
    miniapp_user,  # noqa: F401 - fixture
)


DEPOSIT_BALANCE = 1_000_000
CHARGE_TOMAN = 50_000


def _fail_refresh(monkeypatch, db) -> None:
    async def boom(*args, **kwargs):
        raise RuntimeError('refresh failed after commit')

    monkeypatch.setattr(db, 'refresh', boom)


async def _stored_balance(db, user_id: int) -> int:
    db.expire_all()
    return (await db.execute(select(User.balance_kopeks).where(User.id == user_id))).scalar_one()


async def _rows(db, user_id: int) -> list[tuple[str, int]]:
    result = await db.execute(select(Transaction.type, Transaction.amount_kopeks).where(Transaction.user_id == user_id))
    return [(tx_type, abs(amount)) for tx_type, amount in result.all()]


# ---------------------------------------------------------------- subtract_user_balance


@pytest.mark.asyncio
async def test_refresh_failure_after_commit_still_reports_the_charge(monkeypatch):
    async with memory_session(monkeypatch, TABLES) as db:
        user = User(id=5, telegram_id=5005, balance_kopeks=DEPOSIT_BALANCE)
        db.add(user)
        await db.commit()

        _fail_refresh(monkeypatch, db)
        charged = await subtract_user_balance(db, user, CHARGE_TOMAN, 'charge')

        assert charged is True
        assert await _stored_balance(db, 5) == DEPOSIT_BALANCE - CHARGE_TOMAN


@pytest.mark.asyncio
async def test_refresh_failure_after_commit_with_ledger_row_still_reports_the_charge(monkeypatch):
    async with memory_session(monkeypatch, TABLES) as db:
        user = User(id=5, telegram_id=5005, balance_kopeks=DEPOSIT_BALANCE)
        db.add(user)
        await db.commit()

        real_commit = db.commit

        async def commit_then_break_refresh():
            # The flushed ledger row is refreshed before the commit; only a post-commit failure counts.
            await real_commit()
            _fail_refresh(monkeypatch, db)

        monkeypatch.setattr(db, 'commit', commit_then_break_refresh)
        charged = await subtract_user_balance(
            db,
            user,
            CHARGE_TOMAN,
            'switch',
            create_transaction=True,
            transaction_type=TransactionType.SUBSCRIPTION_PAYMENT,
        )

        assert charged is True
        assert await _stored_balance(db, 5) == DEPOSIT_BALANCE - CHARGE_TOMAN
        assert await _rows(db, 5) == [('subscription_payment', CHARGE_TOMAN)]


@pytest.mark.asyncio
async def test_ledger_row_side_effects_still_fire_after_the_commit(monkeypatch):
    import app.database.crud.transaction as transaction_crud

    async with memory_session(monkeypatch, TABLES) as db:
        user = User(id=5, telegram_id=5005, balance_kopeks=DEPOSIT_BALANCE)
        db.add(user)
        await db.commit()

        side_effects = AsyncMock()
        monkeypatch.setattr(transaction_crud, 'emit_transaction_side_effects', side_effects)
        charged = await subtract_user_balance(
            db,
            user,
            CHARGE_TOMAN,
            'deposit correction',
            create_transaction=True,
            transaction_type=TransactionType.WITHDRAWAL,
        )

        assert charged is True
        side_effects.assert_awaited_once()
        assert side_effects.await_args.kwargs['amount_kopeks'] == CHARGE_TOMAN
        assert side_effects.await_args.kwargs['type'] == TransactionType.WITHDRAWAL


@pytest.mark.asyncio
async def test_failed_commit_still_reports_failure_and_keeps_the_balance(monkeypatch):
    async with memory_session(monkeypatch, TABLES) as db:
        user = User(id=5, telegram_id=5005, balance_kopeks=DEPOSIT_BALANCE)
        db.add(user)
        await db.commit()

        async def boom():
            raise RuntimeError('commit failed')

        monkeypatch.setattr(db, 'commit', boom)
        charged = await subtract_user_balance(db, user, CHARGE_TOMAN, 'charge')

        assert charged is False
        assert await _stored_balance(db, 5) == DEPOSIT_BALANCE


# ---------------------------------------------------------------- cabinet + miniapp tariff switch


def _fail_side_effects(monkeypatch) -> None:
    import app.database.crud.transaction as transaction_crud

    monkeypatch.setattr(
        transaction_crud, 'emit_transaction_side_effects', AsyncMock(side_effect=RuntimeError('side effect failed'))
    )


@pytest.mark.asyncio
async def test_cabinet_switch_succeeds_when_a_post_commit_step_fails(monkeypatch):
    from app.cabinet.routes.subscription_modules import tariff_switch

    monkeypatch.setattr(tariff_switch, 'SubscriptionService', lambda: _FakePanelSync())
    _switch_cost(monkeypatch)
    _fail_side_effects(monkeypatch)
    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, balance_toman=RICH_BALANCE)
        response = await tariff_switch.switch_tariff(
            request=_cabinet_switch_request(), user=user, db=db, subscription_id=None
        )

        assert response['success'] is True
        assert response['new_tariff_id'] == 2
        assert response['balance_kopeks'] == RICH_BALANCE - PRICE_TOMAN
        assert await _balance(db) == RICH_BALANCE - PRICE_TOMAN
        assert await _payments(db) == [('subscription_payment', PRICE_TOMAN)]
        assert await _tariff_id(db) == 2


@pytest.mark.asyncio
async def test_cabinet_switch_succeeds_when_the_response_refresh_fails(monkeypatch):
    from app.cabinet.routes.subscription_modules import tariff_switch

    monkeypatch.setattr(tariff_switch, 'SubscriptionService', lambda: _FakePanelSync())
    _switch_cost(monkeypatch)
    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, balance_toman=RICH_BALANCE)
        real_commit = db.commit

        async def commit_then_break_refresh():
            await real_commit()
            _fail_refresh(monkeypatch, db)

        monkeypatch.setattr(db, 'commit', commit_then_break_refresh)
        response = await tariff_switch.switch_tariff(
            request=_cabinet_switch_request(), user=user, db=db, subscription_id=None
        )

    assert response['success'] is True
    assert response['new_tariff_id'] == 2
    assert response['balance_kopeks'] == RICH_BALANCE - PRICE_TOMAN


@pytest.mark.asyncio
async def test_miniapp_switch_succeeds_when_a_post_commit_step_fails(monkeypatch, miniapp_user):
    from app.webapi.schemas.miniapp import MiniAppTariffSwitchRequest

    _miniapp_switch_cost(monkeypatch, miniapp_user)
    _fail_side_effects(monkeypatch)
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=RICH_BALANCE)
        response = await miniapp_user.switch_tariff_endpoint(
            MiniAppTariffSwitchRequest(init_data='x', tariff_id=2), db=db
        )

        assert response.success is True
        assert response.balance_kopeks == RICH_BALANCE - PRICE_TOMAN
        assert await _balance(db) == RICH_BALANCE - PRICE_TOMAN
        assert await _payments(db) == [('subscription_payment', PRICE_TOMAN)]
        assert await _tariff_id(db) == 2
