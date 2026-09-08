"""M6-T2 Toman dual-scale regression gate.

remnabot has no tests/utils/test_price_display_toman.py; this file is the named
gate. It locks display helpers ported in M4-T7:

- تومان suffix and fa-IR thousands grouping
- catalog kopeks ÷ 100 vs balance Toman 1:1
- BALANCE_TOMAN_CUTOFF_UTC
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.config import settings
from app.services.subscription_renewal_service import calculate_missing_amount
from app.utils.price_display import (
    balance_from_display_amount,
    catalog_price_in_toman,
    display_amount_from_kopeks,
    display_balance_from_storage,
    display_transaction_amount_from_storage,
    format_transaction_amount_for_display,
    normalize_display_amount_text,
    storage_sum_to_display_toman,
    user_can_afford,
)


@pytest.fixture
def toman_suffix(monkeypatch):
    monkeypatch.setattr(settings, 'PRICE_DISPLAY_SUFFIX', ' تومان', raising=False)


def test_format_balance_is_toman_one_to_one_with_fa_grouping(toman_suffix) -> None:
    assert settings.format_balance(1000, language='fa') == '1,000 تومان'
    assert settings.format_balance(120_152, language='fa') == '120,152 تومان'


def test_format_price_divides_catalog_kopeks_with_fa_grouping(toman_suffix) -> None:
    assert settings.format_price(100_000_000, language='fa') == '1,000,000 تومان'
    assert settings.format_price(12_015_200, language='fa') == '120,152 تومان'


def test_dual_scale_same_display_different_storage(toman_suffix) -> None:
    catalog_kopeks = 12_015_200
    balance_toman = 120_152
    assert catalog_price_in_toman(catalog_kopeks) == balance_toman
    assert settings.format_price(catalog_kopeks, language='fa') == settings.format_balance(
        balance_toman, language='fa'
    )
    assert display_amount_from_kopeks(catalog_kopeks) == float(balance_toman)
    assert display_balance_from_storage(balance_toman) == float(balance_toman)


def test_user_can_afford_compares_toman_to_catalog_kopeks() -> None:
    assert user_can_afford(5_000, 500_000) is True
    assert user_can_afford(4_999, 500_000) is False


def test_deposit_stays_toman_subscription_divides_catalog() -> None:
    assert display_transaction_amount_from_storage(100_000, 'deposit') == 100_000.0
    assert display_transaction_amount_from_storage(500_000, 'subscription_payment') == 5_000.0
    assert storage_sum_to_display_toman(1_000_000, 'deposit') == 1_000_000
    assert storage_sum_to_display_toman(500_000, 'subscription_payment') == 5_000

    formatted_deposit = format_transaction_amount_for_display(
        1_000_000,
        'deposit',
        lambda amount: f'{amount:,} تومان',
        lambda kopeks: f'{kopeks // 100:,} تومان',
    )
    formatted_sub = format_transaction_amount_for_display(
        500_000,
        'subscription_payment',
        lambda amount: f'{amount:,} تومان',
        lambda kopeks: f'{kopeks // 100:,} تومان',
    )
    assert formatted_deposit == '1,000,000 تومان'
    assert formatted_sub == '5,000 تومان'


def test_balance_from_display_amount_normalizes_fa_text() -> None:
    assert balance_from_display_amount('۱۰٬۰۰۰ تومان') == 10_000
    assert balance_from_display_amount('10,000') == 10_000
    assert balance_from_display_amount(Decimal('99.6')) == 100
    assert normalize_display_amount_text('۱۰٬۰۰۰ تومان') == '10000'


def test_calculate_missing_amount_uses_toman_not_catalog_diff() -> None:
    assert calculate_missing_amount(9_450, 1_000_000) == 550
    assert user_can_afford(945_000, 1_000_000) is True
    assert catalog_price_in_toman(500_000) == 5_000


def test_addon_insufficient_copy_matches_c2c_toman_not_100x(toman_suffix) -> None:
    """G8: کسری 72,200 تومان must not become C2C 7,220,000 تومان."""
    from app.localization.texts import get_texts
    from app.plugins.c2c.config_helpers import format_card_message
    from app.utils.price_display import render_addon_insufficient_funds

    texts = get_texts('fa')
    price_kopeks = 7_320_000
    balance_toman = 1_000
    mixed_subtract = price_kopeks - balance_toman

    message, missing_toman = render_addon_insufficient_funds(
        texts,
        price_kopeks=price_kopeks,
        balance_toman=balance_toman,
    )

    assert user_can_afford(100_000, price_kopeks) is True
    assert missing_toman == 72_200
    assert mixed_subtract == 7_319_000
    assert '72,200' in message
    assert '73,200' in message
    assert '1,000' in message
    assert '7,319,000' not in message
    assert '7,220,000' not in message

    card = format_card_message(
        {'label': 'RC test', 'number': '6037991111111111', 'holder': 'TEST'},
        missing_toman,
        '',
        texts,
    )
    assert '72,200' in card
    assert '7,220,000' not in card
    assert '7,319,000' not in card


def test_balance_toman_cutoff_utc_is_phase_b_instant() -> None:
    assert settings.BALANCE_TOMAN_CUTOFF_UTC == '2026-06-05T00:00:00Z'
    assert settings.balance_toman_cutoff == datetime(2026, 6, 5, tzinfo=UTC)
