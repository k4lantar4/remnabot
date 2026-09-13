"""The HTTP boundary is the only place a scale hop survives Phase C.

The cabinet frontend still divides ``price_kopeks`` by 100 and still sends top-up amounts multiplied
by 100, so the JSON contract keeps the old catalog scale until the follow-up plan moves the frontend
over. These two functions own that conversion; the rest of the backend is Toman 1:1.

The round-trip is what matters: an amount that leaves as catalog kopeks and comes back must be the
same Toman figure, or a user's top-up silently changes value between the form and the wallet.
"""

import pytest

from app.utils.wire_scale import (
    CATALOG_WIRE,
    TOMAN_WIRE,
    current_wire_scale,
    reset_wire_scale,
    toman_from_wire_catalog,
    use_wire_scale,
    wire_catalog_kopeks,
    wire_scale_from_header,
)


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


# ---- X-Amount-Scale (Phase C-2) -------------------------------------------


def test_the_scale_defaults_to_the_catalog_wire() -> None:
    assert current_wire_scale() == CATALOG_WIRE


def test_under_the_toman_scale_both_directions_are_the_identity() -> None:
    token = use_wire_scale(TOMAN_WIRE)
    try:
        assert current_wire_scale() == TOMAN_WIRE
        assert wire_catalog_kopeks(50_000) == 50_000
        assert toman_from_wire_catalog(50_000) == 50_000
        assert toman_from_wire_catalog(None) == 0
    finally:
        reset_wire_scale(token)

    assert current_wire_scale() == CATALOG_WIRE
    assert wire_catalog_kopeks(50_000) == 5_000_000


def test_the_toman_scale_still_rounds_a_fractional_toman_to_an_integer() -> None:
    token = use_wire_scale(TOMAN_WIRE)
    try:
        assert wire_catalog_kopeks(99.5) == 100
        assert wire_catalog_kopeks(-99.5) == -100
    finally:
        reset_wire_scale(token)


@pytest.mark.parametrize(
    ('header', 'expected'),
    [
        ('toman', TOMAN_WIRE),
        (' TOMAN ', TOMAN_WIRE),
        (None, CATALOG_WIRE),
        ('', CATALOG_WIRE),
        ('kopeks', CATALOG_WIRE),
    ],
)
def test_only_the_toman_header_value_selects_the_toman_scale(header, expected) -> None:
    assert wire_scale_from_header(header) == expected
