"""The HTTP boundary is the only place a scale hop survives Phase C.

The cabinet frontend still divides ``price_kopeks`` by 100 and still sends top-up amounts multiplied
by 100, so the JSON contract keeps the old catalog scale until the follow-up plan moves the frontend
over. These two functions own that conversion; the rest of the backend is Toman 1:1.

The round-trip is what matters: an amount that leaves as catalog kopeks and comes back must be the
same Toman figure, or a user's top-up silently changes value between the form and the wallet.
"""

import pytest

from app.utils.wire_scale import toman_from_wire_catalog, wire_catalog_kopeks


@pytest.mark.parametrize(
    ('toman', 'expected_kopeks'),
    [
        (0, 0),
        (1, 100),
        (100, 10_000),
        (50_000, 5_000_000),
        (120_152, 12_015_200),
        (-50, -5_000),
    ],
)
def test_outbound_scales_toman_up_to_catalog_kopeks(toman: int, expected_kopeks: int) -> None:
    assert wire_catalog_kopeks(toman) == expected_kopeks


@pytest.mark.parametrize(
    ('kopeks', 'expected_toman'),
    [
        (0, 0),
        (100, 1),
        (5_000_000, 50_000),
        (12_015_200, 120_152),
        (-5_000, -50),
    ],
)
def test_inbound_scales_catalog_kopeks_down_to_toman(kopeks: int, expected_toman: int) -> None:
    assert toman_from_wire_catalog(kopeks) == expected_toman


@pytest.mark.parametrize('toman', [0, 1, 999, 50_000, 1_000_000])
def test_the_round_trip_is_lossless_for_whole_toman(toman: int) -> None:
    assert toman_from_wire_catalog(wire_catalog_kopeks(toman)) == toman


def test_inbound_floors_the_magnitude_keeping_the_sign() -> None:
    """A client sending a non-round catalog amount must not round *up* into a bigger charge."""
    assert toman_from_wire_catalog(150) == 1
    assert toman_from_wire_catalog(199) == 1
    assert toman_from_wire_catalog(-199) == -1


def test_inbound_treats_none_as_zero() -> None:
    assert toman_from_wire_catalog(None) == 0


def test_outbound_rounds_a_fractional_toman_half_up() -> None:
    assert wire_catalog_kopeks(99.99) == 9_999
    assert wire_catalog_kopeks(100.005) == 10_001


def test_outbound_rejects_a_value_that_is_not_a_number() -> None:
    with pytest.raises(ValueError, match='Invalid Toman amount'):
        wire_catalog_kopeks('not a number')
