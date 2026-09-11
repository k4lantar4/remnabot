from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.keyboards import topup_amounts
from app.keyboards.topup_amounts import (
    format_quick_amount,
    get_topup_amount_keyboard,
    resolve_config_method_id,
)
from app.localization.loader import DEFAULT_LANGUAGE
from app.localization.texts import get_texts


def test_resolve_maps_callback_methods_to_config_ids():
    assert resolve_config_method_id('stars') == 'telegram_stars'
    assert resolve_config_method_id('yookassa_sbp') == 'yookassa'
    assert resolve_config_method_id('kassa_ai_sberpay') == 'kassa_ai'
    assert resolve_config_method_id('aurapay_card') == 'aurapay'
    assert resolve_config_method_id('donut_sbp_qr') == 'donut'
    assert resolve_config_method_id('platega_m2') == 'platega'


def test_resolve_keeps_direct_config_ids():
    assert resolve_config_method_id('cryptobot') == 'cryptobot'
    assert resolve_config_method_id('freekassa_sbp') == 'freekassa_sbp'
    assert resolve_config_method_id('freekassa_card') == 'freekassa_card'
    assert resolve_config_method_id('overpay') == 'overpay'


def test_resolve_maps_overpay_variants_to_overpay():
    assert resolve_config_method_id('overpay_fps') == 'overpay'
    assert resolve_config_method_id('overpay_card') == 'overpay'
    assert resolve_config_method_id('overpay_int') == 'overpay'


@pytest.mark.parametrize('language', ['fa', 'en'])
def test_format_quick_amount_is_toman_in_user_language(language):
    """Quick amounts sit on the Toman ×100 top-up scale — the catalog price formatter, never «₽»."""
    for amount in (10000, 12550, 5_000_000):
        label = format_quick_amount(amount, language)
        assert label == get_texts(language).format_price(amount)
        assert '₽' not in label


async def test_keyboard_builds_amount_buttons_within_limits(monkeypatch: pytest.MonkeyPatch):
    config = SimpleNamespace(
        quick_amounts=[10000, 30000, 50000],
        min_amount_kopeks=20000,
        max_amount_kopeks=10000000,
    )

    async def fake_get_config(db, method_id):
        assert method_id == 'telegram_stars'
        return config

    monkeypatch.setattr(topup_amounts, 'get_config_by_method_id', fake_get_config)

    keyboard = await get_topup_amount_keyboard('stars', db=object(), back_callback='back_to_menu')

    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert callbacks == ['topup_amount|stars|30000', 'topup_amount|stars|50000', 'back_to_menu']
    assert keyboard.inline_keyboard[0][0].text == get_texts(DEFAULT_LANGUAGE).format_price(30000)
    assert '₽' not in keyboard.inline_keyboard[0][0].text


async def test_keyboard_chunks_amounts_two_per_row(monkeypatch: pytest.MonkeyPatch):
    config = SimpleNamespace(
        quick_amounts=[10000, 30000, 50000],
        min_amount_kopeks=10000,
        max_amount_kopeks=10000000,
    )

    async def fake_get_config(db, method_id):
        return config

    monkeypatch.setattr(topup_amounts, 'get_config_by_method_id', fake_get_config)

    keyboard = await get_topup_amount_keyboard('cryptobot', db=object())

    assert [len(row) for row in keyboard.inline_keyboard] == [2, 1, 1]
    assert keyboard.inline_keyboard[-1][0].callback_data == 'menu_balance'


async def test_keyboard_min_amount_override_raises_lower_bound(monkeypatch: pytest.MonkeyPatch):
    config = SimpleNamespace(
        quick_amounts=[10000, 30000, 50000],
        min_amount_kopeks=10000,
        max_amount_kopeks=10000000,
    )

    async def fake_get_config(db, method_id):
        assert method_id == 'overpay'
        return config

    monkeypatch.setattr(topup_amounts, 'get_config_by_method_id', fake_get_config)

    keyboard = await get_topup_amount_keyboard(
        'overpay_int',
        db=object(),
        back_callback='topup_overpay',
        min_amount_kopeks=30000,
    )

    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert callbacks == [
        'topup_amount|overpay_int|30000',
        'topup_amount|overpay_int|50000',
        'topup_overpay',
    ]


async def test_keyboard_falls_back_to_back_only_on_db_error(monkeypatch: pytest.MonkeyPatch):
    async def failing_get_config(db, method_id):
        raise RuntimeError('db is down')

    monkeypatch.setattr(topup_amounts, 'get_config_by_method_id', failing_get_config)

    keyboard = await get_topup_amount_keyboard('stars', db=object(), back_callback='menu_balance')

    assert len(keyboard.inline_keyboard) == 1
    assert len(keyboard.inline_keyboard[0]) == 1
    assert keyboard.inline_keyboard[0][0].callback_data == 'menu_balance'
