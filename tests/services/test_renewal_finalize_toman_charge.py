"""Renewing from the wallet takes the Toman price off the Toman balance.

``SubscriptionRenewalService.finalize()`` gets ``pricing.final_total`` on the catalog scale
(price_kopeks, Toman x 100). ``User.balance_kopeks`` holds raw Toman (Phase B). The cabinet and the
CryptoBot webhook pass ``charge_balance_amount`` in Toman, but the bot renewal, the main-menu
activate button and the miniapp rely on the default, which was ``final_total`` itself: a
200,000-Toman renewal tried to debit 20,000,000. Most users then hit «Ошибка списания средств»; a
user holding 100x the price was charged 100x.

The transaction row stays on the catalog scale (``subscription_payment`` is a catalog type), like
every other balance purchase records it. Phase C is not in scope here.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

import app.services.subscription_renewal_service as renewal_module
from app.config import Settings, settings
from app.database.models import Base, PaymentMethod, Subscription, SubscriptionStatus, Transaction, User
from app.services.pricing_engine import PricingEngine, RenewalPricing
from app.services.subscription_renewal_service import SubscriptionRenewalChargeError, SubscriptionRenewalService
from tests.fixtures.sqlite_memory import memory_session


TABLES = list(Base.metadata.sorted_tables)

# A 200,000-Toman 30-day renewal: stored, charged and recorded as the same number.
RENEWAL_TOMAN = 200_000
RENEWAL_KOPEKS = RENEWAL_TOMAN


class _FakePanelSync:
    async def update_remnawave_user(self, db, subscription, **kwargs):
        return SimpleNamespace(id=9001, used_traffic_bytes=0)

    async def create_remnawave_user(self, db, subscription, **kwargs):
        return SimpleNamespace(id=9001, used_traffic_bytes=0)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """No panel, admin bot, Redis or multi-tariff branching."""
    import app.services.pricing_engine as pricing_module
    from app.services.user_cart_service import user_cart_service

    # Other modules patch the pricing_engine singleton instance; drop any leftover attribute so the
    # class-level patch below is the one the handlers see.
    pricing_module.pricing_engine.__dict__.pop('calculate_renewal_price', None)

    monkeypatch.setattr(settings, 'RESET_TRAFFIC_ON_PAYMENT', False, raising=False)
    monkeypatch.setattr(settings, 'RESET_DEVICES_ON_RENEWAL', False, raising=False)
    monkeypatch.setattr(settings, 'ADMIN_NOTIFICATIONS_ENABLED', False, raising=False)
    monkeypatch.setattr(Settings, 'is_multi_tariff_enabled', lambda self: False)
    monkeypatch.setattr(Settings, 'is_tariffs_mode', lambda self: False)
    monkeypatch.setattr(renewal_module, 'SubscriptionService', lambda: _FakePanelSync())
    monkeypatch.setattr(user_cart_service, 'save_user_cart', AsyncMock(return_value=True))


def _pricing(final_total: int = RENEWAL_KOPEKS, period_days: int = 30) -> RenewalPricing:
    return RenewalPricing(
        base_price=final_total,
        servers_price=0,
        traffic_price=0,
        devices_price=0,
        promo_group_discount=0,
        promo_offer_discount=0,
        final_total=final_total,
        period_days=period_days,
        is_tariff_mode=False,
        breakdown={},
    )


async def _seed(db, *, balance_toman: int, status: str = SubscriptionStatus.ACTIVE.value) -> tuple[User, Subscription]:
    now = datetime.now(UTC)
    expired = status == SubscriptionStatus.EXPIRED.value
    db.add_all(
        [
            User(
                id=1,
                telegram_id=1001,
                first_name='U',
                language='fa',
                status='active',
                balance_kopeks=balance_toman,
                remnawave_id=9001,
            ),
            Subscription(
                id=10,
                remnawave_short_id='ren1',
                remnawave_id=9001,
                user_id=1,
                status=status,
                is_trial=False,
                start_date=now - timedelta(days=40),
                end_date=now - timedelta(days=1) if expired else now + timedelta(days=5),
                updated_at=now - timedelta(hours=1),
                traffic_limit_gb=100,
                traffic_used_gb=1.0,
                purchased_traffic_gb=0,
                device_limit=1,
                tariff_id=None,
                connected_squads=['squad-1'],
            ),
        ]
    )
    await db.commit()
    return await db.get(User, 1), await db.get(Subscription, 10)


async def _balance(db) -> int:
    result = await db.execute(select(User.balance_kopeks).where(User.id == 1))
    return result.scalar_one()


async def _payments(db) -> list[tuple[str, int]]:
    result = await db.execute(select(Transaction.type, Transaction.amount_kopeks).where(Transaction.user_id == 1))
    return [(tx_type, abs(amount)) for tx_type, amount in result.all()]


async def _end_date(db) -> datetime:
    result = await db.execute(select(Subscription.end_date).where(Subscription.id == 10))
    value = result.scalar_one()
    return value if value.tzinfo else value.replace(tzinfo=UTC)


# ---------------------------------------------------------------- finalize()


@pytest.mark.asyncio
async def test_finalize_default_charge_is_the_toman_price(monkeypatch):
    async with memory_session(monkeypatch, TABLES) as db:
        user, subscription = await _seed(db, balance_toman=1_000_000)

        result = await SubscriptionRenewalService().finalize(
            db, user, subscription, _pricing(), payment_method=PaymentMethod.BALANCE
        )

        assert await _balance(db) == 1_000_000 - RENEWAL_TOMAN
        # the ledger row keeps the catalog scale (subscription_payment is a catalog type)
        assert await _payments(db) == [('subscription_payment', RENEWAL_KOPEKS)]

    assert result.charged_from_balance_kopeks == RENEWAL_TOMAN
    assert result.total_amount_kopeks == RENEWAL_KOPEKS


@pytest.mark.asyncio
async def test_finalize_renews_when_the_balance_covers_only_the_toman_price(monkeypatch):
    """250,000 Toman covers a 200,000-Toman renewal; the old default demanded 20,000,000."""
    async with memory_session(monkeypatch, TABLES) as db:
        user, subscription = await _seed(db, balance_toman=250_000, status=SubscriptionStatus.EXPIRED.value)

        await SubscriptionRenewalService().finalize(db, user, subscription, _pricing())

        assert await _balance(db) == 50_000
        assert await _end_date(db) > datetime.now(UTC) + timedelta(days=29)


@pytest.mark.asyncio
async def test_finalize_respects_an_explicit_toman_charge(monkeypatch):
    """The CryptoBot webhook charges only the part the invoice did not cover."""
    async with memory_session(monkeypatch, TABLES) as db:
        user, subscription = await _seed(db, balance_toman=1_000_000)

        result = await SubscriptionRenewalService().finalize(
            db, user, subscription, _pricing(), charge_balance_amount=50_000
        )

        assert await _balance(db) == 950_000
        assert await _payments(db) == [('subscription_payment', RENEWAL_KOPEKS)]

    assert result.charged_from_balance_kopeks == 50_000


@pytest.mark.asyncio
async def test_finalize_caps_an_explicit_charge_at_the_toman_price(monkeypatch):
    async with memory_session(monkeypatch, TABLES) as db:
        user, subscription = await _seed(db, balance_toman=30_000_000)

        result = await SubscriptionRenewalService().finalize(
            db, user, subscription, _pricing(), charge_balance_amount=RENEWAL_KOPEKS
        )

        assert await _balance(db) == 30_000_000 - RENEWAL_TOMAN

    assert result.charged_from_balance_kopeks == RENEWAL_TOMAN


@pytest.mark.asyncio
async def test_finalize_still_refuses_a_balance_below_the_toman_price(monkeypatch):
    async with memory_session(monkeypatch, TABLES) as db:
        user, subscription = await _seed(db, balance_toman=150_000)

        with pytest.raises(SubscriptionRenewalChargeError):
            await SubscriptionRenewalService().finalize(db, user, subscription, _pricing())

        assert await _balance(db) == 150_000
        assert await _payments(db) == []


@pytest.mark.asyncio
async def test_finalize_refunds_the_toman_charge_when_extension_fails(monkeypatch):
    async def broken_extend(db, subscription, days):
        raise RuntimeError('panel down')

    monkeypatch.setattr(renewal_module, 'extend_subscription', broken_extend)
    async with memory_session(monkeypatch, TABLES) as db:
        user, subscription = await _seed(db, balance_toman=1_000_000)

        with pytest.raises(RuntimeError):
            await SubscriptionRenewalService().finalize(db, user, subscription, _pricing())

        assert await _balance(db) == 1_000_000
        # the compensating refund is a balance-scale row of exactly the Toman charge
        assert await _payments(db) == [('refund', RENEWAL_TOMAN)]


# ---------------------------------------------------------------- callers that rely on the default


def _callback(data: str) -> SimpleNamespace:
    return SimpleNamespace(
        data=data,
        answer=AsyncMock(),
        message=SimpleNamespace(edit_text=AsyncMock(), answer=AsyncMock()),
    )


def _alert_text(callback) -> str:
    args, kwargs = callback.answer.await_args
    return kwargs.get('text') or (args[0] if args else '')


@pytest.mark.asyncio
async def test_miniapp_balance_renewal_debits_the_toman_price(monkeypatch):
    from app.webapi.routes import miniapp
    from app.webapi.schemas.miniapp import MiniAppSubscriptionRenewalRequest

    async def fake_calculate(self, db, subscription, period_days, *, user=None):
        return _pricing(period_days=period_days)

    monkeypatch.setattr(settings, 'SALES_MODE', 'classic', raising=False)
    monkeypatch.setattr(Settings, 'get_available_renewal_periods', lambda self: [30])
    monkeypatch.setattr(PricingEngine, 'calculate_renewal_price', fake_calculate)
    monkeypatch.setattr(miniapp, '_validate_subscription_id', lambda *args, **kwargs: None)

    async with memory_session(monkeypatch, TABLES) as db:
        user, subscription = await _seed(db, balance_toman=250_000)

        async def fake_authorize(init_data, session):
            return user

        monkeypatch.setattr(miniapp, '_authorize_miniapp_user', fake_authorize)
        monkeypatch.setattr(miniapp, '_ensure_paid_subscription', lambda *args, **kwargs: subscription)

        response = await miniapp.submit_subscription_renewal_endpoint(
            MiniAppSubscriptionRenewalRequest(initData='init', subscriptionId=10, periodId='days:30'), db=db
        )

        assert await _balance(db) == 50_000
        assert await _payments(db) == [('subscription_payment', RENEWAL_KOPEKS)]

    assert response.balance_kopeks == 50_000
    assert settings.format_price(RENEWAL_KOPEKS) in (response.message or '')


@pytest.mark.asyncio
async def test_bot_renewal_debits_the_toman_price(monkeypatch):
    from app.database.crud.user import lock_user_for_pricing
    from app.handlers.subscription import purchase

    async def fake_calculate(self, db, subscription, period_days, *, user=None):
        return _pricing(period_days=period_days)

    monkeypatch.setattr(Settings, 'get_available_renewal_periods', lambda self: [30])
    monkeypatch.setattr(PricingEngine, 'calculate_renewal_price', fake_calculate)

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=250_000)
        db_user = await lock_user_for_pricing(db, 1)
        callback = _callback('extend_period_30')

        await purchase.confirm_extend_subscription(callback, db_user, db)

        assert await _balance(db) == 50_000
        assert await _payments(db) == [('subscription_payment', RENEWAL_KOPEKS)]

    success_text = callback.message.edit_text.await_args.args[0]
    assert purchase.get_texts('fa').format_price(RENEWAL_KOPEKS) in success_text


@pytest.mark.asyncio
async def test_bot_renewal_precheck_reports_the_toman_shortfall(monkeypatch):
    from app.database.crud.user import lock_user_for_pricing
    from app.handlers.subscription import purchase

    async def fake_calculate(self, db, subscription, period_days, *, user=None):
        return _pricing(period_days=period_days)

    monkeypatch.setattr(Settings, 'get_available_renewal_periods', lambda self: [30])
    monkeypatch.setattr(PricingEngine, 'calculate_renewal_price', fake_calculate)

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=150_000)
        db_user = await lock_user_for_pricing(db, 1)
        callback = _callback('extend_period_30')

        await purchase.confirm_extend_subscription(callback, db_user, db)

        assert await _balance(db) == 150_000
        assert await _payments(db) == []

    shortfall_text = callback.message.edit_text.await_args.args[0]
    assert purchase.get_texts('fa').format_balance(50_000, round_kopeks=False) in shortfall_text


@pytest.mark.asyncio
async def test_activate_button_renews_for_the_toman_price(monkeypatch):
    from app.database.crud.user import lock_user_for_pricing
    from app.handlers import menu

    async def fake_calculate(self, db, subscription, period_days, *, user=None):
        return _pricing(period_days=period_days)

    monkeypatch.setattr(Settings, 'get_available_subscription_periods', lambda self: [30])
    monkeypatch.setattr(PricingEngine, 'calculate_renewal_price', fake_calculate)

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=250_000, status=SubscriptionStatus.EXPIRED.value)
        db_user = await lock_user_for_pricing(db, 1)
        callback = _callback('activate_button')

        await menu.handle_activate_button(callback, db_user, db)

        assert await _balance(db) == 50_000
        assert await _payments(db) == [('subscription_payment', RENEWAL_KOPEKS)]
        assert await _end_date(db) > datetime.now(UTC) + timedelta(days=29)

    text = _alert_text(callback)
    assert menu.get_texts('fa').format_price(RENEWAL_KOPEKS) in text
    assert '₽' not in text


@pytest.mark.asyncio
async def test_activate_button_reports_the_toman_shortfall(monkeypatch):
    from app.database.crud.user import lock_user_for_pricing
    from app.handlers import menu

    async def fake_calculate(self, db, subscription, period_days, *, user=None):
        return _pricing(period_days=period_days)

    monkeypatch.setattr(Settings, 'get_available_subscription_periods', lambda self: [30])
    monkeypatch.setattr(PricingEngine, 'calculate_renewal_price', fake_calculate)

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=150_000, status=SubscriptionStatus.EXPIRED.value)
        db_user = await lock_user_for_pricing(db, 1)
        callback = _callback('activate_button')

        await menu.handle_activate_button(callback, db_user, db)

        assert await _balance(db) == 150_000
        assert await _payments(db) == []

    text = _alert_text(callback)
    assert menu.get_texts('fa').format_balance(50_000, round_kopeks=False) in text
    assert '₽' not in text


@pytest.mark.asyncio
async def test_activate_button_new_subscription_debits_the_toman_price(monkeypatch):
    """Same handler, no subscription yet: the pre-check and the debit share the fix."""
    import app.services.subscription_service as subscription_service_module
    from app.database.crud.user import lock_user_for_pricing
    from app.handlers import menu

    async def fake_new_price(self, db, period_days, squads, traffic_gb, devices, *, user=None):
        return SimpleNamespace(final_total=RENEWAL_KOPEKS)

    monkeypatch.setattr(Settings, 'get_available_subscription_periods', lambda self: [30])
    monkeypatch.setattr(PricingEngine, 'calculate_classic_new_subscription_price', fake_new_price)
    monkeypatch.setattr(subscription_service_module, 'SubscriptionService', lambda: _FakePanelSync())

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=250_000)
        await db.delete(await db.get(Subscription, 10))
        await db.commit()
        db_user = await lock_user_for_pricing(db, 1)
        callback = _callback('activate_button')

        await menu.handle_activate_button(callback, db_user, db)

        assert await _balance(db) == 50_000
        assert await _payments(db) == [('subscription_payment', RENEWAL_KOPEKS)]

    text = _alert_text(callback)
    assert menu.get_texts('fa').format_price(RENEWAL_KOPEKS) in text
    assert '₽' not in text


# ---------------------------------------------------------------- admin renewal notification


@pytest.mark.asyncio
async def test_admin_renewal_notification_shows_the_toman_balance(monkeypatch):
    """«Баланс после операции» is the Toman balance; the payment line stays a catalog price."""
    from app.services.admin_notification_service import AdminNotificationService

    service = AdminNotificationService(SimpleNamespace())
    sent: list[str] = []

    async def capture(message, **kwargs):
        sent.append(message)
        return True

    monkeypatch.setattr(service, '_record_subscription_event', AsyncMock())
    monkeypatch.setattr(service, '_is_enabled', lambda: True)
    monkeypatch.setattr(service, '_get_servers_info', AsyncMock(return_value='squad-1'))
    monkeypatch.setattr(service, '_get_user_promo_group', AsyncMock(return_value=None))
    monkeypatch.setattr(service, '_send_message', capture)

    now = datetime.now(UTC)
    user = SimpleNamespace(id=1, telegram_id=1001, email=None, username=None, first_name='U', last_name=None)
    subscription = SimpleNamespace(
        id=10, end_date=now + timedelta(days=30), connected_squads=['squad-1'], traffic_limit_gb=100, device_limit=1
    )
    transaction = SimpleNamespace(
        id=501,
        type='subscription_payment',
        amount_kopeks=-RENEWAL_KOPEKS,
        payment_method=PaymentMethod.BALANCE.value,
        completed_at=now,
        created_at=now,
    )

    await service.send_subscription_extension_notification(
        None, user, subscription, transaction, 30, now, new_end_date=subscription.end_date, balance_after=50_000
    )

    (message,) = sent
    assert f'Сумма: {settings.format_price(RENEWAL_KOPEKS)}' in message
    assert f'Баланс после операции:</b> {settings.format_balance(50_000)}' in message
