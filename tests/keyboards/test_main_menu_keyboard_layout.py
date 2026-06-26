"""Regression tests for default-mode main menu keyboard layout."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.keyboards.inline import get_main_menu_keyboard


@pytest.fixture(autouse=True)
def _default_menu_mode():
    from app.config import settings

    with (
        patch('app.config.Settings.is_cabinet_mode', return_value=False),
        patch.object(settings, 'MENU_LAYOUT_ENABLED', False),
        patch('app.config.Settings.is_multi_tariff_enabled', return_value=True),
        patch.object(settings, 'MINIAPP_CUSTOM_URL', 'https://cabinet.example.com'),
        patch('app.config.Settings.is_referral_program_enabled', return_value=True),
        patch.object(settings, 'SIMPLE_SUBSCRIPTION_ENABLED', True),
        patch.object(settings, 'CONTESTS_ENABLED', False),
        patch('app.config.Settings.is_language_selection_enabled', return_value=False),
        patch.object(settings, 'ACTIVATE_BUTTON_VISIBLE', False),
    ):
        yield


def _flat_buttons(markup):
    return [btn for row in markup.inline_keyboard for btn in row]


def _callback_data_set(markup) -> set[str]:
    return {btn.callback_data for btn in _flat_buttons(markup) if btn.callback_data}


def _webapp_urls(markup) -> list[str]:
    return [btn.web_app.url for btn in _flat_buttons(markup) if btn.web_app]


def test_new_user_wallet_row_below_buy_not_first() -> None:
    kb = get_main_menu_keyboard(
        language='fa',
        balance_kopeks=50_000,
        has_active_subscription=False,
        subscription_is_active=False,
        has_had_paid_subscription=False,
    )
    buttons = _flat_buttons(kb)
    buy_idx = next(i for i, b in enumerate(buttons) if b.callback_data == 'menu_buy')
    wallet_idx = next(i for i, b in enumerate(buttons) if b.callback_data == 'menu_balance')
    assert wallet_idx > buy_idx
    assert buttons[0].callback_data != 'menu_balance'


def test_wallet_button_uses_fixed_label_not_dynamic_balance() -> None:
    kb = get_main_menu_keyboard(language='fa', balance_kopeks=999_999)
    wallet = next(b for b in _flat_buttons(kb) if b.callback_data == 'menu_balance')
    from app.localization.texts import get_texts

    texts = get_texts('fa')
    assert texts.format_balance(999_999) not in wallet.text


def test_menu_info_removed_from_main_menu() -> None:
    kb = get_main_menu_keyboard(language='fa', balance_kopeks=0)
    assert 'menu_info' not in _callback_data_set(kb)


def test_cabinet_and_referral_webapp_urls() -> None:
    kb = get_main_menu_keyboard(language='fa', balance_kopeks=0)
    urls = _webapp_urls(kb)
    assert 'https://cabinet.example.com' in urls
    assert 'https://cabinet.example.com/referral' in urls


def test_cabinet_wallet_share_a_row() -> None:
    kb = get_main_menu_keyboard(language='fa', balance_kopeks=0, has_active_subscription=False)
    for row in kb.inline_keyboard:
        cbs = {b.callback_data for b in row if b.callback_data}
        webapps = [b.web_app.url for b in row if b.web_app]
        if 'menu_balance' in cbs:
            assert any(url == 'https://cabinet.example.com' for url in webapps)
            assert len(row) == 2
            break
    else:
        pytest.fail('wallet row not found')
