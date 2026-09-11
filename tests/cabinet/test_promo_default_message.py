"""The default promo-offer broadcast text is rendered in the bot's default language (F-009).

When the admin sends a promo offer from the cabinet without a custom text, every recipient got
the hard-coded Russian «🎁 Специальное предложение для вас! … Бонус 500₽ на баланс … Нажмите
кнопку ниже, чтобы активировать!» with a «🎁 Получить» button. The broadcast carries one text for
all recipients, so it is rendered with ``settings.DEFAULT_LANGUAGE``.

The bonus keeps the catalog scale every other display of ``bonus_amount_kopeks`` uses
(``format_price``: the old ``/ 100`` without the ``₽``), so the amount itself does not change.
"""

from __future__ import annotations

import re

import pytest

from app.cabinet.routes import admin_promo_offers
from app.config import settings


CYRILLIC = re.compile('[А-Яа-яЁё]')
PERSIAN_DIGITS = re.compile('[۰-۹٠-٩]')


@pytest.fixture
def fa_default(monkeypatch):
    monkeypatch.setattr(settings, 'DEFAULT_LANGUAGE', 'fa', raising=False)


def test_default_promo_message_is_persian_for_fa_default(fa_default):
    text = admin_promo_offers._build_default_promo_message(
        discount_percent=20,
        bonus_amount_kopeks=5_000_000,
        valid_hours=48,
    )

    assert not CYRILLIC.search(text), text
    assert '₽' not in text
    assert not PERSIAN_DIGITS.search(text), text
    assert '20%' in text
    assert '48' in text
    assert settings.format_price(5_000_000) in text  # 50,000 تومان, same scale as before
    assert 'تومان' in text


def test_default_promo_message_skips_empty_parts(fa_default):
    text = admin_promo_offers._build_default_promo_message(discount_percent=0, bonus_amount_kopeks=0, valid_hours=24)

    assert '%' not in text
    assert 'تومان' not in text
    assert '24' in text


def test_default_promo_button_is_persian_for_fa_default(fa_default):
    label = admin_promo_offers._default_promo_button_text()

    assert not CYRILLIC.search(label), label
    assert label.strip()


def test_default_promo_message_keeps_russian_for_ru_default(monkeypatch):
    monkeypatch.setattr(settings, 'DEFAULT_LANGUAGE', 'ru', raising=False)

    assert 'Специальное предложение' in admin_promo_offers._build_default_promo_message(
        discount_percent=10, bonus_amount_kopeks=0, valid_hours=12
    )
    assert admin_promo_offers._default_promo_button_text() == '🎁 Получить'
