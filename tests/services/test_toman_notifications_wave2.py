"""Server-side notifications and admin screens show wallet amounts in Toman (wave 2, Task 4).

The wallet balance, referral terms (``REFERRAL_*_KOPEKS``, Toman since #35), referral commissions and
``ReferralEarning`` sums are raw Toman. They were shown with ``/ 100`` or ``format_price`` (the catalog
formatter), so a 150,000-Toman balance read «1,500». Catalog prices (a daily tariff's price) keep
``format_price``. Poll rewards are typed and stored on the catalog scale (x100), like prices, and were
credited to the wallet unconverted (100x).
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.config import Settings, settings
from app.localization.texts import get_texts


ROOT = Path(__file__).resolve().parents[2]

BALANCE_TOMAN = 150_000
DAILY_PRICE_KOPEKS = 1_000_000  # catalog: a 10,000-Toman day


def _toman(amount: int) -> str:
    return settings.format_balance(amount)  # «150,000 تومان»


# ---------------------------------------------------------------- daily tariff notifications


@pytest.fixture
def daily_notifications(monkeypatch):
    from app.services import daily_subscription_service as module

    delivery = SimpleNamespace(notify_daily_debit=AsyncMock(), send_notification=AsyncMock())
    monkeypatch.setattr(module, 'notification_delivery_service', delivery)
    monkeypatch.setattr(Settings, 'is_multi_tariff_enabled', lambda self: True)
    service = module.DailySubscriptionService()
    service._bot = object()
    return service, delivery


def _daily_user(balance: int) -> SimpleNamespace:
    return SimpleNamespace(id=1, language='fa', balance_kopeks=balance)


def _daily_subscription() -> SimpleNamespace:
    return SimpleNamespace(id=10, tariff=SimpleNamespace(name='روزانه'))


@pytest.mark.asyncio
async def test_daily_charge_message_shows_the_toman_balance_and_price(daily_notifications):
    service, delivery = daily_notifications

    await service._notify_daily_charge(_daily_user(BALANCE_TOMAN), _daily_subscription(), DAILY_PRICE_KOPEKS)

    kwargs = delivery.notify_daily_debit.await_args.kwargs
    message = kwargs['telegram_message']
    assert _toman(BALANCE_TOMAN) in message  # «150,000 تومان» left
    assert settings.format_price(DAILY_PRICE_KOPEKS) in message  # «10,000 تومان» charged
    assert '₽' not in message
    assert 'Списано' not in message  # the fa reader gets Persian
    assert 'روزانه' in message
    assert (kwargs['amount_kopeks'], kwargs['new_balance_kopeks']) == (DAILY_PRICE_KOPEKS, BALANCE_TOMAN)


@pytest.mark.asyncio
async def test_daily_insufficient_message_shows_the_toman_balance_and_price(daily_notifications):
    service, delivery = daily_notifications

    await service._notify_insufficient_balance(_daily_user(5_000), _daily_subscription(), DAILY_PRICE_KOPEKS)

    kwargs = delivery.send_notification.await_args.kwargs
    message = kwargs['telegram_message']
    assert _toman(5_000) in message
    assert settings.format_price(DAILY_PRICE_KOPEKS) in message
    assert '₽' not in message
    assert kwargs['context'] == {
        'required_amount': settings.format_price(DAILY_PRICE_KOPEKS),
        'current_balance': _toman(5_000),
    }
    texts = get_texts('fa')
    buttons = [button.text for row in kwargs['telegram_markup'].inline_keyboard for button in row]
    assert buttons == [texts.t('BALANCE_TOPUP', ''), texts.t('MY_SUBSCRIPTION_BUTTON', '')]


# ---------------------------------------------------------------- referral notifications (legacy scheme, live)


def _ref_user(uid: int, *, referred_by: int | None = None, first_topup: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        id=uid,
        telegram_id=1000 + uid,
        email=None,
        full_name=f'User {uid}',
        language='fa',
        referred_by_id=referred_by,
        has_made_first_topup=first_topup,
        referral_commission_percent=None,
        balance_kopeks=0,
    )


@pytest.fixture
def referral(monkeypatch):
    """The live .env terms: 10,000-Toman minimum, 10,000 bonuses, 25% commission."""
    from app.services import referral_service

    users = {1: _ref_user(1), 2: _ref_user(2, referred_by=1)}
    sent: list[dict] = []

    async def get_user(_db, uid):
        return users.get(uid)

    async def notify(bot, telegram_id, message, **kwargs):
        sent.append({'to': telegram_id, 'message': message, **kwargs})

    monkeypatch.setattr(referral_service, 'get_user_by_id', get_user)
    monkeypatch.setattr(referral_service, 'add_user_balance', AsyncMock(return_value=True))
    monkeypatch.setattr(referral_service, 'create_referral_earning', AsyncMock(return_value=SimpleNamespace(id=1)))
    monkeypatch.setattr(referral_service, 'get_user_campaign_id', AsyncMock(return_value=None))
    monkeypatch.setattr(referral_service, 'get_referral_reward_payment_count', AsyncMock(return_value=0))
    monkeypatch.setattr(referral_service, '_is_commission_limit_reached', AsyncMock(return_value=False))
    monkeypatch.setattr(referral_service, 'send_referral_notification', notify)
    monkeypatch.setattr(settings, 'REFERRAL_REWARD_SCHEME', 'legacy', raising=False)
    monkeypatch.setattr(settings, 'REFERRAL_MINIMUM_TOPUP_KOPEKS', 10_000, raising=False)
    monkeypatch.setattr(settings, 'REFERRAL_FIRST_TOPUP_BONUS_KOPEKS', 10_000, raising=False)
    monkeypatch.setattr(settings, 'REFERRAL_INVITER_BONUS_KOPEKS', 10_000, raising=False)
    monkeypatch.setattr(settings, 'REFERRAL_COMMISSION_PERCENT', 25, raising=False)
    monkeypatch.setattr(settings, 'REFERRAL_FIRST_PAYMENT_COMMISSION_PERCENT', None, raising=False)
    monkeypatch.setattr(settings, 'REFERRAL_RECURRING_COMMISSION_TIERS', '', raising=False)
    monkeypatch.setattr(settings, 'REFERRAL_MAX_COMMISSION_PAYMENTS', 0, raising=False)
    return SimpleNamespace(service=referral_service, users=users, sent=sent)


def _db_without_pending_row() -> SimpleNamespace:
    no_row = SimpleNamespace(scalar_one_or_none=lambda: None)
    return SimpleNamespace(execute=AsyncMock(return_value=no_row), commit=AsyncMock(), rollback=AsyncMock())


def _to(referral, uid: int) -> str:
    return next(item['message'] for item in referral.sent if item['to'] == 1000 + uid)


@pytest.mark.asyncio
async def test_registration_messages_promise_the_toman_terms(referral):
    assert await referral.service.process_referral_registration(_db_without_pending_row(), 2, 1, bot=object())

    welcome, inviter = _to(referral, 2), _to(referral, 1)
    for message in (welcome, inviter):
        assert _toman(10_000) in message  # the 10,000-Toman minimum and bonus, not «100»
        assert '₽' not in message and 'Когда' not in message and 'При первом' not in message
    assert 'User 1' in welcome and 'User 2' in inviter
    assert '25%' in inviter


@pytest.mark.asyncio
async def test_first_topup_messages_show_toman_bonus_and_reward_breakdown(referral):
    await referral.service.process_referral_topup(AsyncMock(), 2, BALANCE_TOMAN, bot=object())

    bonus, reward = _to(referral, 2), _to(referral, 1)
    assert _toman(10_000) in bonus
    assert _toman(BALANCE_TOMAN) in reward  # the 150,000 top-up
    assert _toman(47_500) in reward  # 10,000 fixed + 25% of 150,000
    assert _toman(37_500) in reward and _toman(10_000) in reward
    for message in (bonus, reward):
        assert 'Бонус' not in message and 'награда' not in message


@pytest.mark.asyncio
async def test_commission_message_shows_the_toman_topup_and_commission(referral):
    referral.users[2].has_made_first_topup = True

    await referral.service.process_referral_topup(AsyncMock(), 2, BALANCE_TOMAN, bot=object())

    message = _to(referral, 1)
    assert _toman(BALANCE_TOMAN) in message and _toman(37_500) in message
    assert 'комиссия' not in message.lower()


def test_referral_earnings_total_is_formatted_in_toman():
    from app.services.referral_reward_service import format_reward_total

    assert format_reward_total(47_500, 0) == _toman(47_500)
    assert format_reward_total(47_500, 7, 'fa').startswith(_toman(47_500))


# ---------------------------------------------------------------- admin referral screens


@pytest.mark.asyncio
async def test_admin_referral_rules_show_the_toman_terms(monkeypatch):
    from app.handlers.admin import referrals

    monkeypatch.setattr(settings, 'REFERRAL_REWARD_SCHEME', 'legacy', raising=False)
    monkeypatch.setattr(settings, 'REFERRAL_MINIMUM_TOPUP_KOPEKS', 10_000, raising=False)
    monkeypatch.setattr(settings, 'REFERRAL_FIRST_TOPUP_BONUS_KOPEKS', 20_000, raising=False)
    monkeypatch.setattr(settings, 'REFERRAL_INVITER_BONUS_KOPEKS', 30_000, raising=False)

    block = await referrals._program_rules_block(None, get_texts('fa'))

    for amount in (10_000, 20_000, 30_000):
        assert _toman(amount) in block
    assert 'Минимальное' not in block


def test_admin_referral_screens_format_no_amount_as_a_catalog_price():
    """Every amount on these screens is Toman: terms, commissions, earnings, diagnostics bonuses."""
    tree = ast.parse((ROOT / 'app' / 'handlers' / 'admin' / 'referrals.py').read_text(encoding='utf-8'))
    calls = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'format_price'
    ]
    assert calls == []


# ---------------------------------------------------------------- guard: Toman amounts never divided by 100

DIVIDE_GUARDED = [
    'app/services/daily_subscription_service.py',
    'app/services/referral_service.py',
    'app/webapi/routes/users.py',
]


def _toman_divided_by_100() -> list[str]:
    """``<balance or REFERRAL_* expr> / 100`` in the guarded modules, and ``format_price(REFERRAL_*)`` anywhere."""
    hits: list[str] = []
    for path in sorted((ROOT / 'app').rglob('*.py')):
        relative = str(path.relative_to(ROOT))
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == 'format_price'
                and node.args
                and 'REFERRAL_' in ast.unparse(node.args[0])
            ):
                hits.append(f'{relative}:{node.lineno}: format_price({ast.unparse(node.args[0])})')
            if (
                relative in DIVIDE_GUARDED
                and isinstance(node, ast.BinOp)
                and isinstance(node.op, (ast.Div, ast.FloorDiv))
                and isinstance(node.right, ast.Constant)
                and node.right.value == 100
                and any(word in ast.unparse(node.left) for word in ('balance', 'REFERRAL_'))
            ):
                hits.append(f'{relative}:{node.lineno}: {ast.unparse(node)}')
    return hits


def test_no_toman_amount_is_divided_by_100():
    assert _toman_divided_by_100() == []


# ---------------------------------------------------------------- web API manual deposit


@pytest.mark.asyncio
async def test_webapi_deposit_reports_the_new_balance_in_toman(monkeypatch):
    from app.webapi.routes import users
    from app.webapi.schemas.users import BalanceDepositRequest

    user = SimpleNamespace(id=1, telegram_id=1001)
    result = SimpleNamespace(
        duplicate=False,
        transaction=SimpleNamespace(id=5, amount_kopeks=50_000, user_id=1),
        old_balance_kopeks=100_000,
        new_balance_kopeks=BALANCE_TOMAN,
    )
    monkeypatch.setattr(users, '_get_user_by_id_or_telegram_id', AsyncMock(return_value=user))
    monkeypatch.setattr(users, '_open_bot', lambda: None)
    monkeypatch.setattr(users, 'credit_manual_topup', AsyncMock(return_value=result))

    response = await users.deposit_balance(
        1, BalanceDepositRequest(amount_kopeks=50_000, idempotency_key='wave2-test'), token=None, db=None
    )

    assert response.new_balance_kopeks == BALANCE_TOMAN
    assert response.new_balance_rubles == BALANCE_TOMAN  # display Toman, like every *_rubles field since #35


# ---------------------------------------------------------------- poll reward credit


@pytest.mark.asyncio
async def test_poll_reward_credits_the_toman_amount(monkeypatch):
    """The admin types 10,000 Toman; it is stored x100 like a price and shown with format_price."""
    from app.database.models import TransactionType
    from app.services import poll_service

    credit = AsyncMock(return_value=True)
    monkeypatch.setattr(poll_service, 'add_user_balance', credit)
    poll = SimpleNamespace(reward_enabled=True, reward_amount_kopeks=1_000_000, title='Q')
    response = SimpleNamespace(poll=poll, reward_given=False, reward_amount_kopeks=0, user=SimpleNamespace(id=1))
    db = SimpleNamespace(refresh=AsyncMock())

    granted = await poll_service.reward_user_for_poll(db, response)

    assert credit.await_args.args[2] == 10_000
    assert credit.await_args.kwargs['transaction_type'] == TransactionType.POLL_REWARD
    assert settings.format_price(granted) == _toman(10_000)  # what the bot and cabinet then show
