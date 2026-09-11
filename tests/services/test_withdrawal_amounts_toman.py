"""Referral withdrawals and notification amounts are shown in Toman, not divided by 100.

``WithdrawalRequest.amount_kopeks``, ``ReferralEarning.amount_kopeks``, the wallet balance and the
``REFERRAL_*_KOPEKS`` settings all hold raw Toman since Phase B. The withdrawal flow still divided them
by 100 (``amount / 100``, ``format_price``), so a 60,000-Toman withdrawal read «600». The bot also
multiplied the typed withdrawal amount by 100, so after the display fix a user typing the amount the
screen shows (60000) would have requested 6,000,000.

The email/WS context of ``notification_delivery_service`` had the same ÷100 on every ``*_rubles``
field; it now picks the scale per event like ``app/cabinet/routes/websocket.py``: balance events use
``display_balance_from_storage`` / ``format_balance``, catalog events (autopay, daily debit amount)
use ``display_amount_from_kopeks`` / ``format_price``.

Presentation and input parsing only: the approval debit (1:1 of ``amount_kopeks``) is unchanged.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import Settings, settings
from app.database.models import (
    Base,
    ReferralEarning,
    Transaction,
    TransactionType,
    User,
    WithdrawalRequest,
    WithdrawalRequestStatus,
)
from app.localization.texts import get_texts
from app.services.notification_delivery_service import NotificationDeliveryService
from app.services.referral_withdrawal_service import ReferralWithdrawalService
from tests.fixtures.sqlite_memory import memory_session


TABLES = list(Base.metadata.sorted_tables)

WITHDRAWAL = 60_000  # Toman
AVAILABLE = 100_000  # Toman
MIN_WITHDRAWAL = 50_000  # Toman
TEXTS_FA = get_texts('fa')


def _fa(amount: int) -> str:
    return TEXTS_FA.format_balance(amount)


def test_expected_labels():
    """Pin the exact strings the manual test list quotes."""
    assert _fa(WITHDRAWAL) == '60,000 تومان'
    assert _fa(AVAILABLE) == '100,000 تومان'
    assert _fa(MIN_WITHDRAWAL) == '50,000 تومان'


@pytest.fixture
def _withdrawals_on(monkeypatch):
    monkeypatch.setattr(Settings, 'is_referral_withdrawal_enabled', lambda self: True)
    monkeypatch.setattr(settings, 'REFERRAL_WITHDRAWAL_MIN_AMOUNT_KOPEKS', MIN_WITHDRAWAL)
    monkeypatch.setattr(settings, 'REFERRAL_WITHDRAWAL_ONLY_REFERRAL_BALANCE', True)
    monkeypatch.setattr(settings, 'REFERRAL_WITHDRAWAL_TEST_MODE', False)


# ---------------------------------------------------------------- notification_delivery_service


def _capturing_service() -> tuple[NotificationDeliveryService, dict]:
    service = NotificationDeliveryService()
    captured: dict = {}

    async def fake_send(**kwargs):
        captured.update(kwargs['context'])
        return True

    service.send_notification = fake_send
    return service, captured


_USER = SimpleNamespace(id=1, language='fa')


async def test_withdrawal_approved_context_is_toman():
    service, ctx = _capturing_service()
    await service.notify_withdrawal_approved(user=_USER, amount_kopeks=WITHDRAWAL)
    assert ctx['amount_rubles'] == 60000
    assert ctx['formatted_amount'] == settings.format_balance(WITHDRAWAL)


async def test_withdrawal_rejected_context_is_toman():
    service, ctx = _capturing_service()
    await service.notify_withdrawal_rejected(user=_USER, amount_kopeks=WITHDRAWAL, comment='x')
    assert ctx['amount_rubles'] == 60000
    assert ctx['formatted_amount'] == settings.format_balance(WITHDRAWAL)


async def test_balance_topup_context_is_toman():
    service, ctx = _capturing_service()
    await service.notify_balance_topup(user=_USER, amount_kopeks=50_000, new_balance_kopeks=1_000_000)
    assert ctx['amount_rubles'] == 50000
    assert ctx['new_balance_rubles'] == 1000000
    assert ctx['formatted_amount'] == settings.format_balance(50_000)
    assert ctx['formatted_balance'] == settings.format_balance(1_000_000)


async def test_referral_bonus_context_is_toman():
    service, ctx = _capturing_service()
    await service.notify_referral_bonus(user=_USER, bonus_kopeks=25_000, referral_name='Ali')
    assert ctx['bonus_rubles'] == 25000
    assert ctx['formatted_bonus'] == settings.format_balance(25_000)
    assert ctx['formatted_reward'] == settings.format_balance(25_000)


async def test_daily_debit_amount_is_catalog_and_balance_is_toman():
    service, ctx = _capturing_service()
    # daily_price_kopeks is catalog: 500,000 → 5,000 Toman charged; wallet left with 145,000 Toman.
    await service.notify_daily_debit(user=_USER, amount_kopeks=500_000, new_balance_kopeks=145_000)
    assert ctx['amount_rubles'] == 5000
    assert ctx['formatted_amount'] == settings.format_price(500_000)
    assert ctx['new_balance_rubles'] == 145000
    assert ctx['formatted_balance'] == settings.format_balance(145_000)


async def test_autopay_success_amount_is_catalog():
    service, ctx = _capturing_service()
    await service.notify_autopay_success(user=_USER, amount_kopeks=7_000_000, new_expires_at=datetime.now(UTC))
    assert ctx['amount_rubles'] == 70000
    assert ctx['formatted_amount'] == settings.format_price(7_000_000)


async def test_email_amount_alias_for_referral_bonus_is_toman(monkeypatch):
    """``{amount}`` in a DB override for referral_bonus falls back to the bonus — in Toman."""
    service = NotificationDeliveryService()
    service._email_service = SimpleNamespace(is_configured=lambda: True, send_email=lambda **kw: True)
    captured: dict = {}

    async def fake_override(notification_type, language, context):
        captured.update(context)
        return ('subject', '<p>body</p>')

    import app.cabinet.services.email_template_overrides as overrides

    monkeypatch.setattr(overrides, 'get_rendered_override', fake_override)
    user = SimpleNamespace(id=1, language='fa', email='a@b.c', email_verified=True, first_name='A', username=None)
    ctx = {
        'bonus_kopeks': 25_000,
        'bonus_rubles': 25_000.0,
        'formatted_bonus': settings.format_balance(25_000),
        'referral_name': 'Ali',
    }
    from app.services.notification_delivery_service import NotificationType

    assert await service._send_email_notification(user, NotificationType.REFERRAL_BONUS, ctx) is True
    assert captured['amount'] == settings.format_balance(25_000)


def test_email_placeholder_list_offers_toman_twins():
    from app.cabinet.routes.admin_email_templates import TEMPLATE_TYPES

    by_type = {meta['type']: meta['context_vars'] for meta in TEMPLATE_TYPES}
    for notification_type in ('balance_topup', 'withdrawal_approved', 'withdrawal_rejected'):
        assert 'amount_rubles' in by_type[notification_type]  # old placeholder names keep working
        assert 'amount_toman' in by_type[notification_type]
    assert 'new_balance_toman' in by_type['balance_topup']
    assert 'bonus_toman' in by_type['referral_bonus']


async def test_toman_twins_are_in_the_context():
    service, ctx = _capturing_service()
    await service.notify_withdrawal_approved(user=_USER, amount_kopeks=WITHDRAWAL)
    assert ctx['amount_toman'] == 60000
    service, ctx = _capturing_service()
    await service.notify_balance_topup(user=_USER, amount_kopeks=50_000, new_balance_kopeks=1_000_000)
    assert ctx['amount_toman'] == 50000
    assert ctx['new_balance_toman'] == 1000000
    service, ctx = _capturing_service()
    await service.notify_referral_bonus(user=_USER, bonus_kopeks=25_000, referral_name='Ali')
    assert ctx['bonus_toman'] == 25000
    service, ctx = _capturing_service()
    await service.notify_daily_debit(user=_USER, amount_kopeks=500_000, new_balance_kopeks=145_000)
    assert ctx['amount_toman'] == 5000
    assert ctx['new_balance_toman'] == 145000


# ---------------------------------------------------------------- referral_withdrawal_service


def _user_row(user_id: int = 1, balance: int = AVAILABLE, language: str = 'fa') -> User:
    return User(
        id=user_id,
        telegram_id=1000 + user_id,
        first_name='U',
        language=language,
        status='active',
        balance_kopeks=balance,
    )


async def test_spending_is_summed_in_toman(monkeypatch, _withdrawals_on):
    """subscription_payment rows are catalog (×100), withdrawal rows Toman: sum them per scale."""
    now = datetime.now(UTC)
    async with memory_session(monkeypatch, TABLES) as db:
        db.add(_user_row())
        db.add(_user_row(user_id=3, balance=0))
        db.add(
            ReferralEarning(
                user_id=1,
                referral_id=3,
                amount_kopeks=200_000,
                reason='referral_commission_topup',
                created_at=now - timedelta(days=10),
            )
        )
        db.add_all(
            [
                Transaction(
                    user_id=1,
                    type=TransactionType.SUBSCRIPTION_PAYMENT.value,
                    amount_kopeks=-7_000_000,
                    description='sub',
                    is_completed=True,
                    created_at=now - timedelta(days=5),
                ),
                Transaction(
                    user_id=1,
                    type=TransactionType.WITHDRAWAL.value,
                    amount_kopeks=-WITHDRAWAL,
                    description='wd',
                    is_completed=True,
                    created_at=now - timedelta(days=4),
                ),
            ]
        )
        await db.commit()

        service = ReferralWithdrawalService()
        stats = await service.get_referral_balance_stats(db, 1)

    assert stats['spending'] == 130_000  # 70,000 subscription + 60,000 withdrawal
    assert stats['referral_spent'] == 130_000


async def test_below_minimum_reason_is_localized_toman(monkeypatch, _withdrawals_on):
    async with memory_session(monkeypatch, TABLES) as db:
        db.add(_user_row(balance=40_000))
        db.add(_user_row(user_id=3, balance=0))
        db.add(ReferralEarning(user_id=1, referral_id=3, amount_kopeks=40_000, reason='referral_commission_topup'))
        await db.commit()

        ok, reason, _stats = await ReferralWithdrawalService().can_request_withdrawal(db, 1)

    assert ok is False
    assert _fa(MIN_WITHDRAWAL) in reason
    assert _fa(40_000) in reason
    assert '₽' not in reason
    assert 'Минимальная' not in reason


async def test_create_request_insufficient_is_localized_toman(monkeypatch, _withdrawals_on):
    async with memory_session(monkeypatch, TABLES) as db:
        db.add(_user_row())
        db.add(_user_row(user_id=3, balance=0))
        db.add(ReferralEarning(user_id=1, referral_id=3, amount_kopeks=AVAILABLE, reason='referral_commission_topup'))
        await db.commit()

        request, error = await ReferralWithdrawalService().create_withdrawal_request(db, 1, 150_000, 'card 6037')

    assert request is None
    assert _fa(AVAILABLE) in error
    assert '₽' not in error


async def test_create_request_stores_toman_and_flags_in_toman(monkeypatch, _withdrawals_on):
    async with memory_session(monkeypatch, TABLES) as db:
        db.add(_user_row())
        db.add(_user_row(user_id=3, balance=0))
        db.add(ReferralEarning(user_id=1, referral_id=3, amount_kopeks=AVAILABLE, reason='referral_commission_topup'))
        db.add(
            Transaction(
                user_id=1,
                type=TransactionType.DEPOSIT.value,
                amount_kopeks=50_000,
                description='c2c',
                payment_method='c2c',
                is_completed=True,
            )
        )
        await db.commit()

        request, error = await ReferralWithdrawalService().create_withdrawal_request(db, 1, WITHDRAWAL, 'card 6037')

    assert error == ''
    assert request.amount_kopeks == WITHDRAWAL
    flags = json.loads(request.risk_analysis)['flags']
    assert any(settings.format_balance(50_000) in flag for flag in flags), flags
    assert not any('₽' in flag for flag in flags), flags


async def test_approve_debits_toman_one_to_one_and_low_balance_error_is_toman(monkeypatch, _withdrawals_on):
    async with memory_session(monkeypatch, TABLES) as db:
        db.add(_user_row(balance=AVAILABLE))
        db.add(_user_row(user_id=2, balance=0))  # admin
        db.add(WithdrawalRequest(id=1, user_id=1, amount_kopeks=WITHDRAWAL, payment_details='card'))
        db.add(WithdrawalRequest(id=2, user_id=1, amount_kopeks=500_000, payment_details='card'))
        await db.commit()

        service = ReferralWithdrawalService()
        ok, error = await service.approve_request(db, 1, admin_id=2)
        assert (ok, error) == (True, '')
        user = await db.get(User, 1)
        assert user.balance_kopeks == AVAILABLE - WITHDRAWAL  # unchanged 1:1 debit

        ok, error = await service.approve_request(db, 2, admin_id=2)

    assert ok is False
    assert _fa(AVAILABLE - WITHDRAWAL) in error
    assert '₽' not in error


def test_user_balance_stats_are_toman():
    stats = {
        'total_earned': 200_000,
        'referral_spent': 70_000,
        'withdrawn': WITHDRAWAL,
        'pending': 10_000,
        'available_total': AVAILABLE,
        'only_referral_mode': True,
    }
    text = ReferralWithdrawalService().format_balance_stats_for_user(stats, TEXTS_FA)
    for amount in (200_000, 70_000, WITHDRAWAL, 10_000, AVAILABLE):
        assert _fa(amount) in text


def test_admin_analysis_is_toman():
    analysis = {
        'risk_level': 'low',
        'risk_score': 0,
        'flags': [],
        'details': {
            'balance_stats': {'total_earned': 200_000, 'own_deposits': 50_000, 'spending': 70_000, 'withdrawn': 0},
            'referral_count': 1,
            'referral_deposits': {'paying_referrals': 1, 'total_deposits': 2, 'total_amount': 1_000_000},
            'suspicious_referrals': [{'name': 'R', 'deposits_count': 2, 'deposits_total': 1_000_000, 'flags': []}],
            'earnings_by_reason': {'referral_commission_topup': {'count': 2, 'total': 200_000}},
        },
    }
    text = ReferralWithdrawalService().format_analysis_for_admin(analysis)
    for amount in (200_000, 50_000, 70_000, 1_000_000):
        assert settings.format_balance(amount) in text
    assert '₽' not in text


def test_format_analysis_for_admin_without_analysis_is_empty():
    # A request with no stored risk_analysis reaches the formatter as {} (admin referrals.py,
    # referral.py); indexing analysis['risk_level'] raised KeyError and broke the request screen.
    assert ReferralWithdrawalService().format_analysis_for_admin({}) == ''


def test_format_analysis_for_admin_without_risk_level_keeps_the_rest():
    text = ReferralWithdrawalService().format_analysis_for_admin({'flags': ['flag-x']})
    assert 'flag-x' in text


# ---------------------------------------------------------------- bot: user withdrawal flow


def _state(data: dict) -> MagicMock:
    state = MagicMock()
    state.get_data = AsyncMock(return_value=data)
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()
    state.clear = AsyncMock()
    return state


def _message(text: str) -> MagicMock:
    message = MagicMock()
    message.text = text
    message.answer = AsyncMock()
    return message


_DB_USER = SimpleNamespace(id=1, telegram_id=1001, email=None, language='fa', full_name='Ali')


async def test_start_withdrawal_shows_toman_and_withdraw_all_button(monkeypatch):
    import app.handlers.referral as ref

    captured = {}

    async def fake_edit(callback, text, keyboard):
        captured['text'] = text
        captured['keyboard'] = keyboard

    monkeypatch.setattr(ref, 'edit_or_answer_photo', fake_edit)
    monkeypatch.setattr(
        ref.referral_withdrawal_service,
        'can_request_withdrawal',
        AsyncMock(return_value=(True, 'OK', {'available_total': AVAILABLE})),
    )
    callback = MagicMock()
    callback.answer = AsyncMock()

    await ref.start_withdrawal_request(callback, _DB_USER, None, _state({}))

    assert _fa(AVAILABLE) in captured['text']
    assert 'روبل' not in captured['text']
    button = captured['keyboard'].inline_keyboard[0][0]
    assert _fa(AVAILABLE) in button.text
    assert '₽' not in button.text
    assert button.callback_data == f'referral_withdrawal_amount_{AVAILABLE}'


@pytest.mark.parametrize('typed', ['60000', '60,000', '۶۰۰۰۰', '60000 تومان'])
async def test_typed_withdrawal_amount_is_toman(monkeypatch, typed):
    import app.handlers.referral as ref

    monkeypatch.setattr(settings, 'REFERRAL_WITHDRAWAL_MIN_AMOUNT_KOPEKS', MIN_WITHDRAWAL)
    state = _state({'available_balance': AVAILABLE})
    message = _message(typed)

    await ref.process_withdrawal_amount(message, _DB_USER, None, state)

    state.update_data.assert_awaited_once_with(withdrawal_amount=WITHDRAWAL)


async def test_typed_amount_below_minimum_shows_toman(monkeypatch):
    import app.handlers.referral as ref

    monkeypatch.setattr(settings, 'REFERRAL_WITHDRAWAL_MIN_AMOUNT_KOPEKS', MIN_WITHDRAWAL)
    state = _state({'available_balance': AVAILABLE})
    message = _message('40000')

    await ref.process_withdrawal_amount(message, _DB_USER, None, state)

    state.update_data.assert_not_awaited()
    assert _fa(MIN_WITHDRAWAL) in message.answer.await_args.args[0]


async def test_typed_amount_above_available_shows_toman(monkeypatch):
    import app.handlers.referral as ref

    monkeypatch.setattr(settings, 'REFERRAL_WITHDRAWAL_MIN_AMOUNT_KOPEKS', MIN_WITHDRAWAL)
    state = _state({'available_balance': AVAILABLE})
    message = _message('150000')

    await ref.process_withdrawal_amount(message, _DB_USER, None, state)

    state.update_data.assert_not_awaited()
    assert _fa(AVAILABLE) in message.answer.await_args.args[0]


async def test_confirm_screen_shows_toman(monkeypatch):
    import app.handlers.referral as ref

    message = _message('6037-9912-3456-7890 Ali')
    await ref.process_payment_details(message, _DB_USER, None, _state({'withdrawal_amount': WITHDRAWAL}))
    assert _fa(WITHDRAWAL) in message.answer.await_args.args[0]


async def test_confirm_request_admin_text_and_user_text_are_toman(monkeypatch):
    import app.handlers.referral as ref

    captured = {}

    async def fake_edit(callback, text, keyboard):
        captured['user_text'] = text

    admin_service = MagicMock()
    admin_service.send_admin_notification = AsyncMock()
    monkeypatch.setattr(ref, 'edit_or_answer_photo', fake_edit)
    monkeypatch.setattr(ref, 'AdminNotificationService', lambda bot: admin_service)
    monkeypatch.setattr(settings, 'REFERRAL_WITHDRAWAL_NOTIFICATIONS_TOPIC_ID', None)
    request = SimpleNamespace(id=7, risk_analysis=json.dumps({'risk_level': 'low', 'risk_score': 0}))
    monkeypatch.setattr(
        ref.referral_withdrawal_service, 'create_withdrawal_request', AsyncMock(return_value=(request, ''))
    )
    callback = MagicMock()
    callback.answer = AsyncMock()

    await ref.confirm_withdrawal_request(
        callback, _DB_USER, None, _state({'withdrawal_amount': WITHDRAWAL, 'payment_details': 'card 6037'})
    )

    admin_text = admin_service.send_admin_notification.await_args.args[0]
    assert settings.format_balance(WITHDRAWAL) in admin_text
    assert '600₽' not in admin_text
    assert _fa(WITHDRAWAL) in captured['user_text']


def test_referral_terms_on_the_bot_screen_are_toman(monkeypatch):
    """REFERRAL_MINIMUM_TOPUP / *_BONUS_KOPEKS are compared with and credited to the Toman wallet."""
    import inspect

    import app.handlers.referral as ref

    source = inspect.getsource(ref)
    for name in ('REFERRAL_FIRST_TOPUP_BONUS_KOPEKS', 'REFERRAL_MINIMUM_TOPUP_KOPEKS', 'REFERRAL_INVITER_BONUS_KOPEKS'):
        assert f'format_price(settings.{name})' not in source
        assert f'format_balance(settings.{name})' in source


# ---------------------------------------------------------------- bot: admin withdrawal screens


def _unwrap(fn):
    while hasattr(fn, '__wrapped__'):
        fn = fn.__wrapped__
    return fn


async def test_admin_bot_list_and_detail_show_toman(monkeypatch):
    import app.handlers.admin.referrals as admin_ref

    request = SimpleNamespace(
        id=7,
        user_id=1,
        amount_kopeks=WITHDRAWAL,
        risk_score=10,
        created_at=datetime.now(UTC),
        status=WithdrawalRequestStatus.PENDING.value,
        payment_details='card',
        risk_analysis=json.dumps({'risk_level': 'low', 'risk_score': 10}),
    )
    monkeypatch.setattr(
        admin_ref.referral_withdrawal_service, 'get_pending_requests', AsyncMock(return_value=[request])
    )
    monkeypatch.setattr(
        admin_ref,
        'get_user_by_id',
        AsyncMock(
            return_value=SimpleNamespace(
                id=1,
                full_name='Ali',
                telegram_id=1001,
                email=None,
            )
        ),
    )
    callback = MagicMock()
    callback.answer = AsyncMock()
    callback.message.edit_text = AsyncMock()
    callback.data = 'admin_withdrawal_view_7'

    await _unwrap(admin_ref.show_pending_withdrawal_requests)(callback, SimpleNamespace(id=2), None)
    list_text = callback.message.edit_text.await_args.args[0]
    markup = callback.message.edit_text.await_args.kwargs['reply_markup']
    assert settings.format_balance(WITHDRAWAL) in list_text
    assert settings.format_balance(WITHDRAWAL) in markup.inline_keyboard[0][0].text
    assert '600₽' not in list_text

    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=request)
    db.execute = AsyncMock(return_value=result)
    await _unwrap(admin_ref.view_withdrawal_request)(callback, SimpleNamespace(id=2), db)
    detail_text = callback.message.edit_text.await_args.args[0]
    assert settings.format_balance(WITHDRAWAL) in detail_text
    assert '600₽' not in detail_text


def test_admin_bot_user_notifications_format_toman():
    import inspect

    import app.handlers.admin.referrals as admin_ref

    source = inspect.getsource(admin_ref)
    assert 'format_price(request.amount_kopeks)' not in source
    assert source.count('texts.format_balance(request.amount_kopeks)') == 3


# ---------------------------------------------------------------- cabinet / API


async def test_cabinet_history_amount_rubles_is_toman(monkeypatch):
    from app.cabinet.routes import withdrawal as route

    async with memory_session(monkeypatch, TABLES) as db:
        db.add(_user_row())
        db.add(WithdrawalRequest(id=1, user_id=1, amount_kopeks=WITHDRAWAL, payment_details='card'))
        await db.commit()
        user = await db.get(User, 1)
        response = await route.get_withdrawal_history(user=user, db=db)

    assert response.items[0].amount_kopeks == WITHDRAWAL
    assert response.items[0].amount_rubles == 60000


async def test_cabinet_admin_list_and_detail_amount_rubles_is_toman(monkeypatch):
    from app.cabinet.routes import admin_withdrawals as route

    async with memory_session(monkeypatch, TABLES) as db:
        db.add(_user_row())
        db.add(WithdrawalRequest(id=1, user_id=1, amount_kopeks=WITHDRAWAL, payment_details='card'))
        await db.commit()
        admin = SimpleNamespace(id=99)
        listing = await route.list_withdrawals(withdrawal_status=None, offset=0, limit=20, admin=admin, db=db)
        detail = await route.get_withdrawal_detail(withdrawal_id=1, admin=admin, db=db)

    assert listing.items[0].amount_rubles == 60000
    assert detail.amount_rubles == 60000


@pytest.mark.parametrize('action', ['approve', 'reject'])
async def test_cabinet_admin_decision_telegram_message_is_toman_and_localized(monkeypatch, action):
    from app import bot_factory
    from app.cabinet.routes import admin_withdrawals as route
    from app.cabinet.schemas.withdrawals import AdminApproveWithdrawalRequest, AdminRejectWithdrawalRequest
    from app.services.notification_delivery_service import notification_delivery_service

    bot = MagicMock()
    bot.session.close = AsyncMock()
    monkeypatch.setattr(bot_factory, 'create_bot', lambda: bot)
    monkeypatch.setattr(settings, 'BOT_TOKEN', 'x')
    notify = AsyncMock(return_value=True)
    notifier = 'notify_withdrawal_approved' if action == 'approve' else 'notify_withdrawal_rejected'
    monkeypatch.setattr(notification_delivery_service, notifier, notify)
    monkeypatch.setattr(route.referral_withdrawal_service, f'{action}_request', AsyncMock(return_value=(True, '')))

    async with memory_session(monkeypatch, TABLES) as db:
        db.add(_user_row())
        db.add(WithdrawalRequest(id=1, user_id=1, amount_kopeks=WITHDRAWAL, payment_details='card'))
        await db.commit()
        admin = SimpleNamespace(id=99)
        if action == 'approve':
            await route.approve_withdrawal(
                withdrawal_id=1, request=AdminApproveWithdrawalRequest(comment='<ok>'), admin=admin, db=db
            )
        else:
            await route.reject_withdrawal(
                withdrawal_id=1, request=AdminRejectWithdrawalRequest(comment='<bad card>'), admin=admin, db=db
            )

    tg_message = notify.await_args.kwargs['telegram_message']
    assert _fa(WITHDRAWAL) in tg_message
    assert 'Ваш запрос' not in tg_message
    assert '&lt;' in tg_message  # the admin comment is HTML-escaped (parse_mode=HTML)


async def test_cabinet_referral_terms_rubles_are_toman(monkeypatch):
    from app.cabinet.routes import referral as route

    monkeypatch.setattr(settings, 'REFERRAL_MINIMUM_TOPUP_KOPEKS', 10_000)
    monkeypatch.setattr(settings, 'REFERRAL_FIRST_TOPUP_BONUS_KOPEKS', 20_000)
    monkeypatch.setattr(settings, 'REFERRAL_INVITER_BONUS_KOPEKS', 30_000)
    monkeypatch.setattr(Settings, 'is_referral_levels_scheme', lambda self: False)

    async with memory_session(monkeypatch, TABLES) as db:
        db.add(_user_row())
        await db.commit()
        user = await db.get(User, 1)
        terms = await route.get_referral_terms(user=user, db=db)

    assert terms.minimum_topup_rubles == 10000
    assert terms.first_topup_bonus_rubles == 20000
    assert terms.inviter_bonus_rubles == 30000


def test_cabinet_admin_users_total_balance_rubles_is_toman():
    import inspect

    from app.cabinet.routes import admin_users

    source = inspect.getsource(admin_users)
    assert 'total_balance_rubles=total_balance / 100' not in source
    assert 'total_balance_rubles=display_balance_from_storage(total_balance)' in source
