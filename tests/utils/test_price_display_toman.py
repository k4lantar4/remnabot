"""Toman display gate, rewritten for the single Phase C scale.

This file was the M6-T2 dual-scale regression gate: it pinned that a catalog price rendered the same
as the balance it could buy, while the two were stored 100x apart. Revision ``0115`` removed that
gap, so what it now guards is the opposite property — *storage and display are the same number* —
plus the parts that never depended on the gap: the تومان suffix, Persian digit normalisation of
typed input, and the Phase B cutoff instant.

The insufficient-funds copy is kept here in full because it is the case the dual scale kept getting
wrong: the shortfall in the message and the amount on the C2C card must be the same figure.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.config import settings
from app.services.subscription_renewal_service import calculate_missing_amount
from app.utils.price_display import (
    balance_from_display_amount,
    display_balance_from_storage,
    display_transaction_amount_from_storage,
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


def test_format_price_renders_the_stored_number(toman_suffix) -> None:
    """Prices are Toman 1:1 now, so 120,152 stored is 120,152 shown — no division."""
    assert settings.format_price(1_000_000, language='fa') == '1,000,000 تومان'
    assert settings.format_price(120_152, language='fa') == '120,152 تومان'


def test_one_scale_one_rendering(toman_suffix) -> None:
    """The dual scale is gone: a price and a balance of equal value are equal integers."""
    amount = 120_152
    assert settings.format_price(amount, language='fa') == settings.format_balance(amount, language='fa')
    assert display_balance_from_storage(amount) == float(amount)


def test_user_can_afford_compares_two_toman_numbers() -> None:
    assert user_can_afford(5_000, 5_000) is True
    assert user_can_afford(4_999, 5_000) is False


def test_every_transaction_type_keeps_its_stored_number() -> None:
    """Deposits and subscription charges are the same scale now; the type decides nothing."""
    assert display_transaction_amount_from_storage(100_000) == 100_000.0
    assert display_transaction_amount_from_storage(5_000) == 5_000.0
    assert storage_sum_to_display_toman(1_000_000) == 1_000_000
    assert storage_sum_to_display_toman(-5_000) == 5_000


def test_balance_from_display_amount_normalizes_fa_text() -> None:
    assert balance_from_display_amount('۱۰٬۰۰۰ تومان') == 10_000
    assert balance_from_display_amount('10,000') == 10_000
    assert balance_from_display_amount(Decimal('99.6')) == 100
    assert normalize_display_amount_text('۱۰٬۰۰۰ تومان') == '10000'


def test_calculate_missing_amount_is_a_plain_toman_difference() -> None:
    assert calculate_missing_amount(9_450, 10_000) == 550
    assert user_can_afford(945_000, 10_000) is True


def test_addon_insufficient_copy_matches_the_c2c_card(toman_suffix) -> None:
    """G8: a 72,200 تومان shortfall must appear as 72,200 in the message and on the card."""
    from app.localization.texts import get_texts
    from app.plugins.c2c.config_helpers import format_card_message
    from app.utils.price_display import render_addon_insufficient_funds

    texts = get_texts('fa')
    price_toman = 73_200
    balance_toman = 1_000

    message, shortfall = render_addon_insufficient_funds(
        texts,
        price_toman=price_toman,
        balance_toman=balance_toman,
    )

    assert user_can_afford(100_000, price_toman) is True
    assert shortfall == 72_200
    assert '72,200' in message
    assert '73,200' in message
    assert '1,000' in message
    # The 100x shapes the dual scale used to produce.
    assert '7,220,000' not in message
    assert '7,319,000' not in message

    card = format_card_message(
        {'label': 'RC test', 'number': '6037991111111111', 'holder': 'TEST'},
        shortfall,
        '',
        texts,
    )
    assert '72,200' in card
    assert '7,220,000' not in card


def test_balance_toman_cutoff_utc_is_phase_b_instant() -> None:
    assert settings.BALANCE_TOMAN_CUTOFF_UTC == '2026-06-05T00:00:00Z'
    assert settings.balance_toman_cutoff == datetime(2026, 6, 5, tzinfo=UTC)
