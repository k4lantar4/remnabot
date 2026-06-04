import pytest
from decimal import Decimal

from app.utils.price_display import display_amount_from_kopeks, kopeks_from_display_amount


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
