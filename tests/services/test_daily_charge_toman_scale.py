"""Recurring daily charges take the Toman amount off the Toman balance.

``daily_price_kopeks`` is a catalog price (Toman x 100, shown via ``format_price``), while
``User.balance_kopeks`` holds raw Toman. The first-day activation converts with
``catalog_price_in_toman``; the recurring charges (scheduler, cabinet / Mini App / bot resume,
resume after a top-up) passed the catalog number straight to ``subtract_user_balance`` and
compared it with the balance. A 10,000 Toman/day tariff therefore charged 1,000,000 Toman a
day, or never found enough balance. Found live: tariff 9 (1,000,000 kopeks) on a 19,981,200
Toman balance, two subscriptions due for their first recurring charge.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.config import settings
from app.database.models import Base, Subscription, SubscriptionStatus, Tariff, User
from tests.fixtures.sqlite_memory import memory_session


TABLES = list(Base.metadata.sorted_tables)
ROOT = Path(__file__).resolve().parents[2]

# Stored and charged are one number since revision 0115.
DAILY_PRICE_TOMAN = 10_000  # per day
DAILY_PRICE_KOPEKS = DAILY_PRICE_TOMAN


class _FakePanelSync:
    async def update_remnawave_user(self, db, subscription, **kwargs):
        return SimpleNamespace(id=9001, used_traffic_bytes=0)

    async def create_remnawave_user(self, db, subscription, **kwargs):
        return SimpleNamespace(id=9001, used_traffic_bytes=0)


def _rows(*, balance_toman: int, status: str) -> list:
    now = datetime.now(UTC)
    active = status == SubscriptionStatus.ACTIVE.value
    return [
        User(
            id=1,
            telegram_id=1001,
            first_name='U',
            language='fa',
            status='active',
            balance_kopeks=balance_toman,
            remnawave_id=9001,
        ),
        Tariff(
            id=1,
            name='daily',
            description='',
            is_active=True,
            is_daily=True,
            daily_price_kopeks=DAILY_PRICE_KOPEKS,
            traffic_limit_gb=100,
            traffic_reset_mode='NO_RESET',
            device_limit=1,
            allowed_squads=['squad-1'],
            display_order=1,
        ),
        Subscription(
            id=10,
            remnawave_short_id='day1',
            remnawave_id=9001,
            user_id=1,
            status=status,
            is_trial=False,
            is_daily_paused=False,
            start_date=now - timedelta(days=5),
            end_date=now + timedelta(hours=2) if active else now - timedelta(hours=1),
            last_daily_charge_at=now - timedelta(days=1, hours=1),
            updated_at=now - timedelta(hours=1),
            traffic_limit_gb=100,
            traffic_used_gb=1.0,
            device_limit=1,
            tariff_id=1,
            connected_squads=['squad-1'],
        ),
    ]


@pytest.fixture(autouse=True)
def _no_reset(monkeypatch):
    monkeypatch.setattr(settings, 'RESET_TRAFFIC_ON_PAYMENT', False)


async def _scheduler_charge(db, monkeypatch, *, balance_toman: int) -> str:
    import app.services.subscription_renewal_service as renewal_module
    import app.services.subscription_service as subscription_service_module
    from app.services.daily_subscription_service import DailySubscriptionService

    monkeypatch.setattr(subscription_service_module, 'SubscriptionService', lambda: _FakePanelSync())
    monkeypatch.setattr(renewal_module, 'with_admin_notification_service', AsyncMock(return_value=None))
    db.add_all(_rows(balance_toman=balance_toman, status=SubscriptionStatus.ACTIVE.value))
    await db.commit()

    service = DailySubscriptionService()
    service._bot = None
    subscription = await service._reload_daily_subscription(db, 10)
    return await service._process_single_charge(db, subscription)


@pytest.mark.asyncio
async def test_scheduler_charges_the_toman_amount(monkeypatch):
    async with memory_session(monkeypatch, TABLES) as db:
        result = await _scheduler_charge(db, monkeypatch, balance_toman=50_000)
        user = await db.get(User, 1)

    assert result == 'charged'
    assert user.balance_kopeks == 50_000 - DAILY_PRICE_TOMAN


@pytest.mark.asyncio
async def test_scheduler_suspends_when_the_toman_amount_is_not_covered(monkeypatch):
    async with memory_session(monkeypatch, TABLES) as db:
        result = await _scheduler_charge(db, monkeypatch, balance_toman=5_000)
        user = await db.get(User, 1)

    assert result == 'suspended'
    assert user.balance_kopeks == 5_000


@pytest.mark.asyncio
async def test_cabinet_resume_charges_the_toman_amount(monkeypatch):
    import app.cabinet.routes.subscription_modules.daily as cabinet_daily

    monkeypatch.setattr(cabinet_daily, 'SubscriptionService', lambda: _FakePanelSync())
    async with memory_session(monkeypatch, TABLES) as db:
        db.add_all(_rows(balance_toman=50_000, status=SubscriptionStatus.DISABLED.value))
        await db.commit()
        user = await db.get(User, 1)

        await cabinet_daily.toggle_subscription_pause(user=user, db=db, subscription_id=10)
        user = await db.get(User, 1)

    assert user.balance_kopeks == 50_000 - DAILY_PRICE_TOMAN


@pytest.mark.asyncio
async def test_miniapp_resume_charges_the_toman_amount(monkeypatch):
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    import app.services.subscription_service as subscription_service_module
    from app.webapi.routes import miniapp
    from app.webapi.schemas.miniapp import MiniAppDailySubscriptionToggleRequest

    monkeypatch.setattr(subscription_service_module, 'SubscriptionService', lambda: _FakePanelSync())
    async with memory_session(monkeypatch, TABLES) as db:
        db.add_all(_rows(balance_toman=50_000, status=SubscriptionStatus.DISABLED.value))
        await db.commit()
        loaded = await db.execute(select(User).options(selectinload(User.subscriptions)).where(User.id == 1))
        user = loaded.scalar_one()

        async def _fake_authorize(init_data, session):
            return user

        monkeypatch.setattr(miniapp, '_authorize_miniapp_user', _fake_authorize)
        payload = MiniAppDailySubscriptionToggleRequest(init_data='stub', subscriptionId=10)
        await miniapp.toggle_daily_subscription_pause_endpoint(payload=payload, db=db)
        user = await db.get(User, 1)

    assert user.balance_kopeks == 50_000 - DAILY_PRICE_TOMAN


@pytest.mark.asyncio
async def test_topup_resume_charges_the_toman_amount(monkeypatch):
    import app.cabinet.routes.websocket as websocket_module
    import app.services.subscription_auto_purchase_service as auto_module
    from app.config import Settings

    monkeypatch.setattr(Settings, 'is_multi_tariff_enabled', lambda self: True)
    monkeypatch.setattr(auto_module, 'SubscriptionService', lambda: _FakePanelSync())
    monkeypatch.setattr(websocket_module, 'notify_user_subscription_renewed', AsyncMock())
    monkeypatch.setattr(auto_module, '_notify_email_user_auto_purchase', AsyncMock())
    async with memory_session(monkeypatch, TABLES) as db:
        db.add_all(_rows(balance_toman=50_000, status=SubscriptionStatus.DISABLED.value))
        await db.commit()
        user = await db.get(User, 1)

        resumed = await auto_module.try_resume_disabled_daily_after_topup(db, user, bot=None)
        user = await db.get(User, 1)

    assert resumed is True
    assert user.balance_kopeks == 50_000 - DAILY_PRICE_TOMAN


# file -> function that moves balance for a recurring daily charge
DAILY_CHARGE_SITES = {
    'app/services/daily_subscription_service.py': '_process_single_charge',
    'app/cabinet/routes/subscription_modules/daily.py': 'toggle_subscription_pause',
    'app/webapi/routes/miniapp.py': 'toggle_daily_subscription_pause_endpoint',
    'app/handlers/subscription/purchase.py': 'handle_toggle_daily_subscription_pause',
    'app/services/subscription_auto_purchase_service.py': 'try_resume_disabled_daily_after_topup',
}
BALANCE_CALLS = {'subtract_user_balance', 'add_user_balance'}


def _function(relative: str, name: str) -> ast.AST:
    tree = ast.parse((ROOT / relative).read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f'{relative}: function {name} not found; update this guard')


def _amount_argument(call: ast.Call) -> ast.expr | None:
    for keyword in call.keywords:
        if keyword.arg == 'amount_kopeks':
            return keyword.value
    return call.args[2] if len(call.args) > 2 else None


@pytest.mark.parametrize(('relative', 'function_name'), DAILY_CHARGE_SITES.items())
def test_every_daily_charge_site_still_moves_the_balance(relative, function_name):
    """The daily fee is charged and refunded at each of these sites.

    This guard used to assert that none of them passed ``daily_price`` — the catalog variable — to a
    balance call, because doing so charged 100x. Revision ``0115`` put ``daily_price_kopeks`` on the
    Toman scale, so ``daily_price`` is the right thing to pass and the old assertion would now be
    backwards. "Nothing converts anywhere" is asserted once, in ``test_phase_c_single_scale.py``.

    What is still worth pinning here is the site list itself: if a charge path stops moving the
    balance, this list is stale and the rest of the file is testing nothing.
    """
    func = _function(relative, function_name)
    calls = [
        node
        for node in ast.walk(func)
        if isinstance(node, ast.Call)
        and (node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, 'id', None))
        in BALANCE_CALLS
    ]
    assert calls, f'{relative}:{function_name}: no balance call found; guard is stale'
