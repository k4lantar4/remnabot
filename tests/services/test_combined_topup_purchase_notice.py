"""One message after a top-up that completes a saved purchase (plan 2026-09-12 notifications, task 3b: B6, C6, Q6).

Audit 2026-09-12: `send_cart_notification_after_topup` always returned False, so C2C followed a successful
auto-purchase with «return to checkout»; CryptoBot, manual top-up and Stars sent the top-up notice as a
separate message; the top-up keyboard renewed whichever subscription came first.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.config import Settings, settings
from app.localization.texts import get_texts
from app.services import subscription_auto_purchase_service as auto_mod
from app.services.payment import common as payment_common


CABINET = 'https://panel.example.com'
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _cabinet_multi_tariff(monkeypatch):
    monkeypatch.setattr(Settings, 'is_cabinet_mode', lambda self: True)
    monkeypatch.setattr(Settings, 'is_multi_tariff_enabled', lambda self: True)
    monkeypatch.setattr(settings, 'MINIAPP_CUSTOM_URL', CABINET, raising=False)


def _user(subscriptions=None) -> SimpleNamespace:
    return SimpleNamespace(
        id=7, telegram_id=7007, language='fa', balance_kopeks=40_000, email=None, subscriptions=subscriptions or []
    )


def _subscription(sub_id: int) -> SimpleNamespace:
    return SimpleNamespace(id=sub_id, is_active=True, is_trial=False, actual_status='active')


def _urls(keyboard) -> list[str]:
    return [button.web_app.url for row in keyboard.inline_keyboard for button in row if button.web_app]


def _lines(texts, amount: int, balance: int) -> tuple[str, str]:
    return (
        texts.t('TOPUP_CREDITED_LINE').format(amount=settings.format_balance(amount)),
        texts.t('TOPUP_BALANCE_LEFT_LINE').format(balance=settings.format_balance(balance)),
    )


def _cart_hook_env(monkeypatch, purchase_result: bool) -> dict:
    seen: dict = {}

    async def purchase(db, user, *, bot=None, topup_amount=None):
        seen['topup_amount'] = topup_amount
        return purchase_result

    monkeypatch.setattr(payment_common, 'notify_email_user_topup', AsyncMock())
    monkeypatch.setattr(auto_mod, 'try_resume_disabled_daily_after_topup', AsyncMock(return_value=False))
    monkeypatch.setattr(auto_mod, 'auto_purchase_saved_cart_after_topup', purchase)
    monkeypatch.setattr(
        payment_common.user_cart_service,
        'get_user_cart',
        AsyncMock(return_value={'cart_mode': 'tariff_purchase', 'total_price': 10_000}),
    )
    return seen


async def test_cart_hook_returns_true_when_the_saved_purchase_succeeds(monkeypatch):
    seen = _cart_hook_env(monkeypatch, purchase_result=True)

    assert await payment_common.send_cart_notification_after_topup(_user(), 50_000, None, None) is True
    assert seen['topup_amount'] == 50_000


async def test_cart_hook_returns_false_when_the_saved_purchase_fails(monkeypatch):
    _cart_hook_env(monkeypatch, purchase_result=False)

    assert await payment_common.send_cart_notification_after_topup(_user(), 50_000, None, None) is False


def test_topup_lines_frame_only_the_first_purchase_notice():
    texts = get_texts('fa')
    user = _user()
    credited, left = _lines(texts, 50_000, 40_000)

    token = auto_mod._topup_credit.set(50_000)
    try:
        first = auto_mod._with_topup_lines(texts, user, 'BODY')
        second = auto_mod._with_topup_lines(texts, user, 'BODY')
    finally:
        auto_mod._topup_credit.reset(token)

    assert first == f'{credited}\n\nBODY\n\n{left}'
    assert second == 'BODY'
    assert auto_mod._with_topup_lines(texts, user, 'BODY') == 'BODY'


async def test_saved_cart_purchase_after_topup_frames_its_notice(monkeypatch):
    monkeypatch.setattr(Settings, 'is_auto_purchase_after_topup_enabled', lambda self: True)
    monkeypatch.setattr(auto_mod.user_cart_service, 'get_user_cart', AsyncMock(return_value=None))
    monkeypatch.setattr(
        auto_mod.user_cart_service,
        'get_all_subscription_carts',
        AsyncMock(return_value=[{'cart_mode': 'tariff_purchase', 'subscription_id': 42}]),
    )
    monkeypatch.setattr(auto_mod.user_cart_service, 'has_topup_intent', AsyncMock(return_value=True))
    monkeypatch.setattr(auto_mod.user_cart_service, 'clear_topup_intent', AsyncMock())
    texts = get_texts('fa')
    framed: list[str] = []

    async def process(db, user, cart_data, *, bot=None, manual=False):
        framed.append(auto_mod._with_topup_lines(texts, user, 'BODY'))
        return True

    monkeypatch.setattr(auto_mod, '_process_single_cart', process)

    assert await auto_mod.auto_purchase_saved_cart_after_topup(None, _user(), bot=None, topup_amount=50_000)

    credited, left = _lines(texts, 50_000, 40_000)
    assert framed == [f'{credited}\n\nBODY\n\n{left}']
    assert auto_mod._topup_credit.get() is None


def test_every_saved_cart_notice_goes_through_the_topup_frame():
    source = (ROOT / 'app/services/subscription_auto_purchase_service.py').read_text(encoding='utf-8')

    # Cart path: extend, tariff, daily tariff, devices, traffic, legacy cart.
    assert source.count('text=_with_topup_lines(texts, user, ') == 6


async def _topup_keyboard(monkeypatch, subscriptions):
    monkeypatch.setattr(payment_common.user_cart_service, 'get_user_cart', AsyncMock(return_value=None))
    monkeypatch.setattr(payment_common, 'has_subscription_checkout_draft', AsyncMock(return_value=False))
    return await payment_common.PaymentCommonMixin().build_topup_success_keyboard(_user(subscriptions))


async def test_topup_keyboard_renews_the_only_active_subscription(monkeypatch):
    keyboard = await _topup_keyboard(monkeypatch, [_subscription(42)])

    assert _urls(keyboard)[0] == f'{CABINET}/subscriptions/42/renew'


async def test_topup_keyboard_with_several_subscriptions_opens_the_list(monkeypatch):
    keyboard = await _topup_keyboard(monkeypatch, [_subscription(42), _subscription(43)])

    assert _urls(keyboard)[0] == f'{CABINET}/subscriptions'


async def test_topup_keyboard_accepts_an_explicit_subscription(monkeypatch):
    monkeypatch.setattr(payment_common.user_cart_service, 'get_user_cart', AsyncMock(return_value=None))
    monkeypatch.setattr(payment_common, 'has_subscription_checkout_draft', AsyncMock(return_value=False))

    keyboard = await payment_common.PaymentCommonMixin().build_topup_success_keyboard(
        _user([_subscription(42), _subscription(43)]), subscription_id=43
    )

    assert _urls(keyboard)[0] == f'{CABINET}/subscriptions/43/renew'
