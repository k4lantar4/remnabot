"""Low-balance alert shows the wallet balance and threshold in Toman (F-003).

``User.balance_kopeks`` holds raw Toman (Phase B) and the cabinet stores
``balance_low_threshold`` as the number the user typed, compared 1:1 with the balance.
The alert divided both by 100 and printed ``₽`` from the locale string, so a 50,000 Toman
balance read "500 ₽". The top-up button label key was missing (Russian default) and the button
opened the cabinet root instead of the top-up page.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.config import settings
from app.services.monitoring_service import MonitoringService


CABINET_URL = 'https://cabinet.example.com'
BALANCE_TOMAN = 50_000
THRESHOLD_TOMAN = 100_000


@pytest.fixture
def cabinet_mode(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, 'MAIN_MENU_MODE', 'cabinet', raising=False)
    monkeypatch.setattr(settings, 'MINIAPP_CUSTOM_URL', CABINET_URL, raising=False)
    return monkeypatch


def _user(language: str) -> SimpleNamespace:
    return SimpleNamespace(id=1, language=language, balance_kopeks=BALANCE_TOMAN)


def test_fa_alert_shows_toman_amounts_unscaled(cabinet_mode) -> None:
    text, _ = MonitoringService._build_low_balance_alert(_user('fa'), BALANCE_TOMAN, THRESHOLD_TOMAN)

    assert '50,000 تومان' in text
    assert '100,000 تومان' in text
    assert '₽' not in text
    assert 'تومان تومان' not in text
    assert '500 ' not in text
    assert '1,000 ' not in text


@pytest.mark.parametrize('language', ['en', 'ru', 'ua', 'zh'])
def test_no_ruble_sign_in_any_locale(cabinet_mode, language: str) -> None:
    text, _ = MonitoringService._build_low_balance_alert(_user(language), BALANCE_TOMAN, THRESHOLD_TOMAN)

    assert '₽' not in text
    assert '50' in text and ('50,000' in text or '50 000' in text)


def test_fa_topup_button_opens_cabinet_topup_page_with_persian_label(cabinet_mode) -> None:
    _, keyboard = MonitoringService._build_low_balance_alert(_user('fa'), BALANCE_TOMAN, THRESHOLD_TOMAN)

    [[button]] = keyboard.inline_keyboard
    assert button.web_app is not None
    assert button.web_app.url == f'{CABINET_URL}/balance/top-up'
    assert button.text == '💳 شارژ موجودی'
    assert 'Пополнить' not in button.text


def test_bot_mode_topup_button_is_the_topup_callback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, 'MAIN_MENU_MODE', 'default', raising=False)

    _, keyboard = MonitoringService._build_low_balance_alert(_user('fa'), BALANCE_TOMAN, THRESHOLD_TOMAN)

    [[button]] = keyboard.inline_keyboard
    assert button.callback_data == 'balance_topup'
