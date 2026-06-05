import pytest
from decimal import Decimal

from app.utils.price_display import (
    catalog_price_in_toman,
    display_amount_from_kopeks,
    display_balance_from_storage,
    display_transaction_amount_from_storage,
    kopeks_from_display_amount,
    user_can_afford,
)


@pytest.mark.parametrize(
    ('kopeks', 'expected'),
    [
        (0, 0.0),
        (100, 1.0),
        (10000, 100.0),
        (12015200, 120152.0),
        (-5000, -50.0),
    ],
)
def test_display_amount_from_kopeks(kopeks: int, expected: float) -> None:
    assert display_amount_from_kopeks(kopeks) == expected


@pytest.mark.parametrize(
    ('amount', 'expected_kopeks'),
    [
        (0, 0),
        (1, 100),
        (100, 10000),
        (120152, 12015200),
        (-50, -5000),
        (99.99, 9999),
        (100.005, 10001),
    ],
)
def test_kopeks_from_display_amount(amount: float, expected_kopeks: int) -> None:
    assert kopeks_from_display_amount(amount) == expected_kopeks


def test_kopeks_from_display_amount_decimal() -> None:
    assert kopeks_from_display_amount(Decimal('100.50')) == 10050


def test_kopeks_from_display_amount_invalid() -> None:
    with pytest.raises(ValueError, match='Invalid display amount'):
        kopeks_from_display_amount(float('nan'))


@pytest.mark.parametrize(
    ('price_kopeks', 'expected_toman'),
    [
        (0, 0),
        (100, 1),
        (500000, 5000),
        (12015200, 120152),
    ],
)
def test_catalog_price_in_toman(price_kopeks: int, expected_toman: int) -> None:
    assert catalog_price_in_toman(price_kopeks) == expected_toman


@pytest.mark.parametrize(
    ('balance_toman', 'price_kopeks', 'expected'),
    [
        (100000, 500000, True),
        (4999, 500000, False),
        (5000, 500000, True),
        (0, 0, True),
    ],
)
def test_user_can_afford(balance_toman: int, price_kopeks: int, expected: bool) -> None:
    assert user_can_afford(balance_toman, price_kopeks) is expected


def test_display_balance_from_storage_is_one_to_one() -> None:
    assert display_balance_from_storage(1000) == 1000.0


def test_display_transaction_amount_deposit_phase_b() -> None:
    assert display_transaction_amount_from_storage(1000, 'deposit') == 1000.0


def test_display_transaction_amount_subscription_catalog_scale() -> None:
    assert display_transaction_amount_from_storage(500000, 'subscription_payment') == 5000.0
