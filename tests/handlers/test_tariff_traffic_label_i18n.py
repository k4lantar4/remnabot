"""Tariff screens print traffic in the user's language (F-036).

tariff_purchase.py used app.utils.formatting.format_traffic, which hard-codes «ГБ» / «Безлимит».
"""

from app.database.models import Tariff
from app.handlers.subscription.tariff_purchase import format_tariff_info_for_user


def _tariff(traffic_limit_gb: int) -> Tariff:
    return Tariff(name='Test', description=None, traffic_limit_gb=traffic_limit_gb, device_limit=2)


def _has_cyrillic(text: str) -> bool:
    return any('Ѐ' <= ch <= 'ӿ' for ch in text)


def test_fa_tariff_info_shows_persian_traffic_amount():
    text = format_tariff_info_for_user(_tariff(50), language='fa')
    assert '50 گیگ' in text
    assert 'ГБ' not in text


def test_fa_tariff_info_shows_persian_unlimited():
    text = format_tariff_info_for_user(_tariff(0), language='fa')
    assert 'نامحدود' in text
    assert not _has_cyrillic(text)


def test_ru_tariff_info_keeps_russian_units():
    assert '50 ГБ' in format_tariff_info_for_user(_tariff(50), language='ru')
