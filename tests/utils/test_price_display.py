"""Unit tests for the display helpers that survived Phase C.

This file used to pin the conversions between the catalog x100 scale and Toman 1:1
(``catalog_price_in_toman``, ``display_amount_from_kopeks``, ``kopeks_from_display_amount``).
Revision ``0115`` put storage on one scale and those functions were deleted, so what is left to test
is that nothing converts: a stored amount is displayed as itself, and affordability is a comparison.

The rounding behaviour the deleted ``kopeks_from_display_amount`` owned did not disappear — it moved
to the HTTP boundary and is tested in ``test_wire_scale.py``. The whole-system Phase C contract is
in ``test_phase_c_single_scale.py``.
"""

import pytest

from app.utils.price_display import (
    display_balance_from_storage,
    display_transaction_amount_from_storage,
    missing_toman,
    storage_sum_to_display_toman,
    user_can_afford,
)


@pytest.mark.parametrize(
    ('balance_toman', 'price_toman', 'expected'),
    [
        (100_000, 5_000, True),
        (4_999, 5_000, False),
        (5_000, 5_000, True),
        (0, 0, True),
    ],
)
def test_user_can_afford_compares_two_toman_numbers(balance_toman: int, price_toman: int, expected: bool) -> None:
    assert user_can_afford(balance_toman, price_toman) is expected


@pytest.mark.parametrize(
    ('balance_toman', 'price_toman', 'expected'),
    [
        (150_000, 200_000, 50_000),
        (200_000, 200_000, 0),
        (250_000, 200_000, 0),
        (0, 1, 1),
    ],
)
def test_missing_toman_is_the_plain_shortfall(balance_toman: int, price_toman: int, expected: int) -> None:
    assert missing_toman(balance_toman, price_toman) == expected


def test_affordability_helpers_treat_none_as_zero() -> None:
    """Columns are nullable, and a NULL balance must read as "cannot afford", never as a crash."""
    assert user_can_afford(None, 1) is False
    assert user_can_afford(None, 0) is True
    assert missing_toman(None, 5_000) == 5_000


def test_display_balance_from_storage_is_one_to_one() -> None:
    assert display_balance_from_storage(1000) == 1000.0


@pytest.mark.parametrize('stored', [0, 1000, 500_000, -500_000])
def test_a_transaction_displays_its_stored_number_whatever_its_type(stored: int) -> None:
    assert display_transaction_amount_from_storage(stored) == float(stored)


@pytest.mark.parametrize(('stored', 'expected'), [(0, 0), (1000, 1000), (-500_000, 500_000)])
def test_storage_sum_to_display_toman_only_takes_the_magnitude(stored: int, expected: int) -> None:
    assert storage_sum_to_display_toman(stored) == expected
