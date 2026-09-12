"""Every amount a user or admin reads is shown in Toman, not divided by 100.

Written for Phase B, where ``settings.format_price`` was a separate catalog formatter
(``price_kopeks / 100``) and passing a balance to it made a 150,000-Toman wallet read
«1,500 تومان». Phase C collapsed the two: ``format_price`` is now an alias of
``format_balance``, so the two formatters can no longer disagree, and what these tests still
pin is that each screen prints the stored number.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.config import Settings, settings
from app.database.models import Base, Subscription, SubscriptionStatus, Tariff, Transaction, User
from tests.fixtures.sqlite_memory import memory_session


ROOT = Path(__file__).resolve().parents[2]
TABLES = list(Base.metadata.sorted_tables)

BALANCE_TOMAN = 150_000
BALANCE_LABEL = settings.format_balance(BALANCE_TOMAN)  # «150,000 تومان»

GUARDED = [ROOT / 'app']


def _format_price_on_balance() -> list[str]:
    """Every ``*.format_price(<expr mentioning a balance>)`` call in the guarded modules."""
    files: list[Path] = []
    for root in GUARDED:
        files.extend([root] if root.is_file() else sorted(root.rglob('*.py')))

    hits: list[str] = []
    for path in files:
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == 'format_price'
                and node.args
                and 'balance' in ast.unparse(node.args[0]).lower()
            ):
                hits.append(f'{path.relative_to(ROOT)}:{node.lineno}: {ast.unparse(node.args[0])}')
    return hits


def test_no_balance_reaches_for_the_legacy_catalog_formatter():
    assert _format_price_on_balance() == []


def test_the_guard_sees_the_balance_labels():
    """Keep the guard honest: it must be scanning code that formats balances at all."""
    source = (ROOT / 'app' / 'cabinet' / 'routes' / 'subscription_modules' / 'daily.py').read_text(encoding='utf-8')
    assert "'balance_label': settings.format_balance(user.balance_kopeks)" in source


# ---------------------------------------------------------------- cabinet / miniapp daily pause


def _daily_rows() -> list:
    now = datetime.now(UTC)
    return [
        User(
            id=1,
            telegram_id=1001,
            first_name='U',
            language='fa',
            status='active',
            balance_kopeks=BALANCE_TOMAN,
            remnawave_id=9001,
        ),
        Tariff(
            id=1,
            name='daily',
            description='',
            is_active=True,
            is_daily=True,
            daily_price_kopeks=500_000,  # catalog: 5,000 Toman a day
            period_prices={},
            traffic_limit_gb=100,
            traffic_reset_mode='NO_RESET',
            device_limit=1,
            max_device_limit=10,
            device_price_kopeks=100,
            allowed_squads=['squad-1'],
            display_order=1,
        ),
        Subscription(
            id=10,
            remnawave_short_id='day1',
            remnawave_id=9001,
            user_id=1,
            status=SubscriptionStatus.ACTIVE.value,
            is_trial=False,
            start_date=now - timedelta(days=1),
            end_date=now + timedelta(hours=20),
            updated_at=now - timedelta(hours=1),
            traffic_limit_gb=100,
            traffic_used_gb=1.0,
            purchased_traffic_gb=0,
            device_limit=1,
            tariff_id=1,
            connected_squads=['squad-1'],
            is_daily_paused=False,
        ),
    ]


@pytest.fixture
def _single_tariff(monkeypatch):
    monkeypatch.setattr(Settings, 'is_multi_tariff_enabled', lambda self: False)
    monkeypatch.setattr(Settings, 'is_tariffs_mode', lambda self: True)


@pytest.mark.asyncio
async def test_cabinet_daily_pause_labels_the_toman_balance(monkeypatch, _single_tariff):
    from app.cabinet.routes.subscription_modules import daily

    async with memory_session(monkeypatch, TABLES) as db:
        db.add_all(_daily_rows())
        await db.commit()
        user = await db.get(User, 1)

        response = await daily.toggle_subscription_pause(user=user, db=db, subscription_id=None)

    assert response['is_paused'] is True
    assert response['balance_kopeks'] == BALANCE_TOMAN
    assert response['balance_label'] == BALANCE_LABEL


@pytest.mark.asyncio
async def test_miniapp_daily_pause_labels_the_toman_balance(monkeypatch, _single_tariff):
    from app.database.crud.user import lock_user_for_pricing
    from app.webapi.routes import miniapp
    from app.webapi.schemas.miniapp import MiniAppDailySubscriptionToggleRequest

    async with memory_session(monkeypatch, TABLES) as db:
        db.add_all(_daily_rows())
        await db.commit()
        # _authorize_miniapp_user hands over the user with subscriptions loaded
        user = await lock_user_for_pricing(db, 1)

        monkeypatch.setattr(miniapp, '_authorize_miniapp_user', AsyncMock(return_value=user))

        response = await miniapp.toggle_daily_subscription_pause_endpoint(
            MiniAppDailySubscriptionToggleRequest(init_data='init'), db=db
        )

    assert response.balance_label == BALANCE_LABEL


# ---------------------------------------------------------------- admin notifications


def _user() -> User:
    """Transient model instance: every attribute the notifications read exists."""
    return User(id=1, telegram_id=1001, first_name='U', language='fa', status='active', balance_kopeks=BALANCE_TOMAN)


def _subscription() -> Subscription:
    now = datetime.now(UTC)
    return Subscription(
        id=10,
        user_id=1,
        status=SubscriptionStatus.ACTIVE.value,
        is_trial=False,
        start_date=now,
        end_date=now + timedelta(days=30),
        traffic_limit_gb=100,
        device_limit=1,
        connected_squads=['squad-1'],
    )


@pytest.fixture
def notifier(monkeypatch):
    from app.services.admin_notification_service import AdminNotificationService

    service = AdminNotificationService(SimpleNamespace())
    service.sent = []

    async def capture(message, **kwargs):
        service.sent.append(message)
        return True

    monkeypatch.setattr(service, '_record_subscription_event', AsyncMock())
    monkeypatch.setattr(service, '_is_enabled', lambda: True)
    monkeypatch.setattr(service, '_get_servers_info', AsyncMock(return_value='squad-1'))
    monkeypatch.setattr(service, '_get_user_promo_group', AsyncMock(return_value=None))
    monkeypatch.setattr(service, '_send_message', capture)
    return service


def _only_message(service) -> str:
    (message,) = service.sent
    return message


@pytest.mark.asyncio
async def test_subscription_purchase_notification_shows_the_toman_balance(notifier):
    now = datetime.now(UTC)
    transaction = Transaction(
        id=501,
        type='subscription_payment',
        amount_kopeks=-20_000_000,
        payment_method='balance',
        completed_at=now,
        created_at=now,
    )

    await notifier.send_subscription_purchase_notification(None, _user(), _subscription(), transaction, 30)

    message = _only_message(notifier)
    assert f'Баланс: {BALANCE_LABEL}' in message
    assert settings.format_balance(20_000_000) in message


@pytest.mark.asyncio
async def test_balance_topup_notification_shows_toman_amounts(notifier):
    now = datetime.now(UTC)
    transaction = Transaction(
        id=601,
        type='deposit',
        amount_kopeks=50_000,  # deposit rows are balance scale (Toman)
        payment_method='c2c',
        completed_at=now,
        created_at=now,
    )

    message = notifier._build_balance_topup_message(
        _user(),
        transaction,
        100_000,
        topup_status='🆕 Первое пополнение',
        referrer_info='Нет',
        subscription=None,
        promo_group=None,
    )

    assert f'<b>{settings.format_balance(50_000)}</b>' in message
    assert f'{settings.format_balance(100_000)} → 📈 {BALANCE_LABEL}' in message
    assert f'+{settings.format_balance(50_000)}' in message


@pytest.mark.asyncio
async def test_promocode_notification_shows_the_toman_balance(notifier):
    await notifier.send_promocode_activation_notification(
        None,
        _user(),
        {'code': 'GIFT', 'type': 'balance', 'balance_bonus_kopeks': 50_000},
        'bonus',
        balance_before_kopeks=100_000,
        balance_after_kopeks=BALANCE_TOMAN,
    )

    assert f'{settings.format_balance(100_000)} → {BALANCE_LABEL}' in _only_message(notifier)


@pytest.mark.asyncio
async def test_promo_group_change_notification_shows_the_toman_balance(notifier):
    group = SimpleNamespace(
        id=2,
        name='VIP',
        server_discount_percent=0,
        traffic_discount_percent=0,
        device_discount_percent=0,
        period_discounts={},
        auto_assign_total_spent_kopeks=0,
        is_default=False,
        apply_discounts_to_addons=False,
    )

    await notifier.send_user_promo_group_change_notification(None, _user(), None, group, automatic=True)

    assert f'Баланс пользователя: {BALANCE_LABEL}' in _only_message(notifier)


@pytest.mark.asyncio
async def test_subscription_update_notification_shows_the_toman_balance(notifier):
    await notifier.send_subscription_update_notification(None, _user(), _subscription(), 'devices', 1, 2, 1_000_000)

    message = _only_message(notifier)
    assert f'Баланс: {BALANCE_LABEL}' in message
    assert settings.format_balance(1_000_000) in message


@pytest.mark.asyncio
async def test_withdrawal_request_notification_shows_toman_amounts(notifier):
    """The requested amount is taken from the Toman wallet (checked against balance_kopeks)."""
    await notifier.send_withdrawal_request_notification(_user(), 50_000, 'card 6037')

    message = _only_message(notifier)
    assert f'Сумма: {settings.format_balance(50_000)}' in message
    assert f'Баланс: {BALANCE_LABEL}' in message


# ---------------------------------------------------------------- user-facing top-up messages


@pytest.mark.asyncio
async def test_manual_topup_message_shows_toman_amount_and_balance(monkeypatch):
    """Admin manual top-up: the user's «Баланс пополнен» message (amount and wallet are Toman)."""
    import app.services.manual_topup_service as manual_topup
    from app.services.payment.common import PaymentCommonMixin

    monkeypatch.setattr(Settings, 'is_notifications_enabled', lambda self: True)
    monkeypatch.setattr(PaymentCommonMixin, 'build_topup_success_keyboard', AsyncMock(return_value=None))
    monkeypatch.setattr(manual_topup, 'notify_email_user_topup', AsyncMock(), raising=False)
    bot = SimpleNamespace(send_message=AsyncMock())

    await manual_topup._notify_user(_user(), 50_000, Transaction(id=701), bot=bot)

    text = bot.send_message.await_args.args[1]
    assert f'Сумма: {settings.format_balance(50_000)}' in text
    assert f'Текущий баланс: {BALANCE_LABEL}' in text


@pytest.mark.asyncio
async def test_topup_delivery_context_formats_toman(monkeypatch):
    """Email / non-Telegram top-up notice built by notification_delivery_service."""
    from app.services.notification_delivery_service import notification_delivery_service

    captured: dict = {}

    async def fake_send(user, notification_type, context, **kwargs):
        captured.update(context)
        return True

    monkeypatch.setattr(notification_delivery_service, 'send_notification', fake_send)

    await notification_delivery_service.notify_balance_topup(_user(), 50_000, BALANCE_TOMAN)

    assert captured['formatted_amount'] == settings.format_balance(50_000)
    assert captured['formatted_balance'] == BALANCE_LABEL
