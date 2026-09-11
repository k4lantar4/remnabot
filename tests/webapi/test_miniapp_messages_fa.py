"""Legacy miniapp messages for Persian users are not Russian (F-009).

The miniapp helpers branched on ``language_code in {'ru', 'fa'}`` and sent fa users the Russian
text («Подписка продлена до …», «Триал активирован на N дн.»). They now render locale keys in the
user's language; ru keeps its Russian text through ``ru.json``.
"""

from __future__ import annotations

import re
import types
from datetime import UTC, datetime, timedelta

import pytest

from app.config import Settings
from app.webapi.routes import miniapp


CYRILLIC = re.compile('[А-Яа-яЁё]')
PERSIAN_DIGITS = re.compile('[۰-۹٠-٩]')


def _user(language: str) -> types.SimpleNamespace:
    return types.SimpleNamespace(
        id=1,
        language=language,
        promo_offer_discount_percent=15,
        promo_offer_discount_expires_at=datetime.now(UTC) + timedelta(hours=5),
        promo_group=None,
    )


def _subscription() -> types.SimpleNamespace:
    return types.SimpleNamespace(end_date=datetime(2026, 10, 11, 12, 0, tzinfo=UTC), tariff=None)


@pytest.fixture(autouse=True)
def _single_tariff(monkeypatch):
    monkeypatch.setattr(Settings, 'is_multi_tariff_enabled', lambda self: False)


@pytest.mark.parametrize(
    ('charged', 'promo'),
    [(1_500_000, 0), (0, 0), (1_500_000, 200_000)],
)
def test_renewal_success_message_is_persian(charged, promo):
    message = miniapp._build_renewal_success_message(_user('fa'), _subscription(), charged, promo)

    assert not CYRILLIC.search(message), message
    assert '₽' not in message
    assert not PERSIAN_DIGITS.search(message), message
    assert '2026' in message


def test_renewal_success_message_keeps_russian_for_ru():
    message = miniapp._build_renewal_success_message(_user('ru'), _subscription(), 1_500_000)

    assert message.startswith('Подписка продлена до')


def test_renewal_status_message_is_persian():
    message = miniapp._build_renewal_status_message(_user('fa'))

    assert message.strip()
    assert not CYRILLIC.search(message), message


@pytest.mark.parametrize(('days', 'charged_label'), [(3, None), (None, None), (3, '5,000 تومان')])
def test_trial_activation_message_is_persian(days, charged_label):
    message = miniapp._build_trial_activation_message(_user('fa'), days, charged_label)

    assert not CYRILLIC.search(message), message
    if days:
        assert '3' in message
    if charged_label:
        assert charged_label in message


def test_trial_activation_message_keeps_russian_for_ru():
    assert miniapp._build_trial_activation_message(_user('ru'), 3, None).startswith('Триал активирован на 3 дн.')


def test_promo_offer_payload_message_is_persian(monkeypatch):
    monkeypatch.setattr(miniapp, 'get_user_active_promo_discount_percent', lambda user: 15)

    payload = miniapp._build_promo_offer_payload(_user('fa'))

    assert payload is not None
    assert payload['percent'] == 15
    assert not CYRILLIC.search(payload['message']), payload['message']
